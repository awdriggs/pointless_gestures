import board
import busio
import time
import random
from adafruit_ht16k33.segments import Seg7x4

i2c = busio.I2C(board.GP5, board.GP4)
display = Seg7x4(i2c)
display.brightness = 1.0

DISPLAY_DELAY = 0.5

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

valid_combinations = [c for c in range(128) if c not in DO_NOT_DISPLAY]

def shuffle(lst):
    for i in range(len(lst) - 1, 0, -1):
        j = random.randint(0, i)
        lst[i], lst[j] = lst[j], lst[i]

# Each digit gets its own shuffled deck and index
decks = []
indices = []
for _ in range(4):
    deck = list(valid_combinations)
    shuffle(deck)
    decks.append(deck)
    indices.append(0)

# Draw initial state
for d in range(4):
    display.set_digit_raw(d, decks[d][indices[d]])

# Cycle order: 3, 2, 1, 0, 3, 2, 1, 0, ...
order = [3, 2, 1, 0]
step = 0

while True:
    time.sleep(DISPLAY_DELAY)

    d = order[step % 4]
    indices[d] = (indices[d] + 1) % len(decks[d])
    if indices[d] == 0:
        shuffle(decks[d])
    display.set_digit_raw(d, decks[d][indices[d]])

    step += 1
