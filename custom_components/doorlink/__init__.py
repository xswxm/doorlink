"""The doorlink integration."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import suppress
from typing import Any
from urllib.parse import parse_qs, urlparse

import aiofiles
import aiohttp
from aiohttp.web import Request, Response, json_response

from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.util import dt as dt_util

from .client import Client, SIPContact
from .const import (
    ATTR_DIRECT,
    ATTR_FLOOR,
    ATTR_JSON_DATA,
    ATTR_SIP_INFO,
    CONF_SERVER_ADDRESS,
    DIRECT_UP,
    DOMAIN,
    EVENT_APPOINT,
    EVENT_BYE,
    EVENT_PERMIT,
    EVENT_RELOAD,
    EVENT_RING,
    EVENT_UNLOCK,
    LATEST_EVENT,
    PLATFORMS,
    PLAYBACK_POLL_ATTEMPTS,
    PLAYBACK_POLL_INTERVAL,
    PORT_CONFIG,
    RING_STATUS,
    EVENT_SOC_TEMP, 
    SOC_TEMP,
)

_LOGGER = logging.getLogger(__name__)

SERVICES: tuple[str, ...] = (
    EVENT_UNLOCK,
    EVENT_APPOINT,
    EVENT_PERMIT,
    EVENT_BYE,
    "execute",
)

VIEW_REGISTERED: str = f"{DOMAIN}_view"


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _normalize_server(address: str) -> str:
    """Normalize a server address so it can be compared with Client.server_addr."""
    parsed = urlparse(address if "//" in address else f"//{address}")
    scheme = parsed.scheme or "http"
    host = parsed.hostname or ""
    port = parsed.port or PORT_CONFIG
    return f"{scheme}://{host}:{port}"


async def _async_run_service(
    hass: HomeAssistant, service: str, call: ServiceCall
) -> dict[str, str]:
    """Run a doorlink service against one or all configured servers."""
    clients: list[Client] = list(hass.data.get(DOMAIN, {}).values())
    address = call.data.get(CONF_SERVER_ADDRESS)
    if address:
        wanted = _normalize_server(address)
        clients = [client for client in clients if client.server_addr == wanted]
        if not clients:
            message = f"Server '{address}' not found"
            hass.bus.async_fire(
                f"{DOMAIN}.{service}", {"status": "error", "message": message}
            )
            raise HomeAssistantError(message)
    if not clients:
        raise HomeAssistantError("No doorlink server is configured")

    sip_info = call.data.get(ATTR_SIP_INFO)
    floor = call.data.get(ATTR_FLOOR)
    direct = call.data.get(ATTR_DIRECT)
    tasks = []
    for client in clients:
        if service == EVENT_UNLOCK:
            tasks.append(client.unlock(sip_to=sip_info))
        elif service == EVENT_APPOINT:
            tasks.append(
                client.appoint(
                    sip_to=sip_info,
                    direct=direct if direct is not None else DIRECT_UP,
                    floor=floor,
                )
            )
        elif service == EVENT_PERMIT:
            tasks.append(client.permit(sip_to=sip_info, floor=floor))
        elif service == EVENT_BYE:
            tasks.append(client.bye(sip_to=sip_info))
        elif service == "execute":
            tasks.append(client.execute(data=call.data.get(ATTR_JSON_DATA)))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    errors = [
        str(result) for result in results if isinstance(result, BaseException)
    ]
    for result in results:
        if isinstance(result, BaseException):
            _LOGGER.debug("doorlink.%s failed", service, exc_info=result)

    payload: dict[str, str] = {"status": "error" if errors else "success"}
    if errors:
        payload["message"] = "; ".join(errors)
    hass.bus.async_fire(f"{DOMAIN}.{service}", payload)
    if errors:
        raise HomeAssistantError(payload["message"])
    return payload


def _async_register_services(hass: HomeAssistant) -> None:
    """Register the doorlink services once."""
    for service in SERVICES:
        if hass.services.has_service(DOMAIN, service):
            continue

        async def _handle(call: ServiceCall, _service: str = service) -> dict[str, str]:
            return await _async_run_service(hass, _service, call)

        hass.services.async_register(
            DOMAIN,
            service,
            _handle,
            supports_response=SupportsResponse.OPTIONAL,
        )


def _async_unregister_services(hass: HomeAssistant) -> None:
    """Remove the doorlink services when the last entry is unloaded."""
    for service in SERVICES:
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)


async def _async_announce(client: Client, entry_id: str) -> None:
    """Tell the doorlink server where to push its events."""
    payload = {
        "event": "doorlink",
        "data": json.dumps({"api": f"/api/doorlink/{entry_id}"}),
    }
    try:
        await client.post_request(payload)
    except HomeAssistantError as err:
        _LOGGER.warning("Unable to announce the callback URL: %s", err)


# ----------------------------------------------------------------------
# Entry setup
# ----------------------------------------------------------------------
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up doorlink from a config entry."""
    _LOGGER.debug("entry.data: %s", entry.data)

    hass.data.setdefault(DOMAIN, {})

    client = Client(hass, entry)
    # Raises ConfigEntryNotReady (and retries later) when the server is away.
    await client.initialize()
    hass.data[DOMAIN][entry.entry_id] = client

    if not hass.data.get(VIEW_REGISTERED):
        hass.http.register_view(DoorlinkView(hass))
        hass.data[VIEW_REGISTERED] = True

    _async_register_services(hass)

    async def _async_handle_reload() -> None:
        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{DOMAIN}_{entry.entry_id}_{EVENT_RELOAD}", _async_handle_reload
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_create_background_task(
        hass,
        _async_announce(client, entry.entry_id),
        f"{DOMAIN} announce {entry.entry_id}",
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a doorlink config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            _async_unregister_services(hass)
    return unloaded


# ----------------------------------------------------------------------
# HTTP view
# ----------------------------------------------------------------------
class DoorlinkView(HomeAssistantView):
    """Receive the events pushed by the doorlink server."""

    url = "/api/doorlink/{entry_id}"
    name = "api:doorlink"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the view."""
        self._hass = hass
        self._downloaded: set[str] = set()
        self._downloading: set[str] = set()
        _LOGGER.debug("HTTP server URL: %s", self.url)

    async def post(self, request: Request, entry_id: str) -> Response:
        """Handle an event posted by the doorlink server."""
        client: Client | None = self._hass.data.get(DOMAIN, {}).get(entry_id)
        if client is None:
            return json_response(
                {"error": f"Unknown doorlink entry: {entry_id}"}, status=404
            )

        content_type = (
            request.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        )
        try:
            if content_type == "application/json":
                payloads = await request.json()
                _LOGGER.debug("Received JSON data: %s", payloads)
            elif content_type == "application/x-www-form-urlencoded":
                raw_data = await request.text()
                payloads = {
                    key: value[0]
                    for key, value in parse_qs(
                        raw_data, keep_blank_values=True
                    ).items()
                }
                _LOGGER.debug("Received form-urlencoded data: %s", payloads)
            else:
                _LOGGER.warning("Unsupported Content-Type: %s", content_type)
                return json_response(
                    {"error": f"Unsupported Content-Type: {content_type}"}, status=415
                )
        except (ValueError, UnicodeDecodeError) as err:
            _LOGGER.error("Invalid payload: %s", err)
            return json_response({"error": "Invalid payload"}, status=400)

        if not isinstance(payloads, dict):
            return json_response({"error": "Payload must be an object"}, status=400)

        await self._async_handle_event(client, payloads)
        return json_response({"status": "success"}, status=200)

    async def _async_handle_event(
        self, client: Client, payloads: dict[str, Any]
    ) -> None:
        """Dispatch a single event to the entities."""
        if client.monitor is None:  # pragma: no cover - defensive
            return

        state_attributes = {
            key: value for key, value in payloads.items() if value is not None
        }
        event = payloads.get("event", EVENT_RING)
        state_attributes["event"] = event
        state_attributes["time"] = dt_util.now().isoformat()

        async_dispatcher_send(
            self._hass,
            f"{DOMAIN}_{client.monitor.device_id}_{LATEST_EVENT}",
            state_attributes,
        )

        if event == EVENT_RING:
            async_dispatcher_send(
                self._hass,
                f"{DOMAIN}_{client.monitor.device_id}_{RING_STATUS}",
                True,
            )
            sip_from = SIPContact(payloads.get("from"))
            if sip_from.device_id:
                async_dispatcher_send(
                    self._hass,
                    f"{DOMAIN}_{sip_from.device_id}_{RING_STATUS}",
                    True,
                )
            if client.playback_path:
                self._hass.async_create_task(
                    self._async_download_playback(client),
                    name=f"{DOMAIN} playback {client.entry_id}",
                )
        elif event == EVENT_SOC_TEMP:
            try:
                soc_temp = float(payloads.get(SOC_TEMP))
            except (TypeError, ValueError):
                _LOGGER.warning("Invalid soc_temp payload: %s", payloads)
                return
            async_dispatcher_send(
                self._hass,
                f"{DOMAIN}_{client.monitor.device_id}_{SOC_TEMP}",
                soc_temp,
            )
        elif event == EVENT_RELOAD:
            async_dispatcher_send(
                self._hass, f"{DOMAIN}_{client.entry_id}_{EVENT_RELOAD}"
            )

    # ------------------------------------------------------------------
    # Playback video
    # ------------------------------------------------------------------
    async def _async_download_playback(self, client: Client) -> None:
        """Download the playback video of the last call, once per file."""
        if client.entry_id in self._downloading:
            return
        self._downloading.add(client.entry_id)
        try:
            await self._async_download_playback_file(client)
        except Exception:  # noqa: BLE001 - background task must not explode
            _LOGGER.exception("Playback download failed")
        finally:
            self._downloading.discard(client.entry_id)

    async def _async_download_playback_file(self, client: Client) -> None:
        """Poll the playback info endpoint and download the finished file."""
        video_url = f"{client.server_addr}{client.playback_path}"
        info_url = f"{video_url}/info"
        session = async_get_clientsession(self._hass)

        filename = ""
        last_size = -1
        for _ in range(PLAYBACK_POLL_ATTEMPTS):
            await asyncio.sleep(PLAYBACK_POLL_INTERVAL)
            try:
                async with session.get(
                    info_url, timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status != 200:
                        _LOGGER.debug(
                            "Playback info returned HTTP %s", response.status
                        )
                        continue
                    info = await response.json(content_type=None)
            except (aiohttp.ClientError, TimeoutError, ValueError) as err:
                _LOGGER.debug("Playback info polling failed: %s", err)
                return

            if not isinstance(info, dict):
                _LOGGER.debug("Unexpected playback info payload: %s", info)
                return

            # Only keep the base name, the server must not pick our local path.
            filename = os.path.basename(str(info.get("filename") or ""))
            try:
                size = int(info.get("size") or 0)
            except (TypeError, ValueError):
                _LOGGER.debug("Invalid playback size: %s", info.get("size"))
                return
            if not filename or size == 0:
                return
            if filename in self._downloaded:
                return
            if size == last_size:
                break
            last_size = size
        else:
            _LOGGER.debug("Playback info polling timed out")
            return

        if not filename:  # pragma: no cover - defensive
            return

        filepath = os.path.join(client.filepath, filename)
        if await self._hass.async_add_executor_job(os.path.isfile, filepath):
            self._downloaded.add(filename)
            return

        await self._hass.async_add_executor_job(
            os.makedirs, os.path.dirname(filepath), 0o750, True
        )
        try:
            async with session.get(
                video_url, timeout=aiohttp.ClientTimeout(total=None)
            ) as response:
                if response.status != 200:
                    _LOGGER.warning(
                        "Playback download returned HTTP %s", response.status
                    )
                    return
                async with aiofiles.open(filepath, "wb") as file:
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        await file.write(chunk)
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            _LOGGER.warning("Playback download failed: %s", err)
            with suppress(OSError):
                await self._hass.async_add_executor_job(os.remove, filepath)
            return

        self._downloaded.add(filename)
        _LOGGER.debug("Playback saved as %s", filepath)
