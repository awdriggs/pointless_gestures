import board
import busio  # Use busio for I2C communication
import digitalio
import time
from adafruit_as7341 import AS7341
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

# function to convert spectral values to rgb values
def rgb():
    channels = get_channels() # a dict, ignoring the data you don't need

    # print(channels)
    # print(maxValue)
    normalized = normalize(channels)
    # print(normalized)

    r = 0.3 * normalized["F6"] + 0.5 * normalized["F7"] + 0.7 * normalized["F8"]
    g = 0.3 * normalized["F4"] + 0.7 * normalized["F5"] 
    b = 0.5 * normalized["F2"] + 0.5 * normalized["F3"] 

    # Normalize RGB values if any exceed 1.0
    max_rgb = max(r, g, b)
    if max_rgb > 1.0:
        r /= max_rgb
        g /= max_rgb
        b /= max_rgb

    # convert to a 0-255 scale:
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

# function that normalizes accroding to the highest value 
def normalize(channels): #normalize according to the highest value
    max_val = max(channels.values()) # calc the max for normalizing
    return {key: value / max_val for key, value in channels.items()}


# while True:
#     print(rgb())
#     print("\n------------------------------------------------")
#     time.sleep(1)

print("\nStarting streaming light readings...")
last_send = time.monotonic()
SEND_INTERVAL = 0.05  # seconds (20 readings/sec - adjust as needed)


while True:
    try:
        # Check for incoming messages (ping/pong handling)
        # This allows the library to respond to server pings
        try:
            msg = ws.recv()  # Non-blocking due to settimeout(0.1)
            if msg:
                print(f"Received: {msg}")
        except:
            pass  # No message available or timeout, that's OK

        # Send light readings at regular intervals
        if time.monotonic() - last_send >= SEND_INTERVAL:
            values = rgb()
            # Send light data
            data_msg = {
                "type": "data",
                # "max": 65535,
                "values": values
            }
            ws.send(json.dumps(data_msg))
            print(f"Sent to server: {len(values)}")
            print("-" * 80)
            last_send = time.monotonic()

        time.sleep(0.01)  # Small delay to prevent busy-waiting

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


 
