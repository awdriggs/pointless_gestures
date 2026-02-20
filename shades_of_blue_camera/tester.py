import time
import math
import busio
import board
import digitalio
import adafruit_ov5640
import displayio
import gc

# wifi imports
from os import getenv
import ipaddress
import wifi
import socketpool
import microcontroller
import json
import cpwebsockets.client

print("shades of blue")
print("read color from a ov5640 camera")
print()

# --- Wifi Setup ---
# Get WiFi details, ensure these are setup in settings.toml
ssid = getenv("CIRCUITPY_WIFI_SSID")
password = getenv("CIRCUITPY_WIFI_PASSWORD")

if None in [ssid, password]:
    raise RuntimeError(
            "WiFi settings are kept in settings.toml, "
            "please add them there. The settings file must contain "
            "'CIRCUITPY_WIFI_SSID', 'CIRCUITPY_WIFI_PASSWORD', "
            "at a minimum."
            )

print()
print("Connecting to WiFi")

#  connect to your SSID
try:
    wifi.radio.connect(ssid, password)
except TypeError:
    print("Could not find WiFi info. Check your settings.toml file!")
    raise

print("Connected to WiFi")

pool = socketpool.SocketPool(wifi.radio)

#  prints MAC address to REPL
print("My MAC addr:", [hex(i) for i in wifi.radio.mac_address])

#  prints IP address to REPL
print(f"My IP address is {wifi.radio.ipv4_address}")

# Sockets Business
WS_URL = "wss://micro-api.awdokku.site/"
STREAM_NAME = "shades-of-blue"

print("\nConnecting to WebSocket server...")
ws = cpwebsockets.client.connect(WS_URL, wifi.radio)
ws.settimeout(0.1)  # Make recv() non-blocking

# Join the stream
join_msg = {"type": "join", "stream": STREAM_NAME}
ws.send(json.dumps(join_msg))
print(f"Joined stream: {STREAM_NAME}")

# Test send before camera init
test_msg = {"type": "data", "values": {"r": 0, "g": 0, "b": 0}}
print(f"[{time.monotonic():.1f}] Test send before camera...")
ws.send(json.dumps(test_msg))
print(f"[{time.monotonic():.1f}] Test send complete")

# --- Camera setup ---
print("construct bus")
i2c = busio.I2C(board.GP5, board.GP4)

# PWDN pin managed separately so we can power down the camera during WiFi sends
pwdn = digitalio.DigitalInOut(board.GP1)
pwdn.direction = digitalio.Direction.OUTPUT
pwdn.value = False  # LOW = camera on

def init_camera():
    reset = digitalio.DigitalInOut(board.GP14)
    cam = adafruit_ov5640.OV5640(
            i2c,
            data_pins=(
                board.GP6, board.GP7, board.GP8, board.GP9,
                board.GP10, board.GP11, board.GP12, board.GP13,
                ),
            clock=board.GP3,
            vsync=board.GP0,
            href=board.GP2,
            mclk=None,
            shutdown=None,
            reset=reset,
            size=adafruit_ov5640.OV5640_SIZE_96X96,
            )
    cam.colorspace = adafruit_ov5640.OV5640_COLOR_RGB
    cam.flip_y = False
    cam.flip_x = False
    cam.test_pattern = False
    return cam

print("construct camera")
cam = init_camera()
print("chip id:", cam.chip_id)

# --- Bitmap setup ---
bitmap = displayio.Bitmap(cam.width, cam.height, 65535)

print(cam.width, cam.height)

TWO_PI = 6.2831853

SAMPLE_STEP = 2

