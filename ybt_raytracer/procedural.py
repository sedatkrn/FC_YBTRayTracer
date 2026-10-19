# -*- coding: utf-8 -*-
"""Prosedürel dokular (saf numpy): görüntü gerektirmeyen 3B desenler.

Her desen doku uzayı koordinatı p (n,3; 1.0 = doku boyu) üzerinden 0..1 arası bir değer verir. Gürültü 3B gradyan (Perlin
benzeri) gürültüdür: UV gerekmez, nesne üzerinde dikişsizdir. Uzak yüzeylerde yüksek frekanslı katmanlar sönümlenir (footprint).
TYPES: (anahtar, Türkçe ad) listesi; arayüz bu listeyi kullanır."""
import numpy as np

TYPES = [
    ("turbulence", "Türbülans"),
    ("fractal", "Fraktal gürültü"),
    ("veins", "Damarlar"),
    ("marble", "Mermer"),
    ("wood", "Ahşap halkaları"),
    ("checker", "Dama"),
    ("grid", "Izgara"),
    ("dots", "Noktalar"),
    ("bricks", "Tuğla örgüsü"),
    ("ripples", "Dalgalar"),
]
TYPE_KEYS = tuple(k for k, _n in TYPES)

_GRAD = np.array([[1, 1, 0], [-1, 1, 0], [1, -1, 0], [-1, -1, 0], [1, 0, 1], [-1, 0, 1], [1, 0, -1], [-1, 0, -1],
                  [0, 1, 1], [0, -1, 1], [0, 1, -1], [0, -1, -1], [1, 1, 0], [-1, 1, 0], [0, -1, 1], [0, -1, -1]], dtype=np.float64)


def _ihash(ix, iy, iz, seed):
    """Tamsayı kafes noktası -> 32 bit karma (int64 dizisi)."""
    m = 0xFFFFFFFF
    h = (ix * 374761393 + iy * 668265263 + iz * 1274126177 + seed * 144665 + 1013904223) & m
    h = ((h ^ (h >> 13)) * 1274126177) & m
    h = (h ^ (h >> 16)) & m
    return h


def gnoise(p, seed=0):
    """3B gradyan gürültüsü, (n,) ~[-1, 1]."""
    i = np.floor(p)
    f = p - i
    ii = i.astype(np.int64)
    u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0)
    ux, uy, uz = u[:, 0], u[:, 1], u[:, 2]
    fx, fy, fz = f[:, 0], f[:, 1], f[:, 2]
    c = np.empty((8, len(p)))
    k = 0
    for dz in (0, 1):
        for dy in (0, 1):
            for dx in (0, 1):
                g = _GRAD[_ihash(ii[:, 0] + dx, ii[:, 1] + dy, ii[:, 2] + dz, seed) & 15]
                c[k] = g[:, 0] * (fx - dx) + g[:, 1] * (fy - dy) + g[:, 2] * (fz - dz)
                k += 1
    x00 = c[0] + (c[1] - c[0]) * ux
    x10 = c[2] + (c[3] - c[2]) * ux
    x01 = c[4] + (c[5] - c[4]) * ux
    x11 = c[6] + (c[7] - c[6]) * ux
    y0 = x00 + (x10 - x00) * uy
    y1 = x01 + (x11 - x01) * uy
    return np.clip(y0 + (y1 - y0) * uz, -1.0, 1.0)


def _fbm(p, octaves, gain, seed, foot, mode):
    """mode: 'turb' (|n| toplamı), 'fract' (işaretli toplam), 'ridge' (1-|n| kare). Çıktı 0..1 civarı. foot: doku birimiyle piksel boyu (n,)."""
    n = len(p)
    acc = np.zeros(n)
    norm = np.zeros(n)
    amp = 1.0
    fr = 1.0
    for k in range(int(octaves)):
        fade = np.clip(1.0 - fr * foot * 2.0, 0.0, 1.0)         # dalga boyu piksele yaklaşınca sön (kenar kırpılması olmasın)
        if k > 0 and not fade.any():
            break
        v = gnoise(p * fr + k * 17.31, seed + k)
        if mode == "turb":
            v = np.abs(v) * 1.7
        elif mode == "ridge":
            v = (1.0 - np.abs(v)) ** 2
        else:
            v = v * 0.5 + 0.5
        acc += amp * fade * v
        norm += amp * fade
        amp *= gain
        fr *= 2.0
    return acc / np.maximum(norm, 1e-9)


