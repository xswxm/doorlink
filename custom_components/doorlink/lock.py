"""Lock for the doorlink integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_call_later

from .const import (
    DOMAIN,
    LOCK_AUTO_RELOCK_DELAY,
    MANUFACTURER,
    SW_VERSION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up one lock per monitor / station."""
    client = hass.data[DOMAIN][entry.entry_id]
    device_id = client.monitor.device_id

    entities = [AccessControlLock(hass, client, device_id, "unlock")]
    for contact in client.stations.contacts.values():
        entities.append(
            AccessControlLock(
                hass, client, contact.device_id, "unlock", sip_info=contact.info
            )
        )

    async_add_entities(entities)


class AccessControlLock(LockEntity):
    """A stateless door opener exposed as a lock."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_is_locked = True

    def __init__(self, hass, client, device_id, translation_key, sip_info=None):
        """Initialize the lock."""
        self.hass = hass
        self._client = client
        self._device_id = device_id
        self._translation_key = translation_key
        self._sip_info = sip_info
        self._unsub_relock = None

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return f"{DOMAIN}_{self._device_id}_{self._translation_key}"

    @property
    def translation_key(self) -> str:
        """Return the translation key."""
        return self._translation_key

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_id,
            manufacturer=MANUFACTURER,
            sw_version=SW_VERSION,
        )

    async def async_added_to_hass(self) -> None:
        """Make sure the re-lock timer is cancelled on unload."""
        self.async_on_remove(self._cancel_relock)

    async def async_lock(self, **kwargs: Any) -> None:
        """The door locks itself, only update the reported state."""
        self._cancel_relock()
        self._attr_is_locked = True
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Open the door and report unlocked for a short while."""
        await self._client.unlock(self._sip_info)

        self._attr_is_locked = False
        self.async_write_ha_state()

        self._cancel_relock()
        self._unsub_relock = async_call_later(
            self.hass, LOCK_AUTO_RELOCK_DELAY, self._auto_relock
        )

    @callback
    def _auto_relock(self, _now=None) -> None:
        """Report the lock as locked again."""
        self._unsub_relock = None
        self._attr_is_locked = True
        self.async_write_ha_state()

    @callback
    def _cancel_relock(self) -> None:
        """Cancel a pending re-lock."""
        if self._unsub_relock is not None:
            self._unsub_relock()
            self._unsub_relock = None
