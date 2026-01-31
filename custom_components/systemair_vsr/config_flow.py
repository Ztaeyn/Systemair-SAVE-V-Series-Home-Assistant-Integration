import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_MODEL
from .const import DOMAIN, CONF_SLAVE

class SaveVSRConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a generic config flow for SaveVSR."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Step where the user enters the hub details."""
        if user_input is not None:
            # The 'title' is what appears on the Integration card in the UI
            return self.async_create_entry(
                title=f"Systemair {user_input[CONF_MODEL]}", 
                data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                # This is the string the user sees on the device list
                vol.Required(CONF_MODEL, default="VSR300"): str,
                # CRITICAL: This must match the 'name' in configuration.yaml
                vol.Required("hub_name", default="save_hub"): str,
                # Modbus Slave ID (usually 1)
                vol.Required(CONF_SLAVE, default=1): int,
            })
        )