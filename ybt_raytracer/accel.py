# -*- coding: utf-8 -*-
import numpy as np
from . import settings as S
from .core import _any, _dot, _norm


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


def _screen_boxes(sc, pos, right, up, fwd, persp, half_x, half_y, w, h):
    """
    Her üçgenin ekranda kapladığı karoları bulur.
    Perspektifte: tamamen kameranın arkasındaki üçgenler elenir; yakın düzlemi (z=eps) kesenler
    kırpılmış çokgenin sınır kutusuyla karolara yazılır (eskisi hepsini tüm ekrana yazıyordu).
    """
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
    return bx0, bx1, by0, by1, valid


def _screen_bins(sc, pos, right, up, fwd, persp, half_x, half_y, w, h, tile):
    """Her üçgenin ekranda kapladığı karoları bulur (kutular için _screen_boxes)."""
    nx = (w + tile - 1) // tile
    ny = (h + tile - 1) // tile
    bx0, bx1, by0, by1, valid = _screen_boxes(sc, pos, right, up, fwd, persp, half_x, half_y, w, h)
    lim_x, lim_y = w - 1e-6, h - 1e-6

    def tcell(v, lim):
        return np.floor(np.clip(np.where(valid, v, 0.0), 0, lim) / tile).astype(np.int64)

    offs, ids, always = _bin(tcell(bx0, lim_x), tcell(bx1, lim_x), tcell(by0, lim_y), tcell(by1, lim_y),
                             valid, nx, ny)
    return nx, ny, offs, ids, always


def _mask_sat(mask):
    """Toplam-alan tablosu (integral image): (h+1, w+1) int32."""
    h, w = mask.shape
    sat = np.zeros((h + 1, w + 1), dtype=np.int32)
    np.cumsum(np.cumsum(mask, axis=0, dtype=np.int32), axis=1, out=sat[1:, 1:])
    return sat


def band_sel(boxes, r0, r1, w):
    """r0..r1-1 satırlarını (her piksel içi konum için) kapsayabilecek üçgenler; raster_rows(sel=...) ile tekrar kullanılır."""
    bx0, bx1, by0, by1, valid = boxes
    return np.nonzero(valid & (by1 >= r0) & (by0 <= r1) & (bx1 >= 0) & (bx0 <= w))[0]


