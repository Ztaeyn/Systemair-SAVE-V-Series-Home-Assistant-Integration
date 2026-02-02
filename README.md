# Systemair VSR/VTR/VTC 300/400/500+"Most of the other sizes" Integration for Home Assistant
Note: The code is designed and tested on a VSR300 but will work for the others as well, but minor changes as sensor range for bigger fans etc etc can be coded in by request, so that the integration switches to the correct sensor data.
This integration will show  up as a Systemair device.
<img width="1185" height="341" alt="image" src="https://github.com/user-attachments/assets/6fffd555-bdc1-4ac9-b2ed-65477f09f5b5" />



## Information
I had a YAML package running for my VSR300, but I have always wanted to learn python but never getting around to it with young kids messing my sleep. So I have cheated here to find my motivation, and used Gemini a lot to help me with the code. My daily work is PLC programming, so I grasp much of reading the python code and knows how I want things. Aka kind of vibe coded? 

## What it does
If you have not connected your VSR300 to Home Assistant before, this integration lets you control and monitor the Systemair from Home Assistant.
* Set fan modes, setpoints, duration for away etc.
* Configure fan speeds
* See filter replacemnt in days,
* Estimated power usage from the heater
* See alarms (more can be added, take a look in the modbus documentation and tell me if you need some from there)
* Control weekly schedule of how the system runs

### Device elements
The device added by the integration is separated into
* Controls - The typical daily usage
* Sensors - Information, non controllable
* Configuration - Elements you normally don't change more than once.

* ### Free Cooling
* Set temperature limits for start/stop, time schedule.


## Installation
I did not manage for now to make it install without editing files, as it seems I would have to provide the modbus interface myself. So for now you need to add the modbus interface to the configuration.yaml.

0. Prereq: HACS
1. Add the modbus configuration to your HA server. See the file "your_configuration.yaml"
2. In the HACS meny press the top right tree dot menu, and Custom Repos, and add [https://github.com/Ztaeyn/HA-VSR300-modbus-python-integration](https://github.com/Ztaeyn/Systemair-SAVE-V-Series-Home-Assistant-Integration) as category Integration.
3. Search for Systemair and press download.
4. Restart Home Assistant
5. Now go to Devices and add new integration and search for Systemair and add it.
6. It should now be available as a device under Home Assistant.
7. Select your unit from the list. The rest should be from what you configured in configuration.yaml.

<img width="603" height="330" alt="image" src="https://github.com/user-attachments/assets/9eca3de1-5c5d-4ba9-8a87-571a4f9ef7be" />


<img width="1124" height="776" alt="image" src="https://github.com/user-attachments/assets/616d7609-bdff-4be0-9805-427637dd1d77" />

Note. If you previously used the YAML package you will have to remove it first, and the resulting broken entities. I used the Spook integration for removing dead entities. Use at your own risk.


## Hardware 
I use a Elfin EW11 modbus adapter from AliExpress.



## issues
* Minor issue: Not reading fan state Cooker Hood. 
* 
