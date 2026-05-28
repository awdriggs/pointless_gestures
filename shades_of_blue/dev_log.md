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

**Pending**
- Clear blue sky test with `AVG_HSV_SAT_WEIGHTED` + `ae_level(0)` — scheduled for tomorrow (sunny forecast)
- Update `xiao_camera_avg` and `xiao_cam_lora_tx` building block sketches with center crop + sat-weighted HSV
