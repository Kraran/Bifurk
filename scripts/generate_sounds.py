"""Generate original, deterministic effects with Python's standard library.

Run from any directory. No recording, external assets, or gameplay RNG is used.
"""
import math
import random
import struct
import wave
from pathlib import Path

RATE = 44100
OUT = Path(__file__).resolve().parents[1] / 'assets' / 'sounds'


def save(name, samples):
    peak = max(abs(v) for v in samples) or 1
    pcm = b''.join(struct.pack('<h', round(v / peak * 22000)) for v in samples)
    with wave.open(str(OUT / f'{name}.wav'), 'wb') as file:
        file.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        file.writeframes(pcm)


def generate():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(1982)
    page = []
    low = 0
    for i in range(int(RATE * .65)):
        t = i / RATE
        noise = rng.uniform(-1, 1)
        low = .82 * low + .18 * noise
        envelope = math.sin(math.pi * t / .65) ** 1.4
        flutter = .55 + .45 * math.sin(t * 41 + t*t*60) ** 2
        page.append((low * .8 + noise * .08) * envelope * flutter)
    save('page', page)
    dice = []
    impacts = [(.01, 1), (.09, .9), (.19, .8), (.32, .65), (.49, .45), (.67, .2)]
    for i in range(int(RATE * .85)):
        t = i / RATE
        sample = 0
        for onset, amp in impacts:
            d = t - onset
            if 0 <= d < .13:
                sample += amp * math.exp(-d*65) * (.6*rng.uniform(-1, 1)
                           + math.sin(2*math.pi*820*d) + .35*math.sin(2*math.pi*1350*d))
        dice.append(sample)
    save('dice', dice)
    clash = []
    for i in range(int(RATE * .8)):
        t = i / RATE
        strike = sum(math.sin(2*math.pi*f*t) * math.exp(-t*d) * a
                     for f, d, a in [(1230, 9, .5), (2083, 7, .4), (3371, 13, .2), (4627, 18, .1)])
        strike += rng.uniform(-1, 1) * math.exp(-t*65) * .6
        clash.append(strike * min(1, t*2000))
    save('swords', clash)


if __name__ == '__main__':
    generate()
