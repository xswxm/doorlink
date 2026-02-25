from __future__ import annotations
from typing import Any

from homeassistant.components.button import ButtonEntity

from .const import (
    DOMAIN, 
    MANUFACTURER, 
    SW_VERSION, 

    MONITOR, 
    STATIONS,
    UNLOCK,
    BYE,
    ELEV_PERMIT,
    ELEV_UP,
    ELEV_DOWN
)

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    entities = [
        AccessControl(hass=hass, client=hass.data[DOMAIN][entry.entry_id], device_id = hass.data[DOMAIN][MONITOR].device_id, translation_key = UNLOCK),
        AccessControl(hass=hass, client=hass.data[DOMAIN][entry.entry_id], device_id = hass.data[DOMAIN][MONITOR].device_id, translation_key = BYE),
        AccessControl(hass=hass, client=hass.data[DOMAIN][entry.entry_id], device_id = hass.data[DOMAIN][MONITOR].device_id, translation_key = ELEV_PERMIT),
        AccessControl(hass=hass, client=hass.data[DOMAIN][entry.entry_id], device_id = hass.data[DOMAIN][MONITOR].device_id, translation_key = ELEV_UP),
        AccessControl(hass=hass, client=hass.data[DOMAIN][entry.entry_id], device_id = hass.data[DOMAIN][MONITOR].device_id, translation_key = ELEV_DOWN),
    ]
    
    for key, val in hass.data[DOMAIN][STATIONS].contacts.items():
        entities.append(
                AccessControl(
                    hass=hass, 
                    client=hass.data[DOMAIN][entry.entry_id], 
                    device_id = val.device_id,
                    translation_key = UNLOCK, 
                    sip_info=val.info
                )
        )
        entities.append(
                AccessControl(
                    hass=hass, 
                    client=hass.data[DOMAIN][entry.entry_id], 
                    device_id = val.device_id, 
                    translation_key = BYE, 
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
            if self._translation_key == UNLOCK:
                await self._client.unlock(self._sip_info)
            elif self._translation_key == BYE:
                await self._client.bye(self._sip_info)
            elif self._translation_key == ELEV_PERMIT:
                await self._client.permit(self._sip_info)
            elif self._translation_key == ELEV_UP:
                await self._client.appoint(self._sip_info, 1)
            elif self._translation_key == ELEV_DOWN:
                await self._client.appoint(self._sip_info, 2)
        except Exception as e:
            raise Exception(e)
