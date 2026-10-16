# -*- coding: utf-8 -*-
import numpy as np
from .core import _any, _norm


_PAIR_BUDGET = 6000000   # hücre-üçgen çifti üst sınırı (bellek koruması)


def _bin(x0, x1, y0, y1, valid, nx, ny):
    """
    Üçgenleri 2B hücrelere dağıtır. x0..y1: üçgen başına hücre aralığı (dahil, int).
    Döner (offs, ids, always):
      hücre c için üçgenler ids[offs[c]:offs[c+1]]; ayrıca `always` üçgenleri HER hücrede test edilir.
    `always`: hücrelerin büyük bölümünü kaplayan üçgenler (zemin, duvar...). Hücre çiftlerine
    açılmazlar; böylece çift sayısı (bellek/süre) _PAIR_BUDGET ile sınırlı kalır.
    """
    T = len(x0)
    wx = np.where(valid, x1 - x0 + 1, 0)
    wy = np.where(valid, y1 - y0 + 1, 0)
    cnt = np.maximum(wx, 0) * np.maximum(wy, 0)
    thr = 0.35 * nx * ny
    while thr >= 1.0 and cnt[cnt <= thr].sum() > _PAIR_BUDGET:
        thr /= 2.0
    big = cnt > thr
    always = np.nonzero(big)[0].astype(np.int64)
    cnt = np.where(big, 0, cnt)
    total = int(cnt.sum())
    if total == 0:
        return np.zeros(nx * ny + 1, dtype=np.int64), np.zeros(0, dtype=np.int64), always
    tri = np.repeat(np.arange(T), cnt)
    start = np.cumsum(cnt) - cnt
    loc = np.arange(total) - np.repeat(start, cnt)
    wxr = np.repeat(np.maximum(wx, 1), cnt)
    cx = np.repeat(x0, cnt) + loc % wxr
    cy = np.repeat(y0, cnt) + loc // wxr
    cell = cy * nx + cx
    order = np.argsort(cell, kind="stable")
    ids = tri[order]
    counts = np.bincount(cell, minlength=nx * ny)
    offs = np.concatenate([[0], np.cumsum(counts)]).astype(np.int64)
    return offs, ids, always


def _screen_bins(sc, pos, right, up, fwd, persp, half_x, half_y, w, h, tile):
    """
    Her üçgenin ekranda kapladığı karoları bulur.
    Perspektifte: tamamen kameranın arkasındaki üçgenler elenir; yakın düzlemi (z=eps) kesenler
    kırpılmış çokgenin sınır kutusuyla karolara yazılır (eskisi hepsini tüm ekrana yazıyordu).
    """
    nx = (w + tile - 1) // tile
    ny = (h + tile - 1) // tile
    d = sc.tri - pos
    xc, yc, zc = d @ right, d @ up, d @ fwd                 # (T,3)
    if persp:
        eps = 1e-6 * sc.diag
        front = zc > eps
        keep = front.any(1)
        zs = np.where(front, zc, 1.0)
        pxv = (xc / (zs * half_x) + 1.0) / 2.0 * w
        pyv = (1.0 - yc / (zs * half_y)) / 2.0 * h
        lox = np.where(front, pxv, np.inf).min(1)
        hix = np.where(front, pxv, -np.inf).max(1)
        loy = np.where(front, pyv, np.inf).min(1)
        hiy = np.where(front, pyv, -np.inf).max(1)
        for a, b in ((0, 1), (1, 2), (2, 0)):               # yakın düzlemi kesen kenarlar
            cross = front[:, a] != front[:, b]
            if not cross.any():
                continue
            ia = np.nonzero(cross)[0]
            za, zb = zc[ia, a], zc[ia, b]
            t = (eps - za) / (zb - za)
            xi = xc[ia, a] + t * (xc[ia, b] - xc[ia, a])
            yi = yc[ia, a] + t * (yc[ia, b] - yc[ia, a])
            pxi = (xi / (eps * half_x) + 1.0) / 2.0 * w
            pyi = (1.0 - yi / (eps * half_y)) / 2.0 * h
            lox[ia] = np.minimum(lox[ia], pxi)
            hix[ia] = np.maximum(hix[ia], pxi)
            loy[ia] = np.minimum(loy[ia], pyi)
            hiy[ia] = np.maximum(hiy[ia], pyi)
    else:
        keep = np.ones(len(d), dtype=bool)
        pxv = (xc / half_x + 1.0) / 2.0 * w
        pyv = (1.0 - yc / half_y) / 2.0 * h
        lox, hix, loy, hiy = pxv.min(1), pxv.max(1), pyv.min(1), pyv.max(1)
    m = 1.5
    bx0, bx1, by0, by1 = lox - m, hix + m, loy - m, hiy + m
    valid = keep & (bx1 >= 0) & (bx0 <= w) & (by1 >= 0) & (by0 <= h)
    lim_x, lim_y = w - 1e-6, h - 1e-6

    def tcell(v, lim):
        return np.floor(np.clip(np.where(valid, v, 0.0), 0, lim) / tile).astype(np.int64)

    offs, ids, always = _bin(tcell(bx0, lim_x), tcell(bx1, lim_x), tcell(by0, lim_y), tcell(by1, lim_y),
                             valid, nx, ny)
    return nx, ny, offs, ids, always


