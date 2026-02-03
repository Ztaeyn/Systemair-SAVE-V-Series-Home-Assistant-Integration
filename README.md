# Systemair SAVE Modbus Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/Ztaeyn/Systemair-SAVE-V-Series-Home-Assistant-Integration)](https://github.com/Ztaeyn/Systemair-SAVE-V-Series-Home-Assistant-Integration/releases)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

This integration provides local control of **Systemair SAVE** ventilation units...
This integration provides you remote control of the Systemair Save ventilation units (VSR, VTR, VTC and perhaps even VR series). It allows you to monitor sensors, adjust climate settings, adn manage weekly schedules directly from Home Assistant. How about pairing it up with a humidity sensor in the bathroom to automatically trigger the Refresh?
<img width="1185" height="341" alt="image" src="https://github.com/user-attachments/assets/6fffd555-bdc1-4ac9-b2ed-65477f09f5b5" />


# Features
* Full Climate Control: Set target temperature and switch between modes (Auto, Manual, Away, Crowded, etc.).
* Comprehensive Sensors: Real-time data for all temperature probes, fan speeds (RPM), humidity, and heat recovery efficiency.
* Alarms & Diagnostics: Binary sensors for A/B/C alarms and filter change alerts.
* Weekly Schedule: Adjust start/stop times for internal schedules.
* Model Support: Verified for VSR 300/400/500, VTR 300/400/500, VTC 300/700, and VR 700 DCV.
* Norwegian (thats me) and English translation.

# 🛠 Installation
## 1. Modbus adapter
I assume there is a multitude of various modbus adapters you can use. I use an Elfin EW11 myself. (From Aliexpress)

## 2.Prerequisites
Manually configure your **configuration.yaml**. 
```yaml
modbus:
  - name: "save_hub"      # Your HUB ID. If you have multiple devices, this must be a unique name.
    type: tcp
    host: 192.168.10.101  # Your unit's IP address
    port: 8432            # Your Modbus port (often 502 or 8432)
    sensors:
      - name: "Systemair Link"  # This is a kind of lifeline for the integration.
        address: 12101
        slave: 1
```
And if you have installed the older YAML version (or an early version of this python integration) you must remove and probably purge out the old entities from your HA, as well remove and readd the python integration as I renamed it. 
I use the **Spook** integration myself for removing old entities. 

## 3A. Installation via HACS (recommended)
1. Open **HACS** in Home Assistant.
2. Click the three dots in the top right corner and select **Custom repositories**.
3. Paste the URL of this GitHub repository.
4. Select **Integration** as the category and click **Add**.
5. Restart Home Assistant.

## 3B. Alternative Manual installation
1. Download source code.zip from releases
2. Unzip and place the systemair folder under Home assistant folder "Custom components".
3. Restart Home assistant

## 4. Setup
1. Go to **Settings** -> **Devices & Services**.
2. Click **Add Integration** and search for **Systemair Save**
3. Follow the config flow. Select your model. Hub name and Slave ID 

# Systemair VSR/VTR/VTC 300/400/500+"Most of the other sizes" Integration for Home Assistant
Note: The code is designed and tested on a VSR300 but will work for the others as well, but minor changes as sensor range for bigger fans etc etc can be coded in by request, so that the integration switches to the correct sensor data.
This integration will show  up as a Systemair device.

## 🌍 Translations & Entity IDs
This integration is built with ~~full~~ much on the way translation support.
1. Entity IDs remain ~~stable~~ and technical (e.g., sensor.systemair_1_away_mode). **Work in progress or local issue, the entity IDs turn to norwegian for me. This is unwanted** 
2. Friendly Names will automatically translate to English or Norwegian based on your Home Assistant language settings. **More languages can be added. Download the **en/nb.json** and translate it, and add it under the **Systemair/Translations** folder, and when you are happy with it, PM me with a copy if you want it included :)
3. One thing of **note**. Right now Units are hardcoded to norwegian. I can look at making it follow the set language as well, but I took the quick route right now. Please tell me. (if anyone reads this).

## ⚖️ License
This project is licensed under the GNU GPLv3 - see the LICENSE file for details.

## 🤝 Contributing
If you own a VTC or VR model and find that certain sensors are missing or need scaling adjustments, please open an Issue or submit a Pull Request.
My personal time off also varies, after the kids fall asleep I prefer chilling with the Steam Deck than sitting in front of the computer.

## Notice of Vibe coding
Most of the integration is a hybrid of vibe coding. I mostly work with PLC coding, but have wanted to learn python (and C#) but lack of willpower after long work days killed that motivation.
So after my other repo with the YAML version of this was marked for some needed changes due to HA changed parts of the modbus, I felt eager to try it out as a python integration.
So I've used Gemini to help me out, it's been fun, I got it up working but lots of fiddling around. Now I just need to keep at it and restart the python course I once bought at Udemy.