def raster_rows(sc, boxes, r0, r1, w, sx, sy, rays, mask=None, chunk=1500000, sel=None):
    """
    Görünürlük tamponu: r0..r1-1 satırlarındaki piksellerin (piksel içi konum sx, sy) birincil ışınlarının
    ilk çarptığı üçgen. _closest ile AYNI sonucu verir (aynı kesişim sınaması, aynı eşitlik kuralı) ama
    her üçgeni yalnız ekran kutusundaki piksellere uygular; piksel başına tüm üçgenleri taramaz.
    boxes: _screen_boxes çıktısı. rays(px, py, sx, sy) -> (O, D): O (n,3) ya da (3,), D (n,3).
    mask: (h, w) bool; verilirse yalnız True piksellere bakılır.
    Döner (t, id): (r1-r0, w) dizileri; isabet yoksa t=inf, id=-1.
    """
    bx0, bx1, by0, by1, valid = boxes
    nrow = r1 - r0
    out_t = np.full(nrow * w, np.inf)
    out_i = np.full(nrow * w, -1, dtype=np.int64)
    if sel is None:
        sel = band_sel(boxes, r0, r1, w)
    if len(sel) == 0:
        return out_t.reshape(nrow, w), out_i.reshape(nrow, w)
    ix0 = np.maximum(np.ceil(bx0[sel] - sx), 0).astype(np.int64)
    ix1 = np.minimum(np.floor(bx1[sel] - sx), w - 1).astype(np.int64)
    iy0 = np.maximum(np.ceil(by0[sel] - sy), r0).astype(np.int64)
    iy1 = np.minimum(np.floor(by1[sel] - sy), r1 - 1).astype(np.int64)
    nxp, nyp = ix1 - ix0 + 1, iy1 - iy0 + 1
    ok = (nxp > 0) & (nyp > 0)
    if mask is not None and ok.any():                      # kutusunda hiç istenen piksel olmayan üçgenleri baştan ele
        sat = _mask_sat(mask)
        jx0, jy0 = np.where(ok, ix0, 0), np.where(ok, iy0, 0)
        jx1, jy1 = np.where(ok, ix1, 0), np.where(ok, iy1, 0)
        n_in = sat[jy1 + 1, jx1 + 1] - sat[jy0, jx1 + 1] - sat[jy1 + 1, jx0] + sat[jy0, jx0]
        ok &= n_in > 0
    sel, ix0, iy0, nxp, nyp = sel[ok], ix0[ok], iy0[ok], nxp[ok], nyp[ok]
    cnt = nxp * nyp
    if len(sel) == 0:
        return out_t.reshape(nrow, w), out_i.reshape(nrow, w)
    cum = np.cumsum(cnt)
    tol = sc.diag * S.TIE_TOL
    P_, T_, I_ = [], [], []
    a = 0
    while a < len(sel):
        base = cum[a - 1] if a else 0
        b = int(np.searchsorted(cum, base + chunk, side="right"))
        b = max(b, a + 1)
        c = cnt[a:b]
        tot = int(c.sum())
        tri = np.repeat(sel[a:b], c)
        st = np.cumsum(c) - c
        loc = np.arange(tot) - np.repeat(st, c)
        nxr = np.repeat(nxp[a:b], c)
        px = np.repeat(ix0[a:b], c) + loc % nxr
        py = np.repeat(iy0[a:b], c) + loc // nxr
        if mask is not None:
            m = mask[py, px]
            tri, px, py = tri[m], px[m], py[m]
        if len(tri):
            O, D = rays(px, py, sx, sy)
            Nn = sc.N[tri]
            Dn = _dot(D, Nn)
            On = _dot(O, Nn) if O.ndim == 2 else Nn @ O
            with np.errstate(divide="ignore", invalid="ignore"):
                t = (sc.v0N[tri] - On) / Dn
                Aa, Bb = sc.A[tri], sc.B[tri]
                if O.ndim == 2:
                    u = _dot(O, Aa) - sc.v0A[tri] + t * _dot(D, Aa)
                    v = _dot(O, Bb) - sc.v0B[tri] + t * _dot(D, Bb)
                else:
                    u = Aa @ O - sc.v0A[tri] + t * _dot(D, Aa)
                    v = Bb @ O - sc.v0B[tri] + t * _dot(D, Bb)
                hit = (t > 0) & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1.0 + 1e-9)
            if hit.any():
                P_.append(((py[hit] - r0) * w + px[hit]).astype(np.int64))
                T_.append(t[hit])
                I_.append(tri[hit])
        a = b
    if not P_:
        return out_t.reshape(nrow, w), out_i.reshape(nrow, w)
    P_, T_, I_ = np.concatenate(P_), np.concatenate(T_), np.concatenate(I_)
    order = np.lexsort((T_, P_))
    P_, T_, I_ = P_[order], T_[order], I_[order]
    starts = np.nonzero(np.concatenate(([True], P_[1:] != P_[:-1])))[0]
    gid = np.cumsum(np.concatenate(([False], P_[1:] != P_[:-1])))
    tmin = T_[starts]
    near = T_ <= tmin[gid] + tol
    big = np.iinfo(np.int64).max
    rank = I_ if not S.TIE_LAST else -I_
    key = np.where(near, rank, big)
    best = np.minimum.reduceat(key, starts)
    chosen = best if not S.TIE_LAST else -best
    tsel = np.minimum.reduceat(np.where(near & (I_ == chosen[gid]), T_, np.inf), starts)
    pix = P_[starts]
    out_t[pix] = tsel
    out_i[pix] = chosen
    return out_t.reshape(nrow, w), out_i.reshape(nrow, w)


