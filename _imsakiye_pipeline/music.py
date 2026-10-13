"""Original score for the promo: 100 BPM, D Hijaz, plucked-string arpeggios, frame drum, pads."""
import sys, wave
import numpy as np

SR = 44100
DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 29.4
OUT = sys.argv[2] if len(sys.argv) > 2 else "music.wav"
BEAT = 0.6
N = int(DUR * SR)
L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(7)

def hz(m): return 440 * 2 ** ((m - 69) / 12)
def add(sig, start, pan=0.0, gain=1.0):
    i = int(start * SR)
    if i >= N: return
    sig = sig[: N - i] * gain
    L[i:i + len(sig)] += sig * np.sqrt((1 - pan) / 2) * 1.414
    R[i:i + len(sig)] += sig * np.sqrt((1 + pan) / 2) * 1.414

def pluck(freq, length=1.6, bright=0.5):
    """Karplus-Strong plucked string (oud-like)."""
    n = int(length * SR); p = int(SR / freq)
    buf = rng.uniform(-1, 1, p)
    # soften the excitation
    for _ in range(2): buf = 0.5 * (buf + np.roll(buf, 1))
    out = np.empty(n); idx = 0
    for k in range(n):
        out[k] = buf[idx]
        nxt = (idx + 1) % p
        buf[idx] = 0.996 * (bright * buf[idx] + (1 - bright) * buf[nxt]) if bright < 1 else 0.996 * buf[idx]
        buf[idx] = 0.996 * 0.5 * (buf[idx] + buf[nxt]) * 1.0 + 0 * bright
        idx = nxt
    env = np.minimum(1, np.arange(n) / (0.002 * SR))
    return out * env

def pad(midis, length, att=1.2, rel=1.4):
    t = np.arange(int(length * SR)) / SR
    s = np.zeros_like(t)
    for m in midis:
        f = hz(m)
        for det in (-0.12, 0.12):
            ff = f * 2 ** (det / 12)
            s += np.sin(2 * np.pi * ff * t) + 0.18 * np.sin(2 * np.pi * 2 * ff * t) + 0.06 * np.sin(2 * np.pi * 3 * ff * t)
    env = np.minimum(1, t / att) * np.minimum(1, (length - t) / rel)
    return s * np.clip(env, 0, 1) / (len(midis) * 2)

def doum(length=0.7):
    t = np.arange(int(length * SR)) / SR
    f = 55 + 45 * np.exp(-t * 18)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * np.exp(-t * 6.5) + rng.normal(0, 1, len(t)) * np.exp(-t * 90) * 0.15)

def tek(length=0.18):
    t = np.arange(int(length * SR)) / SR
    n = rng.normal(0, 1, len(t))
    n = n - np.concatenate([[0], n[:-1]])          # crude highpass
    return n * np.exp(-t * 38) * 0.25 + np.sin(2 * np.pi * 420 * t) * np.exp(-t * 45) * 0.25

def noise_sweep(length, rise=True):
    t = np.arange(int(length * SR)) / SR
    n = rng.normal(0, 1, len(t))
    # moving-average lowpass with time-varying width
    out = np.zeros_like(n); acc = 0.0
    for k in range(len(n)):
        a = 0.02 + 0.5 * (t[k] / length if rise else 1 - t[k] / length) ** 2
        acc += a * (n[k] - acc); out[k] = acc
    env = (t / length) ** 2 if rise else np.exp(-t * 6)
    return out * env

# D Hijaz: D Eb F# G A Bb C
chords = [[50, 57, 62, 66], [51, 58, 63, 67], [50, 57, 62, 66], [48, 55, 60, 63]]   # D, Eb, D, Cm
arps = [[62, 66, 69, 74, 69, 66, 62, 66], [63, 67, 70, 75, 70, 67, 63, 67],
        [62, 66, 69, 74, 72, 70, 69, 66], [60, 63, 67, 72, 70, 67, 66, 63]]
BAR = BEAT * 4
nbars = int(DUR / BAR) + 1
END = float(sys.argv[3]) if len(sys.argv) > 3 else 24.0
CALM = len(sys.argv) > 4 and sys.argv[4] == 'calm'

for b in range(nbars):
    t0 = b * BAR
    ci = b % 4
    if t0 < END:
        add(pad(chords[ci], BAR + 1.4), t0, gain=0.55)
        add(pad([chords[ci][0] - 12], BAR + 0.8, att=0.05, rel=0.6), t0, gain=0.5)   # bass
        if b >= 1:
            for s, m in enumerate(arps[ci]):
                add(pluck(hz(m), 1.4), t0 + s * BEAT / 2, pan=(-0.35 if s % 2 else 0.35), gain=0.33 if b >= 2 else 0.22)
        if b >= 2 and not CALM:
            for beat in range(4):
                tb = t0 + beat * BEAT
                if beat in (0, 2): add(doum(), tb, gain=0.55)
                add(tek(), tb + BEAT / 2, pan=0.2, gain=0.5)
                if beat == 3: add(tek(), tb + BEAT * 0.75, pan=-0.2, gain=0.35)

# transitions: soft whoosh before each bar change
for b in range(1, int(END / BAR) + 1):
    add(noise_sweep(0.5) * 0.05, b * BAR - 0.5, gain=1.0)
# riser into the end card + impact
add(noise_sweep(1.8) * 0.14, END - 1.8)
add(doum(1.8) * 1.4, END)
add(pad([38, 50, 57, 62, 66], DUR - END + 0.2, att=0.05, rel=2.6), END, gain=0.9)
for s, m in enumerate([74, 69, 66, 62]):
    add(pluck(hz(m), 2.5), END + 0.6 + s * BEAT, pan=0.3 * (-1) ** s, gain=0.4)

# simple stereo reverb
ir_len = int(1.3 * SR)
irt = np.arange(ir_len) / SR
def ir(seed):
    r = np.random.default_rng(seed).normal(0, 1, ir_len) * np.exp(-irt * 4.2)
    r[: int(0.012 * SR)] = 0
    return r / np.sqrt(np.sum(r ** 2))
def conv(x, h):
    n = len(x) + len(h) - 1; F = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, F) * np.fft.rfft(h, F), F)[: len(x)]
L = L + 0.28 * conv(L, ir(1)); R = R + 0.28 * conv(R, ir(2))

t = np.arange(N) / SR
fade = np.clip(t / 0.4, 0, 1) * np.clip((DUR - t) / 1.2, 0, 1)
L *= fade; R *= fade
peak = max(np.abs(L).max(), np.abs(R).max())
L = np.tanh(L / peak * 1.3) * 0.85; R = np.tanh(R / peak * 1.3) * 0.85
pcm = (np.stack([L, R], 1) * 32767).astype(np.int16)
with wave.open(OUT, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print(OUT)
