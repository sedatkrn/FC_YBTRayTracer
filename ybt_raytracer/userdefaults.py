# -*- coding: utf-8 -*-
"""Kullanıcı varsayılanları + geçmiş (history).

settings.py'deki değerlerin fabrika hali import anında saklanır. Kullanıcı panelden "varsayılan olarak kaydet"
deyince tüm ayarların bir kopyası JSON dosyasına yazılır (son MAX_HIST kayıt tutulur); eski bir kayda dönülebilir.
Dosya: FreeCAD kullanıcı veri klasöründe ybt_raytracer_defaults.json"""
import copy
import json
import os
import time
from . import settings as S

MAX_HIST = 10
_SKIP = {"DEBUG", "OUT_NAME"}            # oturuma/çıktıya özgü, kaydedilmez


def _keys():
    return [k for k, v in vars(S).items() if k.isupper() and not k.startswith("_") and k not in _SKIP
            and isinstance(v, (bool, int, float, str, tuple, list))]


def _plain(v):
    if isinstance(v, tuple):
        return [_plain(x) for x in v]
    if isinstance(v, list):
        return [_plain(x) for x in v]
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    return v


def snapshot():
    """Şu anki settings değerlerinin JSON'a uygun kopyası."""
    return {k: _plain(copy.deepcopy(getattr(S, k))) for k in _keys()}


def _factory():
    """settings.py dosyasını temiz bir modül olarak okur (oturumda değişmiş değerlerden etkilenmez)."""
    try:
        import importlib.util
        sp = importlib.util.spec_from_file_location("_ybt_settings_factory", S.__file__)
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        return {k: _plain(copy.deepcopy(getattr(m, k))) for k in _keys() if hasattr(m, k)}
    except Exception:
        return snapshot()


FACTORY = _factory()                      # fabrika ayarları


def _restore_type(key, val):
    """JSON'dan gelen listeyi, fabrika değerinin türüne (tuple) geri çevirir."""
    if key == "LIGHTS":
        out = []
        for d in val:
            d = dict(d)
            if "color" in d:
                d["color"] = tuple(d["color"])
            out.append(d)
        return out
    return val


def apply(values):
    """Değerleri settings modülüne yazar (bilinmeyen / tür uyuşmayan anahtarlar atlanır)."""
    n = 0
    for k, v in values.items():
        if k not in FACTORY:
            continue
        cur = getattr(S, k, None)
        try:
            if isinstance(cur, bool):
                v = bool(v)
            elif isinstance(cur, int):
                v = int(v)
            elif isinstance(cur, float):
                v = float(v)
            elif isinstance(cur, str):
                v = str(v)
            elif isinstance(cur, tuple):
                v = tuple(v)
            elif k == "LIGHTS":
                v = _restore_type(k, v)
            setattr(S, k, v)
            n += 1
        except Exception:
            pass
    return n


def legacy_path():
    """Eski saklama yeri (içerik klasörü ayarlanmadan önceki): <FreeCAD kullanıcı verisi>/ybt_raytracer_defaults.json."""
    try:
        import FreeCAD
        d = FreeCAD.getUserAppDataDir()
    except Exception:
        d = os.path.expanduser("~")
    return os.path.join(d, "ybt_raytracer_defaults.json")


def path():
    """Varsayılanlar dosyası: içerik klasörü ayarlıysa <içerik>/settings/, değilse eski yer."""
    from . import paths as _paths
    d = _paths.settings_dir()
    return os.path.join(d, "ybt_raytracer_defaults.json") if d else legacy_path()


def load():
    """{'hist': [ {ts, name, values}, ... en yeni sonda ], 'current': index veya -1}"""
    try:
        with open(path(), "r", encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d.get("hist"), list):
            d.setdefault("current", len(d["hist"]) - 1)
            return d
    except Exception:
        pass
    return {"hist": [], "current": -1}


def _write(d):
    p = path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def save_current(name=""):
    """Şu anki settings değerlerini yeni varsayılan olarak kaydeder (geçmişe eklenir)."""
    d = load()
    d["hist"].append(dict(ts=time.strftime("%Y-%m-%d %H:%M:%S"), name=name.strip(), values=snapshot()))
    d["hist"] = d["hist"][-MAX_HIST:]
    d["current"] = len(d["hist"]) - 1
    _write(d)
    return d


def make_default(index):
    """Geçmişteki bir kaydı geçerli varsayılan yapar (kayıt silinmez)."""
    d = load()
    if 0 <= index < len(d["hist"]):
        d["current"] = index
        _write(d)
    return d


def delete(index):
    d = load()
    if 0 <= index < len(d["hist"]):
        del d["hist"][index]
        cur = d.get("current", -1)
        d["current"] = cur - 1 if cur > index else (-1 if cur == index else cur)
        if d["current"] < 0 and d["hist"]:
            d["current"] = -1
        _write(d)
    return d


def clear_default():
    d = load()
    d["current"] = -1
    _write(d)
    return d


def apply_saved():
    """Kayıtlı varsayılan varsa settings'e uygular. Oturumda bir kez (FreeCAD yeniden başlayınca)."""
    d = load()
    c = d.get("current", -1)
    if 0 <= c < len(d["hist"]):
        return apply(d["hist"][c]["values"])
    return 0
