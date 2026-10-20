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
    ("beton", "Beton", "beton.png", "repeat", 0.4),
    ("karbon", "Karbon fiber", "karbon.png", "repeat", 0.1),
    ("tugla", "Tuğla", "tugla.png", "repeat", 0.4),
    ("deri", "Deri", "deri.png", "repeat", 0.2),
    ("celik_firca", "Fırçalı metal", "celik_firca.png", "repeat", 0.4),
    # mimari dokular (tools/import_arch_textures.py ile aktarıldı)
    ("mimari_granit1", "Granit (gri)", "mimari_granit1.png", "mirror", 0.35),
    ("mimari_granit2", "Granit (bej)", "mimari_granit2.png", "mirror", 0.35),
    ("mimari_granit_mavi", "Granit (mavi inci)", "mimari_granit_mavi.png", "mirror", 0.35),
    ("mimari_granit_siyah", "Granit (siyah)", "mimari_granit_siyah.png", "mirror", 0.35),
    ("mimari_granit_kirmizi", "Granit (kırmızı)", "mimari_granit_kirmizi.png", "mirror", 0.35),
    ("mimari_granit_yesil", "Granit (yeşil)", "mimari_granit_yesil.png", "mirror", 0.35),
    ("mimari_mermer_carrara", "Mermer (Carrara)", "mimari_mermer_carrara.png", "mirror", 0.45),
    ("mimari_mermer_botticino", "Mermer (Botticino)", "mimari_mermer_botticino.png", "mirror", 0.45),
    ("mimari_mermer_krem", "Mermer (krem)", "mimari_mermer_krem.png", "mirror", 0.45),
    ("mimari_mermer_gri", "Mermer (gri)", "mimari_mermer_gri.png", "mirror", 0.45),
    ("mimari_mermer_kirmizi", "Mermer (rosso)", "mimari_mermer_kirmizi.png", "mirror", 0.45),
    ("mimari_mermer_yesil", "Mermer (yeşil)", "mimari_mermer_yesil.png", "mirror", 0.45),
    ("mimari_kalker", "Kalker", "mimari_kalker.png", "mirror", 0.35),
    ("mimari_kumtasi", "Kumtaşı", "mimari_kumtasi.png", "mirror", 0.35),
    ("mimari_travertin_gri", "Travertin (gümüş)", "mimari_travertin_gri.png", "mirror", 0.45),
    ("mimari_kale_tasi", "Kaba taş (kale)", "mimari_kale_tasi.png", "mirror", 0.35),
    ("mimari_kesme_tas", "Kesme taş", "mimari_kesme_tas.png", "mirror", 0.35),
    ("mimari_dere_tasi", "Dere taşı", "mimari_dere_tasi.png", "mirror", 0.30),
    ("mimari_tas4", "Taş (düz)", "mimari_tas4.png", "mirror", 0.35),
    ("mimari_tugla_eski", "Tuğla (eski)", "mimari_tugla_eski.png", "mirror", 0.35),
    ("mimari_tugla_yeni", "Tuğla (yeni)", "mimari_tugla_yeni.png", "mirror", 0.35),
    ("mimari_tugla_beyaz", "Tuğla (beyaz)", "mimari_tugla_beyaz.png", "mirror", 0.35),
    ("mimari_beton_duz", "Beton (düz)", "mimari_beton_duz.png", "mirror", 0.40),
    ("mimari_beton_dokme", "Beton (dökme)", "mimari_beton_dokme.png", "mirror", 0.40),
    ("mimari_beton_dokme2", "Beton (açık gri)", "mimari_beton_dokme2.png", "mirror", 0.40),
    ("mimari_siva_kirmizi", "Sıva (kırmızı)", "mimari_siva_kirmizi.png", "mirror", 0.30),
    ("mimari_siva_sari", "Sıva (sarı)", "mimari_siva_sari.png", "mirror", 0.30),
    ("mimari_siva_guney", "Sıva (güneybatı)", "mimari_siva_guney.png", "mirror", 0.30),
    ("mimari_stuko", "Stuko", "mimari_stuko.png", "mirror", 0.30),
    ("mimari_siva_beyaz", "Sıva (dokulu beyaz)", "mimari_siva_beyaz.png", "mirror", 0.30),
    ("mimari_kaplama_sedir", "Cephe kaplama (sedir)", "mimari_kaplama_sedir.png", "mirror", 0.40),
    ("mimari_kaplama_koyu", "Cephe kaplama (koyu)", "mimari_kaplama_koyu.png", "mirror", 0.40),
    ("mimari_kaplama_acik", "Cephe kaplama (açık)", "mimari_kaplama_acik.png", "mirror", 0.40),
    ("mimari_kutuk_duvar", "Kütük duvar", "mimari_kutuk_duvar.png", "mirror", 0.40),
    ("mimari_ahsap_dis", "Ahşap (dişbudak)", "mimari_ahsap_dis.png", "mirror", 0.40),
    ("mimari_ahsap_maun", "Ahşap (maun)", "mimari_ahsap_maun.png", "mirror", 0.40),
    ("mimari_ahsap_akcaagac", "Ahşap (akçaağaç)", "mimari_ahsap_akcaagac.png", "mirror", 0.40),
    ("mimari_ahsap_mese_koyu", "Ahşap (meşe, koyu)", "mimari_ahsap_mese_koyu.png", "mirror", 0.40),
    ("mimari_ahsap_mese_acik", "Ahşap (meşe, açık)", "mimari_ahsap_mese_acik.png", "mirror", 0.40),
    ("mimari_ahsap_cam", "Ahşap (çam)", "mimari_ahsap_cam.png", "mirror", 0.40),
    ("mimari_ahsap_ceviz", "Ahşap (ceviz)", "mimari_ahsap_ceviz.png", "mirror", 0.40),
    ("mimari_ahsap_karaagac", "Ahşap (karaağaç)", "mimari_ahsap_karaagac.png", "mirror", 0.40),
    ("mimari_parke4", "Parke (1)", "mimari_parke4.png", "mirror", 0.40),
    ("mimari_parke5", "Parke (2)", "mimari_parke5.png", "mirror", 0.40),
    ("mimari_tahta_doseme", "Tahta döşeme", "mimari_tahta_doseme.png", "mirror", 0.40),
    ("mimari_seramik3", "Seramik karo", "mimari_seramik3.png", "mirror", 0.30),
    ("mimari_karo_gri", "Karo (gri)", "mimari_karo_gri.png", "mirror", 0.30),
    ("mimari_karo_kahve", "Karo (açık kahve)", "mimari_karo_kahve.png", "mirror", 0.30),
    ("mimari_karo_kirmizi", "Karo (kırmızı)", "mimari_karo_kirmizi.png", "mirror", 0.30),
    ("mimari_mozaik", "Mozaik", "mimari_mozaik.png", "mirror", 0.30),
    ("mimari_karo_beyaz", "Karo (beyaz)", "mimari_karo_beyaz.png", "mirror", 0.30),
    ("mimari_karo_mavi", "Karo (mavi)", "mimari_karo_mavi.png", "mirror", 0.30),
    ("mimari_kiremit", "Kiremit", "mimari_kiremit.png", "mirror", 0.30),
    ("mimari_cati1", "Çatı kaplama (kiremit 2)", "mimari_cati1.png", "mirror", 0.30),
    ("mimari_cati_gri", "Çatı kaplama (gri)", "mimari_cati_gri.png", "mirror", 0.30),
    ("mimari_cati_sedir", "Çatı (sedir tahta)", "mimari_cati_sedir.png", "mirror", 0.30),
    ("mimari_cati_terrakota", "Çatı (terrakota)", "mimari_cati_terrakota.png", "mirror", 0.30),
    ("mimari_bakir_eski", "Bakır sac (eskimiş)", "mimari_bakir_eski.png", "mirror", 0.40),
    ("mimari_cinko", "Çinko sac", "mimari_cinko.png", "mirror", 0.40),
    ("mimari_oluklu_sac", "Oluklu sac", "mimari_oluklu_sac.png", "mirror", 0.30),
    ("mimari_asfalt", "Asfalt", "mimari_asfalt.png", "mirror", 0.40),
    ("mimari_toprak", "Toprak", "mimari_toprak.png", "mirror", 0.40),
    ("mimari_kaldirim", "Kesme taş kaldırım", "mimari_kaldirim.png", "mirror", 0.40),
    ("mimari_tugla_yol", "Tuğla yaya yolu", "mimari_tugla_yol.png", "mirror", 0.40),
    ("mimari_hali_gri", "Halı (gri)", "mimari_hali_gri.png", "mirror", 0.20),
    ("mimari_deri3", "Deri (kahverengi)", "mimari_deri3.png", "mirror", 0.20),
    ("mimari_kumas1", "Kumaş", "mimari_kumas1.png", "mirror", 0.20),
    ("mimari_cim", "Çim", "mimari_cim.png", "mirror", 0.40),
]
_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "textures")
# Lisansı belirsiz kişisel doku arşivinden aktarılan "mimari_*" dosyalar depoya konmaz (.gitignore); yoksa listeden düşer.
PRESETS = [p for p in PRESETS if (not p[0].startswith("mimari_")) or os.path.isfile(os.path.join(_DIR, p[2]))]
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
        self.stoch = False                                        # stokastik döşeme (hex-tiling): load(key, "stochastic") açar
        self.once = (mode == "once")                              # "once": görüntü dışı etkisiz (maske render'da)
        self.clamp = mode in ("edge", "once")                     # "edge": kenar pikselleri uzar; "once": tek kez (dışı etkisiz, render'da maskelenir)
        if self.clamp:
            mode = "repeat"
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
        self.mean = self.levels[-1].reshape(-1, 3).mean(0).astype(np.float64)   # varyans korumalı karışım için ortalama renk

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

    def sample(self, u, v, lod, stoch=True):
        """u,v: doku koordinatı (1.0 = tüm doku, tekrarlı); lod: mip düzeyi (kesirli). Döner (n,3) doğrusal renk.
        stoch=False: stokastik döşeme açık olsa da düz örnekle (nesneye sığdır gibi tek görüntü kullanımları)."""
        if self.stoch and stoch and not self.clamp:
            return self._sample_hex(u, v, lod)
        return self._sample_plain(u, v, lod)

    @staticmethod
    def _hash2(ix, iy):
        a = np.sin(ix * 127.1 + iy * 311.7) * 43758.5453
        b = np.sin(ix * 269.5 + iy * 183.3) * 43758.5453
        return a - np.floor(a), b - np.floor(b)

    def _sample_hex(self, u, v, lod):
        """Stokastik döşeme (Mikkelsen hex-tiling + Heitz varyans korumalı karışım): üçgen ızgara, her köşe rastgele öteleme,
        üç örnek ağırlıkla karışır; tekrar deseni görünmez, kontrast korunur. Dikiş yok (öteleme doku periyodunun tam katı değil, doku kendi modunda sarar)."""
        x, y = u * 3.4641016, v * 3.4641016
        s0 = x
        s1 = -0.57735027 * x + 1.15470054 * y
        bx, by = np.floor(s0), np.floor(s1)
        fx, fy = s0 - bx, s1 - by
        fz = 1.0 - fx - fy
        up = fz > 0
        w1 = np.where(up, fz, -fz)
        w2 = np.where(up, fy, 1.0 - fy)
        w3 = np.where(up, fx, 1.0 - fx)
        v1 = (np.where(up, bx, bx + 1), np.where(up, by, by + 1))
        v2 = (np.where(up, bx, bx + 1), np.where(up, by + 1, by))
        v3 = (np.where(up, bx + 1, bx), np.where(up, by, by + 1))
        ws = [np.power(np.maximum(w, 1e-6), 3.0) for w in (w1, w2, w3)]
        tot = ws[0] + ws[1] + ws[2]
        ws = [w / tot for w in ws]
        acc = np.zeros((len(u), 3))
        for w, (vx, vy) in zip(ws, (v1, v2, v3)):
            ox, oy = self._hash2(vx, vy)
            acc += w[:, None] * (self._sample_plain(u + ox, v + oy, lod) - self.mean)
        norm = np.sqrt(ws[0] ** 2 + ws[1] ** 2 + ws[2] ** 2)
        return np.maximum(self.mean + acc / norm[:, None], 0.0)

    def _sample_plain(self, u, v, lod):
        if self.clamp:
            u = np.clip(u, 0.0, 1.0 - 1e-7)
            v = np.clip(v, 0.0, 1.0 - 1e-7)
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


