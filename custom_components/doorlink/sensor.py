"""Sensors for the doorlink integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import STATE_UNKNOWN, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    LATEST_EVENT,
    MANUFACTURER,
    SOC_TEMP,
    SW_VERSION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Set up the doorlink sensors."""
    client = hass.data[DOMAIN][entry.entry_id]
    device_id = client.monitor.device_id

    entities: list[SensorEntity] = [LatestEvent(hass, device_id, LATEST_EVENT)]
    if client.soc_temp is not None:
        entities.append(SocTemperature(hass, device_id, client))

    async_add_entities(entities)


class LatestEvent(SensorEntity, RestoreEntity):
    """The last event received from the doorlink server."""

    _attr_icon = "mdi:calendar"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, device_id: str, translation_key: str):
        """Initialize the sensor."""
        self.hass = hass
        self._device_id = device_id
        self._sensor_id = translation_key
        self._translation_key = translation_key
        self._state: str = STATE_UNKNOWN
        self._extra_state_attributes: dict | None = None

    @property
    def unique_id(self) -> str:
        """Return the unique id, which is also the dispatcher signal."""
        return f"{DOMAIN}_{self._device_id}_{self._sensor_id}"

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
    def has_entity_name(self) -> bool:
        """Return True because the entity is named after the device."""
        return True

    @property
    def translation_key(self) -> str:
        """Return the translation key."""
        return self._translation_key

    @property
    def native_value(self) -> str:
        """Return the last event."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return the event details."""
        return self._extra_state_attributes

    async def async_added_to_hass(self) -> None:
        """Restore the last event and subscribe to updates."""
        await super().async_added_to_hass()
        old_state = await self.async_get_last_state()
        if old_state:
            self._state = old_state.state
            self._extra_state_attributes = dict(old_state.attributes)

        self.async_on_remove(
            async_dispatcher_connect(self.hass, self.unique_id, self._update_state)
        )

    def _update_state(self, state_attributes: dict) -> None:
        """Handle a new event from the server."""
        self._state = state_attributes.get("event", self._state)
        self._extra_state_attributes = state_attributes
        self.async_write_ha_state()


class SocTemperature(SensorEntity):
    """SOC temperature reported by the doorlink server."""

    _attr_has_entity_name = True
    _attr_translation_key = SOC_TEMP
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, device_id: str, client) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._client = client
        self._device_id = device_id
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{SOC_TEMP}"
        self._attr_native_value = client.soc_temp

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
        """Subscribe to temperature updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._attr_unique_id, self._update_state
            )
        )

    def _update_state(self, value: float) -> None:
        """Handle a new temperature value."""
        self._attr_native_value = value
        self._client.soc_temp = value
        self.async_write_ha_state()
