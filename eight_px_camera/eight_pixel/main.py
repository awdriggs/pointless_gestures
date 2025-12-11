import board
import busio
import digitalio
import time
from adafruit_mcp3xxx.mcp3008 import MCP3008
from adafruit_mcp3xxx.analog_in import AnalogIn

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

print("MCP3008 Phototransistor Test")
print("Reading all 8 channels")
print("16-bit resolution (0-65535)")
print("Press Ctrl-C to stop")
print()

while True:
    print("-" * 80)
    for i, chan in enumerate(channels):
        # Read raw value (0-65535, 16-bit)
        raw_value = chan.value

        # Read voltage (0-3.3V)
        voltage = chan.voltage

        # Calculate percentage
        percentage = (raw_value / 65535) * 100

        print(f"CH{i} - Raw: {raw_value:5d} | Voltage: {voltage:.3f}V | Light: {percentage:.1f}%")

    time.sleep(0.5)
