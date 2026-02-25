from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.dispatcher import async_dispatcher_send, async_dispatcher_connect
from aiohttp.web import Request, Response, json_response
from asyncio import create_task
import json
from datetime import datetime
from urllib.parse import parse_qs



from .client import Client, SIPContact
from .const import (
    DOMAIN, 
    PLATFORMS, 

    MONITOR, 
    STATIONS, 
    LATEST_EVENT, 
    RING_STATUS, 
    ELEV_APPOINT,
    UNLOCK,
    ELEV_PERMIT,
    BYE,
    EXECUTE
)

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.debug(f'entry.data: {entry.data}')

    hass.data.setdefault(DOMAIN, {})

    # Initialize Client
    client = Client(hass, entry.data)
    await client.initialize()

    hass.data[DOMAIN][entry.entry_id] = client
    hass.data[DOMAIN][MONITOR] = client.monitor
    hass.data[DOMAIN][STATIONS] = client.stations

    # Initialize HTTP Viewer
    hass.http.register_view(DoorlinkView(hass, entry.entry_id))

    async def appoint(call):
        """Handle the service call."""
        sip_info = call.data.get('sip_info')
        direct = call.data.get('direct')
        _LOGGER.debug(f'appoint request received as {call.data}.')
        try:
            await client.appoint(sip_to=sip_info, direct=direct)
            _LOGGER.debug(f'appoint request executed.')
            hass.bus.fire('doorlink.appoint', {'status': 'success'})
        except Exception as e:
            _LOGGER.debug(f'appoint request failed: {e}.')
            hass.bus.fire('doorlink.appoint', {'status': 'error', 'message': str(e)})
    hass.services.async_register(DOMAIN, ELEV_APPOINT, appoint)

    async def unlock(call):
        """Handle the service call."""
        sip_info = call.data.get('sip_info')
        _LOGGER.debug(f'unlock request received as {call.data}.')
        try:
            await client.unlock(sip_to=sip_info)
            _LOGGER.debug(f'unlock request executed.')
            hass.bus.fire('doorlink.unlock', {'status': 'success'})
        except Exception as e:
            _LOGGER.debug(f'unlock request failed: {e}.')
            hass.bus.fire('doorlink.unlock', {'status': 'error', 'message': str(e)})
    hass.services.async_register(DOMAIN, UNLOCK, unlock)

    async def permit(call):
        """Handle the service call."""
        sip_info = call.data.get('sip_info')
        _LOGGER.debug(f'permit request received as {call.data}.')
        try:
            await client.permit(sip_to=sip_info)
            _LOGGER.debug(f'permit request executed.')
            hass.bus.fire('doorlink.permit', {'status': 'success'})
        except Exception as e:
            _LOGGER.debug(f'permit request failed: {e}.')
            hass.bus.fire('doorlink.permit', {'status': 'error', 'message': str(e)})
    hass.services.async_register(DOMAIN, ELEV_PERMIT, permit)

    async def bye(call):
        """Handle the service call."""
        sip_info = call.data.get('sip_info')
        tag = call.data.get('tag')
        call_id = call.data.get('call_id')
        _LOGGER.debug(f'bye request received as {call.data}.')
        try:
            await client.bye(sip_from=sip_info, tag=tag, call_id=call_id)
            _LOGGER.debug(f'bye request executed.')
            hass.bus.fire('doorlink.bye', {'status': 'success'})
        except Exception as e:
            _LOGGER.debug(f'bye request failed: {e}.')
            hass.bus.fire('doorlink.bye', {'status': 'error', 'message': str(e)})
    hass.services.async_register(DOMAIN, BYE, bye)

    async def execute(call):
        """Handle the service call."""
        json_data = call.data.get('json_data')
        _LOGGER.debug(f'execute request received as {call.data}.')
        try:
            await client.execute(json_data)
            _LOGGER.debug(f'execute request executed.')
            hass.bus.fire('doorlink.execute', {'status': 'success'})
        except Exception as e:
            _LOGGER.debug(f'execute request failed: {e}.')
            hass.bus.fire('doorlink.execute', {'status': 'error', 'message': str(e)})
    hass.services.async_register(DOMAIN, EXECUTE, execute)

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
        _LOGGER.debug(f"HTTP Server URL: {self.url}")
        data = {"api": self.url}
        payloads = {
            "event": 'doorlink',
            "data": json.dumps(data,indent=2),
        }
        hass.loop.call_soon_threadsafe(
            create_task, 
            hass.data[DOMAIN][entry_id].post_request(payloads)
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
            f"{DOMAIN}_{self._hass.data[DOMAIN][MONITOR].device_id}_{LATEST_EVENT}",
            state_attributes,
        )
        if state_attributes['event'] == 'ring':
            async_dispatcher_send(
                self._hass,
                f"{DOMAIN}_{self._hass.data[DOMAIN][MONITOR].device_id}_{RING_STATUS}",
                True,
            )
            sip_from = SIPContact(payloads.get('from'))
            if sip_from.device_id:
                async_dispatcher_send(
                    self._hass,
                    f"{DOMAIN}_{sip_from.device_id}_{RING_STATUS}",
                    True,
                )
        elif state_attributes['event'] == 'reload':
            async_dispatcher_send(
                self._hass,
                f"{DOMAIN}_{self._entry_id}_RELOAD"
            )
