# Shades of Blue — AS7341 Dev Log

## Sensor: AMS AS7341

8-channel spectral sensor (415–680nm). CircuitPython library: `adafruit_as7341`.

**Exposure controls:**
- `sensor.atime` — integration time per cycle (0–255, each step ≈ 2.78ms)
- `sensor.astep` — integration step size (0–65534)
- `sensor.gain` — index 0–10 mapping to: 0.5, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512x
- Actual integration time = `(atime + 1) × (astep + 1) × 2.78µs`

Current settings: `atime=29, astep=599, gain=8` (128x gain, ~50ms integration)

---

## Color Pipeline

Raw channel values → average N readings → normalize by sum → apply spectral weights → scale by brightness.

**Key design decision:** brightness is derived from the raw channel total *before* white balance normalization. This means dark scenes go toward black (like a photograph), rather than reporting full-saturation hue regardless of light level.

`MAX_COUNTS` is the ceiling for brightness scaling — it represents the raw channel total under your brightest expected scene. Needs to be calibrated outdoors.

Constants to tune in `code.py`:
```python
READINGS_N = 10       # samples averaged per reading
MAX_COUNTS = 65535 * 8  # replace with calibrated value
```

---

## Calibration: MAX_COUNTS

**Script:** `05-calibrate_max_counts.py`

1. Copy `05-calibrate_max_counts.py` to the device as `code.py`
2. Open serial monitor (115200 baud)
3. Take the sensor outside on a bright day around peak sun (solar noon ±1hr)
4. Sweep the sensor toward sky, walls, and direct sunlight
5. Watch for `NEW PEAK` lines — when the number stabilizes, that's your value
6. Update `MAX_COUNTS` in `code.py` with the peak value

**Watch for saturation:** if any channel hits 65535, gain=8 (128x) is too high for outdoor light. If that happens, drop `sensor.gain` to 6 (32x) or 7 (64x) in both `code.py` and the calibration script, then re-calibrate.

After calibration, restore the original `code.py`.

---

## White Balance Calibration

Press the button on GP12 while the device is running. Point at a neutral white or grey surface under the target lighting before pressing. Saved to `/white_balance.json` on the device. Applied per-channel before sum normalization.

---

## Hardware

- MCU: Raspberry Pi Pico W (or compatible)
- I2C: SDA=GP14, SCL=GP15
- Button: GP12 (pulled up, connects to GND when pressed)
- Transmits via WebSocket to `wss://micro-api.awdokku.site/`, stream `shades-of-blue`, device ID `ams02`
- Send interval: 67.5 seconds

---

## Low-Light Notes

- Averaging multiple readings reduces shot noise by √N before normalizing
- At very low light, noisy hue ratios are naturally suppressed because brightness → 0
- Single-photon detection is not possible with this sensor (photodiode array, not SPAD/PMT)
- Near-absolute-black is genuinely unknowable — not a software problem
