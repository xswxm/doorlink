from __future__ import annotations
from typing import Any

from homeassistant.components.button import ButtonEntity

from .const import (
    DOMAIN, 
    MANUFACTURER, 
    SW_VERSION, 

    STATIONS, 
    DEVICE_ID
)

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    entities = [
        AccessControl(hass=hass, client=hass.data[DOMAIN][entry.entry_id], device_id = hass.data[DOMAIN][DEVICE_ID], translation_key = 'unlock'),
        AccessControl(hass=hass, client=hass.data[DOMAIN][entry.entry_id], device_id = hass.data[DOMAIN][DEVICE_ID], translation_key = 'bye'),
        AccessControl(hass=hass, client=hass.data[DOMAIN][entry.entry_id], device_id = hass.data[DOMAIN][DEVICE_ID], translation_key = 'elev_permit'),
        AccessControl(hass=hass, client=hass.data[DOMAIN][entry.entry_id], device_id = hass.data[DOMAIN][DEVICE_ID], translation_key = 'elev_up'),
        AccessControl(hass=hass, client=hass.data[DOMAIN][entry.entry_id], device_id = hass.data[DOMAIN][DEVICE_ID], translation_key = 'elev_down'),
    ]
    
    for key, val in hass.data[DOMAIN][STATIONS].contacts.items():
        entities.append(
                AccessControl(
                    hass=hass, 
                    client=hass.data[DOMAIN][entry.entry_id], 
                    device_id = f'{hass.data[DOMAIN][DEVICE_ID]}_{val.ip}', 
                    translation_key = 'unlock', 
                    sip_info=val.info
                )
        )
        entities.append(
                AccessControl(
                    hass=hass, 
                    client=hass.data[DOMAIN][entry.entry_id], 
                    device_id = f'{hass.data[DOMAIN][DEVICE_ID]}_{val.ip}', 
                    translation_key = 'bye', 
                    sip_info=val.info
                )
        )

    async_add_entities(entities)

class AccessControl(ButtonEntity):
    def __init__(self, hass, client, device_id, translation_key, sip_info=None):
        self._hass = hass
        self._client = client
        self._device_id = device_id
        self._translation_key = translation_key
        self._sip_info = sip_info

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_id,
            "manufacturer": MANUFACTURER,
            "sw_version": SW_VERSION
        }

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self._device_id}_{self._translation_key}"

    @property
    def has_entity_name(self) -> bool:
        return True

    @property
    def translation_key(self) -> str:
        return self._translation_key

    @property
    def available(self) -> bool:
        return True
        
    async def async_press(self) -> None:
        try:
            if self._translation_key == 'unlock':
                await self._client.unlock(self._sip_info)
            elif self._translation_key == 'bye':
                await self._client.bye(self._sip_info)
            elif self._translation_key == 'elev_permit':
                await self._client.permit(self._sip_info)
            elif self._translation_key == 'elev_up':
                await self._client.appoint(self._sip_info, 1)
            elif self._translation_key == 'elev_down':
                await self._client.appoint(self._sip_info, 2)
        except Exception as e:
            raise Exception(e)
