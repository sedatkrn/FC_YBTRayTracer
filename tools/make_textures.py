# -*- coding: utf-8 -*-
"""Dikişsiz (periyodik) dokuları üretir: python tools/make_textures.py  -> ybt_raytracer/textures/*.png (256x256, 8 bit RGB)."""
import os
import numpy as np
from PIL import Image

N = 256
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ybt_raytracer", "textures")
rng = np.random.default_rng(7)


def pnoise(period, seed):
    """Periyodik (kenarları örtüşen) değer gürültüsü, 0..1; period hücreli."""
    r = np.random.default_rng(seed)
    g = r.random((period, period))
    xs = np.linspace(0, period, N, endpoint=False)
    i = np.floor(xs).astype(int)
    f = xs - i
    f = f * f * (3 - 2 * f)
    i1 = (i + 1) % period
    a = g[i][:, i] * (1 - f)[None, :] + g[i][:, i1] * f[None, :]
    b = g[i1][:, i] * (1 - f)[None, :] + g[i1][:, i1] * f[None, :]
    return a * (1 - f)[:, None] + b * f[:, None]


def fbm(base, octaves, seed):
    out, amp, tot = np.zeros((N, N)), 1.0, 0.0
    for o in range(octaves):
        out += amp * pnoise(base * 2 ** o, seed + o)
        tot += amp
        amp *= 0.5
    return out / tot


def save(name, rgb):
    a = np.clip(rgb, 0, 1)
    Image.fromarray((a * 255 + 0.5).astype(np.uint8)).save(os.path.join(OUT, name))


def tint(v, c):
    return v[..., None] * np.array(c)[None, None, :]


# beton
v = 0.55 + 0.30 * (fbm(4, 5, 10) - 0.5) + 0.10 * (fbm(32, 2, 20) - 0.5)
pores = (pnoise(48, 30) > 0.93).astype(float) * 0.18
save("beton.png", tint(np.clip(v - pores, 0, 1), (0.80, 0.80, 0.78)))

# karbon fiber: 2x2 dimi örgü
y, x = np.mgrid[0:N, 0:N]
cell = 16
cx, cy = (x // cell), (y // cell)
tw = ((cx + cy) // 2) % 2                      # dimi: çaprazlama yön değişir
along = np.where(tw == 0, (x % cell) / cell, (y % cell) / cell)
shade = 0.30 + 0.35 * np.sin(np.pi * along) ** 1.5
shade *= np.where(((cx + cy) % 2) == 0, 1.0, 0.72)
shade += 0.05 * (fbm(64, 1, 40) - 0.5)
save("karbon.png", tint(np.clip(shade, 0, 1), (0.85, 0.87, 0.92)))

# tuğla
bh, bw, mortar = 32, 64, 4
out = np.zeros((N, N, 3))
out[:] = (0.62, 0.60, 0.56)
for r in range(N // bh):
    off = (bw // 2) if r % 2 else 0
    for c in range(-1, N // bw + 1):
        x0 = c * bw + off
        col = np.array((0.58, 0.24, 0.17)) * (0.78 + 0.35 * rng.random()) * np.array((1.0, 0.95 + 0.1 * rng.random(), 0.95 + 0.1 * rng.random()))
        for yy in range(r * bh + mortar // 2, (r + 1) * bh - mortar // 2):
            for xx in range(x0 + mortar // 2, x0 + bw - mortar // 2):
                out[yy, xx % N] = col
grain = 0.85 + 0.30 * fbm(32, 3, 50)
save("tugla.png", out * grain[..., None])

# deri: hücresel çatlak deseni
pts = rng.random((60, 2)) * N
yy, xx = np.mgrid[0:N, 0:N]
d1 = np.full((N, N), 1e9)
d2 = np.full((N, N), 1e9)
for px, py in pts:
    for ox in (-N, 0, N):
        for oy in (-N, 0, N):
            d = np.hypot(xx - (px + ox), yy - (py + oy))
            nd1 = np.minimum(d1, d)
            d2 = np.minimum(d2, np.maximum(d1, d))
            d1 = nd1
edge = np.clip((d2 - d1) / 5.0, 0, 1)
v = 0.50 + 0.35 * edge ** 0.6 + 0.08 * (fbm(24, 3, 60) - 0.5)
save("deri.png", tint(np.clip(v, 0, 1), (0.52, 0.30, 0.17)))

# fırçalı metal: yatay çiziklenmiş gürültü
r = np.random.default_rng(80)
line = r.random((N, 1))
streak = np.zeros((N, N))
for k, sc in enumerate((1, 3, 9)):
    ln = np.repeat(r.random((N, 1)), N, 1)
    shift = np.fft.ifft(np.fft.fft(ln, axis=1) * np.exp(-((np.fft.fftfreq(N)[None, :] * N / (6.0 * sc)) ** 2))).real
    shift = (shift - shift.min()) / (shift.max() - shift.min() + 1e-9)
    streak += shift / (k + 1)
streak /= streak.max()
v = 0.60 + 0.28 * (streak - 0.5) + 0.04 * (pnoise(64, 90) - 0.5)
save("celik_firca.png", tint(np.clip(v, 0, 1), (0.78, 0.80, 0.84)))
print("tamam")
