# -*- coding: utf-8 -*-
"""Malzeme (yüzey) kütüphanesi: hazır malzemeler + kullanıcı malzemeleri (JSON), nesne bazında atama.

Bir malzeme sözlüğü:
  color   (r,g,b) 0..1 ya da None  -> None: nesnenin FreeCAD rengi kullanılır
  diffuse 0..1   yayılı (mat) ışık çarpanı
  spec    0..1   parlak vurgu (specular) şiddeti
  gloss   0..1   parlaklık (vurgunun keskinliği)
  metal   0..1   metal: vurguyu yüzey rengine boyar, yayılı ışığı azaltır
  refl    0..1   yansıma
  transp  0..1   saydamlık (0 = opak, 1 = tam saydam)
  ior     1..3   kırılma indisi (yalnız saydam malzemede etkili; 1 = düz geçiş)
  lum     0..1   kendi ışığı (parlama, ışıktan bağımsız)
Atama nesnenin 'YBTMaterial' (metin) özelliğinde saklanır; belgeyle birlikte kaydolur.
"Render'a dahil et" işareti nesnenin 'YBTInclude' (mantıksal) özelliğinde saklanır; özellik yoksa nesne dahildir.
"""
import json
import os

PROP = "YBTMaterial"
INC_PROP = "YBTInclude"

DEFAULT = dict(color=None, diffuse=1.0, spec=0.30, gloss=0.28, metal=0.0, refl=0.0, transp=0.0, ior=1.0, lum=0.0)
KEYS = tuple(DEFAULT.keys())


def shininess(gloss):
    """gloss 0..1 -> Blinn-Phong üssü (0.28 ~ eski varsayılan 48)."""
    g = min(max(float(gloss), 0.0), 1.0)
    return 2.0 + 600.0 * g * g


def _m(**kw):
    d = dict(DEFAULT)
    d.update(kw)
    return d


# Ad'lar Türkçe (kaynak); arayüzde i18n.T ile çevrilir.
BUILTIN = {
    "Mat plastik":      _m(color=(0.80, 0.80, 0.82), spec=0.12, gloss=0.18),
    "Parlak plastik":   _m(color=(0.75, 0.10, 0.10), spec=0.60, gloss=0.55, refl=0.06),
    "Kauçuk":           _m(color=(0.06, 0.06, 0.06), spec=0.05, gloss=0.12),
    "Boya (araba)":     _m(color=(0.70, 0.05, 0.05), spec=0.70, gloss=0.70, refl=0.15),
    "Seramik":          _m(color=(0.93, 0.93, 0.90), spec=0.70, gloss=0.65, refl=0.08),
    "Ahşap (cilalı)":   _m(color=(0.55, 0.33, 0.16), spec=0.25, gloss=0.35, refl=0.03),
    "Krom":             _m(color=(0.92, 0.92, 0.95), diffuse=0.20, spec=1.00, gloss=0.90, metal=1.0, refl=0.85),
    "Çelik (fırçalı)":  _m(color=(0.62, 0.63, 0.66), diffuse=0.55, spec=0.55, gloss=0.40, metal=1.0, refl=0.15),
    "Alüminyum":        _m(color=(0.80, 0.81, 0.83), diffuse=0.50, spec=0.70, gloss=0.55, metal=1.0, refl=0.30),
    "Altın":            _m(color=(1.00, 0.77, 0.34), diffuse=0.40, spec=0.90, gloss=0.75, metal=1.0, refl=0.35),
    "Bakır":            _m(color=(0.95, 0.52, 0.38), diffuse=0.45, spec=0.80, gloss=0.65, metal=1.0, refl=0.30),
    "Cam":              _m(color=(0.85, 0.95, 0.95), spec=1.00, gloss=0.90, refl=1.0, transp=0.90, ior=1.5),
    "Su":               _m(color=(0.70, 0.88, 0.95), spec=1.00, gloss=0.90, refl=1.0, transp=0.92, ior=1.33),
    "Buzlu cam":        _m(color=(0.90, 0.95, 0.95), spec=0.40, gloss=0.30, refl=0.40, transp=0.75, ior=1.0),
    "Parlayan (ışık)":  _m(color=(1.00, 0.95, 0.80), spec=0.0, lum=1.0),
}