def evaluate(ptype, p, q, foot):
    """Desen değeri (n,) 0..1.
    p: doku uzayı (n,3, 1.0 = doku boyu); q: ayar sözlüğü (pfreq, pgain(small power), pcontrast, pvalue, pstripes, pseed, axis);
    foot: piksel boyu / doku boyu (n,)."""
    octv = max(1, int(q.get("pfreq", 3)))
    gain = min(max(float(q.get("ppower", 0.5)), 0.05), 0.95)
    seed = int(q.get("pseed", 0))
    stripes = max(float(q.get("pstripes", 6.0)), 0.1)
    ax = int(q.get("axis", 2))
    a_, b_ = ((1, 2), (0, 2), (0, 1))[ax]
    if ptype == "turbulence":
        v = _fbm(p * 4.0, octv, gain, seed, foot * 4.0, "turb")
    elif ptype == "fractal":
        v = _fbm(p * 4.0, octv, gain, seed, foot * 4.0, "fract")
    elif ptype == "veins":
        v = _fbm(p * 4.0, octv, gain, seed, foot * 4.0, "ridge")
    elif ptype == "marble":
        t = _fbm(p * 2.0, octv, gain, seed, foot * 2.0, "turb")
        v = 0.5 + 0.5 * np.sin(2.0 * np.pi * (p[:, ax] * stripes + 0.9 * t))
    elif ptype == "wood":
        r = np.sqrt(p[:, a_] ** 2 + p[:, b_] ** 2)
        t = _fbm(p * 2.0, octv, gain, seed, foot * 2.0, "fract")
        v = (r * stripes + 0.6 * (t - 0.5)) % 1.0
        v = 1.0 - v ** 2                                         # halkada keskin, sonra yumuşak düşüş
    elif ptype == "checker":
        s = np.floor(p * stripes).astype(np.int64)
        v = ((s[:, 0] + s[:, 1] + s[:, 2]) & 1).astype(np.float64)
    elif ptype == "grid":
        f = np.abs(((p * stripes) % 1.0) - 0.5)                  # 0.5 = çizgi, 0 = hücre ortası
        w = 0.5 - 0.06
        line = (f[:, a_] > w) | (f[:, b_] > w)
        v = line.astype(np.float64)
    elif ptype == "dots":
        c = (p * stripes) % 1.0 - 0.5
        v = (np.sqrt((c * c).sum(1)) < 0.32).astype(np.float64)
    elif ptype == "bricks":
        u = p[:, a_] * stripes * 0.5
        w = p[:, b_] * stripes
        row = np.floor(w)
        u = u + 0.5 * (row.astype(np.int64) & 1)
        fu, fv = u % 1.0, w % 1.0
        mortar = (fu < 0.06) | (fv < 0.12)
        cell = _ihash(np.floor(u).astype(np.int64), row.astype(np.int64), np.zeros(len(p), dtype=np.int64), seed)
        tone = 0.62 + 0.38 * ((cell & 255) / 255.0)
        v = np.where(mortar, 0.18, tone)
    elif ptype == "ripples":
        r = np.sqrt((p * p).sum(1))
        t = _fbm(p * 2.0, octv, gain, seed, foot * 2.0, "fract")
        v = 0.5 + 0.5 * np.sin(2.0 * np.pi * (r * stripes + 0.4 * (t - 0.5)))
    else:
        v = np.full(len(p), 0.5)
    c = float(q.get("pcontrast", 0.0))                           # % -100..100
    if c:
        v = (v - 0.5) * (1.0 + c / 100.0 * 3.0 if c > 0 else 1.0 + c / 100.0) + 0.5
    return np.clip(v, 0.0, 1.0) * min(max(float(q.get("pvalue", 1.0)), 0.0), 1.0)
