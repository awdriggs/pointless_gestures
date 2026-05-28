# Shades of Blue — Research Notes

## Concept

Time-pixel image built from 1920 readings taken over a single day — one reading every 45 seconds (86400 / 1920 = 45s interval). Each reading maps to one pixel column of an HD display. Likely a slit-scan or luminance/color sample per cycle.

---

## Hardware

- **Microcontroller:** Seeed XIAO ESP32-S3 Sense
- **Radio:** Wio-SX1262 LoRa module (attaches via SPI)
- **Solar charger:** Adafruit bq24074 (product 4755)
- **Solar panel:** Voltaic P123 R2B — 6V, Imp 0.116A, ~0.7W peak
- **Battery:** 2500mAh LiPo

---

## Power architecture

```
Solar panel (6V) → bq24074 SOLAR input
LiPo (3.7V)      → bq24074 BATT JST
bq24074 LOAD out → XIAO BAT pads (underside, bottom-right, labelled BAT + and -)
```

- bq24074 LOAD output floats at up to 4.4V (tracks battery)
- Feed into XIAO BAT pads directly — within LiPo safe range, bypasses USB path
- Do not use XIAO 5V pin — 4.4V input is marginal for the onboard LDO
- Confirm polarity before soldering — hard to desolder

---

## Power budget

**Duty cycle:** ~5–7% (active ~2–3s per 45s cycle)

| State | Current |
|---|---|
| Deep sleep (ESP32-S3) | ~20µA |
| Active + LoRa TX peak | ~150mA |
| Estimated average | ~8–12mA |

**Daily consumption:** ~200–300mAh

**Daily solar input** (bq24074 efficiency ~87%):

| Condition | Input |
|---|---|
| Summer EU (4h peak sun) | ~400mAh |
| Winter EU good day (1.5h) | ~150mAh |
| Winter EU overcast (0.5h equiv.) | ~50mAh |

**Battery buffer:** 2500mAh ÷ 250mAh/day = ~10 days worst case with no sun. System should run year-round in northern EU — panel is well-matched to the load.

---

## Firmware pattern

```cpp
// persist pixel index across sleep cycles
RTC_DATA_ATTR int pixelIndex = 0;

void loop() {
    // wake, take reading, send LoRa packet
    pixelIndex++;
    esp_sleep_enable_timer_wakeup(45 * 1000000ULL);
    esp_deep_sleep_start();
}
```

LoRa payload is tiny — 3 bytes RGB or 1–2 bytes luminance. SF7 at EU 868MHz = ~10ms packet.

Camera init (OV2640) is the dominant energy cost per cycle (~200–500ms, 50–100mA), not the LoRa TX.

---

## Panel placement

Panel is flat (not tilted to latitude). At northern EU latitudes (~50°N) this loses ~25–35% of annual yield vs. optimal tilt, but the 2500mAh battery provides enough buffer to absorb bad winter days. Tilt if easy, not critical given current sizing.
