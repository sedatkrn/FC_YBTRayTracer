# -*- coding: utf-8 -*-
"""Ortam aydınlatması (HDRI / gökyüzü): equirectangular (enlem-boylam) harita, saf numpy.

* Radiance .hdr (RGBE, RLE) okuyucu; PNG/JPG gibi sıradan görüntüler de olur (doğrusallaştırılır, dinamik aralığı dardır).
* Hazır prosedürel gökyüzü: gradyan + güneş çevresi parıltısı + zemin rengi; güneş ayrı bir yön ışığıdır.
* Harita Z-yukarı dünya koordinatlarında okunur: u = boylam (atan2(y, x) + dönme), v = 0.5 - enlem/pi (üst satır = yukarı).
* Güneş: haritadaki çok parlak küçük bölge otomatik ayrılıp doğrusal (gölgeli) ışığa çevrilir; haritadan çıkarılır (ışın örneklemesinde
  gürültü yapmasın). Pozlama: gökyüzünün yukarı bakan yüzeye verdiği ışık sabit bir düzeye normalleştirilir (farklı HDRI'lar karşılaştırılabilir).
* Işık birimi: render'ın "lit" değeri (yüzeye gelen ışık / pi); beyaz yüzey için 1 = tam beyaz.
"""
import os
import re
import numpy as np

SKY_UP = 0.45
SUN_CAP = 1.0

# SH9 (irradiance/pi) evrişim katsayıları: l=0,1,2
_A = (1.0, 2.0 / 3.0, 0.25)


# ------------------------------------------------------------------ dosya okuma
def read_hdr(path):
    """Radiance .hdr -> (H,W,3) float32 doğrusal. Yeni RLE ve düz (sıkıştırmasız) biçimleri okur."""
    with open(path, "rb") as f:
        data = f.read()
    pos = 0
    if not data.startswith(b"#?"):
        raise ValueError("Radiance .hdr değil")
    # başlık: boş satıra kadar
    while True:
        nl = data.index(b"\n", pos)
        line = data[pos:nl]
        pos = nl + 1
        if line.strip() == b"":
            break
    nl = data.index(b"\n", pos)
    res = data[pos:nl].decode("ascii", "ignore").split()
    pos = nl + 1
    if len(res) != 4:
        raise ValueError("çözünürlük satırı okunamadı")
    ys, h, xs, w = res[0], int(res[1]), res[2], int(res[3])
    out = np.zeros((h, w, 4), dtype=np.uint8)
    for y in range(h):
        if pos + 4 > len(data):
            raise ValueError("beklenmedik dosya sonu")
        b0, b1, b2, b3 = data[pos], data[pos + 1], data[pos + 2], data[pos + 3]
        if b0 == 2 and b1 == 2 and (b2 & 0x80) == 0 and ((b2 << 8) | b3) == w and 8 <= w < 32768:
            pos += 4
            for c in range(4):
                x = 0
                row = out[y, :, c]
                while x < w:
                    cnt = data[pos]
                    pos += 1
                    if cnt > 128:
                        cnt -= 128
                        row[x:x + cnt] = data[pos]
                        pos += 1
                    else:
                        row[x:x + cnt] = np.frombuffer(data, dtype=np.uint8, count=cnt, offset=pos)
                        pos += cnt
                    x += cnt
        else:                                                    # düz RGBE
            raw = np.frombuffer(data, dtype=np.uint8, count=4 * w, offset=pos).reshape(w, 4)
            out[y] = raw
            pos += 4 * w
    e = out[:, :, 3].astype(np.int32)
    f = np.where(e > 0, np.ldexp(1.0, e - 136), 0.0).astype(np.float32)
    rgb = out[:, :, :3].astype(np.float32) * f[:, :, None]
    if ys == "+Y":
        rgb = rgb[::-1]
    if xs == "-X":
        rgb = rgb[:, ::-1]
    return np.ascontiguousarray(rgb)


def read_ldr(path):
    """Sıradan görüntü -> doğrusal float (sRGB ~2,2). Qt ile okunur; dinamik aralık 0..1 ile sınırlı."""
    from .textures import load_image_file
    a = load_image_file(path, maxdim=2048).astype(np.float32) / 255.0
    return a ** 2.2