class _LightGrid(object):
    """Yönlü ışık için: ışık yönüne dik düzleme izdüşüm ızgarası. Gölge ışını = tek nokta."""

    def __init__(self, sc, L, G, subset=None):
        helper = np.array([1.0, 0, 0]) if abs(L[0]) < 0.9 else np.array([0, 1.0, 0])
        a = _norm(np.cross(L, helper))
        b = np.cross(L, a)
        tri = sc.tri if subset is None else sc.tri[subset]
        sa, sb = tri @ a, tri @ b
        self.a, self.b, self.G = a, b, G
        self.amin, self.bmin = sa.min(), sb.min()
        ext = max(sa.max() - self.amin, sb.max() - self.bmin, 1e-9)
        self.scale = G / ext
        mg = 1e-6 * ext
        lim = G - 1e-9

        def cell(v, vmin):
            return np.floor(np.clip((v - vmin) * self.scale, 0, lim)).astype(np.int64)

        x0 = cell(sa.min(1) - mg, self.amin)
        x1 = cell(sa.max(1) + mg, self.amin)
        y0 = cell(sb.min(1) - mg, self.bmin)
        y1 = cell(sb.max(1) + mg, self.bmin)
        self._cell = cell
        self.offs, self.ids, self.always = _bin(x0, x1, y0, y1, np.ones(len(x0), dtype=bool), G, G)
        if subset is not None:                               # yerel indeksleri küresel üçgen indekslerine çevir
            self.ids = subset[self.ids]
            self.always = subset[self.always]

    def shadowed(self, sc, P, L, tk=None):
        """P: (n,3) yüzeyden hafif ofsetli noktalar. Döner bool (n,) — ışığa giden yol kapalı mı."""
        n = len(P)
        occ = np.zeros(n, dtype=bool)
        if n == 0:
            return occ
        cx = self._cell(P @ self.a, self.amin)
        cy = self._cell(P @ self.b, self.bmin)
        cell = cy * self.G + cx
        if len(self.always):
            cand = np.arange(n)                              # her noktayı büyük üçgenlerle de sına
        else:
            cand = np.nonzero(self.offs[cell + 1] - self.offs[cell] > 0)[0]
        if len(cand) == 0:
            return occ
        order = cand[np.argsort(cell[cand], kind="stable")]
        cuts = np.nonzero(np.diff(cell[order]))[0] + 1
        for grp in np.split(order, cuts):
            if tk is not None:
                tk()
            c = cell[grp[0]]
            ids = self.ids[self.offs[c]:self.offs[c + 1]]
            if len(self.always):
                ids = np.concatenate((self.always, ids))
            if len(ids) == 0:
                continue
            Dg = np.broadcast_to(L, (len(grp), 3))
            occ[grp] = _any(sc, P[grp], Dg, ids)
        return occ


