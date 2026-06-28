from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from datetime import timedelta

from .const import (
    DOMAIN, 
    MANUFACTURER, 
    SW_VERSION, 
    RING_STATUS, 
    KEEPALIVE_INTERVAL, 
)

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    client = hass.data[DOMAIN][entry.entry_id]
    entities = [
        RingingSensor(
            hass=hass, 
            device_id=client.monitor.device_id, 
            translation_key=RING_STATUS
            ),
        ServerOnlineSensor(
            hass=hass,
            client=client,
            device_id=client.monitor.device_id, 
            translation_key='status'
        ),
    ]
    for key, val in client.stations.contacts.items():
        entities.append(
            RingingSensor(
                hass=hass, 
                device_id=val.device_id, 
                translation_key=RING_STATUS
            )
        )

    async_add_entities(entities)

class RingingSensor(BinarySensorEntity):
    def __init__(self, hass: HomeAssistant, device_id: str, translation_key: str):
        self.hass = hass
        self._device_id = device_id
        self._sensor_id = translation_key
        self._translation_key = translation_key
        self._triggered = False

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self._device_id}_{self._sensor_id}"

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_id,
            "manufacturer": MANUFACTURER,
            "sw_version": SW_VERSION,
        }

    @property
    def has_entity_name(self) -> bool:
        return True

    @property
    def translation_key(self) -> str:
        return self._translation_key

    @property
    def icon(self) -> str:
        return "mdi:bell-ring"

    @property
    def device_class(self):
        return BinarySensorDeviceClass.MOTION

    @property
    def is_on(self) -> bool:
        return self._triggered

    async def async_added_to_hass(self):
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.unique_id, self._handle_state_update
            )
        )

    async def _handle_state_update(self, state: bool):
        if state:
            await self.trigger()

    async def trigger(self):
        self._triggered = True
        self.schedule_update_ha_state()
        async_call_later(
            self.hass,
            1,
            self._reset_state_callback
        )

    async def _reset_state_callback(self, _now):
        self._reset_state()

    def _reset_state(self):
        self._triggered = False
        self.schedule_update_ha_state()

class ServerOnlineSensor(BinarySensorEntity):
    def __init__(self, hass, client, device_id: str, translation_key: str):
        self.hass = hass
        self._client = client
        self._device_id = device_id
        self._sensor_id = translation_key
        self._translation_key = translation_key

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self._device_id}_{self._sensor_id}"

    @property
    def translation_key(self) -> str:
        return self._translation_key

    @property
    def has_entity_name(self):
        return True

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_id,
            "manufacturer": MANUFACTURER,
            "sw_version": SW_VERSION,
        }

    @property
    def device_class(self):
        return BinarySensorDeviceClass.CONNECTIVITY

    @property
    def entity_category(self) -> EntityCategory:
        return EntityCategory.DIAGNOSTIC

    @property
    def is_on(self):
        return self._client.online

    async def async_added_to_hass(self):
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._update,
                timedelta(seconds=KEEPALIVE_INTERVAL),
            )
        )
        await self._update(None)

    async def _update(self, _):
        await self._client.check_online()
        self.async_write_ha_state()