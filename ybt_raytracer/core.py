# -*- coding: utf-8 -*-
import numpy as np
from . import settings as S


# ============================ SAF NUMPY ÇEKİRDEK ============================
class Scene(object):
    """Üçgen listesi + ışın izleme için ön hesaplar. Her şey sahne merkezine göredir (float64)."""

    def __init__(self, tris, colors, alpha=None):
        tris = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
        colors = np.asarray(colors, dtype=np.float64).reshape(-1, 3)
        flat = tris.reshape(-1, 3)
        self.center = (flat.min(0) + flat.max(0)) / 2.0
        tris = tris - self.center
        diag = float(np.linalg.norm(flat.max(0) - flat.min(0)))
        self.diag = max(diag, 1e-9)
        v0, v1, v2 = tris[:, 0], tris[:, 1], tris[:, 2]
        e1, e2 = v1 - v0, v2 - v0
        n = np.cross(e1, e2)
        nn = (n * n).sum(1)
        ok = nn > (1e-9 * self.diag ** 2) ** 2          # dejenere üçgenleri at
        self.tri = tris[ok]
        v0, e1, e2, n, nn = v0[ok], e1[ok], e2[ok], n[ok], nn[ok]
        self.colors = colors[ok]
        al = np.ones(len(ok)) if alpha is None else np.asarray(alpha, dtype=np.float64).reshape(-1)
        self.alpha = al[ok]                              # opaklık: 1 = opak, 0 = tam saydam
        self.n_unit = n / np.sqrt(nn)[:, None]
        a = np.cross(e2, n) / nn[:, None]               # u = (p-v0)·a
        b = np.cross(n, e1) / nn[:, None]               # v = (p-v0)·b
        self.N, self.A, self.B = n, a, b
        self.v0N = (v0 * n).sum(1)
        self.v0A = (v0 * a).sum(1)
        self.v0B = (v0 * b).sum(1)
        self.count = len(v0)


def _tri_hits(sc, O, D, ids):
    """O,D: (R,3). ids: üçgen indeksleri (K,). Döner t (R,K); isabet yoksa inf."""
    N, A, B = sc.N[ids], sc.A[ids], sc.B[ids]
    Dn = D @ N.T
    On = O @ N.T
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (sc.v0N[ids] - On) / Dn
        u = O @ A.T - sc.v0A[ids] + t * (D @ A.T)
        v = O @ B.T - sc.v0B[ids] + t * (D @ B.T)
        ok = (t > 0) & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1.0 + 1e-9)
    return np.where(ok, t, np.inf)


def _closest(sc, O, D, ids):
    """Her ışın için en yakın isabet. Döner (t, üçgen_id); isabet yoksa t=inf, id=-1."""
    R, K = len(D), len(ids)
    step = max(1, S._MAXPAIR // max(K, 1))
    tb = np.empty(R)
    ib = np.empty(R, dtype=np.int64)
    tol = sc.diag * S.TIE_TOL
    ids = np.asarray(ids, dtype=np.int64)
    for s in range(0, R, step):
        t = _tri_hits(sc, O[s:s + step], D[s:s + step], ids)
        # Çakışan (aynı düzlemdeki) yüzeylerde sayısal gürültü benek yaratmasın: mesafesi en yakından
        # tol kadar uzak olanlar eşit sayılır ve sabit bir kural (en küçük üçgen indeksi) seçilir.
        near = t <= (t.min(1) + tol)[:, None]
        rank = ids if not S.TIE_LAST else -ids                    # tile sırasından bağımsız, üçgen indeksine göre
        j = np.where(near, rank[None, :], np.iinfo(np.int64).max).argmin(1)
        tb[s:s + step] = t[np.arange(len(j)), j]
        ib[s:s + step] = ids[j]
    ib[~np.isfinite(tb)] = -1
    return tb, ib


def _any(sc, O, D, ids):
    R, K = len(D), len(ids)
    step = max(1, S._MAXPAIR // max(K, 1))
    occ = np.empty(R, dtype=bool)
    for s in range(0, R, step):
        occ[s:s + step] = np.isfinite(_tri_hits(sc, O[s:s + step], D[s:s + step], ids)).any(1)
    return occ


def _norm(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), S._EPS)


def camera_basis(fwd, up):
    fwd = fwd / np.linalg.norm(fwd)
    right = np.cross(fwd, up)
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    return right, up, fwd