def user_lib_path():
    try:
        import FreeCAD
        base = FreeCAD.getUserAppDataDir()
    except Exception:
        base = os.path.expanduser("~")
    return os.path.join(base, "YBTRayTracer", "materials.json")


def load_user():
    try:
        with open(user_lib_path(), "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {k: normalize(v) for k, v in raw.items()}
    except Exception:
        return {}


def save_user(lib):
    p = user_lib_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump({k: dict(v, color=list(v["color"]) if v.get("color") else None) for k, v in lib.items()},
                  f, ensure_ascii=False, indent=1)


def normalize(d):
    """Eksik/bozuk alanları varsayılanla tamamla, aralıklara sıkıştır."""
    out = dict(DEFAULT)
    for k in KEYS:
        if k in d and d[k] is not None:
            out[k] = d[k]
    c = out["color"]
    out["color"] = tuple(min(max(float(x), 0.0), 1.0) for x in c) if c else None
    lim = dict(diffuse=(0, 1), spec=(0, 1), gloss=(0, 1), metal=(0, 1), refl=(0, 1), transp=(0, 1), ior=(1, 3), lum=(0, 1))
    for k, (lo, hi) in lim.items():
        out[k] = min(max(float(out[k]), lo), hi)
    return out


def library():
    """Hazır + kullanıcı malzemeleri (kullanıcınınki aynı adı ezer)."""
    lib = dict(BUILTIN)
    lib.update(load_user())
    return lib


def get(name, lib=None):
    if not name:
        return None
    lib = library() if lib is None else lib
    m = lib.get(name)
    return normalize(m) if m is not None else None


def assigned(obj):
    """Nesneye atanmış malzeme adı ('' = yok). Link ise bağlı nesneye de bakılır."""
    for o in (obj, getattr(obj, "LinkedObject", None)):
        if o is None:
            continue
        try:
            v = getattr(o, PROP, "")
        except Exception:
            v = ""
        if v:
            return str(v)
    return ""


def _own(obj, prop):
    """Özellik nesnenin KENDİNDE mi? (App::Link, bağlı nesnenin özelliklerini de yansıtır; hasattr/getattr yanıltır.)"""
    try:
        return prop in obj.PropertiesList
    except Exception:
        return False


def included(obj):
    """Nesne render'a dahil mi? Özellik yoksa (hiç hariç tutulmamışsa) dahildir. Yalnız nesnenin kendi işareti geçerlidir:
    bir parça hariç tutulunca ona bağlı Link'ler (ve tersi) etkilenmez."""
    if not _own(obj, INC_PROP):
        return True
    try:
        return bool(getattr(obj, INC_PROP))
    except Exception:
        return True


def set_included(obj, flag):
    """Dahil et işaretini yaz. Özellik yalnızca ilk kez hariç tutulurken eklenir (belgeyle kaydolur)."""
    if not _own(obj, INC_PROP):
        if flag:
            return
        obj.addProperty("App::PropertyBool", INC_PROP, "YBT RayTracer", "Include this object in raytracer renders")
    if bool(getattr(obj, INC_PROP)) != bool(flag):
        setattr(obj, INC_PROP, bool(flag))


def assign(obj, name):
    """Nesneye malzeme ata ('' = kaldır). Özellik yoksa eklenir (belgeyle kaydolur)."""
    if not hasattr(obj, PROP):
        if not name:
            return
        obj.addProperty("App::PropertyString", PROP, "YBT RayTracer", "Raytracer material name")
    if getattr(obj, PROP) != (name or ""):
        setattr(obj, PROP, name or "")
