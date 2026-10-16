# -*- coding: utf-8 -*-
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as _FutTimeout
import numpy as np
import os
import sys
import time
from . import settings as S
from .textures import load as load_texture
from .core import _any, _closest, _norm, camera_basis
from .parallel import _Ticker, _limit_blas
from .accel import _Clusters, _LightGrid, _closest_general, _screen_bins


def _acc(acc, idx, vals):
    np.add.at(acc, idx, vals)


def render(scene, cam, w, h, shadows=True, progress=None, tile=16, brute=False, tick=None, stage=None):
    """
    cam: dict(pos, fwd, up, persp=bool, size=float)
         persp ise size = dikey bakış açısı (radyan), değilse ortografik görünüm yüksekliği.
    progress(img, rows_done): her bantta çağrılır; False dönerse iptal.
    tick(): uzun döngülerde ~0.15 sn'de bir çağrılır (arayüzü canlı tutmak için); False dönerse
            _Cancelled fırlatılır. stage(mesaj): aşama bildirimi.
    brute=True: eleme yok, her ışın tüm üçgenlerle test edilir (yalnız doğrulama için).
    Ayarlar (modül düzeyi): GLASS (saydamlık), REFLECT_GLASS (cam yansıması), REFLECT_SURF (opak yüzey
    yansıması), BOUNCES (en çok yansıma sayısı).
    Döner: (h, w, 3) uint8 ya da iptal edilirse None.
    """
    tk = _Ticker(tick)
    say = stage if stage is not None else (lambda s: None)
    pos = np.asarray(cam["pos"], dtype=np.float64) - scene.center
    right, up, fwd = camera_basis(np.asarray(cam["fwd"], float), np.asarray(cam["up"], float))
    persp = bool(cam["persp"])
    aspect = float(w) / float(h)
    # Coin'de heightAngle/height küçük kenara uygulanır
    base = (np.tan(cam["size"] / 2.0) if persp else cam["size"] / 2.0)
    if aspect >= 1.0:
        half_y, half_x = base, base * aspect
    else:
        half_x, half_y = base, base / aspect

    lights = []                                              # (yön, doğrusal renk, güç, gölge?)
    for lt in list(S.LIGHTS)[:3]:
        if not lt.get("on", True) or float(lt["power"]) <= 0.0:
            continue
        if "dir" in lt:
            # FreeCAD'in ışık yönü: kamera uzayında, ışığın GİTTİĞİ yön (x sağ, y yukarı, z gözlemciye doğru)
            dx, dy, dz = lt["dir"]
            Ld = _norm(-dx * right - dy * up + dz * fwd)
        else:
            hh, vv = np.radians(float(lt["h"])), np.radians(float(lt["v"]))
            Ld = _norm(-fwd * (np.cos(vv) * np.cos(hh)) + right * (np.cos(vv) * np.sin(hh)) + up * np.sin(vv))
        lights.append((Ld, np.array(lt["color"], dtype=np.float64) ** 2.2, float(lt["power"]),
                       bool(lt.get("shadow", False)) and shadows))
    amb = float(S.AMBIENT) * np.array(S.AMBIENT_COLOR, dtype=np.float64) ** 2.2
    eps = scene.diag * 1e-5

    alpha_t = scene.alpha if S.GLASS else np.ones(scene.count)   # 1 = opak
    r_glass = float(S.REFLECT_GLASS) if S.GLASS else 0.0
    r_surf = float(S.REFLECT_SURF)
    bounces = int(S.BOUNCES)
    has_glass = bool((alpha_t < 0.999).any())
    ior = float(min(max(S.IOR, 1.0), 4.0))
    refr = bool(S.GLASS and has_glass and ior > 1.0005)        # kırılma: Snell yasası, çıkışta tam iç yansıma
    f_on = bool(S.FLOOR)
    f_alpha = float(min(max(S.FLOOR_OPACITY, 0.0), 1.0))
    f_refl = float(min(max(S.FLOOR_REFLECT, 0.0), 1.0))
    if f_on and f_alpha <= S.INVISIBLE_ALPHA:
        f_on = False                                           # görünmez zemin
    secondary = has_glass or r_surf > 0.0 or (f_on and (f_refl > 0.0 or f_alpha < 0.999))
    if f_on and f_refl > 0.0:
        bounces = max(bounces, 1)                              # zemin yansıması en az 1 sekme ister
    fid = scene.count                                          # zeminin 'üçgen' numarası (hızlandırıcılara girmez)
    if f_on:
        zc = scene.__dict__.setdefault("_cache", {})
        if "zmin" not in zc:
            zc["zmin"] = float(scene.tri[:, :, 2].min())
        zmin_c = zc["zmin"]
        z_floor = zmin_c + float(S.FLOOR_OFFSET)
        f_col = np.array(S.FLOOR_COLOR, dtype=np.float64)
        n_ext = np.concatenate([scene.n_unit, [[0.0, 0.0, 1.0]]])
        col_ext = np.concatenate([scene.colors, [f_col]])
        alpha_ext = np.concatenate([alpha_t, [f_alpha]])
        f_rad2 = (float(S.FLOOR_RADIUS) * scene.diag) ** 2
        cam_dist = float(max((-pos) @ fwd, 0.0))             # kameradan sahne merkezine derinlik
        ftex = load_texture(S.FLOOR_TEXTURE)                  # None = düz renk
        if ftex is not None:
            tex_w = float(S.FLOOR_TEX_SCALE) if S.FLOOR_TEX_SCALE > 0 else ftex.rel * scene.diag
            tex_w = max(tex_w, 1e-6 * scene.diag)
            texel = tex_w / ftex.base_w                      # düzey-0 bir texel'in zemindeki uzunluğu
            pix_ang = 2.0 * half_y / h                        # bir pikselin kapladığı açı (ortografikte uzunluk)
    else:
        n_ext, col_ext, alpha_ext = scene.n_unit, scene.colors, alpha_t

    # Ortografik kamerada FreeCAD, kamera konumunun "arkasındaki" nesneleri de gösterir.
    # Bu yüzden ışın başlangıcını tüm sahnenin gerisine çekiyoruz (izdüşüm değişmez).
    zmin = float((scene.tri @ fwd).min() - pos @ fwd)
    o_ortho = pos - fwd * (max(0.0, -zmin) + 0.05 * scene.diag)
    if f_on and not persp and fwd[2] < -1e-6:
        # eğik ortografik kamerada ışın başlangıç düzlemi zemin düzleminin altına inebilir (köşede zemin kaybolurdu):
        # düzlemi, bütün başlangıç noktaları zeminin üstünde kalana dek geri çek
        zlo = min((o_ortho + right * sx_ * half_x + up * sy_ * half_y)[2] for sx_ in (-1.0, 1.0) for sy_ in (-1.0, 1.0))
        need = z_floor + 0.05 * scene.diag - zlo
        if need > 0.0:
            o_ortho = o_ortho - fwd * (need / -fwd[2])

    vn = None                                                  # köşe normalleri (yumuşak gölgeleme)
    if S.SMOOTH and 0 < scene.count <= S.SMOOTH_MAX_TRIS:
        zc2 = scene.__dict__.setdefault("_cache", {})
        vkey = ("vn", float(S.SMOOTH_ANGLE))
        if vkey not in zc2:
            say("yüzey normalleri yumuşatılıyor...")
            zc2[vkey] = scene.smooth_normals(S.SMOOTH_ANGLE)
        vn = zc2[vkey]

    say("üçgenler ekran karolarına dağıtılıyor (%d üçgen)..." % scene.count)
    # Kamera/ışık aynı kaldıysa önceki render'ın ön hesapları (ekran karoları, gölge ızgarası, küme ağacı)
    # sahne nesnesinde saklanır ve yeniden kullanılır; yalnız ışık/kalite ayarı değişince hesap tekrarlanmaz.
    cache = scene.__dict__.setdefault("_cache", {})
    bkey = ("bins", pos.tobytes(), right.tobytes(), up.tobytes(), fwd.tobytes(), persp,
            float(half_x), float(half_y), int(w), int(h), int(tile))
    if cache.get("bins_key") == bkey:
        nx, ny, offs, sids, always = cache["bins"]
    else:
        cache.pop("bins", None)
        nx, ny, offs, sids, always = _screen_bins(scene, pos, right, up, fwd, persp,
                                                  half_x, half_y, w, h, tile)
        cache["bins_key"], cache["bins"] = bkey, (nx, ny, offs, sids, always)
    tk()
    allids = np.arange(scene.count)
    grids = {}
    if shadows and not brute and any(lt[3] for lt in lights):
        say("gölge ızgaraları hazırlanıyor...")
        op_ids = np.nonzero(alpha_t >= 0.5)[0]
        gl_ids = np.nonzero(alpha_t < 0.5)[0]
        G_sh = int(S.SHADOW_GRID)
        if G_sh <= 0:       # üçgen sayısı arttıkça hücre başına üçgen sayısı sabit kalsın (ölçüm: 2,5 M üçgende G=256, G=64'ten 7 kat hızlı)
            G_sh = int(min(256, max(64, 2 ** round(np.log2(max(np.sqrt(scene.count) / 6.0, 1.0))))))
        gcache = cache.setdefault("grids", {})
        if len(gcache) > 6:
            gcache.clear()
        for li, lt in enumerate(lights):
            if lt[3]:
                gk = (lt[0].tobytes(), bool(S.GLASS), G_sh)
                if gk not in gcache:
                    gcache[gk] = (_LightGrid(scene, lt[0], G_sh, op_ids) if len(op_ids) else None,
                                  _LightGrid(scene, lt[0], G_sh, gl_ids) if len(gl_ids) else None)
                grids[li] = gcache[gk]
    clusters = None
    if secondary and not brute:
        say("yansıma/saydamlık hızlandırıcısı hazırlanıyor...")
        if "clusters" not in cache:
            cache["clusters"] = _Clusters(scene)
        clusters = cache["clusters"]
    say("ışınlar izleniyor...")

    top, bot = np.array(S.BG_TOP), np.array(S.BG_BOTTOM)
    nthr = int(S.THREADS) if int(S.THREADS) > 0 else min(os.cpu_count() or 1, 8)
    nthr = max(1, nthr)
    # Linux'ta ayrı süreçler (fork): Python'un GIL kilidi iş parçacıklarını çekirdekleri doyurmaktan alıkoyuyor.
    # Çıktı görüntüsü ortak bellekte durur, çocuk süreçler doğrudan içine yazar.
    use_proc = (nthr > 1 and str(S.PARALLEL) != "thread" and hasattr(os, "fork")
                and sys.platform.startswith("linux"))
    if use_proc:
        try:
            import mmap
            img_buf = mmap.mmap(-1, h * w * 3 * 8)
            img = np.frombuffer(img_buf, dtype=np.float64).reshape(h, w, 3)
        except Exception:
            use_proc = False
    if not use_proc:
        img = np.zeros((h, w, 3), dtype=np.float64)
    xs = ((np.arange(w) + 0.5) / w * 2.0 - 1.0) * half_x
    top_l, bot_l = top ** 2.2, bot ** 2.2

    def lights_blocked(Pl, li):
        """Yüzey noktalarından li. ışığa giden yol: 0 = açık, 1 = opak engel, 2 = cam engel."""
        Ld = lights[li][0]
        out = np.zeros(len(Pl), dtype=np.int8)
        Dg = np.broadcast_to(Ld, (len(Pl), 3))
        if brute:
            if S.GLASS and has_glass:
                oi = np.nonzero(alpha_t >= 0.5)[0]
                gi = np.nonzero(alpha_t < 0.5)[0]
            else:
                oi, gi = allids, np.zeros(0, dtype=np.int64)
            if len(gi):
                out[_any(scene, Pl, Dg, gi)] = 2
            if len(oi):
                out[_any(scene, Pl, Dg, oi)] = 1
            return out
        gop, ggl = grids.get(li, (None, None))
        if ggl is not None:
            out[ggl.shadowed(scene, Pl, Ld, tk)] = 2
        if gop is not None:
            out[gop.shadowed(scene, Pl, Ld, tk)] = 1
        return out

    def trace(px, py, sx, sy):
        """px,py: piksel koordinatları (n,), sx,sy: piksel içi konum (0..1). Döner doğrusal renk (n,3)."""
        n = len(px)
        X = (((px + sx) / w) * 2.0 - 1.0)[:, None] * half_x
        Y = (1.0 - ((py + sy) / h) * 2.0)[:, None] * half_y
        if persp:
            D0 = _norm(fwd + right * X + up * Y)
            O0 = np.tile(pos, (n, 1))
        else:
            D0 = np.tile(fwd, (n, 1))
            O0 = o_ortho + right * X + up * Y
        tv = (((py + sy) / h))[:, None]
        bg_lin = (top * (1 - tv) + bot * tv) ** 2.2
        cid = (py // tile) * nx + (px // tile)                 # her ışının ekran karosu
        acc = np.zeros((n, 3))

        # ışın listesi: piksel, başlangıç, yön, ağırlık, yansıma sayısı, birincil-doğrultu bayrağı
        pix = np.arange(n)
        RO, RD = O0, D0
        RW = np.ones(n)
        RN = np.zeros(n, dtype=np.int64)
        RP = np.ones(n, dtype=bool)
        RF = np.zeros(n, dtype=bool)                           # zeminden yansımış ışın mı
        maxdepth = 1 if not secondary else (9 if refr else 6)
        for depth in range(maxdepth):
            m = len(pix)
            if m == 0:
                break
            tb = np.full(m, np.inf)
            ti = np.full(m, -1, dtype=np.int64)
            pm = np.nonzero(RP)[0]
            if len(pm):
                cs = cid[pix[pm]]
                order = np.argsort(cs, kind="stable")
                pm, cs = pm[order], cs[order]
                cuts = np.nonzero(np.diff(cs))[0] + 1
                for sel in np.split(pm, cuts):
                    tk()
                    if brute:
                        ids = allids
                    else:
                        c = int(cid[pix[sel[0]]])
                        ids = sids[offs[c]:offs[c + 1]]
                        if len(always):
                            ids = np.concatenate((always, ids))
                        if len(ids) == 0:
                            continue
                    t_, i_ = _closest(scene, RO[sel], RD[sel], ids)
                    tb[sel], ti[sel] = t_, i_
            gm = np.nonzero(~RP)[0]
            if len(gm):
                if brute:
                    t_, i_ = _closest(scene, RO[gm], RD[gm], allids)
                else:
                    t_, i_ = _closest_general(scene, clusters, RO[gm], RD[gm], tk)
                tb[gm], ti[gm] = t_, i_

            if f_on:                                           # analitik zemin düzlemi: nesnelerden yakınsa onun yerine
                dzz = RD[:, 2]
                with np.errstate(divide="ignore", invalid="ignore"):
                    tf = (z_floor - RO[:, 2]) / dzz
                okf = (np.abs(dzz) > 1e-12) & (tf > eps) & (tf < tb)
                if okf.any():
                    ix = np.nonzero(okf)[0]
                    hx = RO[ix, :2] + RD[ix, :2] * tf[ix][:, None]
                    far = (hx ** 2).sum(1) > f_rad2
                    ix = ix[~far]
                    tb[ix] = tf[ix]
                    ti[ix] = fid

            miss = np.nonzero(ti < 0)[0]
            if len(miss):
                sky = np.clip(RD[miss][:, 2:3] * 0.5 + 0.5, 0, 1)
                env = np.where(RP[miss][:, None], bg_lin[pix[miss]], top_l * sky + bot_l * (1 - sky))
                if f_on:
                    env = np.where(RF[miss][:, None], env * S.FLOOR_SKY_REFL, env)   # gökyüzü zeminde düz mavi ayna gibi durmasın
                _acc(acc, pix[miss], RW[miss][:, None] * env)

            hi = np.nonzero(ti >= 0)[0]
            if len(hi) == 0:
                break
            tid = ti[hi]
            Dh = RD[hi]
            P = RO[hi] + Dh * tb[hi][:, None]
            ngeo = n_ext[tid].copy()                             # düzlemsel (yüz) normali, bakana dönük
            sgn = np.where((ngeo * Dh).sum(1) > 0, -1.0, 1.0)
            ngeo *= sgn[:, None]
            nrm = ngeo                                           # gölgeleme normali
            Psh = P                                              # gölge ışını çıkış noktası
            if vn is not None:
                sm = np.nonzero(tid < scene.count)[0]
                if len(sm):
                    ts = tid[sm]
                    Ps = P[sm]
                    bu = np.clip((Ps * scene.A[ts]).sum(1) - scene.v0A[ts], 0.0, 1.0)
                    bv = np.clip((Ps * scene.B[ts]).sum(1) - scene.v0B[ts], 0.0, 1.0)
                    bw = np.clip(1.0 - bu - bv, 0.0, 1.0)
                    vns = vn[ts] * sgn[sm][:, None, None]            # bakan tarafa dönük köşe normalleri
                    nsm = bw[:, None] * vns[:, 0] + bu[:, None] * vns[:, 1] + bv[:, None] * vns[:, 2]
                    ln = np.sqrt((nsm * nsm).sum(1))[:, None]
                    nrm = nrm.copy()
                    nrm[sm] = np.where(ln > 1e-12, nsm / np.maximum(ln, 1e-12), ngeo[sm])
                    # gölge terminatörü düzeltmesi (Estevez & Kulla): noktayı köşe teğet düzlemlerinin üstüne taşı
                    Vt = scene.tri[ts]
                    sh = np.zeros_like(Ps)
                    for k_, bk in ((0, bw), (1, bu), (2, bv)):
                        dk = np.minimum(0.0, ((Ps - Vt[:, k_]) * vns[:, k_]).sum(1))
                        sh -= (bk * dk)[:, None] * vns[:, k_]
                    Psh = P.copy()
                    Psh[sm] = Ps + sh
            albedo = col_ext[tid] ** 2.2                        # sRGB -> doğrusal
            if f_on and ftex is not None:
                isf0 = tid == fid
                if isf0.any():                                  # zemin dokusu: pikselin izdüşümüne göre mip düzeyi
                    Pf = P[isf0] + scene.center
                    cosg = np.maximum(np.abs(Dh[isf0, 2]), 0.2)
                    dist = tb[hi][isf0] if persp else np.ones(int(isf0.sum()))
                    foot = dist * pix_ang / cosg * (1.0 + 3.0 * RN[hi][isf0])
                    lod = np.log2(np.maximum(foot / texel, 1.0))
                    per = tex_w * ftex.span                      # bir tekrarın genişliği
                    u = Pf[:, 0] / per
                    v = Pf[:, 1] / (per * ftex.aspect)
                    albedo[isf0] = ftex.sample(u, v, lod)
            a = alpha_ext[tid]

            lit = np.tile(amb, (len(hi), 1))
            spec_sum = np.zeros((len(hi), 3))
            for li, (Ld, lcol, power, cast) in enumerate(lights):
                ndl = np.clip((nrm * Ld).sum(1), 0, None)
                if cast:
                    lit_idx = np.nonzero(ndl > 0)[0]
                    if len(lit_idx):
                        blk = lights_blocked(Psh[lit_idx] + ngeo[lit_idx] * eps, li)
                        ndl[lit_idx[blk == 1]] = 0.0
                        ndl[lit_idx[blk == 2]] *= 0.55            # camdan geçen ışık: yarı gölge
                lit += (power * ndl)[:, None] * lcol
                Hh = _norm(Ld - Dh)
                sp = np.clip((nrm * Hh).sum(1), 0, None) ** S.SHININESS * (ndl > 0)
                spec_sum += (S.SPEC * min(power / 0.7, 1.5) * sp)[:, None] * lcol
            surf = albedo * lit + spec_sum
            if f_on:
                isf = tid == fid
                if isf.any() and persp:                         # ufka doğru hafif sis (yalnız perspektif; ortografikte atmosfer derinliği yok) (kameraya göre sahne merkezinin gerisinde başlar)
                    depth_c = np.clip(((P[isf] - pos) * fwd).sum(1) - cam_dist, 0.0, None)
                    haze = (1.0 - np.exp(-depth_c / (S.FLOOR_HAZE * scene.diag)))[:, None]
                    surf[isf] = surf[isf] * (1.0 - haze) + bot_l * haze

            glass = a < 0.999
            cosv = np.clip(-(nrm * Dh).sum(1), 0, 1)
            R = np.where(glass, np.clip(r_glass * (0.15 + 0.85 * (1 - cosv) ** 5), 0, 0.95), r_surf)
            if f_on:
                f0 = 0.03 + 0.35 * f_refl                         # cilalı zemin: dik bakışta %4, kaydırıcı arttıkça aynaya yaklaşır
                R = np.where(tid == fid, np.clip(f0 + (1.0 - f0) * (1 - cosv) ** 5, 0, 0.95) if f_refl > 0 else 0.0, R)
            rm = None                                           # kırılan (cam) isabetler
            if refr:
                rm = glass & (tid < scene.count)
                if rm.any():
                    entering = sgn > 0                           # yüz normalleri dışa bakar: dışarıdan giren ışın
                    eta = np.where(entering, 1.0 / ior, ior)
                    ci = np.clip(-(nrm * Dh).sum(1), 0.0, 1.0)
                    kk = 1.0 - eta * eta * (1.0 - ci * ci)
                    # tam iç yansıma; yansıma bütçesi (BOUNCES) bittiyse ışın enerji kaybetmesin, düz geçsin
                    tir = rm & (kk < 0.0) & (RN[hi] < bounces)
                    eta = np.where(rm & (kk < 0.0) & ~tir, 1.0, eta)   # bütçesi biten TIR: kırılmadan düz geçer
                    R = np.where(tir, 1.0, R)
                else:
                    rm = None
            wl = a * (1 - R)
            wr = R
            wt = (1 - a) * (1 - R)
            W = RW[hi]
            if f_on:                                            # zeminden yansıyan ışın: uzaktaki nesne silikleşsin (parlak zemin gibi)
                rfh = RF[hi]
                if rfh.any():
                    W = np.where(rfh, W * np.exp(-tb[hi] / (S.FLOOR_FADE * scene.diag)), W)
            _acc(acc, pix[hi], (W * wl)[:, None] * surf)

            if depth + 1 >= maxdepth:
                break
            nxt = []
            sel = np.nonzero((wr * W > S.REFL_MIN_W) & (RN[hi] < bounces))[0]
            if len(sel):                                         # yansıyan ışınlar
                Dr = Dh[sel] - 2.0 * (Dh[sel] * nrm[sel]).sum(1)[:, None] * nrm[sel]
                nxt.append((pix[hi][sel], P[sel] + ngeo[sel] * eps, _norm(Dr), (W * wr)[sel],
                            RN[hi][sel] + 1, np.zeros(len(sel), dtype=bool),
                            (tid[sel] == fid) if f_on else np.zeros(len(sel), dtype=bool)))
            sel = np.nonzero(wt * W > 0.02)[0]
            if len(sel):                                         # camdan geçen ışınlar
                Dt = Dh[sel]
                RPt = RP[hi][sel]
                if rm is not None:
                    rs = rm[sel]
                    if rs.any():                                 # kırılan ışın: yön değişir -> ekran karosu hızlandırıcısı geçersiz
                        ns_ = nrm[sel][rs]
                        Di = Dh[sel][rs]
                        et = eta[sel][rs]
                        cs = np.clip(-(ns_ * Di).sum(1), 0.0, 1.0)
                        kq = np.maximum(1.0 - et * et * (1.0 - cs * cs), 0.0)
                        Dn = et[:, None] * Di + (et * cs - np.sqrt(kq))[:, None] * ns_
                        Dt = Dt.copy()
                        Dt[rs] = _norm(Dn)
                        RPt = RPt & ~rs
                nxt.append((pix[hi][sel], P[sel] + Dt * eps, Dt, (W * wt)[sel],
                            RN[hi][sel], RPt, RF[hi][sel]))
            if not nxt:
                break
            pix = np.concatenate([q[0] for q in nxt])
            RO = np.concatenate([q[1] for q in nxt])
            RD = np.concatenate([q[2] for q in nxt])
            RW = np.concatenate([q[3] for q in nxt])
            RN = np.concatenate([q[4] for q in nxt])
            RP = np.concatenate([q[5] for q in nxt])
            RF = np.concatenate([q[6] for q in nxt])
        return acc

    def to_srgb(lin):
        return np.clip(lin, 0, 1) ** (1 / 2.2)


    def run_threads(items, fn, on_done):
        """İş parçacığı havuzu (yedek yol)."""
        restore_blas = _limit_blas(1)                                 # BLAS kendi iş parçacıklarını açmasın
        ex = ThreadPoolExecutor(max_workers=nthr)
        futs = [ex.submit(fn, it) for it in items]
        n = 0
        ok = True
        try:
            while n < len(futs):
                tk()
                try:
                    futs[n].result(timeout=0.05)
                except _FutTimeout:
                    continue
                n += 1
                if on_done(n) is False:
                    ok = False
                    break
        finally:
            tk.cancel.set()
            for f in futs:
                f.cancel()
            ex.shutdown(wait=True)
            tk.cancel.clear()
            restore_blas()
        return ok

    def run_procs(items, fn, on_done):
        """Çocuk süreçlerle (fork): süreç j, j, j+n, j+2n... numaralı işleri yapar; bitenler ortak bellekteki
        bayraklarla bildirilir. Ana süreç arayüzü canlı tutar. Döner: True / False (iptal)."""
        import signal
        n = min(nthr, len(items))
        flags = mmap.mmap(-1, len(items))
        pids = []
        try:
            for j in range(n):
                pid = os.fork()
                if pid == 0:                                  # ---- çocuk: yalnız numpy hesabı, Qt'ye dokunma
                    code = 0
                    try:
                        tk.fn = None
                        _limit_blas(1)
                        for i in range(j, len(items), n):
                            fn(items[i])
                            flags[i] = 1
                    except BaseException:
                        try:
                            import traceback
                            sys.stderr.write("RayTrace işçi süreç hatası:\n" + traceback.format_exc())
                        except Exception:
                            pass
                        code = 1
                    os._exit(code)
                pids.append(pid)
        except OSError:
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGKILL)
                    os.waitpid(pid, 0)
                except Exception:
                    pass
            return None                                       # fork olmadı: çağıran iş parçacığına düşer
        alive = set(pids)
        done_n = 0
        ok = True
        try:
            while done_n < len(items):
                tk()
                adv = False
                while done_n < len(items) and flags[done_n]:
                    done_n += 1
                    adv = True
                if adv and on_done(done_n) is False:
                    ok = False
                    break
                for pid in list(alive):
                    try:
                        r, st = os.waitpid(pid, os.WNOHANG)
                    except ChildProcessError:
                        alive.discard(pid)
                        continue
                    if r:
                        alive.discard(pid)
                        if st != 0:
                            raise RuntimeError("işçi süreç hata ile bitti (Report View'a / terminale bak)")
                if not alive and done_n < len(items) and not all(flags[i] for i in range(done_n, len(items))):
                    raise RuntimeError("işçi süreçler işi bitirmeden çıktı")
                time.sleep(0.02)
        finally:
            for pid in list(alive):
                try:
                    os.kill(pid, signal.SIGKILL)
                except Exception:
                    pass
                try:
                    os.waitpid(pid, 0)
                except Exception:
                    pass
        return ok

    def run_parallel(items, fn, on_done):
        """items için fn(item) çalıştırır; sırayla biten iş sayısı için on_done(n) çağrılır.
        on_done False dönerse False döner (iptal). Arayüz çağrıları yalnız ana süreçte yapılır."""
        if nthr <= 1 or len(items) < 2:
            for i, it in enumerate(items):
                fn(it)
                if on_done(i + 1) is False:
                    return False
            return True
        if use_proc:
            r = run_procs(items, fn, on_done)
            if r is not None:
                return r
        return run_threads(items, fn, on_done)

    # ---- 1. geçiş: piksel başına 1 örnek (piksel merkezi), bant bant ----
    def band(ty):
        r0, r1 = ty * tile, min(ty * tile + tile, h)
        nrow = r1 - r0
        px = np.tile(np.arange(w), nrow)
        py = np.repeat(np.arange(r0, r1), w)
        img[r0:r1] = to_srgb(trace(px, py, 0.5, 0.5)).reshape(nrow, w, 3)

    def band_done(n):
        if progress is not None:
            return progress(img, min(n * tile, h))
        return True

    if run_parallel(list(range(ny)), band, band_done) is False:
        return None

    # ---- 2. geçiş: kenar yumuşatma (yalnız kenar piksellerinde k x k örnek) ----
    k = int(S.AA)
    if k >= 2:
        say("kenarlar aranıyor...")
        gx = np.zeros((h, w))
        d = np.abs(img[:, 1:] - img[:, :-1]).max(2)
        gx[:, 1:] = np.maximum(gx[:, 1:], d)
        gx[:, :-1] = np.maximum(gx[:, :-1], d)
        d = np.abs(img[1:, :] - img[:-1, :]).max(2)
        gx[1:, :] = np.maximum(gx[1:, :], d)
        gx[:-1, :] = np.maximum(gx[:-1, :], d)
        ey, ex_ = np.nonzero(gx > S.AA_THRESH)
        ne = len(ey)
        say("kenar yumuşatma: %d piksel x %d örnek..." % (ne, k * k))
        offs_s = (np.arange(k) + 0.5) / k
        chunk = 3000 if nthr > 1 else 6000
        starts = list(range(0, ne, chunk))
        # AA, 1. geçişin görüntüsünü okur; yazılan pikseller ayrık olduğundan kopya gerekmez
        # (kenar tespiti yukarıda bitti)

        def aa_job(s0):
            cy, cx = ey[s0:s0 + chunk], ex_[s0:s0 + chunk]
            tot = np.zeros((len(cy), 3))
            for oy in offs_s:
                for ox in offs_s:
                    tot += trace(cx, cy, ox, oy)
            img[cy, cx] = to_srgb(tot / (k * k))

        def aa_done(n):
            if progress is not None:
                return progress(img, h, min(1.0, n * chunk / float(max(ne, 1))), "kenar yumuşatma")
            return True

        if run_parallel(starts, aa_job, aa_done) is False:
            return None
    return (np.clip(img, 0, 1) * 255.0 + 0.5).astype(np.uint8)
