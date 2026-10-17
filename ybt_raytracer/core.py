# -*- coding: utf-8 -*-
import numpy as np
from . import settings as S


# ============================ SAF NUMPY ÇEKİRDEK ============================
class Scene(object):
    """Üçgen listesi + ışın izleme için ön hesaplar. Her şey sahne merkezine göredir (float64)."""

    def __init__(self, tris, colors, alpha=None, mid=None, mtable=None, oid=None, onames=None):
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
        # malzeme: üçgen başına indeks (0 = atanmamış -> genel ayarlar); mtable[i-1] = malzeme sözlüğü
        self.mid = (np.zeros(len(ok), dtype=np.int32) if mid is None else np.asarray(mid, dtype=np.int32).reshape(-1))[ok]
        self.mtable = list(mtable or [])
        # nesne: üçgen başına indeks (-1 = bilinmiyor); onames[i] = nesnenin belge adı (tıkla-seç / pick için)
        self.oid = (np.full(len(ok), -1, dtype=np.int32) if oid is None else np.asarray(oid, dtype=np.int32).reshape(-1))[ok]
        self.onames = list(onames or [])
        self.n_unit = n / np.sqrt(nn)[:, None]
        a = np.cross(e2, n) / nn[:, None]               # u = (p-v0)·a
        b = np.cross(n, e1) / nn[:, None]               # v = (p-v0)·b
        self.N, self.A, self.B = n, a, b
        self.v0N = (v0 * n).sum(1)
        self.v0A = (v0 * a).sum(1)
        self.v0B = (v0 * b).sum(1)
        self.count = len(v0)

    def smooth_normals(self, angle_deg=45.0):
        """Köşe normalleri (count,3,3): aynı noktada buluşan, aralarındaki açı eşikten küçük yüzlerin alan ağırlıklı
        ortalaması. Eğri yüzeyler (küre, simit, silindir yanı) pürüzsüz görünür; keskin kenarlar (küp, plaka) korunur."""
        n = self.count
        cos_t = float(np.cos(np.radians(angle_deg)))
        fn = self.n_unit
        wt = np.sqrt((self.N * self.N).sum(1))                    # 2 x alan
        q = np.round(self.tri.reshape(-1, 3) / (self.diag * 1e-6)).astype(np.int64)
        # Köşe kimliği ÇAKIŞMASIZ olmalı: eski xor-özet farklı köşeleri aynı sayıp normallerini karıştırıyordu
        # (karmaşık yüzeylerde benek/harf biçimli bozulma). Koordinatlar 21 bite sığıyorsa tek int64'e paketlenir.
        q -= q.min(0)
        if int(q.max()) < (1 << 21):
            key = (q[:, 0] << 42) | (q[:, 1] << 21) | q[:, 2]
            _u, vid = np.unique(key, return_inverse=True)
        else:
            _u, vid = np.unique(q, axis=0, return_inverse=True)
        vid = vid.reshape(-1)
        cface = np.repeat(np.arange(n), 3)                         # köşe -> yüz
        order = np.argsort(vid, kind="stable")
        counts = np.bincount(vid)
        starts = np.concatenate(([0], np.cumsum(counts)[:-1]))
        gsize = counts[vid]
        gstart = starts[vid]
        acc = fn[cface] * wt[cface][:, None]                       # kendi yüzü
        kmax = int(min(counts.max(), 48))
        corners = np.arange(3 * n)
        for r in range(kmax):
            sel = corners[gsize > r]
            if len(sel) == 0:
                break
            pc = order[gstart[sel] + r]                            # komşu köşe
            pf = cface[pc]
            ok = (pf != cface[sel]) & ((fn[cface[sel]] * fn[pf]).sum(1) > cos_t)
            sel, pf = sel[ok], pf[ok]
            np.add.at(acc, sel, fn[pf] * wt[pf][:, None])
        ln = np.sqrt((acc * acc).sum(1))
        bad = ln < 1e-30
        acc[bad] = fn[cface[bad]]
        ln[bad] = 1.0
        return (acc / ln[:, None]).reshape(n, 3, 3)


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


def _closest_sorted(sc, O, D, ids, smin, first=256, big=32768):
    """_closest ile aynı sonucu verir ama üçgenleri kameraya yakınlığa göre gruplar halinde dener:
    bir ışının bulduğu isabet, kalan gruplardaki hiçbir üçgenden daha uzak olamıyorsa ışın elenir.
    smin: üçgen başına (köşelerin kamera ekseni üzerindeki en küçük derinliği, kamera konumuna göre).
    Işın başlangıcı kamera konumundan farklıysa (ortografik) çağıran O'nun derinlik farkını smin'e göre düzeltir:
    sınır = smin - o_off; burada o_off ışının kendi derinliği, _closest_sorted içinde hesaplanır (sc._sort_ctx)."""
    pos, fwd = sc._sort_ctx
    ids = np.asarray(ids, dtype=np.int64)
    if len(ids) <= first:
        return _closest(sc, O, D, ids)
    order = np.argsort(smin[ids], kind="stable")
    ids = ids[order]
    ss = smin[ids]
    R, K = len(D), len(ids)
    tb = np.full(R, np.inf)
    ib = np.full(R, -1, dtype=np.int64)
    o_off = (O - pos) @ fwd
    tol = sc.diag * S.TIE_TOL
    act = np.arange(R)
    p, size = 0, first
    while p < K and len(act):
        batch = ids[p:p + size]
        t, i = _closest(sc, O[act], D[act], batch)
        old = tb[act]
        oi = ib[act]
        take = t < old - tol
        near = (~take) & (t <= old + tol) & (i >= 0)
        if near.any():
            better = (i < oi) if not S.TIE_LAST else (i > oi)
            better |= (oi < 0)
            take |= near & better
        tb[act] = np.where(take, t, old)
        ib[act] = np.where(take, i, oi)
        p += len(batch)
        size = min(size * 2, big)
        if p < K:
            bound = ss[p] - o_off[act]
            act = act[~(tb[act] + tol < bound)]
    ib[~np.isfinite(tb)] = -1
    return tb, ib


def _any(sc, O, D, ids):
    R, K = len(D), len(ids)
    step = max(1, S._MAXPAIR // max(K, 1))
    occ = np.empty(R, dtype=bool)
    for s in range(0, R, step):
        occ[s:s + step] = np.isfinite(_tri_hits(sc, O[s:s + step], D[s:s + step], ids)).any(1)
    return occ


def _dot(a, b):
    """Satır başına nokta çarpımı ((a * b).sum(1)'den ~4 kat hızlı; (n,3)x(3,) yayınlama desteklenir)."""
    if a.ndim == 2 and b.ndim == 2 and a.shape == b.shape:
        return np.einsum('ij,ij->i', a, b)
    if b.ndim == 1 and a.ndim == 2:
        return a @ b
    if a.ndim == 1 and b.ndim == 2:
        return b @ a
    return np.einsum('...j,...j->...', a, b)


def _norm(v):
    return v / np.maximum(np.sqrt(_dot(v, v))[..., None], S._EPS)


def camera_basis(fwd, up):
    fwd = fwd / np.linalg.norm(fwd)
    right = np.cross(fwd, up)
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    return right, up, fwd
