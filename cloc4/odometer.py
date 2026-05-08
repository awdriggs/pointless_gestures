import board
import busio
import time
from adafruit_ht16k33.segments import Seg7x4

i2c = busio.I2C(board.GP5, board.GP4)
display = Seg7x4(i2c)

display.brightness = 1.0

DISPLAY_DELAY = 0.2

# Bit mapping: 0=A, 1=B, 2=C, 3=D, 4=E, 5=F, 6=G
DO_NOT_DISPLAY = [
    63,   # 0: A,B,C,D,E,F
    6,    # 1: B,C
    91,   # 2: A,B,D,E,G
    79,   # 3: A,B,C,D,G
    102,  # 4: B,C,F,G
    109,  # 5: A,C,D,F,G
    125,  # 6: A,C,D,E,F,G
    7,    # 7: A,B,C
    127,  # 8: A,B,C,D,E,F,G
    111,  # 9: A,B,C,D,F,G
    39,   # looks like 7
    103
]

valid_combinations = [0] + [c for c in range(1, 128) if c not in DO_NOT_DISPLAY]

# Counter: one index per digit
counters = [0, 0, 0, 0]

def update_display():
    for digit in range(4):
        display.set_digit_raw(digit, valid_combinations[counters[digit]])

update_display()

while True:
    time.sleep(DISPLAY_DELAY)

    # Increment rightmost digit, carry left like an odometer
    for digit in range(3, -1, -1):
        counters[digit] += 1
        if counters[digit] < len(valid_combinations):
            break
        counters[digit] = 0

    update_display()