def _shrink(a, max_w):
    while a.shape[1] > max_w and a.shape[1] % 2 == 0 and a.shape[0] % 2 == 0:
        a = (a[0::2, 0::2] + a[1::2, 0::2] + a[0::2, 1::2] + a[1::2, 1::2]) * 0.25
    if a.shape[1] > max_w:                                       # 2'ye bölünmeyen boyut: en yakın örnekleme
        ys = np.linspace(0, a.shape[0] - 1, max_w // 2).astype(int)
        xs = np.linspace(0, a.shape[1] - 1, max_w).astype(int)
        a = a[ys][:, xs]
    return np.ascontiguousarray(a, dtype=np.float32)


# ------------------------------------------------------------------ yardımcılar
def _dirs_grid(h, w):
    """(h,w,3) birim yön, (h,1) katı açı. Satır 0 = yukarı; u=0.5 -> +X yönü (boylam 0)."""
    lat = (0.5 - (np.arange(h) + 0.5) / h) * np.pi
    lon = ((np.arange(w) + 0.5) / w - 0.5) * 2.0 * np.pi
    cl = np.cos(lat)[:, None]
    d = np.stack([cl * np.cos(lon)[None, :], cl * np.sin(lon)[None, :], np.broadcast_to(np.sin(lat)[:, None], (h, w))], axis=2)
    dom = (2.0 * np.pi / w) * (np.pi / h) * cl
    return d, dom


def _sh9_basis(d):
    x, y, z = d[..., 0], d[..., 1], d[..., 2]
    return np.stack([0.282095 + 0 * x, 0.488603 * y, 0.488603 * z, 0.488603 * x, 1.092548 * x * y, 1.092548 * y * z,
                     0.315392 * (3.0 * z * z - 1.0), 1.092548 * x * z, 0.546274 * (x * x - y * y)], axis=-1)


def _lum(a):
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


class Env(object):
    """Ortam haritası + SH9 + (varsa) güneş. k: poz çarpanı (normalleştirme x kullanıcı yoğunluğu ayrı uygulanır)."""

    def __init__(self, rgb, sun=None, auto_sun=True, name=""):
        a = _shrink(np.asarray(rgb, dtype=np.float32), 2048)
        a = np.maximum(np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0), 0.0)
        self.name = name
        self.sun = None
        if sun is None and auto_sun:
            a, sun = self._split_sun(a)
        self.sun_raw = sun
        # normalleştirme: gökyüzü (güneşsiz) yukarı bakan yüzeye SKY_UP kadar ışık versin
        d8, dom8 = _dirs_grid(32, 64)
        s8 = _shrink(a, 64) if a.shape[1] >= 64 else a
        if s8.shape[:2] != (32, 64):
            ys = np.linspace(0, a.shape[0] - 1, 32).astype(int)
            xs = np.linspace(0, a.shape[1] - 1, 64).astype(int)
            s8 = a[ys][:, xs]
        coef = np.einsum("hwc,hwk->kc", s8 * dom8[:, :, None], _sh9_basis(d8)).astype(np.float64)   # (9,3)
        self.sh = coef
        up = self.irradiance(np.array([[0.0, 0.0, 1.0]]))[0]
        norm = SKY_UP / max(float(_lum(up)), 1e-4)
        self.k = float(norm)
        self.img = a * np.float32(norm)
        self.levels = [self.img]
        while min(self.levels[-1].shape[:2]) > 8:
            b = self.levels[-1]
            h2, w2 = b.shape[0] // 2 * 2, b.shape[1] // 2 * 2
            b = b[:h2, :w2]
            self.levels.append((b[0::2, 0::2] + b[1::2, 0::2] + b[0::2, 1::2] + b[1::2, 1::2]) * 0.25)
        self.coef = coef * norm
        if sun is not None:
            p = np.array(sun["power"], dtype=np.float64) * norm
            lp = float(_lum(p))
            if lp > SUN_CAP:
                p = p * (SUN_CAP / lp)
            self.sun = dict(dir=np.array(sun["dir"], dtype=np.float64), power=p)
        h, w = self.img.shape[:2]
        ce, se = np.cos(np.radians(6.0)), np.sin(np.radians(6.0))                 # ufkun hemen üstü (tam ufuk çizgisi zemin/gökyüzü sınırında koyu çıkabilir)
        hz = np.array([[ce * np.cos(t), ce * np.sin(t), se] for t in np.linspace(0, 2 * np.pi, 16, endpoint=False)])
        self.horizon = self.lookup(hz).mean(0)                    # ufuk rengi (zemin sisi için)

    # -- güneşi ayır
    @staticmethod
    def _split_sun(a):
        h, w = a.shape[:2]
        sw = 1024
        s = _shrink(a, sw) if w > sw else a
        sh_, sw_ = s.shape[:2]
        d, dom = _dirs_grid(sh_, sw_)
        lum = _lum(s)
        mean = float(np.mean(lum))
        med = float(np.median(lum))
        iy, ix = np.unravel_index(int(np.argmax(lum)), lum.shape)
        peak = float(lum[iy, ix])
        if peak < 8.0 or peak < 25.0 * max(med, 1e-6) or peak < 4.0 * mean:
            return a, None                                         # güneş yok (bulutlu/stüdyo/iç mekân haritası)
        pd = d[iy, ix]
        ang = np.arccos(np.clip((d * pd).sum(2), -1.0, 1.0))
        thr = max(0.02 * peak, 6.0 * med)
        reg = (ang < np.radians(12.0)) & (lum > thr)
        e_rgb = (s * dom[:, :, None] * reg[:, :, None]).sum((0, 1))
        if float(_lum(e_rgb)) <= 0.0:
            return a, None
        wdir = (d * (lum * dom * reg)[:, :, None]).sum((0, 1))
        wdir = wdir / max(np.linalg.norm(wdir), 1e-12)
        # tam çözünürlükte bölgeyi halka ortalamasıyla doldur
        dfull, _domf = _dirs_grid(h, w)
        angf = np.arccos(np.clip((dfull * wdir).sum(2), -1.0, 1.0))
        ring = (angf >= np.radians(12.0)) & (angf < np.radians(20.0))
        fill = a[ring].mean(0) if ring.any() else np.full(3, med)
        regf = (angf < np.radians(12.0)) & (_lum(a) > thr)
        b = a.copy()
        b[regf] = np.minimum(b[regf], fill)
        return b, dict(dir=wdir, power=e_rgb / np.pi)

    # -- örnekleme
    def irradiance(self, n):
        """n (m,3) -> yüzeye gelen gökyüzü ışığı / pi, (m,3) (güneş hariç, görünürlük yok). Normalleştirme coef'te değil: ham coef üzerinden."""
        B = _sh9_basis(n)                                          # (m,9)
        wgt = np.array([_A[0], _A[1], _A[1], _A[1], _A[2], _A[2], _A[2], _A[2], _A[2]])
        return np.maximum((B * wgt) @ self.sh, 0.0)

    def sh_light(self, n):
        return self.irradiance(n) * self.k

    def lookup(self, d, level=0.0, rot=0.0):
        """Yön (m,3) -> radyans (m,3) (normalleştirilmiş, yoğunluk uygulanmamış). rot: derece (boylam kaydırma)."""
        d = np.asarray(d, dtype=np.float64)
        lon = np.arctan2(d[:, 1], d[:, 0]) / (2.0 * np.pi) + 0.5 - rot / 360.0
        lat = np.arcsin(np.clip(d[:, 2], -1.0, 1.0))
        u = lon - np.floor(lon)
        v = np.clip(0.5 - lat / np.pi, 0.0, 1.0)
        top = len(self.levels) - 1
        lv = float(min(max(level, 0.0), top))
        l0 = int(np.floor(lv))
        f = lv - l0
        out = self._bil(l0, u, v)
        if f > 1e-3 and l0 < top:
            out = out * (1.0 - f) + self._bil(l0 + 1, u, v) * f
        return out

    def _bil(self, lv, u, v):
        t = self.levels[lv]
        h, w = t.shape[:2]
        x = u * w - 0.5
        y = v * h - 0.5
        x0 = np.floor(x)
        y0 = np.floor(y)
        fx = (x - x0)[:, None]
        fy = (y - y0)[:, None]
        x0 = x0.astype(np.int64)
        y0 = y0.astype(np.int64)
        x1 = (x0 + 1) % w
        x0 = x0 % w
        y1 = np.clip(y0 + 1, 0, h - 1)
        y0 = np.clip(y0, 0, h - 1)
        return (t[y0, x0] * (1 - fx) + t[y0, x1] * fx) * (1 - fy) + (t[y1, x0] * (1 - fx) + t[y1, x1] * fx) * fy


