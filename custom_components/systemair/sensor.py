import asyncio
import logging
from homeassistant.components.sensor import (
    SensorEntity, 
    SensorDeviceClass, 
    SensorStateClass
)
from homeassistant.const import (
    UnitOfTemperature, 
    UnitOfPower,
    CONF_MODEL
)
from homeassistant.components.modbus.const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT
)
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

SYSTEMAIR_SENSORS = [
    # --- Temperatures ---
    ("outdoor_temp", 12101, SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, 0.1, "mdi:home-thermometer", SensorStateClass.MEASUREMENT),
    ("supply_temp", 12102, SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, 0.1, "mdi:home-thermometer", SensorStateClass.MEASUREMENT),
    ("extract_temp", 12105, SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, 0.1, "mdi:home-thermometer", SensorStateClass.MEASUREMENT),
    ("eff_temp", 12106, SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, 0.1, "mdi:home-thermometer", SensorStateClass.MEASUREMENT),
    ("overheat_temp", 12107, SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, 0.1, "mdi:home-thermometer", SensorStateClass.MEASUREMENT),      
    ("exhaust_temp", 12543, SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, 0.1, "mdi:home-thermometer", SensorStateClass.MEASUREMENT),

    # --- Moisture/Humidity ---
    ("rel_moisture", 12135, SensorDeviceClass.HUMIDITY, "%", 1.0, "mdi:water-percent", SensorStateClass.MEASUREMENT),
    ("calc_moisture_extract", 2210, SensorDeviceClass.HUMIDITY, "%", 1.0, "mdi:water-plus", SensorStateClass.MEASUREMENT),
    ("calc_moisture_intake", 2211, SensorDeviceClass.HUMIDITY, "%", 1.0, "mdi:water-minus", SensorStateClass.MEASUREMENT),

    # --- Fans & Airflow ---
    ("sf_rpm", 12400, None, "o/min", 1.0, "mdi:speedometer", SensorStateClass.MEASUREMENT),
    ("ef_rpm", 12401, None, "o/min", 1.0, "mdi:speedometer", SensorStateClass.MEASUREMENT),
    ("sf_speed_pct", 14000, None, "%", 1.0, "mdi:fan", SensorStateClass.MEASUREMENT),
    ("ef_speed_pct", 14001, None, "%", 1.0, "mdi:fan", SensorStateClass.MEASUREMENT),
    ("sf_flow_rate", 14000, None, "m³/t", 3.0, "mdi:home-switch", SensorStateClass.MEASUREMENT),
    ("ef_flow_rate", 14001, None, "m³/t", 3.0, "mdi:home-switch", SensorStateClass.MEASUREMENT),

    # --- System Status & Energy ---
    ("fan_mode", 1160, None, None, 1.0, "mdi:air-conditioner", None),
    ("mode_time_rem", 1111, None, "min", 1.0, "mdi:timer-sand", None), 
    ("summer_winter", 1038, None, None, 1, "mdi:sun-snowflake-variant", None),
    ("heat_recovery_efficiency", 14102, SensorDeviceClass.POWER_FACTOR, "%", 1.0, "mdi:sync", SensorStateClass.MEASUREMENT),
    ("heater_pct", 2148, None, "%", 1.0, "mdi:heating-coil", SensorStateClass.MEASUREMENT),
    ("heater_watts", 2148, SensorDeviceClass.POWER, UnitOfPower.WATT, 16.7, "mdi:lightning-bolt", SensorStateClass.MEASUREMENT),
    
    # --- Filter & Maintenance ---
    ("filter_time_rem", 7005, None, "days", 1.0, "mdi:clock-end", SensorStateClass.MEASUREMENT),
    ("filter_alarm_code", 15141, None, None, 1.0, "mdi:alert-circle", None),
    ("manual_fan_reg", 1130, None, None, 1.0, "mdi:cog-clockwise", None),
]

async def async_setup_entry(hass, entry, async_add_entities):
    config = entry.data
    from homeassistant.components.modbus import get_hub
    hub = get_hub(hass, config.get("hub_name", "modbus_hub"))
    
    if hub is None:
        _LOGGER.error("Systemair: Modbus hub not found for sensors")
        return

    model = config.get(CONF_MODEL, "SAVE")
    slave = config.get(CONF_SLAVE, 1)
    entities = [SystemairSensor(hub, model, slave, *s) for s in SYSTEMAIR_SENSORS]
    async_add_entities(entities, True)

class SystemairSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, hub, model, slave, translation_key, register, device_class, unit, scale, icon, state_class=None):
        self._hub = hub
        self._slave = slave
        self._model = model
        self._register = register
        self._scale = scale
        
        self._attr_translation_key = translation_key
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_state_class = state_class
        self._attr_unique_id = f"{DOMAIN}_{slave}_sensor_{register}_{translation_key}"
        self._state = None

    @property
    def device_info(self):
        """Link sensors to the device UI."""
        return {
            "identifiers": {(DOMAIN, f"{self._model}_{self._slave}")},
            "name": f"Systemair {self._model}",
            "manufacturer": "Systemair",
            "model": f"SAVE {self._model}",
        }

    @property
    def native_value(self):
        return self._state

    async def async_update(self):
        try:
            # 1. Fan Mode Logic
            if self._register == 1160:
                res_mode = await self._hub.async_pb_call(self._slave, 1160, 1, CALL_TYPE_REGISTER_INPUT)
                if res_mode and hasattr(res_mode, 'registers'):
                    mode_val = res_mode.registers[0]
                    res_cmd = await self._hub.async_pb_call(self._slave, 1130, 1, CALL_TYPE_REGISTER_HOLDING)
                    cmd_val = res_cmd.registers[0] if res_cmd and hasattr(res_cmd, 'registers') else None
                    
                    if mode_val == 0:
                        self._state = {2: "auto_low", 3: "auto_normal", 4: "auto_high"}.get(cmd_val, "auto")
                    elif mode_val == 1:
                        self._state = {0: "manual_stop", 2: "manual_low", 3: "manual_normal", 4: "manual_high"}.get(cmd_val, "manual")
                    else:
                        self._state = {2: "crowded", 3: "refresh", 4: "fireplace", 5: "away", 6: "holiday", 7: "cooker_hood"}.get(mode_val, "unknown")
                return

            # 2. Summer/Winter Logic
            if self._register == 1038:
                result = await self._hub.async_pb_call(self._slave, 1038, 1, CALL_TYPE_REGISTER_HOLDING)
                if result and hasattr(result, 'registers'):
                    self._state = "summer" if result.registers[0] == 0 else "winter"
                return

            # 3. Filter Time
            if self._register == 7005:
                result = await self._hub.async_pb_call(self._slave, 7004, 2, CALL_TYPE_REGISTER_HOLDING)
                if result and hasattr(result, 'registers'):
                    total_seconds = (result.registers[1] << 16) + result.registers[0]
                    self._state = round(total_seconds / 86400, 1)
                return

            # 4. Standard Logic
            is_input = (12000 <= self._register <= 16000)
            call_type = CALL_TYPE_REGISTER_INPUT if is_input else CALL_TYPE_REGISTER_HOLDING
            result = await self._hub.async_pb_call(self._slave, self._register, 1, call_type)
            
            if result and hasattr(result, 'registers'):
                val = float(result.registers[0])
                # Handle signed 16-bit for specific registers
                if is_input and self._register not in [12400, 12401, 12135, 14000, 14001, 14102]:
                    if val > 32767: val -= 65536
                self._state = round(val * self._scale, 1)

        except Exception as e:
            _LOGGER.error("Systemair: Update failed for %s: %s", self._attr_translation_key, e)