from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol
import json
from .const import (
    DOMAIN,

    CONF_SIP_INFO,
    CONF_ELEV_ID,
    CONF_FAMILY, 
    CONF_OPENWRT_ADDREDD,
    CONF_RING_PORT,
    CONF_STATIONS,
    CONF_LIVE_SUPPORT,

    DEFAULT_FAMILY,
    DEFAULT_ELEV_ID, 
    DEFAULT_RING_PORT,
)
from .utils import Stations

import logging
_LOGGER = logging.getLogger(__name__)

class DoorlinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Example."""
    VERSION = 1

    def __init__(self):
        """Initialize the flow."""

        self.sip_info = None
        self.family = DEFAULT_FAMILY
        self.elev_id = DEFAULT_ELEV_ID
        self.openwrt_address = ''
        self.ring_port = DEFAULT_RING_PORT
        self.stations = Stations()
        self.live_support = False

    async def create_entry(self):
        # await save_json(self.stations, STATION_FILENAME)
        await self.stations.save()
        return self.async_create_entry(
                        title=self.sip_info.split('@')[0],
                        data={
                            CONF_SIP_INFO: self.sip_info,
                            CONF_FAMILY: self.family,
                            CONF_ELEV_ID: self.elev_id,
                            CONF_OPENWRT_ADDREDD: self.openwrt_address,
                            CONF_RING_PORT: self.ring_port,
                            CONF_LIVE_SUPPORT: self.live_support,
                        },
                    )

    async def async_step_user(self, user_input=None):
        """Handle the first step (doorlink input)."""
        if user_input is not None:
            # Save user input for next step
            self.sip_info = user_input.get(CONF_SIP_INFO, '')
            self.family = user_input.get(CONF_FAMILY, DEFAULT_FAMILY)
            self.elev_id = user_input.get(CONF_ELEV_ID, DEFAULT_ELEV_ID)
            self.openwrt_address = user_input[CONF_OPENWRT_ADDREDD]
            self.ring_port = user_input[CONF_RING_PORT]
            self.live_support = user_input[CONF_LIVE_SUPPORT]
            
            try:
                stations = user_input.get(CONF_STATIONS, '{}')
                if stations:
                    # self.stations = json.loads(stations)
                    self.stations.load_from_string(stations)
                    _LOGGER.debug("devices parsed.")
            except Exception as e:
                return self.async_abort(reason=f'devices parse failed: {e}')

            return await self.create_entry()

        await self.stations.load()
        # Display the first form with custom title and description
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SIP_INFO, description="SIP CONTACT"): str,
                    vol.Required(CONF_FAMILY, description="Family ID", default=DEFAULT_FAMILY): int,
                    vol.Required(CONF_ELEV_ID, description="Elev ID", default=DEFAULT_ELEV_ID): int,
                    vol.Optional(CONF_OPENWRT_ADDREDD, description="Openwrt Address", default=''): str,
                    vol.Required(CONF_RING_PORT, description="Ring listening port", default=DEFAULT_RING_PORT): int,
                    vol.Required(CONF_LIVE_SUPPORT, description="Live Support", default=True): bool,
                    vol.Optional(CONF_STATIONS, description="Outdoor Stations", default=self.stations.to_string()): str,
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return DoorlinkOptionsFlow(config_entry)

class DoorlinkOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def get_dynamic_schema(self):
        stations = Stations()
        await stations.load()
        # options = self.config_entry.options
        # data = self.config_entry.data
        schema_dict = {
            # vol.Optional(CONF_IP_ADDRESS, description="Monitor IP address", default=options.get(CONF_IP_ADDRESS, data.get(CONF_IP_ADDRESS))): str,
            # vol.Optional(CONF_FAMILY, description="Family ID", default=options.get(CONF_FAMILY, data.get(CONF_FAMILY))): int,
            # vol.Optional(CONF_ELEV_ID, description="Elev ID", default=options.get(CONF_ELEV_ID, data.get(CONF_ELEV_ID))): int,
            # vol.Required(CONF_RING_PORT, description="Ring listening port", default=options.get(CONF_RING_PORT, data.get(CONF_RING_PORT))): int,
            vol.Optional(CONF_STATIONS, description="Outdoor Stations", default=stations.to_string()): str,
        }

        return vol.Schema(schema_dict)

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            stations = Stations()
            stations.load_from_string(user_input[CONF_STATIONS])
            await stations.save()
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema= await self.get_dynamic_schema(),
        )
