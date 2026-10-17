# -*- coding: utf-8 -*-
"""T("...") ile geçen tüm Türkçe metinlerde (ve malzeme/doku adlarında) İngilizce karşılık var mı denetler."""
import ast, os, sys
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, root)
from ybt_raytracer import i18n, materials as M, textures as X
miss = set()
for fn in os.listdir(os.path.join(root, "ybt_raytracer")):
    if not fn.endswith(".py") or fn == "i18n.py":
        continue
    tree = ast.parse(open(os.path.join(root, "ybt_raytracer", fn), encoding="utf-8").read())
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "T" and n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
            miss.add(n.args[0].value)
miss |= set(M.BUILTIN) | {c for c, _ in M.CATEGORIES} | {p[1] for p in X.PRESETS}
from ybt_raytracer.surface_ui import _PARAMS
for k, label, lo, hi, tip in _PARAMS:
    miss |= {label, tip}
bad = sorted(s for s in miss if s not in i18n.EN and s.strip() and any(ord(c) > 127 or c.isalpha() for c in s))
print("eksik:", len(bad))
for b in bad:
    print(repr(b))
