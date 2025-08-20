from homeassistant import config_entries
import voluptuous as vol
from .const import (
    DOMAIN,

    CONF_SERVER_ADDREDD,
)

import logging
_LOGGER = logging.getLogger(__name__)

class DoorlinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Example."""
    VERSION = 1

    def __init__(self):
        """Initialize the flow."""
        self.server_address = ''

    async def create_entry(self):
        return self.async_create_entry(
                        title=self.server_address.split(':')[1][2:].replace('.', '_'),
                        data={
                            CONF_SERVER_ADDREDD: self.server_address,
                        },
                    )

    async def async_step_user(self, user_input=None):
        """Handle the first step (doorlink input)."""
        if user_input is not None:
            # Save user input for next step
            self.server_address = user_input[CONF_SERVER_ADDREDD]

            return await self.create_entry()

        # Display the first form with custom title and description
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERVER_ADDREDD, description="Openwrt Address", default=''): str,
                }
            ),
        )
