# Shades of Blue — Dev Log

---

## 2026-05-21

**Server**
- Added `POST /api/readings/shades-of-blue` to micro-api
- Added `express.json()` middleware
- Endpoint saves to MongoDB `sensor_data` collection and broadcasts via WebSocket to all connected clients
- Renamed old collection to `sensor_data_archive`; new collection is a time series (timeField=timestamp, metaField=device_id, granularity=minutes)

**Basestation (Heltec WiFi LoRa 32 V3)**
- Copied from `heltec_lora_http` building block
- Connects to WiFi, receives LoRa RGB packet, POSTs to server
- NTP time sync with Amsterdam timezone (`CET-1CEST,M3.5.0,M10.5.0/3`)
- Display layout: device name + WiFi status / last send timestamp / R G B values
- Display only updates on successful POST
- DEVICE_ID=`ams01`

**Camera (XIAO ESP32-S3 Sense + Wio-SX1262)**
- Copied from `xiao_camera_avg` building block
- Architecture: all logic in `setup()`, deep sleep between readings
- 45s sleep cycle → 1920 readings/day = one per pixel column of a 1920px display
- Timestamp from basestation NTP acts as pixel index — no separate index needed
- 10 frames discarded before capture to let AEC settle
- Packet format: `"r,g,b"` string over LoRa

---

## 2026-05-26

**OV3660 pixel decode fix**
- Identified that RGB readings were wrong — blue sky returning high R, low B
- Root cause: OV3660 outputs big-endian BGR565; ESP32 is little-endian, so raw `uint16_t` read reverses bytes
- Fix: byte-swap before decoding channels
  ```cpp
  uint16_t raw = pixels[y * w + x];
  uint16_t px  = (raw << 8) | (raw >> 8);  // OV3660: big-endian BGR565
  float b  = ((px >> 11) & 0x1F) / 31.0f;
  float gr = ((px >>  5) & 0x3F) / 63.0f;
  float r  = (px & 0x1F) / 31.0f;
  ```
- Confirmed via `xiao_camera_debug` sketch: byte-swap-BGR consistently gives b>g>r for pure blue sky

**AEC tuning**
- Disabled night-mode AEC (`set_aec2(0)`)
- Initially set `ae_level(-2)` to bias toward underexposure for color accuracy — later found to be too aggressive (see 2026-05-27)

**Debug sketch** (`esp_party/xiao_camera_debug`)
- Standalone sketch: no sleep, no LoRa, loops every 5s
- Prints 9 center pixels with both decode options side by side
- Runs all three averaging modes for comparison

---

## 2026-05-27

**Averaging algorithm overhaul**
- Problem: HSV circular average is numerically unstable for low-saturation colors (overcast sky)
  — near-gray pixels have ill-defined hue; tiny channel differences give wildly different hue values
- Problem: averages were much darker than center pixels (~115 vs ~210) due to lens vignetting
- Added center crop to reduce vignetting impact: 70.7% of each dimension (~50% of total pixels)
  ```cpp
  int xStart = (int)(w * 0.146f);
  int xEnd   = w - xStart;
  int yStart = (int)(h * 0.146f);
  int yEnd   = h - yStart;
  ```
- Added `#define AVG_MODE` to switch between three algorithms at compile time:
  - `AVG_LINEAR_RGB` — simple channel mean; accurate for low saturation
  - `AVG_HSV_CIRCULAR` — original circular mean; unstable for near-gray
  - `AVG_HSV_SAT_WEIGHTED` — circular mean weighted by per-pixel saturation; saturated pixels dominate hue, near-gray pixels fall back to value average naturally
- Default: `AVG_HSV_SAT_WEIGHTED`
- Debug sketch updated to print all three modes side by side for field comparison

**JPEG debug sketch** (`esp_party/xiao_camera_jpeg`)
- New sketch: captures JPEG and writes to microSD card
- Used to visually confirm what the camera actually sees
- WiFi approach abandoned — Wio-SX1262 physically blocks the XIAO's WiFi antenna, giving -91 dBm signal at arm's length
- SD card uses same SPI bus (D8/D9/D10) as Wio-SX1262; SX1262 NSS (D4) driven HIGH to avoid bus conflict
- Files saved as `sky0000.jpg`, incrementing on each run

