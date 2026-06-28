from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.dispatcher import async_dispatcher_send, async_dispatcher_connect
from aiohttp import ClientSession
from aiohttp.web import Request, Response, json_response
import asyncio
import aiofiles
import json
import os
from datetime import datetime
from urllib.parse import parse_qs, urlparse

from .client import Client, SIPContact
from .const import (
    DOMAIN, 
    PLATFORMS, 
    CONF_SERVER_ADDRESS, 
    PORT_CONFIG,

    LATEST_EVENT, 
    RING_STATUS, 
)

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.debug(f'entry.data: {entry.data}')

    hass.data.setdefault(DOMAIN, {})

    # Initialize Client
    client = Client(hass, entry)
    await client.initialize()
    hass.data[DOMAIN][entry.entry_id] = client

    # Initialize HTTP Viewer
    hass.http.register_view(DoorlinkView(hass, entry.entry_id))

    # Register Services
    async def unlock(call):
        server_addr = call.data.get(CONF_SERVER_ADDRESS)
        sip_info = call.data.get("sip_info")
        tasks = []
        if server_addr:
            for c in hass.data[DOMAIN].values():
                if urlparse(server_addr) == c.server:
                    tasks.append(c.unlock(sip_to=sip_info))
                    break
            if not tasks:
                hass.bus.fire(
                    "doorlink.unlock",
                    {
                        "status": "error",
                        "message": f"Server '{server_addr}' not found",
                    },
                )
                return
        else:
            tasks = [
                c.unlock(sip_to=sip_info)
                for c in hass.data[DOMAIN].values()
            ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success = True
        errors = []
        for result in results:
            if isinstance(result, Exception):
                success = False
                errors.append(str(result))
                _LOGGER.exception("unlock failed", exc_info=result)
        payload = {"status": "success" if success else "error"}
        if errors:
            payload["message"] = "; ".join(errors)
        hass.bus.fire("doorlink.unlock", payload)
    if not hass.services.has_service(DOMAIN, "unlock"):
        hass.services.async_register(DOMAIN, "unlock", unlock)

    async def appoint(call):
        server_addr = call.data.get(CONF_SERVER_ADDRESS)
        sip_info = call.data.get("sip_info")
        floor = call.data.get("floor")
        direct = call.data.get("direct")
        tasks = []
        if server_addr:
            for c in hass.data[DOMAIN].values():
                if urlparse(server_addr) == c.server:
                    tasks.append(c.appoint(sip_to=sip_info, floor=floor, direct=direct))
                    break
            if not tasks:
                hass.bus.fire(
                    "doorlink.appoint",
                    {
                        "status": "error",
                        "message": f"Server '{server_addr}' not found",
                    },
                )
                return
        else:
            tasks = [
                c.appoint(sip_to=sip_info, floor=floor, direct=direct)
                for c in hass.data[DOMAIN].values()
            ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success = True
        errors = []
        for result in results:
            if isinstance(result, Exception):
                success = False
                errors.append(str(result))
                _LOGGER.exception("appoint failed", exc_info=result)
        payload = {"status": "success" if success else "error"}
        if errors:
            payload["message"] = "; ".join(errors)
        hass.bus.fire("doorlink.appoint", payload)
    if not hass.services.has_service(DOMAIN, "appoint"):
        hass.services.async_register(DOMAIN, "appoint", appoint)

    async def permit(call):
        server_addr = call.data.get(CONF_SERVER_ADDRESS)
        sip_info = call.data.get("sip_info")
        floor = call.data.get("floor")
        tasks = []
        if server_addr:
            for c in hass.data[DOMAIN].values():
                if urlparse(server_addr) == c.server:
                    tasks.append(c.permit(sip_to=sip_info, floor=floor))
                    break
            if not tasks:
                hass.bus.fire(
                    "doorlink.permit",
                    {
                        "status": "error",
                        "message": f"Server '{server_addr}' not found",
                    },
                )
                return
        else:
            tasks = [
                c.permit(sip_to=sip_info, floor=floor)
                for c in hass.data[DOMAIN].values()
            ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success = True
        errors = []
        for result in results:
            if isinstance(result, Exception):
                success = False
                errors.append(str(result))
                _LOGGER.exception("permit failed", exc_info=result)
        payload = {"status": "success" if success else "error"}
        if errors:
            payload["message"] = "; ".join(errors)
        hass.bus.fire("doorlink.permit", payload)
    if not hass.services.has_service(DOMAIN, "permit"):
        hass.services.async_register(DOMAIN, "permit", permit)

    async def bye(call):
        server_addr = call.data.get(CONF_SERVER_ADDRESS)
        sip_info = call.data.get("sip_info")
        tasks = []
        if server_addr:
            for c in hass.data[DOMAIN].values():
                if urlparse(server_addr) == c.server:
                    tasks.append(c.bye(sip_to=sip_info))
                    break
            if not tasks:
                hass.bus.fire(
                    "doorlink.bye",
                    {
                        "status": "error",
                        "message": f"Server '{server_addr}' not found",
                    },
                )
                return
        else:
            tasks = [
                c.bye(sip_to=sip_info)
                for c in hass.data[DOMAIN].values()
            ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success = True
        errors = []
        for result in results:
            if isinstance(result, Exception):
                success = False
                errors.append(str(result))
                _LOGGER.exception("bye failed", exc_info=result)
        payload = {"status": "success" if success else "error"}
        if errors:
            payload["message"] = "; ".join(errors)
        hass.bus.fire("doorlink.bye", payload)
    if not hass.services.has_service(DOMAIN, "bye"):
        hass.services.async_register(DOMAIN, "bye", bye)

    async def execute(call):
        server_addr = call.data.get(CONF_SERVER_ADDRESS)
        json_data = call.data.get('json_data')
        tasks = []
        if server_addr:
            for c in hass.data[DOMAIN].values():
                if urlparse(server_addr) == c.server:
                    tasks.append(c.execute(data=json_data))
                    break
            if not tasks:
                hass.bus.fire(
                    "doorlink.execute",
                    {
                        "status": "error",
                        "message": f"Server '{server_addr}' not found",
                    },
                )
                return
        else:
            tasks = [
                c.execute(data=json_data)
                for c in hass.data[DOMAIN].values()
            ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success = True
        errors = []
        for result in results:
            if isinstance(result, Exception):
                success = False
                errors.append(str(result))
                _LOGGER.exception("execute failed", exc_info=result)
        payload = {"status": "success" if success else "error"}
        if errors:
            payload["message"] = "; ".join(errors)
        hass.bus.fire("doorlink.execute", payload)
    if not hass.services.has_service(DOMAIN, "execute"):
        hass.services.async_register(DOMAIN, "execute", execute)

    # Reload Entity
    async def handle_reload():
        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{entry.entry_id}_RELOAD",
            handle_reload
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data[DOMAIN].pop(entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

class DoorlinkView(HomeAssistantView):
    requires_auth = True

    def __init__(self, hass: HomeAssistant, entry_id: str):
        self._hass = hass
        self._entry_id = entry_id
        self.url = f"/api/doorlink/{entry_id}"
        self.name = f"api:doorlink:{entry_id}"
        self.client = hass.data[DOMAIN][entry_id]
        self.filename = ""
        _LOGGER.debug(f"HTTP Server URL: {self.url}")
        data = {"api": self.url}
        payloads = {
            "event": 'doorlink',
            "data": json.dumps(data,indent=2),
        }
        hass.loop.call_soon_threadsafe(
            asyncio.create_task, 
            self.client.post_request(payloads)
            )

    def _parse_content_type(self, content_type: str) -> str:
        if content_type:
            return content_type.split(";", 1)[0].strip()
        return ""

    async def post(self, request: Request) -> Response:
        try:
            content_type = self._parse_content_type(request.headers.get("Content-Type", ""))
            if content_type == "application/json":
                payloads = await request.json()
                _LOGGER.debug(f"Received JSON data: {payloads}")
            elif content_type == "application/x-www-form-urlencoded":
                raw_data = await request.text()
                payloads = {k: v[0] for k, v in parse_qs(raw_data, keep_blank_values=True).items()}
                _LOGGER.debug(f"Received form-urlencoded data: {payloads}")
            else:
                _LOGGER.warning(f"Unsupported Content-Type: {content_type}")
                return json_response({"error": f"Unsupported Content-Type: {content_type}"}, status=400)

            await self.handle_post(payloads)
            return json_response({"status": "success"}, status=200)

        except json.JSONDecodeError as e:
            _LOGGER.error(f"Invalid JSON: {e}")
            return json_response({"error": "Invalid JSON"}, status=400)
        except UnicodeDecodeError as e:
            _LOGGER.error(f"UnicodeDecodeError: {e}")
            return json_response({"error": "Invalid data encoding"}, status=400)
        except Exception as e:
            _LOGGER.error(f"Exception: {e}")
            return json_response({"error": str(e)}, status=400)

    async def handle_post(self, payloads: dict):
        state_attributes = {k: v for k, v in payloads.items() if v is not None}
        state_attributes['event'] = payloads.get('event', 'ring')
        state_attributes['time'] = datetime.now().isoformat()
        async_dispatcher_send(
            self._hass,
            f"{DOMAIN}_{self.client.monitor.device_id}_{LATEST_EVENT}",
            state_attributes,
        )
        if state_attributes['event'] == 'ring':
            async_dispatcher_send(
                self._hass,
                f"{DOMAIN}_{self.client.monitor.device_id}_{RING_STATUS}",
                True,
            )
            sip_from = SIPContact(payloads.get('from'))
            if sip_from.device_id:
                async_dispatcher_send(
                    self._hass,
                    f"{DOMAIN}_{sip_from.device_id}_{RING_STATUS}",
                    True,
                )
            if self.client.playback_path:
                self._hass.async_create_task(self.download_playback_video())
        elif state_attributes['event'] == 'reload':
            async_dispatcher_send(
                self._hass,
                f"{DOMAIN}_{self._entry_id}_RELOAD"
            )

    async def download_playback_video(self):
        video_url = f'{self.client.server.scheme}://{self.client.server.hostname}:{PORT_CONFIG}{self.client.playback_path}'
        info_url = f"{video_url}/info"

        last_size = -1
        filename = ""
        sync_count = 0
        async with ClientSession() as session:
            while True:
                try:
                    await asyncio.sleep(3)
                    async with session.get(info_url, timeout=5) as resp:
                        info = await resp.json()
                    sync_count += 1
                    filename = info["filename"]
                    size = info["size"]
                    if size == 0 or filename == self.filename:
                        return
                    if size > 0 and (size == last_size or sync_count > 60):
                        break
                    last_size = size
                except Exception as err:
                    _LOGGER.warning("Playback info polling failed: %s", err)
                    return
            async with session.get(video_url) as resp:
                if resp.status == 200:
                    filepath = os.path.join(self.client.filepath, filename)
                    if os.path.isfile(filepath):
                        self.filename = filename
                        return
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    try:
                        async with aiofiles.open(filepath, "wb") as f:
                            async for chunk in resp.content.iter_chunked(1024 * 1024):
                                await f.write(chunk)
                    except Exception:
                        if os.path.exists(filepath):
                            os.remove(filepath)
                        raise
                    _LOGGER.debug("Playback saved as {filePath}")
            self.filename = filename