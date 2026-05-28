import board
import busio  # Use busio for I2C communication
import digitalio
import time
from adafruit_as7341 import AS7341
from adafruit_debouncer import Debouncer
from os import getenv
import ipaddress
import wifi
import socketpool
import microcontroller
import json
import cpwebsockets.client

print("shades of blue")
print("read color from a as7341 board")
print()

# Sensor business
# Define I2C using specific pins for the Raspberry Pi Pico
# blue qt stemma cable goes to 16 for sda
# yellow qt stemma calbe goes to 17 for scl
# i2c = busio.I2C(scl=board.GP17, sda=board.GP16)  # Replace with the correct pins
i2c = busio.I2C(scl=board.GP15, sda=board.GP14)  #using i2c1 here
sensor = AS7341(i2c) #color sensor on a breakout board

# Configure sensor for faster reads
# Lower atime = faster but less sensitive. Range: 0-255, each step = 2.78ms
# Default is 100 (278ms). Lower values like 29 (~81ms) or 10 (~28ms) are faster
sensor.atime = 29  # Integration time (lower = faster reads)
sensor.astep = 599  # Integration step (affects precision)
sensor.gain = 8  # Gain: 0.5, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512 (higher = more sensitive)
print(f"Sensor configured: atime={sensor.atime}, astep={sensor.astep}, gain={sensor.gain}")

# Button for white balance calibration
button_pin = digitalio.DigitalInOut(board.GP12)
button_pin.direction = digitalio.Direction.INPUT
button_pin.pull = digitalio.Pull.UP  # Button connects to ground when pressed
button = Debouncer(button_pin)

print(f"Button initial state: {button_pin.value}")  # Should be True (HIGH) when not pressed

# wifi business
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
ws.settimeout(0.1)  # Make recv() non-blocking with 0.1 second timeout

# Join the stream
join_msg = {"type": "join", "stream": STREAM_NAME}
ws.send(json.dumps(join_msg))
print(f"Joined stream: {STREAM_NAME}")

# White balance reference (captured during calibration)
white_balance_ref = None

def calibrate_white_balance():
    """Capture current spectral reading as white reference for color balancing"""
    global white_balance_ref
    print("\n=== WHITE BALANCE CALIBRATION ===")
    print("Capturing white reference...")

    # Take 3 quick samples and average (reduced from 5 for speed)
    samples = []
    for i in range(3):
        samples.append(get_channels())
        time.sleep(0.02)  # Reduced from 0.1s for faster calibration

    # Average the samples
    white_balance_ref = {}
    for key in samples[0].keys():
        white_balance_ref[key] = sum(s[key] for s in samples) / len(samples)

    print("White balance captured!")
    print(f"Reference: {white_balance_ref}")
    print("=" * 40)

# function to convert spectral values to rgb values
def rgb():
    channels = get_channels() # a dict, ignoring the data you don't need

    # Calculate total intensity BEFORE normalization (preserves brightness info)
    total_intensity = sum(channels.values())

    # Normalize to get spectral proportions (color information)
    normalized = normalize(channels)

    # Improved weights based on human color perception
    # Red: peaks at longer wavelengths (630-680nm)
    r = 0.1 * normalized["F6"] + 0.5 * normalized["F7"] + 1.0 * normalized["F8"]

    # Green: peaks around 530nm, between F4 (515nm) and F5 (555nm)
    # Reduced F5 weight since 555nm is already yellow-green
    g = 0.1 * normalized["F3"] + 0.6 * normalized["F4"] + 0.4 * normalized["F5"]

    # Blue: peaks around 450nm, include violet channel
    b = 0.3 * normalized["F1"] + 1.0 * normalized["F2"] + 0.5 * normalized["F3"]

    # Scale by total intensity to preserve brightness information
    # The normalized values (r,g,b) are proportions that sum to fractions
    # We need to scale them by brightness to get actual RGB values
    # Typical indoor total_intensity: 10,000-50,000
    # Typical outdoor total_intensity: 100,000-300,000
    # Scale factor chosen to map typical indoor to mid-range RGB
    BRIGHTNESS_SCALE = 8.0  # Compensates for 8-channel normalization
    INTENSITY_REFERENCE = 30000  # Reference intensity for calibration

    brightness_factor = (total_intensity / INTENSITY_REFERENCE) * BRIGHTNESS_SCALE

    r *= brightness_factor
    g *= brightness_factor
    b *= brightness_factor

    # Clamp to 0-1 range before final scaling
    r = min(1.0, max(0.0, r))
    g = min(1.0, max(0.0, g))
    b = min(1.0, max(0.0, b))

    # Final scaling to 0-255 range
    r_int = int(r * 255)
    g_int = int(g * 255)
    b_int = int(b * 255)

    return {"r": r_int, "g": g_int, "b": b_int} 

