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
    CONF_MODEL, 
    CONF_NAME
)
from homeassistant.components.modbus.const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT
)
from .const import DOMAIN, CONF_SLAVE

_LOGGER = logging.getLogger(__name__)

VSR_SENSORS = [
    ("Outdoor Temperature", 12101, SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, 0.1, None, SensorStateClass.MEASUREMENT),
    ("Supply Air Temperature", 12102, SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, 0.1, None, SensorStateClass.MEASUREMENT),
    ("Extract Air Temperature", 12105, SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, 0.1, "mdi:home-thermometer", SensorStateClass.MEASUREMENT),
    ("Overheat Temperature", 12107, SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, 0.1, None, SensorStateClass.MEASUREMENT),      
    ("Exhaust Air Temperature", 12543, SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, 0.1, None, SensorStateClass.MEASUREMENT),
    ("Relative Moisture Extraction", 12135, SensorDeviceClass.HUMIDITY, "%", 1.0, None, SensorStateClass.MEASUREMENT),
    ("Calculated Moisture Extraction", 2210, SensorDeviceClass.HUMIDITY, "%", 1.0, None, SensorStateClass.MEASUREMENT),
    ("Calculated Moisture Intake", 2211, SensorDeviceClass.HUMIDITY, "%", 1.0, None, SensorStateClass.MEASUREMENT),
    ("Supply Air Fan RPM", 12400, None, "rpm", 1.0, "mdi:speedometer", SensorStateClass.MEASUREMENT),
    ("Extractor Air Fan RPM", 12401, None, "rpm", 1.0, "mdi:speedometer", SensorStateClass.MEASUREMENT),
    ("Supply Air Fan Speed", 14000, None, "%", 1.0, "mdi:fan", SensorStateClass.MEASUREMENT),
    ("Extractor Air Fan Speed", 14001, None, "%", 1.0, "mdi:fan", SensorStateClass.MEASUREMENT),
    ("Supply Airflow Rate", 14000, None, "m³/h", 3.0, "mdi:home-switch", SensorStateClass.MEASUREMENT),
    ("Extractor Airflow Rate", 14001, None, "m³/h", 3.0, "mdi:home-switch", SensorStateClass.MEASUREMENT), 
    ("Current Fan Mode", 1160, None, None, 1.0, "mdi:air-conditioner", None),
    ("Mode Time Remaining", 1111, None, None, 1.0, "mdi:timer-sand", None), 
    ("Filter Time Remaining", 7005, None, "days", 1.0, "mdi:clock-end", SensorStateClass.MEASUREMENT),
    ("Filter Alarm Code", 15141, None, None, 1.0, "mdi:alert-circle", None),
    ("Heat Recovery", 14102, None, "%", 1.0, "mdi:sync", SensorStateClass.MEASUREMENT),
    ("Summer Winter Operation", 1038, None, None, 1, "mdi:sun-snowflake-variant", None),
    
    # Both of these will now point to register 2148 internally
    ("Heater Power (TRIAC)", 2148, None, "%", 1.0, "mdi:heating-coil", SensorStateClass.MEASUREMENT),
    ("Heater Power Watts", 2148, SensorDeviceClass.POWER, UnitOfPower.WATT, 16.7, "mdi:lightning-bolt", SensorStateClass.MEASUREMENT),
    
    ("Manual Fan Speed Setting", 1130, None, None, 1.0, "mdi:cog-clockwise", None),
]

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SaveVSR sensors."""
    config = entry.data
    hub_name = config.get("hub_name", "modbus_hub")
    from homeassistant.components.modbus import get_hub
    hub = get_hub(hass, hub_name)
    if hub is None:
        _LOGGER.error("SaveVSR: Modbus hub '%s' not found", hub_name)
        return
    model = config.get(CONF_MODEL, "SAVE")
    slave = config.get(CONF_SLAVE, 1)
    entities = [SaveVSRGenericSensor(hub, model, slave, *s) for s in VSR_SENSORS]
    async_add_entities(entities, True)

class SaveVSRGenericSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, hub, model, slave, name, register, device_class, unit, scale, icon, state_class=None):
        self._hub = hub
        self._slave = slave
        self._model = model
        self._register = register
        self._scale = scale
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_state_class = state_class
        clean_name = name.lower().replace(" ", "_")
        self._attr_unique_id = f"{DOMAIN}_{slave}_sensor_{register}_{clean_name}"
        self._state = None

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, f"{self._model}_{self._slave}")}, "name": f"Systemair {self._model}", "manufacturer": "Systemair", "model": f"SAVE {self._model}"}

    @property
    def native_value(self):
        return self._state

    async def async_update(self):
        try:
            # 1. 32-bit Timers
            if self._register == 1111:
                res_l = await self._hub.async_pb_call(self._slave, 1110, 1, CALL_TYPE_REGISTER_INPUT)
                res_h = await self._hub.async_pb_call(self._slave, 1111, 1, CALL_TYPE_REGISTER_INPUT)
                if res_l and res_h and hasattr(res_l, 'registers'):
                    total_seconds = (res_h.registers[0] << 16) + res_l.registers[0]
                    if total_seconds > 0:
                        h, m = total_seconds // 3600, (total_seconds % 3600) // 60
                        self._state = f"{h}h {m}min" if h > 0 else f"{m}min"
                    else:
                        self._state = "Inactive"
                return

            # 2. Fan Mode
            if self._register == 1160:
                res_mode = await self._hub.async_pb_call(self._slave, 1160, 1, CALL_TYPE_REGISTER_INPUT)
                if res_mode and hasattr(res_mode, 'registers'):
                    mode_val = res_mode.registers[0]
                    res_cmd = await self._hub.async_pb_call(self._slave, 1130, 1, CALL_TYPE_REGISTER_HOLDING)
                    cmd_val = res_cmd.registers[0] if res_cmd and hasattr(res_cmd, 'registers') else None
                    if mode_val == 0:
                        self._state = {2: "Auto - Low", 3: "Auto - Normal", 4: "Auto - High"}.get(cmd_val, "Auto")
                    elif mode_val == 1:
                        self._state = {0: "Manual STOP", 2: "Manual Low", 3: "Manual Normal", 4: "Manual High"}.get(cmd_val, "Manual")
                    else:
                        mode_map = {2: "Crowded", 3: "Refresh", 4: "Fireplace", 5: "Away", 6: "Holiday", 7: "Cooker Hood"}
                        self._state = mode_map.get(mode_val, f"Mode {mode_val}")
                return

            # 3. Filter Time
            if self._register == 7005:
                result = await self._hub.async_pb_call(self._slave, 7004, 2, CALL_TYPE_REGISTER_HOLDING)
                if result and hasattr(result, 'registers') and len(result.registers) >= 2:
                    total_seconds = (result.registers[1] << 16) + result.registers[0]
                    self._state = round(total_seconds / 86400, 1)
                return

            # 4. Standard Logic
            is_input = (12000 <= self._register <= 16000) or self._register in [1160, 1111]
            call_type = CALL_TYPE_REGISTER_INPUT if is_input else CALL_TYPE_REGISTER_HOLDING

            result = await self._hub.async_pb_call(self._slave, self._register, 1, call_type)
            
            if result and hasattr(result, 'registers'):
                val = result.registers[0]
                if self._register == 1038: 
                    self._state = "Summer" if val == 0 else "Winter"
                elif self._register == 1130:
                    self._state = {1: "Off", 2: "Low", 3: "Normal", 4: "High"}.get(val, f"Level {val}")
                elif self._register == 15141: 
                    self._state = {0: "No Alarm", 1: "Warning", 2: "Overdue"}.get(val, val)
                else:
                    float_val = float(val)
                    
                    # Prevent negative values for the TRIAC/Power register
                    if self._register == 2148:
                        float_val = max(0.0, float_val)

                    # Temperature sign handling
                    if is_input and self._register not in [12400, 12401, 12135, 14000, 14001, 14102]:
                        if float_val > 32767: float_val -= 65536
                    
                    self._state = round(float_val * self._scale, 1)

        except Exception as e:
            _LOGGER.error("SaveVSR: Update failed for %s: %s", self._attr_name, e)