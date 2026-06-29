import board
import busio
import time
from adafruit_as7341 import AS7341

i2c = busio.I2C(scl=board.GP15, sda=board.GP14)
sensor = AS7341(i2c)

# Match your main code settings exactly
sensor.atime = 29
sensor.astep = 599
sensor.gain = 8

READINGS_N = 10

def get_channels():
    return {
        "F1": sensor.channel_415nm,
        "F2": sensor.channel_445nm,
        "F3": sensor.channel_480nm,
        "F4": sensor.channel_515nm,
        "F5": sensor.channel_555nm,
        "F6": sensor.channel_590nm,
        "F7": sensor.channel_630nm,
        "F8": sensor.channel_680nm,
    }

def get_channels_averaged(n=READINGS_N):
    sums = {k: 0 for k in ["F1","F2","F3","F4","F5","F6","F7","F8"]}
    for _ in range(n):
        ch = get_channels()
        for k in sums:
            sums[k] += ch[k]
    return {k: v / n for k, v in sums.items()}

print("MAX_COUNTS calibration — point at brightest light source and wait")
print("Set MAX_COUNTS in code.py to the peak value shown below")
print("-" * 50)

peak = 0

while True:
    channels = get_channels_averaged()
    raw_total = sum(channels.values())

    if raw_total > peak:
        peak = raw_total
        print(f"  NEW PEAK --> {int(peak)}   (set MAX_COUNTS = {int(peak)})")
    else:
        print(f"  current: {int(raw_total):>8}   peak: {int(peak):>8}")

    time.sleep(1)
