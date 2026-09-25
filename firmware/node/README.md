# The sensor node

One NodeMCU ESP8266 with a DHT11, taped inside the lid of a cooler box with two
ice packs. It is the only real truck in the fleet: TRK-07.

## Wiring

| DHT11 pin | NodeMCU pin |
| --- | --- |
| + / VCC | 3V3 |
| − / GND | G |
| S / OUT / DATA | D2 (GPIO4) |

Optional lid switch: between D5 (GPIO14) and G, then set `HAS_DOOR_SWITCH` to
`true`. Without it the backend still recognises a lid opening from the shape of
the temperature curve, so the switch is a nicety, not a requirement.

## Flashing

1. Arduino IDE 2 → Preferences → Additional Boards Manager URLs:
   `http://arduino.esp8266.com/stable/package_esp8266com_index.json`
2. Boards Manager → **esp8266 by ESP8266 Community** → install.
3. Board: **NodeMCU 1.0 (ESP-12E Module)**. Use a **data** USB cable; install the
   CP210x or CH340 driver if no port appears.
4. Library Manager: **DHT sensor library** (Adafruit), **Adafruit Unified
   Sensor**, **PubSubClient**.
5. Fill in `WIFI_SSID`, `WIFI_PASS` and `MQTT_HOST` (the laptop's fixed IP), then
   upload. Serial Monitor at **115200**.

The Wi-Fi password lives in this file and nowhere else in the project. Fill it
in on the demo laptop and do not commit it.

## What it does

- Publishes every 2 s to `coldguard/TRK-07/telemetry`:
  `{"truck_id":"TRK-07","air_c":3.4,"hum_pct":86,"door_open":false}`
- Reconnects to Wi-Fi and to MQTT on its own, without rebooting.
- The blue LED is **on while it is not connected** — the fastest way to see a
  problem from across the room.
- A failed DHT read is published as `-127`, which the backend reads as a sensor
  fault and uses to pause the freshness clock. It never invents a reading.

## Checks before the demo

```bash
mosquitto_sub -h localhost -t 'coldguard/#' -v     # readings arriving?
curl -s localhost:8000/api/trucks/TRK-07 | grep live_sensor
```

- Resting temperature in the closed box should settle **below 6 °C**. Write down
  what it actually reaches; the DHT11 is only accurate to about ±2 °C.
- The DHT11 is **not waterproof**: tape it to the lid, in cold air, never against
  an ice pack and never in meltwater.
- The ESP8266 is **2.4 GHz only**. A phone hotspot set to 5 GHz will not appear.

If the board fails on stage, open the dashboard's demo panel and switch
**backup mode** on: the simulator takes over TRK-07 and the demo continues.
