# -*- coding: utf-8 -*-
"""Zemin dokuları: hazır PNG'ler (textures/ klasörü) + isteğe bağlı kendi görüntü dosyanız.
Bağımlılıksız: PNG'yi zlib + numpy ile okur. Doku doğrusal renk uzayında tutulur, mip piramidi çıkarılır
(uzaktaki zemin benekli/moire olmasın diye üçlü doğrusal süzme yapılır)."""
import os
import zlib
import struct
import numpy as np

# (anahtar, ad, dosya, mod, otomatik genişlik)   mod: "repeat" = kesintisiz, "mirror" = kenarlar aynalanarak tekrarlanır;
# otomatik genişlik: görüntünün zemindeki genişliği = sahne köşegeni x bu sayı (Doku boyu = Otomatik iken)
PRESETS = [
    ("travertin", "Travertin karo", "travertin.png", "repeat", 0.5),
    ("cakil", "Çakıl", "cakil.png", "mirror", 0.2),
    ("mermer", "Beyaz mermer", "mermer.png", "mirror", 0.9),
    ("tas_duvar", "Taş kaplama", "tas_duvar.png", "mirror", 0.5),
    ("terrakota", "Terrakota karo", "terrakota.png", "repeat", 0.7),
    ("siva", "Sıva (kaba)", "siva.png", "repeat", 0.25),
    ("ahsap", "Ahşap", "ahsap.png", "mirror", 0.5),
]
_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "textures")
_CACHE = {}
_CUSTOM = {}          # yol -> (uint8 dizi, mod)


def read_png(path):
    """8 bit, interlace'siz PNG -> (h, w, 3) uint8."""
    with open(path, "rb") as f:
        data = f.read()
    pos, idat, w = 8, [], 0
    while pos < len(data):
        n, typ = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + n]
        if typ == b"IHDR":
            w, h, depth, ctype, _c, _f, inter = struct.unpack(">IIBBBBB", chunk)
            if depth != 8 or inter != 0 or ctype not in (0, 2, 4, 6):
                raise ValueError("desteklenmeyen PNG biçimi (8 bit, interlace'siz olmalı)")
        elif typ == b"IDAT":
            idat.append(chunk)
        pos += 12 + n
    ch = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    raw = np.frombuffer(zlib.decompress(b"".join(idat)), dtype=np.uint8)
    stride = w * ch
    raw = raw.reshape(h, stride + 1)
    out = np.zeros((h, stride), dtype=np.uint8)
    prev = np.zeros(stride, dtype=np.int32)
    for y in range(h):
        ft, line = int(raw[y, 0]), raw[y, 1:].astype(np.int32)
        if ft == 0:
            cur = line
        elif ft == 2:
            cur = (line + prev) & 255
        elif ft == 1:
            cur = line.copy()
            for i in range(ch, stride):
                cur[i] = (cur[i] + cur[i - ch]) & 255
        elif ft == 3:
            cur = line.copy()
            for i in range(stride):
                left = cur[i - ch] if i >= ch else 0
                cur[i] = (cur[i] + ((left + prev[i]) >> 1)) & 255
        else:                                                     # Paeth
            cur = line.copy()
            for i in range(stride):
                a = cur[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                cur[i] = (cur[i] + pr) & 255
        out[y] = cur
        prev = cur
    img = out.reshape(h, w, ch)
    if ch <= 2:
        img = np.repeat(img[:, :, :1], 3, axis=2)
    return img[:, :, :3].copy()


class Texture(object):
    """Kesintisiz tekrarlanan doku + mip piramidi (doğrusal renk, float32)."""

    def __init__(self, rgb8, mode="repeat"):
        a = (np.asarray(rgb8, dtype=np.float32) / 255.0) ** 2.2
        self.rel = 0.4                                            # otomatik genişlik (sahne köşegeni oranı)
        self.base_w = a.shape[1]                                  # orijinal görüntü genişliği (texel)
        self.span = 2 if mode == "mirror" else 1                  # bir tekrar kaç görüntü genişliğinde
        if mode == "mirror":                                      # 2x2 aynalı karo -> kenar çizgisi olmaz
            a = np.concatenate([a, a[:, ::-1]], axis=1)
            a = np.concatenate([a, a[::-1]], axis=0)
        self.levels = [a]
        while min(self.levels[-1].shape[:2]) > 2:
            b = self.levels[-1]
            h2, w2 = b.shape[0] // 2 * 2, b.shape[1] // 2 * 2
            b = b[:h2, :w2]
            self.levels.append((b[0::2, 0::2] + b[1::2, 0::2] + b[0::2, 1::2] + b[1::2, 1::2]) * 0.25)
        self.h, self.w = a.shape[:2]
        self.aspect = self.h / float(self.w)

    def _bilinear(self, lv, u, v, idx):
        t = self.levels[lv]
        h, w = t.shape[:2]
        x = u[idx] * w - 0.5
        y = v[idx] * h - 0.5
        x0, y0 = np.floor(x), np.floor(y)
        fx, fy = (x - x0)[:, None], (y - y0)[:, None]
        x0, y0 = x0.astype(np.int64), y0.astype(np.int64)
        x1, y1 = (x0 + 1) % w, (y0 + 1) % h
        x0, y0 = x0 % w, y0 % h
        return ((t[y0, x0] * (1 - fx) + t[y0, x1] * fx) * (1 - fy) + (t[y1, x0] * (1 - fx) + t[y1, x1] * fx) * fy)

    def sample(self, u, v, lod):
        """u,v: doku koordinatı (1.0 = tüm doku, tekrarlı); lod: mip düzeyi (kesirli). Döner (n,3) doğrusal renk."""
        u = u - np.floor(u)
        v = v - np.floor(v)
        n = len(u)
        out = np.zeros((n, 3), dtype=np.float64)
        top = len(self.levels) - 1
        lod = np.clip(lod, 0.0, float(top))
        l0 = np.minimum(np.floor(lod).astype(np.int64), top)
        fr = lod - l0
        for lv in np.unique(l0):
            idx = np.nonzero(l0 == lv)[0]
            lo = self._bilinear(int(lv), u, v, idx)
            if lv < top:
                hi = self._bilinear(int(lv) + 1, u, v, idx)
                f = fr[idx][:, None]
                lo = lo * (1 - f) + hi * f
            out[idx] = lo
        return out


def register_custom(path, rgb8, mode="mirror"):
    """Arayüzün (QImage ile) okuduğu kendi görüntüyü kaydeder; ayarlarda doku adı olarak yol kullanılır."""
    _CUSTOM[path] = (np.ascontiguousarray(rgb8[:, :, :3], dtype=np.uint8), mode)
    _CACHE.pop(path, None)


def load(key):
    """Anahtar (hazır doku adı) ya da kayıtlı özel yol -> Texture; bulunamazsa None."""
    if not key:
        return None
    if key in _CACHE:
        return _CACHE[key]
    tex = None
    if key in _CUSTOM:
        arr, mode = _CUSTOM[key]
        tex = Texture(arr, mode)
    else:
        for k, _name, fn, mode, rel in PRESETS:
            if k == key:
                p = os.path.join(_DIR, fn)
                if os.path.isfile(p):
                    tex = Texture(read_png(p), mode)
                    tex.rel = rel
                break
    _CACHE[key] = tex
    return tex