# function to get the channel data
def get_channels(): #package the channels as a dict
    data = {"F1": sensor.channel_415nm, 
            "F2": sensor.channel_445nm, 
            "F3": sensor.channel_480nm,
            "F4": sensor.channel_515nm,
            "F5": sensor.channel_555nm,
            "F6": sensor.channel_590nm,
            "F7": sensor.channel_630nm,
            "F8": sensor.channel_680nm
            }

    return data

# function that normalizes according to total spectral intensity
def normalize(channels):
    # Apply white balance if calibrated
    if white_balance_ref is not None:
        # Divide each channel by its white reference to correct color temperature
        balanced = {}
        for key, value in channels.items():
            if white_balance_ref[key] > 0:
                balanced[key] = value / white_balance_ref[key]
            else:
                balanced[key] = 0
        channels = balanced

    # Sum all spectral channels to get total light intensity
    total = sum(channels.values())
    if total == 0:
        return {key: 0 for key in channels.keys()}
    return {key: value / total for key, value in channels.items()}


# while True:
#     print(rgb())
#     print("\n------------------------------------------------")
#     time.sleep(1)

print("\nStarting streaming light readings...")
last_send = time.monotonic()
SEND_INTERVAL = 1.0  # seconds (1 reading/sec as requested)

while True:
    try:
        # Tight button checking loop - runs many times per sensor read
        for _ in range(10):  # Check button 10 times
            button.update()
            if button.fell:
                print("\n*** BUTTON PRESSED - STARTING CALIBRATION ***")
                calibrate_white_balance()
                print("*** CALIBRATION COMPLETE - RESUMING ***\n")
            time.sleep(0.001)  # 1ms between button checks

        # Check for incoming messages (ping/pong handling)
        try:
            msg = ws.recv()  # Non-blocking due to settimeout(0.1)
            if msg:
                print(f"Received: {msg}")
        except:
            pass  # No message available or timeout, that's OK

        # Send light readings at regular intervals
        if time.monotonic() - last_send >= SEND_INTERVAL:
            sensor_start = time.monotonic()
            values = rgb()
            sensor_time = time.monotonic() - sensor_start

            # Send light data
            try:
                data_msg = {
                    "type": "data",
                    "values": values
                }
                ws.send(json.dumps(data_msg))
                print(f"Sent RGB: {values} (sensor read: {sensor_time*1000:.1f}ms)")
                print("-" * 80)
            except Exception as e:
                print(f"Error sending data: {e}")

            last_send = time.monotonic()

    except OSError as e:
        if e.errno == 32:  # Broken pipe
            print(f"Connection lost (Error {e.errno})")
        else:
            print(f"Error: {e}")
        print("Reconnecting...")
        time.sleep(5)
        try:
            ws.close()
        except:
            pass
        ws = cpwebsockets.client.connect(WS_URL, wifi.radio)
        ws.settimeout(0.1)  # Make recv() non-blocking
        ws.send(json.dumps(join_msg))


 