def sample_gray(tex, u, v, lod, stoch=True):
    """Doku parlaklığı 0..1 (sRGB kodlu gri değer: harita pikselinin değeri). Gri tonlu kanallar ve bump yüksekliği için."""
    c = tex.sample(u, v, lod, stoch)
    return np.clip(0.2126 * c[:, 0] + 0.7152 * c[:, 1] + 0.0722 * c[:, 2], 0.0, 1.0) ** (1.0 / 2.2)


def register_custom(path, rgb8, mode="mirror"):
    """Arayüzün (QImage ile) okuduğu kendi görüntüyü kaydeder; ayarlarda doku adı olarak yol kullanılır."""
    _CUSTOM[path] = (np.ascontiguousarray(rgb8[:, :, :3], dtype=np.uint8), mode)
    _CACHE.pop(path, None)


def load_image_file(path, maxdim=1024):
    """Görüntü dosyası -> (h, w, 3) uint8. Önce Qt (png/jpg/bmp...), olmazsa yerleşik PNG okuyucu. En çok maxdim piksel (bellek/hız)."""
    try:
        from PySide import QtGui, QtCore
        img = QtGui.QImage(path)
        if not img.isNull():
            if max(img.width(), img.height()) > maxdim:
                img = img.scaled(maxdim, maxdim, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            img = img.convertToFormat(QtGui.QImage.Format_RGB888)
            w, h, bpl = img.width(), img.height(), img.bytesPerLine()
            buf = np.frombuffer(bytes(img.constBits()), dtype=np.uint8)[:bpl * h].reshape(h, bpl)[:, :w * 3]
            return np.ascontiguousarray(buf.reshape(h, w, 3))
    except Exception:
        pass
    return read_png(path)


def _read_fast(path):
    """PNG -> (h,w,3) uint8. Önce Qt (hızlı); yoksa saf Python/numpy okuyucu (satır döngüsü: yavaş, ~0.1-0.5 sn)."""
    try:
        from PySide import QtGui
        img = QtGui.QImage(path)
        if not img.isNull():
            img = img.convertToFormat(QtGui.QImage.Format_RGB888)
            w, h, bpl = img.width(), img.height(), img.bytesPerLine()
            buf = np.frombuffer(bytes(img.constBits()), dtype=np.uint8)[:bpl * h].reshape(h, bpl)[:, :w * 3]
            return np.ascontiguousarray(buf.reshape(h, w, 3))
    except Exception:
        pass
    return read_png(path)


def load(key, tile=None):
    """Anahtar (hazır doku adı) ya da kayıtlı özel yol -> Texture; bulunamazsa None.
    tile: None/"auto" = dokunun kendi modu (hazır dokularda listedeki, kendi dosyalarda ayna); "repeat" = düz tekrar; "mirror" = aynalı tekrar;
    "edge" = tek görüntü, kenar pikselleri uzar; "once" = tek görüntü, dışı etkisiz."""
    if not key:
        return None
    stoch = (tile == "stochastic")
    force = tile if tile in ("repeat", "mirror", "edge", "once") else None
    ck = key if force is None else (key, force)
    if stoch:
        ck = (key, "stochastic")
    if ck in _CACHE:
        return _CACHE[ck]
    tex = None
    if key in _CUSTOM:
        arr, mode = _CUSTOM[key]
        tex = Texture(arr, force or mode)
    else:
        for k, _name, fn, mode, rel in PRESETS:
            if k == key:
                p = os.path.join(_DIR, fn)
                if os.path.isfile(p):
                    tex = Texture(_read_fast(p), force or mode)
                    tex.rel = rel
                break
    if tex is None and key not in _CUSTOM:
        fp = key
        if not os.path.isfile(fp):
            from . import paths as _paths
            fp = _paths.resolve(key, "tex")                              # belge başka bilgisayardan geldiyse doku klasöründe aynı adı ara
        if os.path.isfile(fp):                                           # doğrudan dosya yolu (kullanıcı görüntüsü; yeniden başlatınca da çalışır)
            try:
                tex = Texture(load_image_file(fp), force or "mirror")
            except Exception:
                tex = None
    if tex is not None and stoch:
        tex.stoch = True
    if tex is not None:                                                  # bulunamayan doku önbelleğe alınmaz (klasör sonradan ayarlanabilir)
        _CACHE[ck] = tex
    return tex
