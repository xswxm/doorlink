"""Binary sensors for the doorlink integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.event import async_call_later, async_track_time_interval

from .const import (
    DOMAIN,
    KEEPALIVE_INTERVAL,
    MANUFACTURER,
    RING_RESET_DELAY,
    RING_STATUS,
    SW_VERSION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Set up the ring and online binary sensors."""
    client = hass.data[DOMAIN][entry.entry_id]
    device_id = client.monitor.device_id

    entities: list[BinarySensorEntity] = [
        RingingSensor(hass, device_id, RING_STATUS),
        ServerOnlineSensor(hass, client, device_id, "status"),
    ]
    for contact in client.stations.contacts.values():
        entities.append(RingingSensor(hass, contact.device_id, RING_STATUS))

    async_add_entities(entities)


class RingingSensor(BinarySensorEntity):
    """Indicates that a station is currently calling."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:bell-ring"
    _attr_device_class = BinarySensorDeviceClass.MOTION
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, device_id: str, translation_key: str):
        """Initialize the sensor."""
        self.hass = hass
        self._device_id = device_id
        self._sensor_id = translation_key
        self._translation_key = translation_key
        self._triggered = False
        self._unsub_reset = None

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
    def translation_key(self) -> str:
        """Return the translation key."""
        return self._translation_key

    @property
    def is_on(self) -> bool:
        """Return True while the station is ringing."""
        return self._triggered

    async def async_added_to_hass(self) -> None:
        """Subscribe to ring events."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self.unique_id, self._handle_ring)
        )
        self.async_on_remove(self._cancel_reset)

    @callback
    def _handle_ring(self, state: bool) -> None:
        """Handle a ring event."""
        if not state:
            return
        self._triggered = True
        self.async_write_ha_state()

        self._cancel_reset()
        self._unsub_reset = async_call_later(
            self.hass,
            RING_RESET_DELAY,
            self._reset_state,
        )

    @callback
    def _reset_state(self, _now=None) -> None:
        """Turn the sensor off again."""
        self._unsub_reset = None
        self._triggered = False
        self.async_write_ha_state()

    @callback
    def _cancel_reset(self) -> None:
        """Cancel a pending reset."""
        if self._unsub_reset is not None:
            self._unsub_reset()
            self._unsub_reset = None


class ServerOnlineSensor(BinarySensorEntity):
    """Whether the doorlink server answers on its status endpoint."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, hass, client, device_id: str, translation_key: str):
        """Initialize the sensor."""
        self.hass = hass
        self._client = client
        self._device_id = device_id
        self._sensor_id = translation_key
        self._translation_key = translation_key

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return f"{DOMAIN}_{self._device_id}_{self._sensor_id}"

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

    @property
    def is_on(self) -> bool:
        """Return True when the server is reachable."""
        return self._client.online

    async def async_added_to_hass(self) -> None:
        """Start polling the status endpoint."""
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._update,
                timedelta(seconds=KEEPALIVE_INTERVAL),
            )
        )
        await self._update(None)

    async def _update(self, _now) -> None:
        """Refresh the online state."""
        try:
            await self._client.check_online()
        except Exception:  # noqa: BLE001 - polling must never break the timer
            _LOGGER.exception("Checking the doorlink server status failed")
        self.async_write_ha_state()