class _LightGrid(object):
    """
    Yönlü ışık için gölge hızlandırıcısı: ışık yönüne dik düzleme izdüşüm ızgarası, ÇOK SEVİYELİ.
    Her üçgen, ayak izi en çok 4 hücre olan en ince seviyeye konur (küçük üçgenler ince ızgaraya, büyükler kaba
    ızgaraya); böylece toplam kayıt sayısı üçgen sayısının ~4 katıyla sınırlı kalır ve bir hücrede hep birkaç üçgen
    bulunur (eski tek ızgarada büyük üçgenler 'always' listesine düşüp her ışına test ediliyordu).
    Her hücrede ayrıca üçgenlerin ışık yönündeki en yüksek konumu (lmax) tutulur: yüzey noktası hücredeki hiçbir
    üçgenin üstünde değilse ışın hiçbir şeye çarpamaz -> üçgen testi yapılmadan 'aydınlık' denir (kesin, yaklaşık değil).
    Gölge ışını = tek nokta; çarpışma testi eskisiyle aynıdır.
    """
    FOOT = 4          # bir üçgenin bir seviyedeki en çok hücre sayısı
    STEP = 3          # seviyeler arası ızgara küçülmesi: 2**STEP

    def __init__(self, sc, L, G, subset=None):
        helper = np.array([1.0, 0, 0]) if abs(L[0]) < 0.9 else np.array([0, 1.0, 0])
        a = _norm(np.cross(L, helper))
        b = np.cross(L, a)
        tri = sc.tri if subset is None else sc.tri[subset]
        sa, sb, sl = tri @ a, tri @ b, tri @ L
        self.a, self.b, self.L, self.diag = a, b, np.asarray(L, dtype=np.float64), sc.diag
        self.amin, self.bmin = sa.min(), sb.min()
        ext = max(sa.max() - self.amin, sb.max() - self.bmin, 1e-9)
        G = int(G)
        self.G = G
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
        lmax = sl.max(1)
        T = len(x0)
        # seviye ata: ayak izi FOOT hücreyi aşmayan ilk (en ince) seviye; kaba uç: ızgara >= 4 hücre
        lvl = np.zeros(T, dtype=np.int64)
        undone = np.ones(T, dtype=bool)
        shifts = []
        k = 0
        while True:
            sh = k * self.STEP
            Gk = max(G >> sh, 1)
            shifts.append((sh, Gk))
            cnt = ((x1 >> sh) - (x0 >> sh) + 1) * ((y1 >> sh) - (y0 >> sh) + 1)
            fit = undone & (cnt <= self.FOOT)
            lvl[fit] = k
            undone &= ~fit
            if not undone.any() or Gk <= 4:
                lvl[undone] = k
                break
            k += 1
        self.levels = []
        for k, (sh, Gk) in enumerate(shifts):
            idx = np.nonzero(lvl == k)[0]
            if len(idx) == 0:
                continue
            cx0, cx1, cy0, cy1 = x0[idx] >> sh, x1[idx] >> sh, y0[idx] >> sh, y1[idx] >> sh
            wx, wy = cx1 - cx0 + 1, cy1 - cy0 + 1
            cnt = wx * wy
            tot = int(cnt.sum())
            ti = np.repeat(np.arange(len(idx)), cnt)
            st = np.cumsum(cnt) - cnt
            loc = np.arange(tot) - np.repeat(st, cnt)
            wxr = np.repeat(wx, cnt)
            cell_id = (np.repeat(cy0, cnt) + loc // wxr) * Gk + (np.repeat(cx0, cnt) + loc % wxr)
            order = np.argsort(cell_id, kind="stable")
            ids_l = idx[ti[order]]
            counts = np.bincount(cell_id, minlength=Gk * Gk)
            offs = np.concatenate([[0], np.cumsum(counts)]).astype(np.int64)
            cmax = np.full(Gk * Gk, -np.inf)
            ne = np.nonzero(counts > 0)[0]
            cmax[ne] = np.maximum.reduceat(lmax[ids_l], offs[ne])
            ids_g = (subset[ids_l] if subset is not None else ids_l).astype(np.int64)
            self.levels.append((sh, Gk, offs, ids_g, cmax))

    def shadowed(self, sc, P, L, tk=None, want_t=False):
        """P: (n,3) yüzeyden hafif ofsetli noktalar. Döner bool (n,) — ışığa giden yol kapalı mı.
        want_t=True: (bool, t) — t, bulunan bir engelle olan mesafe (yumuşak gölge yarı gölge genişliği için; en yakın olması garanti değil)."""
        n = len(P)
        occ = np.zeros(n, dtype=bool)
        tmin = np.full(n, np.inf) if want_t else None
        if n == 0:
            return (occ, tmin) if want_t else occ
        L = np.asarray(L, dtype=np.float64)
        lP = P @ L - 1e-9 * self.diag                         # bu yüksekliğin altında kalan üçgenler ışını kesemez
        cx = self._cell(P @ self.a, self.amin)
        cy = self._cell(P @ self.b, self.bmin)
        cells = []
        need = np.zeros(n, dtype=bool)
        for sh, Gk, offs, ids, cmax in self.levels:
            c = (cy >> sh) * Gk + (cx >> sh)
            cells.append(c)
            need |= cmax[c] > lP
        cand = np.nonzero(need)[0]
        for (sh, Gk, offs, ids, cmax), c in zip(self.levels, cells):
            if len(cand) == 0:
                break
            cc = c[cand]
            cnt = offs[cc + 1] - offs[cc]
            keep = (cnt > 0) & (cmax[cc] > lP[cand])
            if not keep.any():
                continue
            sub = cand[keep]
            cnt = cnt[keep]
            start = offs[cc[keep]]
            if want_t:
                tm_ = np.full(len(sub), np.inf)
                occ[sub] |= self._pairs(sc, P, L, sub, start, cnt, ids, tk, tm=tm_)
                tmin[sub] = np.minimum(tmin[sub], tm_)
            else:
                occ[sub] |= self._pairs(sc, P, L, sub, start, cnt, ids, tk)
            cand = cand[~occ[cand]]
        return (occ, tmin) if want_t else occ

    @staticmethod
    def _pairs(sc, P, L, sub, start, cnt, ids, tk, chunk=1500000, tm=None):
        """(nokta, üçgen) çiftlerini vektörel sınar; her nokta için en az bir çarpışma var mı."""
        res = np.zeros(len(sub), dtype=bool)
        cum = np.cumsum(cnt)
        a = 0
        while a < len(sub):
            if tk is not None:
                tk()
            base = cum[a - 1] if a else 0
            e = max(int(np.searchsorted(cum, base + chunk, side="right")), a + 1)
            c = cnt[a:e]
            tot = int(c.sum())
            pl = np.repeat(np.arange(a, e), c)
            st = np.cumsum(c) - c
            tri = ids[np.repeat(start[a:e], c) + (np.arange(tot) - np.repeat(st, c))]
            Pp = P[sub[pl]]
            Nn = sc.N[tri]
            Aa, Bb = sc.A[tri], sc.B[tri]
            with np.errstate(divide="ignore", invalid="ignore"):
                t = (sc.v0N[tri] - _dot(Pp, Nn)) / (Nn @ L)
                u = _dot(Pp, Aa) - sc.v0A[tri] + t * (Aa @ L)
                v = _dot(Pp, Bb) - sc.v0B[tri] + t * (Bb @ L)
                hit = (t > 0) & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1.0 + 1e-9)
            if hit.any():
                res[np.unique(pl[hit])] = True
                if tm is not None:
                    np.minimum.at(tm, pl[hit], t[hit])
            a = e
        return res


