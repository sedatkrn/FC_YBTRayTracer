# -*- coding: utf-8 -*-
"""İçerik klasörü (Content Directory) ve alt klasörleri.

Seçenekler penceresinde tek bir içerik klasörü seçilir; altında sabit adlı alt klasörler olur:

  <içerik>/materials/   kullanıcı malzeme kütüphanesi (materials.json)
  <içerik>/textures/    doku görüntüleri (dosya seçiciler buradan açılır, listelerde görünür)
  <içerik>/hdri/        HDRI / ortam haritaları
  <içerik>/settings/    kayıtlı varsayılanlar (ybt_raytracer_defaults.json)
  <içerik>/renders/     render çıktıları (OUT_TO = "renders"; "document" = belgenin yanı)

İçerik klasörünün yolu FreeCAD kullanıcı parametresinde tutulur (Mod/FCYBTRayTracer/ContentDir): ayar dosyaları
klasörün içinde olduğundan yol onlarda saklanamaz. Klasör ayarsızsa her şey eski yerlerindedir (davranış değişmez).
İlk kez ayarlanırken eski yerdeki malzeme kütüphanesi ve varsayılanlar silinmeden yeni klasöre kopyalanır
(hedefte yoksa): migrate_to_content().

Belgeye gömülü bir doku / HDRI yolu bu bilgisayarda yoksa (belge başka makineden geldi), aynı dosya adı
textures / hdri klasöründe (alt klasörler dahil) aranır: resolve().
"""
import os
import re
import shutil
import time
from . import settings as S

PARAM = "User parameter:BaseApp/Preferences/Mod/FCYBTRayTracer"      # i18n.py ile aynı grup
SUBDIRS = ("materials", "textures", "hdri", "settings", "renders")
IMG_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".gif", ".webp")
HDRI_EXT = (".hdr", ".pic", ".png", ".jpg", ".jpeg")
_MAX_WALK = 20000        # alt klasörlerde arama sınırı (dosya sayısı)
_MAX_DEPTH = 4
_mem = {"dir": ""}       # FreeCAD dışında (testler) parametre yerine


def _expand(p):
    return os.path.expanduser(os.path.expandvars(str(p or "").strip()))


def content_dir():
    """Ayarlı içerik klasörü ('' = ayarsız). Klasör henüz var olmayabilir."""
    try:
        import FreeCAD
        v = FreeCAD.ParamGet(PARAM).GetString("ContentDir", "")
    except Exception:
        v = _mem["dir"]
    return _expand(v)


def set_content_dir(path):
    """İçerik klasörünü ayarlar ve alt klasörlerini oluşturur ('' = ayarı kaldır). Oluşturulamazsa OSError."""
    path = _expand(path)
    if path:
        for n in SUBDIRS:
            os.makedirs(os.path.join(path, n), exist_ok=True)
    try:
        import FreeCAD
        FreeCAD.ParamGet(PARAM).SetString("ContentDir", path)
    except Exception:
        pass
    _mem["dir"] = path
    _FOUND.clear()
    return path


def sub_dir(name):
    """Alt klasörün yolu (içerik klasörü ayarsızsa '')."""
    c = content_dir()
    return os.path.join(c, name) if c else ""


def _existing(name):
    d = sub_dir(name)
    return d if d and os.path.isdir(d) else ""


def texture_dir():
    return _existing("textures")


def hdri_dir():
    return _existing("hdri")


def materials_dir():
    """Malzeme kütüphanesi klasörü (içerik klasörü ayarlıysa; yoksa oluşturulur), değilse ''."""
    return _ensure("materials")


def settings_dir():
    return _ensure("settings")


def _ensure(name):
    d = sub_dir(name)
    if d:
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            return ""
    return d


def out_dir(doc_filename=""):
    """Çıktı klasörü (henüz var olmayabilir): içerik klasörü ayarlı ve OUT_TO == "renders" ise <içerik>/renders, aksi halde ''
    (yani belgenin yanı; pick_out_path eski zincire düşer)."""
    if str(getattr(S, "OUT_TO", "renders")) != "renders":
        return ""
    return sub_dir("renders")


def migrate_to_content():
    """İçerik klasörü ayarlandıktan sonra çağrılır: eski yerdeki malzeme kütüphanesi ve varsayılanlar, hedefte yoksa
    KOPYALANIR (eskiler silinmez). Kopyalanan dosyaların adlarını döndürür."""
    from . import materials as _m
    from . import userdefaults as _u
    copied = []
    for src, dst in ((_m.legacy_lib_path(), os.path.join(sub_dir("materials"), "materials.json")),
                     (_u.legacy_path(), os.path.join(sub_dir("settings"), "ybt_raytracer_defaults.json"))):
        if not sub_dir("materials") or not os.path.isfile(src) or os.path.exists(dst):
            continue
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(os.path.basename(dst))
        except OSError:
            pass
    return copied


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
