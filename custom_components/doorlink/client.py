from datetime import datetime
import json
import socket
import random
import aiohttp
import asyncio

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .utils import SIPContact
from .const import (
    DOMAIN, 
    DEVICE_ID, 
    SENSOR_LAST_EVENT, 
    SENSOR_RING_STATUS, 

    CONF_SIP_INFO,
    CONF_ELEV_ID, 
    CONF_OPENWRT_ADDREDD,
    CONF_FAMILY, 
)
 
import logging
_LOGGER = logging.getLogger(__name__)

class DnakeUDPClient:
    def __init__(self, sip_contact, openwrt_address = None) -> None:
        self.sip_contact = sip_contact
        self.openwrt_address = openwrt_address

    async def post_request(self, data):
        _LOGGER.info(f"Aiohttp send: {data}")
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(self.openwrt_address, data=data) as response:
                    status = response.status
                    response_text = await response.text()
                    
                    _LOGGER.info(f"Aiohttp sent with status {status} response {response_text}.")
            except aiohttp.ClientError as e:
                _LOGGER.warning(f"Aiohttp failed: {str(e)}")

    async def join(self, sip_from, sip_to):
        data = {
            "from": sip_from if sip_from else self.sip_contact.info,
            "to": sip_to,
            "event": 'join',
            "family": '1',
            "elev": 0,
            "direct": '1',
        }
        await self.post_request(data=data)

    async def appoint(self, sip_from, sip_to, elev, direct, family = 1):
        data = {
            "from": sip_from if sip_from else self.sip_contact.info,
            "to": sip_to,
            "event": 'appoint',
            "family": family,
            "elev": elev,
            "direct": direct,
        }
        await self.post_request(data=data)

    async def unlock(self, sip_from, sip_to, family = 1):
        data = {
            "from": sip_from if sip_from else self.sip_contact.info,
            "to": sip_to,
            "event": 'unlock',
            "family": family,
            "elev": 0,
            "direct": '1',
        }
        await self.post_request(data=data)

    async def permit(self, sip_from, sip_to, elev, family = 1):
        data = {
            "from": sip_from if sip_from else self.sip_contact.info,
            "to": sip_to,
            "event": 'permit',
            "family": family,
            "elev": elev,
            "direct": '1',
        }
        await self.post_request(data=data)

    async def bye(self, sip_from, sip_to, tag, call_id):
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

class Client:
    def __init__(self, hass: HomeAssistant, config):
        # super().__init__(hass, config)
        self.hass = hass
        self.sip_contact = SIPContact(config[CONF_SIP_INFO])
        self.elev = config[CONF_ELEV_ID]
        self.family = config[CONF_FAMILY]
        self.openwrt_address = config[CONF_OPENWRT_ADDREDD]
        self.client = DnakeUDPClient(
            sip_contact=self.sip_contact,
            openwrt_address=self.openwrt_address
        )

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
        await self.client.join(
            sip_from=sip_from, 
            sip_to=sip_to
        )
        # appoint
        await self.client.appoint(
            sip_from=sip_from, 
            sip_to=sip_to, 
            elev=elev, 
            direct=direct, 
            family = family
        )
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
            family = self.family
        )

    async def unlock_advanced(self, sip_from, sip_to, family):
        await self.client.unlock(
            sip_from=sip_from,
            sip_to=sip_to,
            family=family
        )
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

    async def permit_advanced(self, sip_from, sip_to, elev, family):
        await self.client.permit(
            sip_from=sip_from, 
            sip_to=sip_to, 
            elev=elev, 
            family=family
        )
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
        await self.client.bye(
            sip_from=sip_from, 
            sip_to=sip_to, 
            tag=tag, 
            call_id=call_id
        )
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
