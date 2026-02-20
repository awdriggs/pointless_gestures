# Shades of Blue Camera - Dev Log

## 2026-02-17: WebSocket send blocking issue

### Goal
Send average color data from OV5640 camera to micro-api server via WebSocket (same setup as working `shades_of_blue` project with AS7341 sensor).

### Problem
`ws.send()` blocks for 20-30 seconds consistently. Server heartbeat (30s interval) terminates the connection as dead before data arrives.

### What we tried
1. **Fixed indentation bug** in original main loop send block
2. **Changed values format** from raw RGB565 int to `{"r": r, "g": g, "b": b}` dict to match working project
3. **Added recv() ping/pong handling** and reconnection logic (matching shades_of_blue pattern)
4. **Removed display code** (not needed, saves some memory/pins)
5. **Removed sleep-based timing** - switched from `time.sleep(TARGET_MS)` to monotonic clock interval (like shades_of_blue) so `recv()` runs frequently
6. **Adjusted settimeout** - tried 0.01 and 0.1, no difference
7. **Added gc.collect() before send** - free memory is ~62KB, not the bottleneck
8. **Added timestamps** to all key events - confirmed send takes 20-30s, everything else is normal

### What we know
- `compute_average_color` takes ~1 second (not the issue)
- Free memory is ~62KB (not critically low)
- The working `shades_of_blue` project uses the exact same server, URL, library, board, and payload format
- The only difference is this project uses the OV5640 camera + bitmap buffer

### Resolution
The **PWDN pin (GP1)** was the fix. Driving it HIGH before `ws.send()` powers down the camera chip entirely, stopping it from toggling the 8 data pins. This eliminated the 30-second block.

```python
pwdn.value = True   # power down camera
ws.send(...)        # now completes instantly
pwdn.value = False  # power up camera
cam = init_camera() # reinit for next capture
```

**Root cause:** The PiCowbell has an onboard 16MHz oscillator that continuously drives the camera's XCLK. Even after `cam.deinit()` (which releases PIO/DMA), the camera chip stays active and keeps toggling the 8 parallel data pins. This electrical activity interferes with the Pico W's CYW43439 WiFi chip during sends. Powering the camera down via PWDN stops the data pins from toggling and lets WiFi operate normally.

Note: `cam.deinit()` alone (releasing PIO) did not fix the issue. The camera hardware itself needed to be powered off.

### Key files
- `main.py` - camera + websocket code
- `../shades_of_blue/code.py` - working reference (AS7341 sensor, same server)
- `../../micro-api/websocket/heartbeat.js` - server heartbeat (30s interval)
- `../../micro-api/controllers/shadesOfBlueController.js` - server handler for this stream
