"""HTTP/SIP helpers for the doorlink integration."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlparse

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import (
    CONF_FAMILY,
    CONF_FILEPATH,
    CONF_PLAYBACK,
    CONF_RTSP_URL,
    CONF_SERVER_ADDRESS,
    CONF_SIP_INFO,
    CONF_SOC_TEMP,
    CONF_STATIONS,
    CONF_STREAM,
    DIRECT_UP,
    DOMAIN,
    EVENT_APPOINT,
    EVENT_BYE,
    EVENT_PERMIT,
    EVENT_UNLOCK,
    LATEST_EVENT,
    PORT_CONFIG,
    PORT_STREAM,
    REQUEST_TIMEOUT,
    STREAM_TYPE_H264,
    STREAM_TYPE_MJPEG,
)

_LOGGER = logging.getLogger(__name__)


class SIPContact:
    """A SIP contact, e.g. ``10019901@172.16.0.101:5060``."""

    def __init__(self, info: str | None, rtsp_url: str | None = None) -> None:
        """Parse the SIP info string and the optional RTSP url."""
        self.info = info
        self.ip: str | None = None
        self.port: str | None = None
        self.name: str | None = None
        self.device_id: str = ""

        self.rtsp_username: str | None = None
        self.rtsp_password: str | None = None
        self.rtsp_url: str | None = None

        self.mjpeg_url: str | None = None
        self.snapshot_url: str | None = None
        self.playback_url: str | None = None
        self.stream_type: str | None = None

        if info and isinstance(info, str):
            name_psk, separator, ip_port = info.rpartition("@")
            if not separator or not name_psk or not ip_port:
                _LOGGER.warning(
                    "Malformed SIP info '%s', expected 'name@ip:port'", info
                )
            else:
                self.name = name_psk.split(":", 1)[0] or name_psk
                host, port_separator, port = ip_port.rpartition(":")
                if port_separator:
                    self.ip, self.port = host, port
                else:
                    self.ip, self.port = ip_port, None
                self.device_id = self.ip.replace(".", "_").replace(":", "_")

        if rtsp_url:
            parsed = urlparse(rtsp_url)
            self.rtsp_username = parsed.username
            self.rtsp_password = parsed.password
            host = parsed.hostname or ""
            netloc = f"{host}:{parsed.port}" if parsed.port else host
            self.rtsp_url = parsed._replace(netloc=netloc).geturl()


class Stations:
    """All the indoor monitors of a doorlink server."""

    def __init__(self, stations: list[dict[str, Any]] | None = None) -> None:
        """Build the contact list from the ``/config`` payload."""
        self.contacts: dict[str, SIPContact] = {}
        for station in stations or []:
            if not isinstance(station, dict):
                continue
            info = station.get(CONF_SIP_INFO)
            if not info:
                continue
            contact = SIPContact(info, station.get(CONF_RTSP_URL))
            if not contact.ip:
                continue
            self.contacts[contact.ip] = contact


class Client:
    """Talk to one doorlink server."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the client."""
        self.hass = hass
        self.entry_id = entry.entry_id

        self.server = urlparse(entry.data[CONF_SERVER_ADDRESS])
        self.scheme = self.server.scheme or "http"
        self.host = self.server.hostname or ""
        self.port = self.server.port or PORT_CONFIG
        self.server_addr = f"{self.scheme}://{self.host}:{self.port}"

        self.filepath = entry.data.get(CONF_FILEPATH) or "/media/doorlink"

        self.online = False
        self.monitor: SIPContact | None = None
        self.stations = Stations()
        self.family = 1
        self.soc_temp: float | None = None
        self.playback_path: str | None = None

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    async def initialize(self) -> None:
        """Read the server configuration; raises ConfigEntryNotReady on failure."""
        status, text = await self.get_request("/config")
        if status is None:
            raise ConfigEntryNotReady(
                f"Unable to reach doorlink server {self.server_addr}"
            )
        if status != 200:
            raise ConfigEntryNotReady(
                f"doorlink server {self.server_addr} returned HTTP {status}"
            )
        try:
            data = json.loads(text or "{}")
        except ValueError as err:
            raise ConfigEntryNotReady(f"Invalid /config payload: {err}") from err
        if not isinstance(data, dict):
            raise ConfigEntryNotReady("Invalid /config payload: not an object")

        monitor_info = data.get(CONF_SIP_INFO)
        if not monitor_info:
            raise ConfigEntryNotReady("doorlink /config is missing the 'sip' key")

        self.monitor = SIPContact(monitor_info)
        if not self.monitor.device_id:
            raise ConfigEntryNotReady(f"Invalid SIP info in /config: {monitor_info}")

        self.stations = Stations(data.get(CONF_STATIONS))
        self.family = data.get(CONF_FAMILY, 1)
        self.playback_path = data.get(CONF_PLAYBACK)

        if CONF_SOC_TEMP in data:
            try:
                self.soc_temp = float(data[CONF_SOC_TEMP])
            except (TypeError, ValueError):
                _LOGGER.warning("Invalid soc_temp value: %s", data[CONF_SOC_TEMP])

        self.monitor.stream_type = data.get(CONF_STREAM)
        if self.monitor.stream_type == STREAM_TYPE_MJPEG:
            self.monitor.mjpeg_url = f"{self.scheme}://{self.host}:{PORT_STREAM}"
            self.monitor.snapshot_url = (
                f"{self.scheme}://{self.host}:{PORT_STREAM}/snapshot"
            )
            if self.playback_path:
                self.monitor.playback_url = (
                    f"{self.scheme}://{self.host}:{PORT_STREAM}{self.playback_path}"
                )
        elif self.monitor.stream_type == STREAM_TYPE_H264:
            self.monitor.rtsp_url = f"rtsp://{self.host}:{PORT_STREAM}"
            if self.playback_path:
                self.monitor.playback_url = (
                    f"{self.scheme}://{self.host}:{PORT_CONFIG}{self.playback_path}"
                )
        else:
            _LOGGER.debug("Unknown stream type: %s", self.monitor.stream_type)

    # ------------------------------------------------------------------
    # Low level HTTP
    # ------------------------------------------------------------------
    async def _async_request(
        self, method: str, path: str = "/", **kwargs: Any
    ) -> tuple[int | None, str | None]:
        """Perform a request against the doorlink server."""
        url = f"{self.server_addr}{path}"
        kwargs.setdefault("timeout", aiohttp.ClientTimeout(total=REQUEST_TIMEOUT))
        session = async_get_clientsession(self.hass)
        try:
            async with session.request(method, url, **kwargs) as response:
                text = await response.text()
                _LOGGER.debug(
                    "HTTP %s %s -> %s: %s", method, url, response.status, text
                )
                return response.status, text
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("HTTP %s %s failed: %s", method, url, err)
            return None, None

    async def get_request(self, path: str = "/") -> tuple[int | None, str | None]:
        """GET a path from the doorlink server."""
        return await self._async_request("GET", path)

    async def post_request(self, data: Any) -> None:
        """POST a command to the doorlink server.

        aiohttp form encoding only accepts ``str`` / ``bytes`` values, so ints
        (``family``, ``direct``, ``floor``) must be stringified and ``None``
        values dropped before sending.
        """
        if isinstance(data, dict):
            data = {
                key: value if isinstance(value, (str, bytes)) else str(value)
                for key, value in data.items()
                if value is not None
            }
        status, text = await self._async_request("POST", "/", data=data)
        if status is None:
            raise HomeAssistantError(
                f"Unable to reach doorlink server {self.server_addr}"
            )
        if status >= 400:
            raise HomeAssistantError(
                f"doorlink server returned HTTP {status}: {text or ''}"
            )

    async def check_online(self) -> bool:
        """Poll the server status endpoint."""
        status, _ = await self._async_request("GET", "/status")
        self.online = status == 200
        return self.online

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    def update_latest_event(self, state_attributes: dict[str, Any]) -> None:
        """Push the latest event to the sensor entity."""
        if self.monitor is None:
            return
        async_dispatcher_send(
            self.hass,
            f"{DOMAIN}_{self.monitor.device_id}_{LATEST_EVENT}",
            state_attributes,
        )

    async def execute(self, data: Any) -> None:
        """Execute a raw command (usually from the ``doorlink.execute`` service)."""
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except ValueError as err:
                raise HomeAssistantError(f"Invalid JSON data: {err}") from err
        if not isinstance(data, dict):
            raise HomeAssistantError("JSON data must be an object")

        if self.monitor is None:
            raise HomeAssistantError("doorlink server is not initialised")

        event = data.get("event")
        sip_from = data.get("sip_from") or self.monitor.info
        sip_to = data.get("sip_to")
        direct = data.get("direct", DIRECT_UP)
        family = data.get("family", self.family)
        floor = data.get("floor")

        if event == EVENT_UNLOCK:
            await self.unlock_advanced(sip_from=sip_from, sip_to=sip_to, family=family)
        elif event == EVENT_APPOINT:
            await self.appoint_advanced(
                sip_from=sip_from,
                sip_to=sip_to,
                direct=direct,
                floor=floor,
                family=family,
            )
        elif event == EVENT_PERMIT:
            await self.permit_advanced(
                sip_from=sip_from, sip_to=sip_to, floor=floor, family=family
            )
        elif event == EVENT_BYE:
            await self.bye_advanced(
                sip_from=sip_from,
                sip_to=sip_to,
                tag=data.get("tag"),
                call_id=data.get("call_id"),
            )
        else:
            raise HomeAssistantError(f"Unsupported event '{event}'")

    async def unlock_advanced(
        self, sip_from: str | None, sip_to: str | None, family: int = 1
    ) -> None:
        """Send an unlock command."""
        sip_from = sip_from or (self.monitor.info if self.monitor else None)
        await self.post_request(
            data={
                "from": sip_from,
                "to": sip_to or "",
                "event": EVENT_UNLOCK,
                "family": family,
                "direct": "1",
            }
        )
        self.update_latest_event(
            {
                "event": EVENT_UNLOCK,
                "from": sip_from,
                "to": sip_to,
                "time": dt_util.now().isoformat(),
            }
        )

    async def unlock(self, sip_to: str | None) -> None:
        """Unlock through the indoor monitor of this server."""
        await self.unlock_advanced(
            sip_from=self.monitor.info if self.monitor else None,
            sip_to=sip_to,
            family=self.family,
        )

    async def appoint_advanced(
        self,
        sip_from: str | None,
        sip_to: str | None,
        direct: int | str = DIRECT_UP,
        floor: int | str | None = None,
        family: int = 1,
    ) -> None:
        """Send an elevator appointment command."""
        sip_from = sip_from or (self.monitor.info if self.monitor else None)
        await self.post_request(
            data={
                "from": sip_from,
                "to": sip_to or "",
                "event": EVENT_APPOINT,
                "family": family,
                "direct": direct,
                "floor": floor if floor is not None else "",
            }
        )
        self.update_latest_event(
            {
                "event": EVENT_APPOINT,
                "from": sip_from,
                "to": sip_to,
                "direct": direct,
                "floor": floor if floor is not None else "",
                "time": dt_util.now().isoformat(),
            }
        )

    async def appoint(
        self,
        sip_to: str | None,
        direct: int | str = DIRECT_UP,
        floor: int | str | None = None,
    ) -> None:
        """Call the elevator of this server."""
        await self.appoint_advanced(
            sip_from=self.monitor.info if self.monitor else None,
            sip_to=sip_to,
            direct=direct,
            floor=floor,
            family=self.family,
        )

    async def permit_advanced(
        self,
        sip_from: str | None,
        sip_to: str | None,
        floor: int | str | None = None,
        family: int = 1,
    ) -> None:
        """Send a floor permit command."""
        sip_from = sip_from or (self.monitor.info if self.monitor else None)
        await self.post_request(
            data={
                "from": sip_from,
                "to": sip_to or "",
                "event": EVENT_PERMIT,
                "family": family,
                "floor": floor if floor is not None else "",
                "direct": "1",
            }
        )
        self.update_latest_event(
            {
                "event": EVENT_PERMIT,
                "from": sip_from,
                "to": sip_to,
                "floor": floor if floor is not None else "",
                "time": dt_util.now().isoformat(),
            }
        )

    async def permit(
        self, sip_to: str | None, floor: int | str | None = None
    ) -> None:
        """Grant floor access from this server."""
        await self.permit_advanced(
            sip_from=self.monitor.info if self.monitor else None,
            sip_to=sip_to,
            floor=floor,
            family=self.family,
        )

    async def bye_advanced(
        self,
        sip_from: str | None = None,
        sip_to: str | None = None,
        tag: str | None = None,
        call_id: str | None = None,
    ) -> None:
        """Hang up the current call."""
        sip_to = sip_to or (self.monitor.info if self.monitor else None)
        await self.post_request(
            data={
                "from": sip_from or "",
                "to": sip_to,
                "event": EVENT_BYE,
                "family": 1,
                "direct": "1",
                "tag": tag,
                "call_id": call_id,
            }
        )
        self.update_latest_event(
            {
                "event": EVENT_BYE,
                "from": sip_from,
                "to": sip_to,
                "time": dt_util.now().isoformat(),
            }
        )

    async def bye(self, sip_to: str | None) -> None:
        """Hang up the call of this server."""
        await self.bye_advanced(sip_to=sip_to)