# ------------------------------------------------------------------ hazır gökyüzü ve yükleme
def sky_env(sun_elev=45.0, sun_az=135.0, glow=True):
    """Prosedürel gökyüzü (512x256): zirve maviden ufukta açık maviye, altta zemin; güneş çevresinde yumuşak parıltı. Güneş ayrı ışık."""
    h, w = 256, 512
    d, _ = _dirs_grid(h, w)
    z = d[:, :, 2]
    t = np.clip(z, 0.0, 1.0) ** 0.55
    zen = np.array([0.20, 0.42, 0.90])
    hor = np.array([0.72, 0.84, 1.00])
    sky = hor[None, None, :] * (1.0 - t[:, :, None]) + zen[None, None, :] * t[:, :, None]
    gnd = np.array([0.30, 0.28, 0.25])
    g = np.clip((-z + 0.02) / 0.10, 0.0, 1.0)[:, :, None]
    img = sky * (1.0 - g) + gnd[None, None, :] * g * 0.7
    el, az = np.radians(sun_elev), np.radians(sun_az)
    sd = np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])
    if glow:
        ang = np.arccos(np.clip((d * sd).sum(2), -1.0, 1.0))
        gl = np.exp(-(ang / np.radians(9.0)) ** 2) * 1.6 + np.exp(-(ang / np.radians(40.0)) ** 2) * 0.35
        img = img + gl[:, :, None] * np.array([1.0, 0.9, 0.72])[None, None, :] * (sd[2] > -0.05)
    # güneş gücü: 1,0 ~ gökyüzüne göre belirgin; normalleştirme Env içinde
    e = np.array([1.0, 0.93, 0.80]) * 6.0 * max(np.sin(el), 0.0) ** 0.6
    return Env(img.astype(np.float32), sun=dict(dir=sd, power=e) if sd[2] > 0.02 else None, name="Gökyüzü")


