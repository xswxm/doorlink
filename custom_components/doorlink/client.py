from datetime import datetime
import json
import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from urllib.parse import urlparse

from .const import (
    DOMAIN, 
    MONITOR, 
    LATEST_EVENT, 

    CONF_SIP_INFO,
    CONF_STATIONS,
    CONF_ELEV_ID, 
    CONF_STREAM, 
    CONF_SERVER_ADDREDD,
    CONF_FAMILY, 
    CONF_RTSP_URL,
    PORT_CONFIG, 
    PORT_STREAM, 
    STREAM_TYPE_MJPEG,
    STREAM_TYPE_RTSP, 
)
 
import logging
_LOGGER = logging.getLogger(__name__)


class SIPContact:
    def __init__(self, info, rtsp_url = '') -> None:
        self.info = info
        if info:
            name_psk, ip_port = info.split('@')
            self.ip, self.port = ip_port.split(':')
            self.name = name_psk.split(':')[0] if ':' in name_psk else name_psk
            self.device_id = self.ip.replace('.', '_')
        else:
            self.ip = None
            self.port = None
            self.name = None
            self.device_id = ""
        if rtsp_url:
            rtsp_prefix, rstp_suffix = rtsp_url.split('@')
            self.rtsp_username, self.rtsp_password = rtsp_prefix[7:].split(':')
            self.rtsp_url = f'{rtsp_url[:7]}{rstp_suffix}'
        else:
            self.rtsp_username = None
            self.rtsp_password = None
            self.rtsp_url = None
        self.mjpeg_url = None
        self.snapshot_url = None

class Stations:
    def __init__(self, stations = []) -> None:
        self.contacts = {}
        for station in stations:
            contact = SIPContact(station[CONF_SIP_INFO], station[CONF_RTSP_URL])
            self.contacts[contact.ip] = contact

