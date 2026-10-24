# -*- coding: utf-8 -*-
"""Resim geçmişi: son MAX render PNG olarak kullanıcı klasöründe saklanır (FreeCAD kapanıp açılınca da durur).

  <UserAppData>/YBTRayTracer/history/index.json  {"items": [{file, name, ts, w, h, info}, ... en yeni başta], "count": {belge: n}}
  <UserAppData>/YBTRayTracer/history/<ad>.png
"""
import json
import os
import time

from .output import write_png

MAX = 10


def folder():
    """Kalıcı kullanıcı klasörü (önbellek klasörü Windows'ta Temp altındadır, temizlik araçları silebilir)."""
    try:
        import FreeCAD
        base = FreeCAD.getUserAppDataDir()
    except Exception:
        base = os.path.expanduser("~")
    d = os.path.join(base, "YBTRayTracer", "history")
    os.makedirs(d, exist_ok=True)
    _migrate(d)
    return d


def _read_index(dirname):
    try:
        with open(os.path.join(dirname, "index.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _migrate(dst):
    """Eski sürümün önbellek klasöründe (Windows'ta Temp altı) kalan geçmişi kalıcı klasördekiyle BİRLEŞTİRİR:
    dosyalar taşınır (aynı ad varsa yeni numara alır), kayıtlar tarihe göre sıralanır, en yeni MAX tanesi kalır."""
    try:
        import FreeCAD
        import shutil
        old = os.path.join(FreeCAD.getUserCachePath(), "YBTRayTracer", "history")
        if not os.path.isdir(old) or os.path.abspath(old) == os.path.abspath(dst):
            return
        di, do = _read_index(dst), _read_index(old)
        items = [it for it in di.get("items", []) if os.path.isfile(os.path.join(dst, it.get("file", "")))]
        count = dict(di.get("count", {}))
        for k, v in do.get("count", {}).items():
            count[k] = max(int(count.get(k, 0)), int(v))
        for it in do.get("items", []):
            src = os.path.join(old, it.get("file", ""))
            if not os.path.isfile(src):
                continue
            it = dict(it)
            if os.path.exists(os.path.join(dst, it["file"])):        # çakışma: belgenin sıradaki numarasıyla yeniden adlandır
                base = it["name"].rsplit("_", 1)[0]
                count[base] = int(count.get(base, 0)) + 1
                it["name"] = "%s_%03d" % (base, count[base])
                it["file"] = it["name"] + ".png"
            shutil.move(src, os.path.join(dst, it["file"]))
            items.append(it)
        items.sort(key=lambda x: x.get("ts", ""), reverse=True)
        for it in items[MAX:]:
            try:
                os.remove(os.path.join(dst, it["file"]))
            except OSError:
                pass
        _save_to(dst, {"items": items[:MAX], "count": count})
        shutil.rmtree(old, ignore_errors=True)
    except Exception:
        pass


def _save_to(dirname, d):
    p = os.path.join(dirname, "index.json")
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def _index_path():
    return os.path.join(folder(), "index.json")


def load():
    """Kayıtlar (en yeni başta); dosyası silinmiş olanlar atlanır."""
    try:
        with open(_index_path(), "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    items = [it for it in d.get("items", []) if isinstance(it, dict) and os.path.isfile(os.path.join(folder(), it.get("file", "")))]
    return {"items": items, "count": dict(d.get("count", {}))}


def _save(d):
    p = _index_path()
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def path_of(item):
    return os.path.join(folder(), item["file"])


def _safe(s):
    s = "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(s or "render"))
    return s.strip("_") or "render"


def add(img, doc_name, info="", meta=None):
    """Yeni render'ı geçmişe ekler (en başa); MAX'ı aşan en eski kayıt ve dosyası silinir. Döner: eklenen kayıt."""
    d = load()
    base = _safe(doc_name)
    n = int(d["count"].get(base, 0)) + 1
    d["count"][base] = n
    name = "%s_%03d" % (base, n)
    fn = name + ".png"
    k = 1
    while os.path.exists(os.path.join(folder(), fn)):           # aynı ad başka oturumdan kalmışsa
        k += 1
        fn = "%s_%d.png" % (name, k)
    h, w = img.shape[:2]
    write_png(os.path.join(folder(), fn), img, meta)
    item = dict(file=fn, name=name, ts=time.strftime("%Y-%m-%d %H:%M:%S"), w=int(w), h=int(h), info=str(info))
    d["items"].insert(0, item)
    for old in d["items"][MAX:]:
        try:
            os.remove(path_of(old))
        except OSError:
            pass
    d["items"] = d["items"][:MAX]
    _save(d)
    return item
