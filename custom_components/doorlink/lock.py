from __future__ import annotations
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    DOMAIN, 
    MANUFACTURER, 
    SW_VERSION, 
)

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    client = hass.data[DOMAIN][entry.entry_id]
    entities = [
        AccessControlLock(hass=hass, client=client, device_id = client.monitor.device_id, translation_key = 'unlock'),
    ]
    
    for key, val in client.stations.contacts.items():
        entities.append(
                AccessControlLock(
                    hass=hass, 
                    client=client, 
                    device_id = val.device_id,
                    translation_key = 'unlock', 
                    sip_info=val.info
                )
        )

    async_add_entities(entities)

class AccessControlLock(LockEntity):
    def __init__(self, hass, client, device_id, translation_key, sip_info=None):
        self.hass = hass
        self._client = client
        self._device_id = device_id
        self._translation_key = translation_key
        self._sip_info = sip_info
        self._is_locked = True
        self._attr_should_poll = False

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

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_id,
            "manufacturer": MANUFACTURER,
            "sw_version": SW_VERSION,
        }

    @property
    def is_locked(self) -> bool:
        return self._is_locked

    async def async_lock(self, **kwargs: Any) -> None:
        self._is_locked = True
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs: Any) -> None:
        await self._client.unlock(self._sip_info)

        self._is_locked = False
        self.async_write_ha_state()

        async_call_later(self.hass, 2, self._auto_lock)

    async def _auto_lock(self, _):
        self._is_locked = True
        self.async_write_ha_state()