**AEC level correction**
- `ae_level(-2)` was making images 1–2 stops too dark and suppressing color
- Confirmed via JPEG: clear blue visible once sun removed from frame; previous shots were AEC-pulled-down by sun in lower corner
- Changed to `ae_level(0)` in both `camera.ino` and `xiao_camera_jpeg.ino`
- Sun in frame will push readings toward white end of spectrum — acceptable; dark grays were not

---

## 2026-05-28

**First full-day run (2026-05-27)**
- ~19 hours of readings captured and rendered
- Results: green-gray dominant, no blue — incorrect for a blue sky day
- Battery (old, a few years) died shortly after midnight, recovered briefly at 6am, not fully operational until 11am
- Battery swapped for a newer unit

**Root cause: pixel format + AWB**
- JPEG test images from `xiao_camera_jpeg` looked visually correct (real blue visible)
- RGB565 raw decode was producing wrong colors even with the byte-swap fix
- Auto white balance in auto mode actively neutralizes scene color — blue sky → AWB adds red, suppresses blue → green-gray output
- HSV averaging also showed instability: olive/yellow artifacts at sunrise, hue landing in wrong range under transitional light

**Fix: JPEG decode pipeline**
- Switched camera to `PIXFORMAT_JPEG`
- Decode to RGB565 via `jpg2rgb565()` (software conversion from JPEG — standard RGB565, no byte-swap needed, R in high bits)
- All three `AVG_MODE` options preserved, now operating on JPEG-decoded pixels
- Default changed to `AVG_LINEAR_RGB` for reliability

**Fix: white balance**
- Disabled auto AWB gain: `set_awb_gain(s, 0)`
- Fixed sunny preset: `set_wb_mode(s, 1)`
- Prevents AWB from hunting and neutralizing sky color

**Confirmed working**
- First reading after fix: `r=109, g=124, b=152` — b > g > r on a blue sky day ✓

---

## 2026-05-29

**Full-day run confirmed (test-05282026.jpg)**
- Colors accurate: real blue on clear afternoon, cool gray on overcast morning ✓
- JPEG decode pipeline + fixed sunny WB confirmed working end-to-end

**Twilight exposure problem**
- AEC boosts exposure at dusk/dawn making twilight appear brighter/bluer than reality
- No direct max-AEC-cap in esp_camera API for OV3660
- Decision: use fixed manual exposure — honest representation of actual luminance

**Exposure bracketing** (`esp_party/xiao_camera_bracket`)
- New sketch: AEC auto-settles, reads back settled value, switches to manual, shoots ±2 stops around base
- Files named `m2_XXXX.jpg` / `m1_XXXX.jpg` / `00_XXXX.jpg` / `p1_XXXX.jpg` / `p2_XXXX.jpg` where XXXX = actual aec_value
- Full sun test: AEC settled at 14, bracket range 3–56
- m1 (aec=7) selected as best — good blue, sky detail preserved without washing out
- Fixed exposure set in `camera.ino`: `set_exposure_ctrl(s, 0)` + `set_aec_value(s, 7)`

---

## 2026-06-29

**Hardware notes**
- Investigating battery drain on 2-3 consecutive overcast days
- Estimated daily consumption: ~320mAh; 0.64W panel marginal on very overcast days
- Upgrading solar panel to 1W 6V (Voltaic) — same voltage, ~55% more harvest, no charger changes needed
- Sleep current measurement pending — need multimeter in series (µA range); USB inline meters only resolve to 1mA, insufficient for sleep floor measurement
- bq24074 NTC thermistor input not yet wired — risk of charging below 0°C damaging battery; worth adding before permanent winter installation

**Battery chemistry notes**
- LiPo vs Li-ion: no meaningful difference for this project — same chemistry, different form factor
- Both degrade above 40°C (sealed enclosure in direct sun is a risk) and cannot be safely charged below 0°C
- LiPo flat pouch easier to fit in weatherproof enclosure

**Pending**
- Wire NTC thermistor to bq24074 for cold-charge protection
- Measure actual sleep current draw
- Upgrade to 1W solar panel
- Update `xiao_camera_avg` and `xiao_cam_lora_tx` building block sketches with center crop + JPEG decode pipeline
