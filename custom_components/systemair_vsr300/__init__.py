import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

#separated into folders
PLATFORMS = [
    "climate",
    "sensor",
    "binary_sensor",
    "button",
    "number",
    "switch",
    "select"
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Store data and load platforms."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the integration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)