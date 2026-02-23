from homeassistant import config_entries
import voluptuous as vol
from .const import (
    DOMAIN,

    CONF_SERVER_ADDREDD,
)

import logging
_LOGGER = logging.getLogger(__name__)

class DoorlinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self.server_address = ''

    async def create_entry(self):
        return self.async_create_entry(
                        title=self.server_address.split(':')[1][2:].replace('.', '_'),
                        data={
                            CONF_SERVER_ADDREDD: self.server_address,
                        },
                    )

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self.server_address = user_input[CONF_SERVER_ADDREDD]

            return await self.create_entry()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERVER_ADDREDD, description="Openwrt Address", default=''): str,
                }
            ),
        )
