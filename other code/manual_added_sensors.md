

Here are some sensors from the old code not incorporated right now.
Untested.

Either add this in your yaml sensors, og all between {} in a template helper.
```yaml
template:
  - sensor:
      - name: "Heat Recovery Efficiency"
        unique_id: vsr_recovery_efficiency_calc
        unit_of_measurement: "%"
        state: >
          {% set supply = states('sensor.systemair_save_supply_air_temperature') | float(0) %}    
          {% set outdoor = states('sensor.systemair_save_outdoor_temperature') | float(0) %}
          {% set exhaust = states('sensor.systemair_save_exhaust_air_temperature') | float(0) %}
          
          {% set denominator = (exhaust - outdoor) %}
          
          {# Prevent division by zero if temps are equal #}
          {% if denominator > 0.5 %}
            {{ (((supply - outdoor) / denominator) * 100) | round(1) }}
          {% else %}
            0
          {% endif %}
        icon: mdi:sprout
```
