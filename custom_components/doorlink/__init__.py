from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from asyncio import create_task
import json
from datetime import datetime
import threading
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

from .client import Client
from .const import (
    DOMAIN, 
    PLATFORMS, 
    DEVICE_ID, 
    CONF_RING_PORT,

    STATIONS, 
    STATION_LIST,

    SENSOR_LAST_EVENT, 
    SENSOR_RING_STATUS, 
)
from .utils import SIPContact, Stations

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.debug(f'entry.data: {entry.data}')

    hass.data.setdefault(DOMAIN, {})

    # Initialize Client
    client = Client(hass, entry.data)

    # Initialize http server
    server_thread = threading.Thread(
        target=ring_service, 
        kwargs={'hass': hass, 'entry_id': entry.entry_id, 'port': entry.data[CONF_RING_PORT]}
    )
    server_thread.start()

    stations = Stations()
    await stations.load()
    hass.data[DOMAIN][entry.entry_id] = client
    hass.data[DOMAIN][DEVICE_ID] = client.sip_contact.name
    hass.data[DOMAIN][STATIONS] = stations
    hass.data[DOMAIN][STATION_LIST] = list(hass.data[DOMAIN][STATIONS].contacts.keys())

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
    hass.services.async_register(DOMAIN, 'appoint', appoint)

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
    hass.services.async_register(DOMAIN, 'unlock', unlock)

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
    hass.services.async_register(DOMAIN, 'permit', permit)

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
    hass.services.async_register(DOMAIN, 'bye', bye)

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
    hass.services.async_register(DOMAIN, 'execute', execute)

    async def play_on_monitor(call):
        """Handle the service call."""
        target = call.data.get('target')
        file_path = call.data.get('file_path')
        music_length = call.data.get('music_length', 5)
        _LOGGER.debug(f'play_on_monitor request received as {call.data}.')
        try:
            await client.play_on_monitor(target = target, file_path = file_path, music_length = music_length)
            _LOGGER.debug(f'play_on_monitor request executed.')
            hass.bus.fire('doorlink.play_on_monitor', {'status': 'success'})
        except Exception as e:
            _LOGGER.debug(f'play_on_monitor request failed: {e}.')
            hass.bus.fire('doorlink.play_on_monitor', {'status': 'error', 'message': str(e)})
    hass.services.async_register(DOMAIN, 'play_on_monitor', play_on_monitor)

    async def play_on_station(call):
        """Handle the service call."""
        target = call.data.get('target')
        file_path = call.data.get('file_path')
        video_length = call.data.get('video_length', 20)
        diable_gallery = call.data.get('diable_gallery', True)
        _LOGGER.debug(f'play_on_station request received as {call.data}.')
        try:
            await client.play_on_station(target = target, file_path = file_path, video_length = video_length, diable_gallery=diable_gallery)
            _LOGGER.debug(f'play_on_station request executed.')
            hass.bus.fire('doorlink.play_on_station', {'status': 'success'})
        except Exception as e:
            _LOGGER.debug(f'play_on_station request failed: {e}.')
            hass.bus.fire('doorlink.play_on_station', {'status': 'error', 'message': str(e)})
    hass.services.async_register(DOMAIN, 'play_on_station', play_on_station)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data[DOMAIN].pop(entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

class RequestHandler(BaseHTTPRequestHandler):
    def __init__(self, hass, entry_id, *args, **kwargs):
        self._hass = hass
        self._entry_id = entry_id
        super().__init__(*args, **kwargs)

    def _parse_content_type(self, content_type):
        if content_type:
            return content_type.split(';', 1)[0].strip()
        return ''

    def _set_headers(self, status_code=200):
        self.send_response(status_code)
        self.end_headers()

    def handle_post(self, payloads):
        # update saved clients
        sip_contact = SIPContact(payloads['from'])
        
        if sip_contact.name not in self._hass.data[DOMAIN][STATION_LIST]:
            self._hass.data[DOMAIN][STATION_LIST].append(sip_contact.name)
            self._hass.data[DOMAIN][STATIONS].contacts[sip_contact.name] = sip_contact
            self._hass.loop.call_soon_threadsafe(
                create_task, 
                self._hass.data[DOMAIN][STATIONS].save()
                )

        state_attributes = {
            'event': 'ring',
            'from': payloads['from'],
            'to': payloads['to'],
            'tag': payloads.get('tag'),
            'call_id': payloads.get('call_id'),
            'time': datetime.now().isoformat()
        }
        
        # update sensor
        self._hass.loop.call_soon_threadsafe(
            async_dispatcher_send,
            self._hass,
            f"{DOMAIN}_{self._hass.data[DOMAIN][DEVICE_ID]}_{SENSOR_LAST_EVENT}",
            state_attributes
        )

        # update ring status sensor
        self._hass.loop.call_soon_threadsafe(
            async_dispatcher_send,
            self._hass,
            f"{DOMAIN}_{self._hass.data[DOMAIN][DEVICE_ID]}_{SENSOR_RING_STATUS}",
            True
        )

    def do_POST(self):
        try:
            content_type = self._parse_content_type(self.headers.get('Content-Type', ''))
            content_length = int(self.headers.get('Content-Length', 0))
            raw_data = self.rfile.read(content_length).decode('utf-8')
            if content_type == 'application/json':
                payloads = json.loads(raw_data)
                _LOGGER.debug(f"Received JSON data: {payloads}")
            elif content_type == 'application/x-www-form-urlencoded':
                payloads = {k: v[0] for k, v in parse_qs(raw_data, keep_blank_values=True).items()}
                _LOGGER.debug(f"Received form-urlencoded data: {payloads}")
            else:
                _LOGGER.warning(f"Unsupported Content-Type: {content_type}")
                self._set_headers(400)
                return
            self.handle_post(payloads)
            self._set_headers()
        except UnicodeDecodeError as e:
            _LOGGER.debug(f"UnicodeDecodeError: {e}")
            self._set_headers(400)
        except Exception as e:
            _LOGGER.debug(f"Exception: {e}")
            self._set_headers(400)

def ring_service(server_class=HTTPServer, handler_class=RequestHandler, hass=None, entry_id=None, port=30884):
    server_address = ('', port)
    handler = partial(handler_class, hass, entry_id)
    httpd = server_class(server_address, handler)
    _LOGGER.debug(f"Http server running on port {port}")
    httpd.serve_forever()
