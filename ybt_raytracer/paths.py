# -*- coding: utf-8 -*-
"""Klasör ayarları: render çıktısı, dokular ve HDRI dosyaları nerede.

settings.py:
  DIR_OUT   çıktı klasörü. Boş = belgenin yanı (eski davranış); mutlak yol = sabit klasör;
            göreli ad (ör. "render") = belgenin yanında bu alt klasör. Klasör yoksa oluşturulur.
  DIR_TEX   doku klasörü: dosya seçiciler buradan açılır, görüntüler dokular listesine eklenir.
  DIR_HDRI  HDRI klasörü: dosya seçici buradan açılır, dosyalar HDRI listesinde görünür.

Belgeye gömülü bir doku / HDRI yolu bu bilgisayarda yoksa (belge başka makineden geldi), aynı dosya adı
ilgili klasörde (alt klasörler dahil) aranır: resolve().
"""
import os
import re
import time
from . import settings as S

IMG_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".gif", ".webp")
HDRI_EXT = (".hdr", ".pic", ".png", ".jpg", ".jpeg")
_MAX_WALK = 20000        # alt klasörlerde arama sınırı (dosya sayısı)
_MAX_DEPTH = 4


def _expand(p):
    return os.path.expanduser(os.path.expandvars(str(p or "").strip()))


def _dir(name):
    """Ayar klasörü; ayarsız ya da klasör yoksa ''."""
    d = _expand(getattr(S, name, ""))
    return d if d and os.path.isdir(d) else ""


def texture_dir():
    return _dir("DIR_TEX")


def hdri_dir():
    return _dir("DIR_HDRI")


def out_dir(doc_filename=""):
    """Ayarlanan çıktı klasörü (henüz var olmayabilir); ayarsızsa ya da göreli ad verilip belge kayıtsızsa ''."""
    raw = _expand(getattr(S, "DIR_OUT", ""))
    if not raw:
        return ""
    if os.path.isabs(raw):
        return raw
    if doc_filename:
        return os.path.join(os.path.dirname(doc_filename), raw)
    return ""


def list_files(folder, exts, limit=400):
    """Klasördeki (alt klasörsüz) uygun uzantılı dosya adları, alfabetik; en çok `limit`."""
    if not folder or not os.path.isdir(folder):
        return []
    try:
        names = [n for n in os.listdir(folder)
                 if n.lower().endswith(exts) and os.path.isfile(os.path.join(folder, n))]
    except OSError:
        return []
    return sorted(names, key=str.lower)[:limit]


_FOUND = {}              # (klasör, küçük harfli ad) -> (yol ya da None, zaman)


def _basename(path):
    return re.split(r"[\\/]", str(path))[-1]       # Windows yolları Linux'ta da bölünsün


def _search(folder, base):
    direct = os.path.join(folder, base)
    if os.path.isfile(direct):
        return direct
    low, seen = base.lower(), 0
    root_depth = folder.rstrip(os.sep).count(os.sep)
    for cur, dirs, files in os.walk(folder):
        if cur.count(os.sep) - root_depth >= _MAX_DEPTH:
            dirs[:] = []
        seen += len(files)
        if seen > _MAX_WALK:
            return None
        for f in files:
            if f.lower() == low:
                return os.path.join(cur, f)
    return None


def resolve(path, kind):
    """Dosya yoksa ayarlı klasörde (kind: "tex" ya da "hdri") aynı adı arar; bulursa o yolu, yoksa `path`'i aynen döndürür."""
    if not path or os.path.isfile(path):
        return path
    base = _basename(path)
    folder = texture_dir() if kind == "tex" else hdri_dir()
    if not base or not folder:
        return path
    key = (folder, base.lower())
    hit = _FOUND.get(key)
    now = time.time()
    if hit is not None:
        p, t = hit
        if (p and os.path.isfile(p)) or (not p and now - t < 10.0):      # bulunamayan arama 10 sn hatırlanır
            return p or path
    p = _search(folder, base)
    _FOUND[key] = (p, now)
    return p or path
