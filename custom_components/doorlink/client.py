from datetime import datetime
import json
import socket
import random
import aiohttp
import asyncio

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DOMAIN, 
    DEVICE_ID, 
    SENSOR_LAST_EVENT, 
    SENSOR_RING_STATUS, 

    CONF_SIP_INFO,
    CONF_STATIONS,
    CONF_ELEV_ID, 
    CONF_SERVER_ADDREDD,
    CONF_FAMILY, 
    CONF_RTSP_URL,
)
 
import logging
_LOGGER = logging.getLogger(__name__)

class SIPContact:
    def __init__(self, info, rtsp_url = '') -> None:
        self.info = info
        name_psk, ip_port = info.split('@')
        self.ip, self.port = ip_port.split(':')
        self.name = name_psk.split(':')[0] if ':' in name_psk else name_psk
        if rtsp_url:
            rtsp_prefix, rstp_suffix = rtsp_url.split('@')
            self.rtsp_username, self.rtsp_passwod = rtsp_prefix[7:].split(':')
            self.rtsp_url = f'{rtsp_url[:7]}{rstp_suffix}'
        else:
            self.rtsp_username = None
            self.rtsp_passwod = None
            self.rtsp_url = None

class Stations:
    def __init__(self, stations = []) -> None:
        self.contacts = {}
        for station in stations:
            contact = SIPContact(station[CONF_SIP_INFO], station[CONF_RTSP_URL])
            self.contacts[f'{contact.name}@{contact.ip}'] = contact

class Client:
    def __init__(self, hass: HomeAssistant, config):
        # super().__init__(hass, config)
        self.hass = hass
        self.server_address = config[CONF_SERVER_ADDREDD][:-1] if config[CONF_SERVER_ADDREDD][-1] == '/' else config[CONF_SERVER_ADDREDD]
        self.sip_contact = None
        self.elev = None
        self.family = None
        self.stations = None

    async def initialize(self):
        response_str = await self.get_request('/config')
        try:
            data = json.loads(response_str)
            self.sip_contact = SIPContact(data[CONF_SIP_INFO])
            self.family = data.get(CONF_FAMILY, 1)
            self.elev = data.get(CONF_ELEV_ID, 0)
            self.stations = Stations(data.get(CONF_STATIONS, []))
        except Exception as e:
            _LOGGER.info(f"Failed to initialize: {str(e)}")

    async def get_request(self, api_path="/"):
        full_url = f"{self.server_address}{api_path}"
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
                async with session.post(self.server_address, data=data) as response:
                    status = response.status
                    response_text = await response.text()
                    
                    _LOGGER.info(f"Aiohttp sent with status {status} response {response_text}.")
            except aiohttp.ClientError as e:
                _LOGGER.warning(f"Aiohttp failed: {str(e)}")

    def update_last_event(self, state_attributes):
        self.hass.loop.call_soon_threadsafe(
            async_dispatcher_send,
            self.hass,
            f"{DOMAIN}_{self.hass.data[DOMAIN][DEVICE_ID]}_{SENSOR_LAST_EVENT}",
            state_attributes
        )
        if state_attributes['event'] == 'ring':
            self.hass.loop.call_soon_threadsafe(
                async_dispatcher_send,
                self.hass,
                f"{DOMAIN}_{self.hass.data[DOMAIN][DEVICE_ID]}_{SENSOR_RING_STATUS}",
                True
            )

    async def execute(self, data):
        if isinstance(data, str):
            data = json.loads(data)

        sip_from = data.get('sip_from', self.sip_contact.info)
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
        #     "from": sip_from if sip_from else self.sip_contact.info,
        #     "to": sip_to,
        #     "event": 'join',
        #     "family": '1',
        #     "elev": 0,
        #     "direct": '1',
        # }
        # await self.post_request(data=data)

        # appoint
        data = {
            "from": sip_from if sip_from else self.sip_contact.info,
            "to": sip_to,
            "event": 'appoint',
            "family": family,
            "elev": elev,
            "direct": direct,
        }
        await self.post_request(data=data)

        # update sensor
        state_attributes = {
            'event': 'elev_up' if direct == 1 else 'elev_down',
            'from': sip_from,
            'to': sip_to,
            'time': datetime.now().isoformat()
        }
        self.update_last_event(state_attributes)

    async def appoint(self, sip_to, direct):
        await self.appoint_advanced(
            sip_from=self.sip_contact.info, 
            sip_to=sip_to, 
            elev=self.elev, 
            direct=direct, 
            family=self.family
        )

    async def unlock_advanced(self, sip_from, sip_to, family = 1):
        data = {
            "from": sip_from if sip_from else self.sip_contact.info,
            "to": sip_to,
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
        self.update_last_event(state_attributes)

    async def unlock(self, sip_to):
        await self.unlock_advanced(
            sip_from=self.sip_contact.info,
            sip_to=sip_to,
            family=self.family
        )

    async def permit_advanced(self, sip_from, sip_to, elev, family = 1):
        data = {
            "from": sip_from if sip_from else self.sip_contact.info,
            "to": sip_to,
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
        self.update_last_event(state_attributes)

    async def permit(self, sip_to):
        await self.permit_advanced(
            sip_from=self.sip_contact.info, 
            sip_to=sip_to,  
            elev=self.elev, 
            family = self.family
        )

    async def bye_advanced(self, sip_from, sip_to, tag, call_id):
        data = {
            "from": sip_from,
            "to": sip_to if sip_to else self.sip_contact.info,
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
            'tag': tag,
            'call_id': call_id,
            'time': datetime.now().isoformat()
        }
        self.update_last_event(state_attributes)

    async def bye(self, sip_from, tag, call_id):
        await self.bye_advanced(
            sip_from=sip_from, 
            sip_to=self.sip_contact.info,  
            tag = tag, 
            call_id = call_id
        )
