import board
import busio
import digitalio
import time
from adafruit_mcp3xxx.mcp3008 import MCP3008
from adafruit_mcp3xxx.analog_in import AnalogIn
from os import getenv
import ipaddress
import wifi
import socketpool
import microcontroller
import json
import cpwebsockets.client

print("8 pixel camera")
print("16-bit resolution (0-65535)")
print()

# Phototransistor Business
# MCP3008 SPI Setup
# Wiring:
#   MCP3008 CLK  -> GP18 (SPI0 SCK)
#   MCP3008 DOUT -> GP16 (SPI0 MISO)
#   MCP3008 DIN  -> GP19 (SPI0 MOSI)
#   MCP3008 CS   -> GP17
#   MCP3008 VDD  -> 3.3V
#   MCP3008 VREF -> 3.3V
#   MCP3008 AGND -> GND
#   MCP3008 DGND -> GND

# Create SPI bus
spi = busio.SPI(clock=board.GP18, MISO=board.GP16, MOSI=board.GP19)

# Create chip select
cs = digitalio.DigitalInOut(board.GP17)

# Create MCP3008 object
mcp = MCP3008(spi, cs)

# Create analog inputs for all 8 channels
channels = [AnalogIn(mcp, i) for i in range(8)]

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
STREAM_NAME = "eight-px"

print("\nConnecting to WebSocket server...")
ws = cpwebsockets.client.connect(WS_URL, wifi.radio)
ws.settimeout(0.1)  # Make recv() non-blocking with 0.1 second timeout

# Join the temperature stream
join_msg = {"type": "join", "stream": STREAM_NAME}
ws.send(json.dumps(join_msg))
print(f"Joined stream: {STREAM_NAME}")

# Main loop - send temperature every 10 seconds
print("\nStarting streaming light readings...")
last_send = time.monotonic()
SEND_INTERVAL = 0.05  # seconds (20 readings/sec - adjust as needed)

# Function to read all 8 phototransistor channels
def get_reading():
    DATA = []
    for i, chan in enumerate(channels):
        # Read raw value (0-65535, 16-bit)
        raw_value = chan.value
        DATA.append(raw_value)
        print(f"CH{i}: {raw_value:5d}", end="  ")
    print()  # New line after all channels
    return DATA 

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
            values = get_reading()
            # Send light data
            data_msg = {
                "type": "data",
                "max": 65535,
                "values": values
            }
            ws.send(json.dumps(data_msg))
            print(f"Sent to server: {len(values)} channels")
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


