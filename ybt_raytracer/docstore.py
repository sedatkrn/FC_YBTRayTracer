# -*- coding: utf-8 -*-
"""Belgeyle birlikte saklama: render paneli ayarları ve belgede kullanılan malzeme tanımları FreeCAD belgesinin
'Meta' özelliğine (FCStd içinde saklanır) JSON olarak yazılır; belge başka bilgisayarda açılınca geri gelir.

  Meta["YBTSettings"]   panel ayarları (userdefaults.snapshot, makineye özgü anahtarlar hariç)
  Meta["YBTMaterials"]  belgedeki nesnelere atanmış malzemelerin tanımları (kullanıcı kütüphanesinde olmayan adlar buradan gelir)
"""
import json
from . import settings as S
from . import materials as M
from . import userdefaults as _ud

K_SET = "YBTSettings"
K_MAT = "YBTMaterials"
_SKIP = {"THREADS", "PARALLEL", "OUT_NAME", "DEBUG"}      # makineye / oturuma özgü


def _meta(doc):
    try:
        return dict(doc.Meta)
    except Exception:
        return None


def _put(doc, key, text):
    m = _meta(doc)
    if m is None or m.get(key) == text:
        return False
    m[key] = text
    try:
        doc.Meta = m
        return True
    except Exception:
        return False


def save(doc):
    """Şu anki panel ayarlarını ve atanmış malzeme tanımlarını belgeye yazar (değişmediyse dokunmaz)."""
    if doc is None:
        return False
    snap = {k: v for k, v in _ud.snapshot().items() if k not in _SKIP}
    ch = _put(doc, K_SET, json.dumps(snap, ensure_ascii=False, sort_keys=True))
    try:
        lib = M.library()
        used = {M.assigned(o) for o in doc.Objects} | {str(getattr(S, "FLOOR_MATERIAL", "") or "")}   # sanal zeminin malzemesi de
        names = sorted(n for n in used if n and n in lib)
        defs = {n: dict(lib[n], color=list(lib[n]["color"]) if lib[n].get("color") else None) for n in names}
        ch = _put(doc, K_MAT, json.dumps(defs, ensure_ascii=False, sort_keys=True)) or ch
    except Exception:
        pass
    return ch


def load_settings(doc):
    """Belgede saklı ayarları settings modülüne uygular; uygulandıysa True."""
    m = _meta(doc) if doc is not None else None
    raw = (m or {}).get(K_SET)
    if not raw:
        return False
    try:
        vals = {k: v for k, v in json.loads(raw).items() if k not in _SKIP}
    except Exception:
        return False
    return _ud.apply(vals) > 0


_CACHE = {"raw": None, "lib": {}}


def doc_materials():
    """Etkin belgeye gömülü malzeme tanımları (normalize edilmiş sözlük); yoksa {}."""
    try:
        import FreeCAD
        doc = FreeCAD.ActiveDocument
        raw = dict(doc.Meta).get(K_MAT) if doc is not None else None
    except Exception:
        raw = None
    if raw != _CACHE["raw"]:
        lib = {}
        if raw:
            try:
                lib = {k: M.normalize(v) for k, v in json.loads(raw).items()}
            except Exception:
                lib = {}
        _CACHE["raw"], _CACHE["lib"] = raw, lib
    return _CACHE["lib"]