_CACHE = {}


def _disk_cache(path, reader):
    """Büyük HDR'lerin (8k+) ilk okunması yavaş: küçültülmüş hali geçici klasöre .npy olarak saklanır, sonraki açılış anlık."""
    import hashlib
    import tempfile
    try:
        st = os.stat(path)
        key = hashlib.md5(("%s|%d|%d" % (path, st.st_size, int(st.st_mtime))).encode("utf-8", "ignore")).hexdigest()
        cf = os.path.join(tempfile.gettempdir(), "ybt_env_%s.npy" % key)
    except OSError:
        return reader(path)
    if os.path.isfile(cf):
        try:
            return np.load(cf)
        except Exception:
            pass
    arr = _shrink(np.asarray(reader(path), dtype=np.float32), 2048)
    try:
        np.save(cf, arr)
    except Exception:
        pass
    return arr


def get_env(S):
    """Ayarlardan (settings) ortam nesnesi; kapalıysa None. Dosya/parametre aynıysa önbellekten."""
    mode = str(getattr(S, "ENV_MODE", "off"))
    if mode == "off":
        return None
    if mode == "sky":
        key = ("sky", round(float(S.ENV_SUN_ELEV), 2), round(float(S.ENV_SUN_AZ), 2))
        if key not in _CACHE:
            _CACHE.clear()
            _CACHE[key] = sky_env(float(S.ENV_SUN_ELEV), float(S.ENV_SUN_AZ))
        return _CACHE[key]
    path = str(getattr(S, "ENV_FILE", "") or "")
    if not path or not os.path.isfile(path):
        return None
    try:
        mt = os.path.getmtime(path)
    except OSError:
        mt = 0
    key = ("hdri", path, mt)
    if key not in _CACHE:
        _CACHE.clear()
        try:
            if path.lower().endswith(".hdr") or path.lower().endswith(".pic"):
                arr = _disk_cache(path, read_hdr)
            else:
                arr = read_ldr(path)
        except Exception:
            return None
        _CACHE[key] = Env(arr, name=os.path.basename(path))
    return _CACHE[key]