class _Clusters(object):
    """
    Yansıma/saydamlık ikincil ışınları için kaba hızlandırıcı: üçgenler Morton sırasıyla 32'şerli
    kümelere bölünür, her kümenin sınır kutusu vardır. Işın önce kutularla, sonra yalnız isabet
    ettiği kümelerin üçgenleriyle sınanır.
    """
    SZ = 8       # küme başına üçgen (ölçüm: 8, eski 32’ye göre ~3,5x hızlı)
    G = 8        # büyük kutu başına küme
    F = 4        # büyük kutu ağacında düğüm başına çocuk

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
        # büyük kutuların üstüne 8'li ağaç: ışın tüm büyük kutuları değil yalnız isabet ettiği dalları sınar
        self.tlo, self.thi, self.tcnt = [self.slo], [self.shi], [K2]
        while self.tcnt[-1] > 1:
            lo_, hi_ = self.tlo[-1], self.thi[-1]
            n_ = len(lo_)
            m_ = -(-n_ // self.F) * self.F
            lo_ = np.concatenate([lo_, np.full((m_ - n_, 3), np.inf)])
            hi_ = np.concatenate([hi_, np.full((m_ - n_, 3), -np.inf)])
            self.tlo.append(lo_.reshape(-1, self.F, 3).min(1))
            self.thi.append(hi_.reshape(-1, self.F, 3).max(1))
            self.tcnt.append(len(self.tlo[-1]))


_BIG = np.iinfo(np.int64).max // 4


def _big_hits(cl, o, d, inv, tmax=np.inf):
    """Işın x büyük kutu isabetleri, 8'li ağaçta yukarıdan aşağıya inerek. Döner (ışın, kutu, giriş mesafesi)."""
    R = len(o)
    F = cl.F
    rr = np.arange(R)
    nn = np.zeros(R, dtype=np.int64)
    for L in range(len(cl.tlo) - 1, -1, -1):
        oo, ii = o[rr], inv[rr]
        with np.errstate(invalid="ignore"):
            t1 = (cl.tlo[L][nn] - oo) * ii
            t2 = (cl.thi[L][nn] - oo) * ii
        tn = np.minimum(t1, t2).max(1)
        tf = np.maximum(t1, t2).min(1)
        ok = (tn <= tf) & (tf >= 0.0) & (tn <= tmax)
        rr, nn, tn = rr[ok], nn[ok], tn[ok]
        if L == 0:
            return rr, nn, tn
        if len(rr) == 0:
            return rr, nn, tn
        rr = np.repeat(rr, F)
        nn = np.repeat(nn, F) * F + np.tile(np.arange(F), len(nn))
        keep = nn < cl.tcnt[L - 1]
        rr, nn = rr[keep], nn[keep]
    return rr, nn, np.zeros(0)


def _closest_general(sc, cl, O, D, tk=None, tmax=None):
    """
    Rastgele yönlü ışınlar için en yakın isabet. Üç kademe: büyük kutular (64 küme) -> küme kutuları
    (32 üçgen) -> üçgenler. Işın yalnız çarptığı kutuların içine girer.
    """
    R = len(O)
    tb = np.full(R, np.inf if tmax is None else float(tmax))      # tmax: bu uzaklığın ötesi aranmaz (AO gibi kısa menzilli ışınlar)
    ib = np.full(R, -1, dtype=np.int64)
    K, G, SZ = cl.K, cl.G, cl.SZ
    tol = float(S.TIE_TOL) * sc.diag
    step = 100000
    CR = 2                                           # tur başına ışın başına küme sayısı
    gar = np.arange(G)
    for s in range(0, R, step):
        o, d = O[s:s + step], D[s:s + step]
        with np.errstate(divide="ignore", invalid="ignore"):
            inv = 1.0 / np.where(np.abs(d) < 1e-12, 1e-12, d)
        r1, s1, tnear1 = _big_hits(cl, o, d, inv, np.inf if tmax is None else float(tmax))
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
            cid, ray, tn = cid[h2], ray[h2], tn[h2]
            pstep = 50000
            slack = tol + 1e-9 * sc.diag

            def tris(rc, kc):
                tid = cl.order[kc].ravel()
                rry = np.repeat(rc, SZ)
                m = tid >= 0
                tid, rry = tid[m], rry[m]
                if len(tid) == 0:
                    return
                Dd, Oo = d[rry], o[rry]
                Nn, An, Bn = sc.N[tid], sc.A[tid], sc.B[tid]
                with np.errstate(divide="ignore", invalid="ignore"):
                    t = (sc.v0N[tid] - _dot(Oo, Nn)) / _dot(Dd, Nn)
                    u = _dot(Oo, An) - sc.v0A[tid] + t * _dot(Dd, An)
                    v = _dot(Oo, Bn) - sc.v0B[tid] + t * _dot(Dd, Bn)
                    okt = (t > 0) & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1.0 + 1e-9)
                t = np.where(okt, t, np.inf)
                order = np.argsort(rry, kind="stable")             # aynı ışının çiftleri bitişik olsun
                rry, t, tid = rry[order], t[order], tid[order]
                uniq, start = np.unique(rry, return_index=True)
                cnt = np.diff(np.append(start, len(t)))
                mins = np.minimum.reduceat(t, start)
                seg = np.repeat(np.arange(len(uniq)), cnt)
                near = np.isfinite(t) & (t <= mins[seg] + tol)        # eşit uzaklıktaki (çakışan) yüzeyler
                if not near.any():
                    return
                cand = np.where(near, tid if not S.TIE_LAST else -tid, _BIG)
                mr = np.minimum.reduceat(cand, start)                 # eşitlikte _closest ile aynı kural: en küçük indeks
                mi = np.nonzero(near & (cand == mr[seg]))[0]
                us, fi = np.unique(seg[mi], return_index=True)
                g = uniq[us] + s
                tt, ii2 = t[mi[fi]], tid[mi[fi]]
                old_t, old_i = tb[g], ib[g]
                r_new = ii2 if not S.TIE_LAST else -ii2
                r_old = np.where(old_i >= 0, old_i if not S.TIE_LAST else -old_i, _BIG)
                better = (tt < old_t - tol) | ((np.abs(tt - old_t) <= tol) & (r_new < r_old))
                tb[g[better]] = tt[better]
                ib[g[better]] = ii2[better]

            # Kümeleri ışına yakından uzağa, turlar halinde işle: ışının o ana kadar bulduğu en yakın isabetten
            # (eşitlik payıyla) uzakta giriş yapan kümeler hiç üçgen sınanmadan atlanır.
            keep = tn <= tb[ray + s] + slack
            cid, ray, tn = cid[keep], ray[keep], np.maximum(tn[keep], 0.0)
            if len(ray) == 0:
                return
            o2 = np.lexsort((tn, ray))
            cid, ray, tn = cid[o2], ray[o2], tn[o2]
            rnd = (np.arange(len(ray)) - np.searchsorted(ray, ray, side="left")) // CR
            o3 = np.argsort(rnd, kind="stable")
            cid, ray, tn, rnd = cid[o3], ray[o3], tn[o3], rnd[o3]
            bd = np.searchsorted(rnd, np.arange(int(rnd[-1]) + 2))
            for k2 in range(len(bd) - 1):
                rc, kc, tc = ray[bd[k2]:bd[k2 + 1]], cid[bd[k2]:bd[k2 + 1]], tn[bd[k2]:bd[k2 + 1]]
                lv = tc <= tb[rc + s] + slack
                if not lv.any():
                    break
                rc, kc = rc[lv], kc[lv]
                for p in range(0, len(rc), pstep):
                    tris(rc[p:p + pstep], kc[p:p + pstep])

        # Büyük kutuları ışına yakından uzağa doğru işle; ışının o ana kadar bulduğu en yakın isabet
        # bir kutunun giriş mesafesinden küçükse o kutu (ve ardındakiler) atlanır.
        if len(r1) == 0:
            continue
        tn1 = np.maximum(tnear1, 0.0)
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
