# Shades of Blue Camera - Research Notes

## Power & Battery

### Current setup
- Pico W + OV5640 camera on 2200mAh LiPo → ~2 days runtime
- Sends every 67.5 seconds, WiFi stays connected between sends

### Deep sleep potential
- Pico W active + WiFi: ~80-120mA
- Pico W deep sleep: ~0.5-1mA
- Sleeping ~95% of the time (between sends) could reduce average draw to 10-15mA → estimated 10-20 days from 2200mAh
- Main variable: WiFi reconnect time per wake cycle (a few seconds, draws significant current)
- Deep sleep requires full WiFi reconnect + WebSocket rejoin on every wake — pushes toward MQTT

---

## Solar Charging

### BQ25185 (current board — Adafruit with 3.3V buck)
- 6-hour unmodifiable safety timeout: if battery doesn't reach termination within 6 hours, charging stops
- `/CE` pin is tied to ground on this board — **cannot be pulsed to reset timer**
- Only reset is a full power cycle (removing/reapplying supply voltage)
- Solar panel staying connected means no natural reset in low-light conditions
- Output: fixed 3.3V regulated (connect to Pico 3V3 pin)

### BQ24074 (better option for this use case)
- CE pin is accessible — can wire to Pico GPIO and pulse every ~5 hours to reset timer
- Safety timer is programmable (not fixed)
- Output: up to 4.4V unregulated (follows battery voltage) → connect directly to Pico VSYS (accepts 1.8–5.5V), no buck needed
- Netherlands context: cloudy days are the norm, so timeout fault is a real practical risk, not theoretical

### Why timeout matters in the Netherlands
- Low light = low charge current = battery may never reach CV termination within 6 hours
- Pico drawing current simultaneously means net charge into battery may be near zero or negative
- With BQ25185, this leads to indefinite lockout requiring physical intervention
- With BQ24074 + CE pin wired to Pico, this is solvable in software

### LIC (Lithium Ion Capacitor) alternative
- Voltec makes small enclosures with 6V panel + 250F LIC charger (2.5–3.8V output)
- Advantages: hundreds of thousands of charge cycles (vs hundreds for LiPo), handles partial charge well, better cold temperature tolerance
- Disadvantages: less total energy storage, narrow/fluctuating output voltage, need to verify continuous current output for WiFi transmit spikes
- 2.5–3.8V is within Pico VSYS range but tight on the low end

---

## Battery Monitoring

### Voltage divider approach
- Two resistors between battery+ and GND, midpoint to Pico ADC pin
- For single-cell LiPo (3.0–4.2V): 100kΩ + 100kΩ (1:1 divider) → max 2.1V at ADC pin, safely within 3.3V limit
- Tiny current draw (~21µA), good for battery life
- Code: `voltage = (pin.value / 65535) * 3.3 * 2`
- Voltage is a reasonable proxy for LiPo state of charge, but sags under load

### Dedicated fuel gauge
- MAX17048 over I2C gives proper percentage reading, handles chemistry math
- Adafruit makes a breakout board
- The Waveshare Pico LoRa board has BAT_AD built in on GP26

---

## LoRa / Wireless

### Waveshare Pico LoRa SX1262 868M
- Pins: GP2 (BUSY), GP3 (CS), GP10 (CLK), GP11 (MOSI), GP12 (MISO), GP15 (RESET), GP20 (DIO1), GP26 (BAT_AD)
- **Conflicts with PiCowbell camera**: GP2, GP3, GP10, GP11, GP12, GP15 all clash
- Works fine alongside I2C sensors (GP4/GP5 are free)
- 868MHz (EU band) — must match gateway frequency

### Heltec ESP32 as base station
- Common LoRa gateway/base station option, well supported
- Can receive from Pico node and forward over WiFi to MQTT broker or WebSocket server
- Eliminates need for Pico to do WiFi → major battery savings
- Confirm frequency match (868MHz EU vs 915MHz US vs 433MHz)

### Raw LoRa vs LoRaWAN
- **Raw LoRa point-to-point**: simpler, right choice for one node to one Heltec at home
- **LoRaWAN**: adds network server layer (TTN, Chirpstack, Helium), useful for multiple nodes or community infrastructure
- TTN was founded in the Netherlands, strong coverage there
- LoRaWAN EU duty cycle limit: ~1% air time — fine for sensor data
- LoRaWAN max payload: ~51 bytes at common data rates — fine for RGB + temp
- Range: 0.5–2 miles urban, 5–10 miles line of sight, 15+ miles ideal conditions

### MQTT vs WebSockets
- MQTT is a better fit for this use case: designed for constrained devices, low overhead, broker handles persistence, connect/publish/disconnect pattern is deep-sleep friendly
- WebSockets require a persistent connection — doesn't survive deep sleep
- Would need an MQTT broker server-side (Mosquitto is common self-hosted option)

---

## Camera Color Issues

### Purple cast
- OV5640 is sensitive to infrared light
- Without an IR cut filter, IR registers as red, combined with blue sky/diffuse daylight produces purple/magenta cast
- Camera pointed straight up at overcast Dutch sky — purple output is expected given IR sensitivity
- Potential fix: IR cut filter film over the lens (cheap)
- No white balance configuration currently set in code — OV5640 AWB may not be settling correctly in short capture window
- Could embrace the cast given project is "shades of blue" — purple-blue sky palette may be aesthetically valid

---

## Placement

- Solar panel placement and aesthetic placement may conflict — sky-facing for color data vs sun-facing for charging
- Wall power eliminates solar/charging complexity entirely and allows placement based purely on where light is interesting