class _Clusters(object):
    """
    Yansıma/saydamlık ikincil ışınları için kaba hızlandırıcı: üçgenler Morton sırasıyla 32'şerli
    kümelere bölünür, her kümenin sınır kutusu vardır. Işın önce kutularla, sonra yalnız isabet
    ettiği kümelerin üçgenleriyle sınanır.
    """
    SZ = 32      # küme başına üçgen
    G = 64       # büyük kutu başına küme

    def __init__(self, sc):
        c = sc.tri.mean(1)
        lo, hi = c.min(0), c.max(0)
        q = np.clip(((c - lo) / np.maximum(hi - lo, 1e-12) * 1023.0), 0, 1023).astype(np.int64)

        def spread(x):
            x = (x | (x << 16)) & 0x030000FF
            x = (x | (x << 8)) & 0x0300F00F
            x = (x | (x << 4)) & 0x030C30C3
            x = (x | (x << 2)) & 0x09249249
            return x

        code = spread(q[:, 0]) | (spread(q[:, 1]) << 1) | (spread(q[:, 2]) << 2)
        order = np.argsort(code, kind="stable")
        n = len(order)
        K = -(-n // self.SZ)
        pad = K * self.SZ - n
        self.order = np.concatenate([order, np.full(pad, -1, dtype=order.dtype)]).reshape(K, self.SZ)
        tri = sc.tri[order]
        mn = np.full((K * self.SZ, 3), np.inf)
        mx = np.full((K * self.SZ, 3), -np.inf)
        mn[:n] = tri.min(1)
        mx[:n] = tri.max(1)
        self.lo = mn.reshape(K, self.SZ, 3).min(1)
        self.hi = mx.reshape(K, self.SZ, 3).max(1)
        self.K = K
        K2 = -(-K // self.G)
        padk = K2 * self.G - K
        lo2 = np.concatenate([self.lo, np.full((padk, 3), np.inf)])
        hi2 = np.concatenate([self.hi, np.full((padk, 3), -np.inf)])
        self.slo = lo2.reshape(K2, self.G, 3).min(1)               # büyük kutular: 64 kümelik gruplar
        self.shi = hi2.reshape(K2, self.G, 3).max(1)


def _closest_general(sc, cl, O, D, tk=None):
    """
    Rastgele yönlü ışınlar için en yakın isabet. Üç kademe: büyük kutular (64 küme) -> küme kutuları
    (32 üçgen) -> üçgenler. Işın yalnız çarptığı kutuların içine girer.
    """
    R = len(O)
    tb = np.full(R, np.inf)
    ib = np.full(R, -1, dtype=np.int64)
    K, G, SZ = cl.K, cl.G, cl.SZ
    K2 = len(cl.slo)
    step = max(1, 3000000 // max(K2, 1))
    gar = np.arange(G)
    for s in range(0, R, step):
        o, d = O[s:s + step], D[s:s + step]
        with np.errstate(divide="ignore", invalid="ignore"):
            inv = 1.0 / np.where(np.abs(d) < 1e-12, 1e-12, d)
            t1 = (cl.slo[None] - o[:, None]) * inv[:, None]
            t2 = (cl.shi[None] - o[:, None]) * inv[:, None]
        tnear = np.minimum(t1, t2).max(2)
        tfar = np.maximum(t1, t2).min(2)
        hit1 = (tnear <= tfar) & (tfar >= 0.0)
        r1, s1 = np.nonzero(hit1)
        P2 = 20000

        def process(rr, ss, o=o, d=d, inv=inv, s=s):
            cid = (ss[:, None] * G + gar[None, :]).ravel()
            ray = np.repeat(rr, G)
            ok = cid < K
            cid, ray = cid[ok], ray[ok]
            with np.errstate(divide="ignore", invalid="ignore"):
                oo, ii = o[ray], inv[ray]
                u1 = (cl.lo[cid] - oo) * ii
                u2 = (cl.hi[cid] - oo) * ii
            tn = np.minimum(u1, u2).max(1)
            tf = np.maximum(u1, u2).min(1)
            h2 = (tf >= np.maximum(tn, 0.0))
            cid, ray = cid[h2], ray[h2]
            pstep = 50000
            for p in range(0, len(ray), pstep):
                rc, kc = ray[p:p + pstep], cid[p:p + pstep]
                tid = cl.order[kc].ravel()
                rry = np.repeat(rc, SZ)
                m = tid >= 0
                tid, rry = tid[m], rry[m]
                if len(tid) == 0:
                    continue
                Dd, Oo = d[rry], o[rry]
                Nn, An, Bn = sc.N[tid], sc.A[tid], sc.B[tid]
                with np.errstate(divide="ignore", invalid="ignore"):
                    t = (sc.v0N[tid] - (Oo * Nn).sum(1)) / (Dd * Nn).sum(1)
                    u = (Oo * An).sum(1) - sc.v0A[tid] + t * (Dd * An).sum(1)
                    v = (Oo * Bn).sum(1) - sc.v0B[tid] + t * (Dd * Bn).sum(1)
                    okt = (t > 0) & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1.0 + 1e-9)
                t = np.where(okt, t, np.inf)
                order = np.argsort(rry, kind="stable")             # aynı ışının çiftleri bitişik olsun
                rry, t, tid = rry[order], t[order], tid[order]
                uniq, start = np.unique(rry, return_index=True)
                cnt = np.diff(np.append(start, len(t)))
                mins = np.minimum.reduceat(t, start)
                seg = np.repeat(np.arange(len(uniq)), cnt)
                mi = np.nonzero(np.isfinite(t) & (t == mins[seg]))[0]
                if len(mi) == 0:
                    continue
                us, fi = np.unique(seg[mi], return_index=True)
                g = uniq[us] + s
                tt, ii2 = t[mi[fi]], tid[mi[fi]]
                better = tt < tb[g]
                tb[g[better]] = tt[better]
                ib[g[better]] = ii2[better]

        # Büyük kutuları ışına yakından uzağa doğru işle; ışının o ana kadar bulduğu en yakın isabet
        # bir kutunun giriş mesafesinden küçükse o kutu (ve ardındakiler) atlanır.
        if len(r1) == 0:
            continue
        tn1 = np.maximum(tnear[r1, s1], 0.0)
        o_ = np.lexsort((tn1, r1))
        r1, s1, tn1 = r1[o_], s1[o_], tn1[o_]
        rank = np.arange(len(r1)) - np.searchsorted(r1, r1, side="left")
        o_ = np.argsort(rank, kind="stable")
        r1, s1, tn1, rank = r1[o_], s1[o_], tn1[o_], rank[o_]
        bnd = np.searchsorted(rank, np.arange(int(rank[-1]) + 2))
        for kk in range(len(bnd) - 1):
            ra, sa, ta = r1[bnd[kk]:bnd[kk + 1]], s1[bnd[kk]:bnd[kk + 1]], tn1[bnd[kk]:bnd[kk + 1]]
            live = ta < tb[ra + s]
            if not live.any():
                break                      # bu sıradaki kutular hiçbir ışına yetmiyor; sonrakiler daha uzak
            ra, sa = ra[live], sa[live]
            for p2 in range(0, len(ra), P2):
                if tk is not None:
                    tk()
                process(ra[p2:p2 + P2], sa[p2:p2 + P2])
    return tb, ib
