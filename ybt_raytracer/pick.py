# -*- coding: utf-8 -*-
"""Tıkla-seç: render görüntüsünde bir piksele tıklanınca o pikselden geçen ışının ilk çarptığı nesneyi bulur.

Render ile aynı kamera modeli kullanılır (render.trace ile aynı ışın üretimi); tek ışın tüm üçgenlerle sınanır
(birkaç yüz bin üçgende ~0.1 sn). Zemin nesne sayılmaz (None döner)."""
import numpy as np

from .core import _tri_hits, camera_basis


def _ray(scene, cam, w, h, fx, fy):
    """fx, fy: görüntü piksel koordinatı (kesirli olabilir; 0..w, 0..h). Döner (O, D) sahne-merkezli."""
    pos = np.asarray(cam["pos"], dtype=np.float64) - scene.center
    right, up, fwd = camera_basis(np.asarray(cam["fwd"], float), np.asarray(cam["up"], float))
    persp = bool(cam["persp"])
    aspect = float(w) / float(h)
    base = (np.tan(cam["size"] / 2.0) if persp else cam["size"] / 2.0)
    half_y, half_x = (base, base * aspect) if aspect >= 1.0 else (base / aspect, base)
    X = (fx / float(w)) * 2.0 - 1.0
    Y = 1.0 - (fy / float(h)) * 2.0
    X, Y = X * half_x, Y * half_y
    if persp:
        D = fwd + right * X + up * Y
        D = D / np.linalg.norm(D)
        return pos, D
    zmin = float((scene.tri @ fwd).min() - pos @ fwd)           # render ile aynı: başlangıç sahnenin gerisine çekilir
    o = pos - fwd * (max(0.0, -zmin) + 0.05 * scene.diag) + right * X + up * Y
    return o, fwd


def pick(scene, cam, w, h, fx, fy):
    """Tıklanan pikselin nesnesi. Döner (nesne_adı, üçgen_indeksi) ya da None (arka plan / zemin / nesnesiz)."""
    if scene is None or scene.count == 0 or not scene.onames:
        return None
    O, D = _ray(scene, cam, w, h, fx, fy)
    best_t, best_i = np.inf, -1
    ids_all = np.arange(scene.count, dtype=np.int64)
    step = 200000
    for s in range(0, scene.count, step):
        ids = ids_all[s:s + step]
        t = _tri_hits(scene, O[None, :], D[None, :], ids)[0]
        j = int(np.argmin(t))
        if t[j] < best_t:
            best_t, best_i = float(t[j]), int(ids[j])
    if best_i < 0 or not np.isfinite(best_t):
        return None
    k = int(scene.oid[best_i])
    if k < 0 or k >= len(scene.onames):
        return None
    return scene.onames[k], best_i


def depth_at(scene, cam, w, h, fx, fy):
    """Tıklanan pikselde ilk çarpılan yüzeyin kamera eksenindeki uzaklığı (mm); çarpma yoksa None (alan derinliği odağı için)."""
    if scene is None or scene.count == 0:
        return None
    O, D = _ray(scene, cam, w, h, fx, fy)
    best_t = np.inf
    ids_all = np.arange(scene.count, dtype=np.int64)
    for s in range(0, scene.count, 200000):
        t = _tri_hits(scene, O[None, :], D[None, :], ids_all[s:s + 200000])[0]
        best_t = min(best_t, float(np.min(t)))
    if not np.isfinite(best_t):
        return None
    _r, _u, fwd = camera_basis(np.asarray(cam["fwd"], float), np.asarray(cam["up"], float))
    return best_t * float(np.dot(D, fwd))
