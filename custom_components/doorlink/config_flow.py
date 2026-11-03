"""Config flow for the doorlink integration."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv

from .const import CONF_FILEPATH, CONF_SERVER_ADDRESS, DOMAIN, PORT_CONFIG

_LOGGER = logging.getLogger(__name__)

DEFAULT_FILEPATH = "/media/doorlink"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERVER_ADDRESS): cv.string,
        vol.Optional(CONF_FILEPATH, default=DEFAULT_FILEPATH): cv.string,
    }
)


class DoorlinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the doorlink config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Ask for the server address."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_SERVER_ADDRESS].strip()
            parsed = urlparse(address if "//" in address else f"//{address}")
            if not parsed.hostname:
                errors[CONF_SERVER_ADDRESS] = "invalid_server_address"
            else:
                await self.async_set_unique_id(
                    f"{parsed.hostname}:{parsed.port or PORT_CONFIG}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=parsed.hostname.replace(".", "_"),
                    data={
                        CONF_SERVER_ADDRESS: address,
                        CONF_FILEPATH: user_input.get(CONF_FILEPATH)
                        or DEFAULT_FILEPATH,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
