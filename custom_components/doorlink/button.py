"""Buttons for the doorlink integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    DIRECT_DOWN,
    DIRECT_UP,
    DOMAIN,
    MANUFACTURER,
    SW_VERSION,
)

_LOGGER = logging.getLogger(__name__)

# translation_key -> (client method, extra kwargs)
BUTTON_ACTIONS: dict[str, tuple[str, dict[str, Any]]] = {
    "bye": ("bye", {}),
    "elev_permit": ("permit", {}),
    "elev_up": ("appoint", {"direct": DIRECT_UP}),
    "elev_down": ("appoint", {"direct": DIRECT_DOWN}),
}


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the doorlink buttons."""
    client = hass.data[DOMAIN][entry.entry_id]
    device_id = client.monitor.device_id

    entities = [
        AccessControl(hass, client, device_id, translation_key)
        for translation_key in BUTTON_ACTIONS
    ]
    for contact in client.stations.contacts.values():
        entities.append(
            AccessControl(hass, client, contact.device_id, "bye", sip_info=contact.info)
        )

    async_add_entities(entities)


class AccessControl(ButtonEntity):
    """A button that sends a SIP command to the server."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hass, client, device_id, translation_key, sip_info=None):
        """Initialize the button."""
        self.hass = hass
        self._client = client
        self._device_id = device_id
        self._translation_key = translation_key
        self._sip_info = sip_info

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_id,
            manufacturer=MANUFACTURER,
            sw_version=SW_VERSION,
        )

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return f"{DOMAIN}_{self._device_id}_{self._translation_key}"

    @property
    def translation_key(self) -> str:
        """Return the translation key."""
        return self._translation_key

    async def async_press(self) -> None:
        """Send the command; failures surface as HomeAssistantError."""
        method_name, kwargs = BUTTON_ACTIONS[self._translation_key]
        await getattr(self._client, method_name)(sip_to=self._sip_info, **kwargs)