class Client:
    def __init__(self, hass: HomeAssistant, config):
        self.hass = hass
        self.server = urlparse(config[CONF_SERVER_ADDREDD])
        self.server_addr = f'{self.server.scheme}://{self.server.hostname}:{PORT_CONFIG}'
        self.monitor = None
        self.stations = None
        self.elev = None
        self.family = None

    async def initialize(self):
        response_str = await self.get_request('/config')
        try:
            data = json.loads(response_str)
            self.monitor = SIPContact(data[CONF_SIP_INFO])
            self.stations = Stations(data.get(CONF_STATIONS, []))
            self.family = data.get(CONF_FAMILY, 1)
            self.elev = data.get(CONF_ELEV_ID, 0)
            stream_type = data.get(CONF_STREAM, None)
            if stream_type == STREAM_TYPE_MJPEG:
                self.monitor.mjpeg_url = f'{self.server.scheme}://{self.server.hostname}:{PORT_STREAM}'
                self.monitor.snapshot_url = f'{self.server.scheme}://{self.server.hostname}:{PORT_STREAM}/snapshot'
            elif stream_type == STREAM_TYPE_RTSP:
                self.monitor.rtsp_url = f'rtsp://{self.server.hostname}:{PORT_STREAM}'
        except Exception as e:
            _LOGGER.info(f"Failed to initialize: {str(e)}")

    async def get_request(self, path="/"):
        full_url = f"{self.server_addr}{path}"
        _LOGGER.info(f"Aiohttp GET request to {full_url}")
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(full_url) as response:
                    status = response.status
                    response_text = await response.text()
                    
                    _LOGGER.info(f"Aiohttp GET completed with status {status} response {response_text}.")
                    return response_text
            except aiohttp.ClientError as e:
                _LOGGER.warning(f"Aiohttp GET failed: {str(e)}")
                return None

    async def post_request(self, data):
        _LOGGER.info(f"Aiohttp send: {data}")
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(self.server_addr, data=data) as response:
                    status = response.status
                    response_text = await response.text()
                    
                    _LOGGER.info(f"Aiohttp sent with status {status} response {response_text}.")
            except aiohttp.ClientError as e:
                _LOGGER.warning(f"Aiohttp failed: {str(e)}")

    def update_latest_event(self, state_attributes):
        self.hass.loop.call_soon_threadsafe(
            async_dispatcher_send,
            self.hass,
            f"{DOMAIN}_{self.hass.data[DOMAIN][MONITOR].device_id}_{LATEST_EVENT}",
            state_attributes
        )

    async def execute(self, data):
        if isinstance(data, str):
            data = json.loads(data)

        sip_from = data.get('sip_from', self.monitor.info)
        sip_to = data.get('sip_to')
        elev = data.get('elev', 0)
        direct = data.get('direct', 1)
        family = data.get('family', self.family)
        tag = data.get('tag')
        call_id = data.get('call_id')

        if data['event'] == 'appoint':
            await self.appoint_advanced(sip_from=sip_from, sip_to=sip_to, elev=elev, direct=direct, family=family)
        elif data['event'] == 'unlock':
            await self.unlock_advanced(sip_from=sip_from, sip_to=sip_to, family=family)
        elif data['event'] == 'permit':
            await self.permit_advanced(sip_from=sip_from, sip_to=sip_to, elev=elev, family=family)
        elif data['event'] == 'bye':
            await self.bye_advanced(sip_from=sip_from, sip_to=sip_to, tag=tag, call_id=call_id)

    async def appoint_advanced(self, sip_from, sip_to, elev, direct, family):
        # join
        # data = {
        #     "from": sip_from if sip_from else self.monitor.info,
        #     "to": sip_to,
        #     "event": 'join',
        #     "family": '1',
        #     "elev": 0,
        #     "direct": '1',
        # }
        # await self.post_request(data=data)

        # appoint
        data = {
            "from": sip_from if sip_from else self.monitor.info,
            "to": sip_to if sip_to else '',
            "event": 'appoint',
            "family": family,
            "elev": elev,
            "direct": direct,
        }
        await self.post_request(data=data)

        # update sensor
        state_attributes = {
            'event': 'appoint',
            'from': sip_from,
            'to': sip_to,
            'direct': direct, 
            'time': datetime.now().isoformat()
        }
        self.update_latest_event(state_attributes)

    async def appoint(self, sip_to, direct):
        await self.appoint_advanced(
            sip_from=self.monitor.info, 
            sip_to=sip_to, 
            elev=self.elev, 
            direct=direct, 
            family=self.family
        )

    async def unlock_advanced(self, sip_from, sip_to, family = 1):
        data = {
            "from": sip_from if sip_from else self.monitor.info,
            "to": sip_to if sip_to else '',
            "event": 'unlock',
            "family": family,
            "elev": 0,
            "direct": '1',
        }
        await self.post_request(data=data)

        # update sensor
        state_attributes = {
            'event': 'unlock',
            'from': sip_from,
            'to': sip_to,
            'time': datetime.now().isoformat()
        }
        self.update_latest_event(state_attributes)

    async def unlock(self, sip_to):
        await self.unlock_advanced(
            sip_from=self.monitor.info,
            sip_to=sip_to,
            family=self.family
        )

    async def permit_advanced(self, sip_from, sip_to, elev, family = 1):
        data = {
            "from": sip_from if sip_from else self.monitor.info,
            "to": sip_to if sip_to else '',
            "event": 'permit',
            "family": family,
            "elev": elev,
            "direct": '1',
        }
        await self.post_request(data=data)

        # update sensor
        state_attributes = {
            'event': 'permit',
            'from': sip_from,
            'to': sip_to,
            'time': datetime.now().isoformat()
        }
        self.update_latest_event(state_attributes)

    async def permit(self, sip_to):
        await self.permit_advanced(
            sip_from=self.monitor.info, 
            sip_to=sip_to,  
            elev=self.elev, 
            family = self.family
        )

    async def bye_advanced(self, sip_from, sip_to, tag=None, call_id=None):
        data = {
            "from": sip_from if sip_from else '',
            "to": sip_to if sip_to else self.monitor.info,
            "event": 'bye',
            "family": 1,
            "elev": 0,
            "direct": '1',
            "tag": tag,
            "call_id": call_id
        }
        await self.post_request(data=data)

        # update sensor
        state_attributes = {
            'event': 'bye',
            'from': sip_from,
            'to': sip_to,
            'time': datetime.now().isoformat()
        }
        self.update_latest_event(state_attributes)

    async def bye(self, sip_from):
        await self.bye_advanced(
            sip_from=sip_from, 
            sip_to=self.monitor.info
        )
