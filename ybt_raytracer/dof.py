# -*- coding: utf-8 -*-
"""Alan derinliği (DOF): render sonrası, derinlik tamponuna dayalı katmanlı bulanıklaştırma (yalnız numpy).

İnce mercek modeli: sensör üzerindeki karışıklık çemberi çapı  c = (f / N) * f / (S - f) * |z - S| / z
(f odak uzaklığı, N diyafram sayısı, S odak mesafesi, z piksel derinliği; hepsi mm). Piksel yarıçapı = c / (sensör piksel boyu) / 2.

Yöntem: her piksel karışıklık yarıçapına göre bir katmana (işaretli düzey: + odağın arkası, - önü) atanır; katmanlar uzaktan yakına doğru
"alfa kompozit" edilir, her katman kendi yarıçapındaki disk çekirdeğiyle (FFT) bulanıklaştırılır. Böylece keskin ön nesne arkadaki bulanıklığa
karışmaz ve bulanık ön nesne keskin arka planı yumuşak kenarla örter. Doğrusal ışıkta çalışır (parlak noktalar bokeh diski olur).
"""
import numpy as np


def _fast(n):
    """n'den küçük olmayan en küçük 2^a 3^b 5^c (FFT hızlı boyutu)."""
    best = 1 << int(np.ceil(np.log2(max(n, 1))))
    a = 1
    while a < best:
        b = a
        while b < best:
            c = b
            while c < best:
                if c >= n:
                    best = c
                    break
                c *= 5
            b *= 3
        a *= 2
    return best


def coc_radius(z, focus, focal, fstop, sensor, width):
    """İşaretli karışıklık yarıçapı (piksel): + odağın arkası, - önü. z: (h,w) derinlik (inf = sonsuz)."""
    S = max(float(focus), float(focal) * 1.001)
    zz = np.where(np.isfinite(z), np.maximum(z, 1e-6), 1e12)
    A = float(focal) / max(float(fstop), 0.1)
    c = A * float(focal) / (S - float(focal)) * (zz - S) / zz
    return c / (float(sensor) / float(width)) / 2.0


def _disc(rho):
    n = int(np.ceil(rho)) + 1
    yy, xx = np.mgrid[-n:n + 1, -n:n + 1]
    k = np.clip(rho + 0.5 - np.sqrt(xx * xx + yy * yy), 0.0, 1.0)
    return k / k.sum()


def _levels(rmax):
    lv = [0.0]
    v = 1.0
    while v < rmax:
        lv.append(v)
        v *= 1.45
    lv.append(float(rmax))
    return np.array(lv)


def apply(img, z, focus, focal, fstop, sensor, tick=None):
    """img: (h,w,3) 0..1 (sRGB); z: (h,w) derinlik. Döner aynı biçimde bulanık görüntü (değişiklik yoksa img'in kendisi)."""
    h, w = z.shape
    r = coc_radius(z, focus, focal, fstop, sensor, w)
    rmax = float(min(np.abs(r).max(), 0.08 * w))
    if rmax < 0.7:
        return img
    r = np.clip(r, -rmax, rmax)
    lv = _levels(rmax)
    mid = (lv[:-1] + lv[1:]) / 2.0
    mid[0] = 0.7                                            # 0,7 pikselin altı keskin sayılır
    li = np.searchsorted(mid, np.abs(r))                    # 0..len-1
    sg = np.sign(r).astype(np.int8)
    lin = np.clip(img, 0.0, 1.0) ** 2.2
    out = lin.copy()
    order = [(1, i) for i in range(len(lv) - 1, 0, -1)] + [(0, 0)] + [(-1, i) for i in range(1, len(lv))]
    for s, i in order:
        m = ((li == i) & ((sg > 0) if s > 0 else (sg <= 0) if s == 0 else (sg < 0))) if i > 0 else (li == 0)
        if not m.any():
            continue
        if tick is not None:
            tick()
        mf = m.astype(np.float64)
        if i == 0:
            out = out * (1.0 - mf[..., None]) + lin * mf[..., None]
            continue
        rho = float(lv[i])
        ker = _disc(rho)
        kh, kw = ker.shape
        c = kh // 2 + 1
        H, W = _fast(h + 2 * c), _fast(w + 2 * c)
        K = np.zeros((H, W))
        K[:kh, :kw] = ker
        K = np.roll(K, (-(kh // 2), -(kw // 2)), (0, 1))
        FK = np.fft.rfft2(K)
        A = np.zeros((4, H, W))
        A[:3, :h, :w] = (lin * mf[..., None]).transpose(2, 0, 1)
        A[3, :h, :w] = mf
        B = np.fft.irfft2(np.fft.rfft2(A, axes=(1, 2)) * FK[None], s=(H, W), axes=(1, 2))[:, :h, :w]
        alpha = np.clip(B[3], 0.0, 1.0)
        out = out * (1.0 - alpha[..., None]) + np.maximum(B[:3].transpose(1, 2, 0), 0.0)
    return np.clip(out, 0.0, 1.0) ** (1.0 / 2.2)
