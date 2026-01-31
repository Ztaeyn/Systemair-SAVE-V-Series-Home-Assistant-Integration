import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_MODEL
from .const import DOMAIN, CONF_SLAVE

# Define the models your integration supports
SUPPORTED_MODELS = [
    "VSR 300",
    "VSR 400",  
    "VSR 500",
    "VTR 300",
    "VTR 500",
#    "VTC 300",
#    "VTC 700",
]

class SaveVSRConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a generic config flow for SaveVSR."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Initial step for the SaveVSR setup."""
        if user_input is not None:
            # title shows up in the 'Integrations' list card
            return self.async_create_entry(
                title=f"Systemair {user_input[CONF_MODEL]}", 
                data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                # Change from a string input to a select list
                vol.Required(CONF_MODEL, default=SUPPORTED_MODELS[0]): vol.In(SUPPORTED_MODELS),
                # This must match the 'name' in configuration.yaml
                vol.Required("hub_name", default="save_hub"): str,
                vol.Required(CONF_SLAVE, default=1): int,
            })
        )