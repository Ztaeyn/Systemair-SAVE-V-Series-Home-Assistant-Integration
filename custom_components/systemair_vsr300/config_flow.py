import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME
import homeassistant.helpers.config_validation as cv
from .const import DOMAIN

class SystemairVSR300ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME, default="Systemair VSR300"): str,
                vol.Required(CONF_HOST, default="192.168.10.101"): str,
                vol.Required(CONF_PORT, default=8432): int,
                vol.Required("slave", default=1): int,
            })
        )