def compute_average_color(bmp, w, h, step):
    """Compute average color using HSV circular hue averaging."""
    sin_sum = 0.0
    cos_sum = 0.0
    s_sum = 0.0
    v_sum = 0.0
    count = 0

    for y in range(0, h, step):
        for x in range(0, w, step):
            val = bmp[x, y]
            # Decode RGB565_SWAPPED to float RGB
            swapped = ((val & 0xFF) << 8) | ((val >> 8) & 0xFF) # reverse order, so we get to RRRRRGGGGGGBBBBB, green is 6 bits
            r = ((swapped >> 11) & 0x1F) / 31.0 # get thef red values, mask any grabage, normalize
            gr = ((swapped >> 5) & 0x3F) / 63.0 # get the green values, mask out red values, normalize
            b = (swapped & 0x1F) / 31.0 # get the vlue values, mask out the left hand bits, normalize

            # RGB to HSV
            mx = max(r, gr, b) # max channel
            mn = min(r, gr, b) # min channel
            d = mx - mn # difference between the two

            # determine which part of the color wheel we are in
            if d < 0.001:
                hue = 0.0
            elif mx == r:
                hue = ((gr - b) / d) % 6.0
            elif mx == gr:
                hue = ((b - r) / d) + 2.0
            else:
                hue = ((r - gr) / d) + 4.0
            hue /= 6.0

            # Circular hue averaging via unit vectors
            angle = hue * TWO_PI
            sin_sum += math.sin(angle)
            cos_sum += math.cos(angle)

            # saturation averaging
            s_sum += (d / mx) if mx > 0.001 else 0.0
            v_sum += mx #value averaging
            count += 1

    # Compute averages
    avg_hue = math.atan2(sin_sum / count, cos_sum / count) / TWO_PI
    avg_hue = avg_hue % 1.0
    avg_sat = s_sum / count
    avg_val = v_sum / count

    # HSV to RGB
    i = int(avg_hue * 6) % 6 # which section fo the color wheel is the average in?
    f = (avg_hue * 6) - i
    p = avg_val * (1 - avg_sat)
    q = avg_val * (1 - f * avg_sat)
    t = avg_val * (1 - (1 - f) * avg_sat)

    if i == 0:
        r, gr, b = avg_val, t, p # truple packing
    elif i == 1:
        r, gr, b = q, avg_val, p
    elif i == 2:
        r, gr, b = p, avg_val, t
    elif i == 3:
        r, gr, b = p, q, avg_val
    elif i == 4:
        r, gr, b = t, p, avg_val
    else:
        r, gr, b = avg_val, p, q

    return int(r * 255), int(gr * 255), int(b * 255)



gc.collect()
print(f"Free memory: {gc.mem_free()} bytes")

# --- Main loop ---
last_send = time.monotonic()
SEND_INTERVAL = 5.0
loop_count = 0

print(f"[{time.monotonic():.1f}] Starting main loop")

while True:
    try:
        # Check for incoming messages (ping/pong handling)
        try:
            msg = ws.recv()
            if msg:
                print(f"[{time.monotonic():.1f}] Received: {msg}")
        except:
            pass

        time.sleep(0.01)
        loop_count += 1

        # Send a reading at regular intervals
        now = time.monotonic()
        if now - last_send >= SEND_INTERVAL:
            print(f"[{now:.1f}] Capturing... (loops since last send: {loop_count})")
            loop_count = 0
            cam.capture(bitmap)

            t0 = time.monotonic_ns()
            r, g, b = compute_average_color(bitmap, cam.width, cam.height, SAMPLE_STEP)
            t1 = time.monotonic_ns()
            elapsed_ms = (t1 - t0) // 1_000_000
            print(f"[{time.monotonic():.1f}] avg color: R={r} G={g} B={b} ({elapsed_ms}ms)")

            # Power down and deinit camera before network op
            print(f"[{time.monotonic():.1f}] Camera off...")
            pwdn.value = True  # HIGH = power down
            cam.deinit()

            # Send light data
            try:
                data_msg = {
                    "type": "data",
                    "values": {"r": r, "g": g, "b": b}
                }
                gc.collect()
                print(f"[{time.monotonic():.1f}] Sending data... (free: {gc.mem_free()})")
                ws.send(json.dumps(data_msg))
                print(f"[{time.monotonic():.1f}] Send complete")
            except Exception as e:
                print(f"[{time.monotonic():.1f}] Error sending data: {e}")

            # Power up and reinit camera
            print(f"[{time.monotonic():.1f}] Camera on...")
            pwdn.value = False  # LOW = power on
            cam = init_camera()

            last_send = time.monotonic()

    except OSError as e:
        print(f"[{time.monotonic():.1f}] OSError: {e} (errno={e.errno})")
        print("Reconnecting...")
        time.sleep(5)
        try:
            ws.close()
        except:
            pass
        ws = cpwebsockets.client.connect(WS_URL, wifi.radio)
        ws.settimeout(0.1)
        ws.send(json.dumps(join_msg))
        print(f"[{time.monotonic():.1f}] Reconnected")
