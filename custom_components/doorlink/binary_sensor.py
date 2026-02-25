from homeassistant.core import HomeAssistant
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_call_later
from .const import (
    DOMAIN, 
    MANUFACTURER, 
    SW_VERSION, 

    RING_STATUS, 
    MONITOR,
    STATIONS, 
)

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    entities = [
        RingingSensor(
            hass=hass, 
            device_id=hass.data[DOMAIN][MONITOR].device_id, 
            translation_key=RING_STATUS
            ),
    ]
    for key, val in hass.data[DOMAIN][STATIONS].contacts.items():
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