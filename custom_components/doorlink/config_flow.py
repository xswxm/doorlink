from homeassistant import config_entries
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from .const import (
    DOMAIN,
    CONF_SERVER_ADDRESS,
    CONF_FILEPATH, 
)

import logging
_LOGGER = logging.getLogger(__name__)

class DoorlinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self.server_address = ''
        self.filepath = ''

    async def create_entry(self):
        return self.async_create_entry(
                        title=self.server_address.split(':')[1][2:].replace('.', '_'),
                        data={
                            CONF_SERVER_ADDRESS: self.server_address,
                            CONF_FILEPATH: self.filepath,
                        },
                    )

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self.server_address = user_input[CONF_SERVER_ADDRESS]
            self.filepath = user_input[CONF_FILEPATH]

            return await self.create_entry()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERVER_ADDRESS, default=''): cv.string,
                    vol.Optional(CONF_FILEPATH, default="/media/doorlink"): cv.string,
                }
            ),
        )
