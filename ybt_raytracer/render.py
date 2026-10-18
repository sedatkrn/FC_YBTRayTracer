# -*- coding: utf-8 -*-
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as _FutTimeout
import numpy as np
import os
import sys
import time
from . import settings as S
from .materials import shininess as _shin
from .i18n import T
from .textures import load as load_texture
from .core import _any, _closest, _closest_sorted, _dot, _norm, camera_basis
from .parallel import _Ticker, _limit_blas
from .accel import _Clusters, _LightGrid, _closest_general, _screen_bins, _screen_boxes, band_sel, raster_rows


def _acc(acc, idx, vals):
    np.add.at(acc, idx, vals)


def _ao_blur(ao, have, ids, ts, n_ext, fid, oid, R):
    """AO'yu seyrek örneklerden tüm piksellere yayan + gürültüyü azaltan bilateral süzgeç: yalnız ışın atılmış (have),
    aynı nesnedeki, benzer derinlik ve normaldeki komşular ağırlıkla karışır."""
    h, w = ao.shape
    hit = ids >= 0
    obj = np.where(hit, np.where(ids == fid, -2, oid[np.minimum(ids, len(oid) - 1)]), -3).astype(np.int32)
    obj = np.where(hit & (ids != fid) & (obj < 0), ids + 1000000, obj)          # nesnesiz (oid=-1) üçgen: kendi kimliği
    nrm = n_ext[np.maximum(ids, 0)].astype(np.float32)
    tt = np.where(np.isfinite(ts), ts, 0.0).astype(np.float32)
    P = R
    pad = lambda a, v: np.pad(a, ((P, P), (P, P)) + ((0, 0),) * (a.ndim - 2), constant_values=v)
    ob_p, tt_p, ao_p, hv_p = pad(obj, -9), pad(tt, 0.0), pad(ao.astype(np.float32), 0.0), pad(have.astype(np.float32), 0.0)
    nr_p = np.pad(nrm, ((P, P), (P, P), (0, 0)))
    acc = np.zeros((h, w), dtype=np.float32)
    wsum = np.zeros((h, w), dtype=np.float32)
    tol = np.maximum(tt * 0.02, 1e-9)
    sig2 = 2.0 * (R * 0.55) ** 2
    for dy in range(-R, R + 1):
        for dx in range(-R, R + 1):
            sl = (slice(P + dy, P + dy + h), slice(P + dx, P + dx + w))
            same = (ob_p[sl] == obj) & hit & (np.abs(tt_p[sl] - tt) < tol * (1.0 + 0.5 * np.hypot(dx, dy)))
            nd = (nr_p[sl] * nrm).sum(2)
            wgt = same * hv_p[sl] * np.clip((nd - 0.7) / 0.3, 0.0, 1.0) * np.float32(np.exp(-(dx * dx + dy * dy) / sig2))
            acc += wgt * ao_p[sl]
            wsum += wgt
    return np.where(hit & (wsum > 1e-6), acc / np.maximum(wsum, 1e-6), 0.0)


def _soft_blur(v0, Tb, valid, oid, foot, ndl, tan_t, rmax=48):
    """Hızlı yumuşak gölge: sert gölge maskesi (v0: 1 aydınlık, 0 gölge, 0.55 cam) her piksel için kendi yarı gölge genişliğinde
    (engel mesafesi x ışık yarıçapı) kutu süzgeçten geçer; her nesne ayrı (gölge nesne kenarından başka yüzeye sızmaz), süzgeç
    toplam-alan tablosuyla (SAT) O(1)/piksel. Kenar çizgisinde kutu ortalaması doğrusal bir geçiştir; smoothstep ile S eğrisine çevrilir."""
    out = v0.copy()
    cand = valid & (v0 < 1.0)
    if not cand.any():
        return out
    sat = lambda a: np.pad(np.cumsum(np.cumsum(a, 0), 1), ((1, 0), (1, 0)))
    for o in np.unique(oid[cand]):
        sel = valid & (oid == o)
        ys, xs = np.nonzero(sel)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        m = sel[y0:y1, x0:x1]
        v, T = v0[y0:y1, x0:x1], Tb[y0:y1, x0:x1]
        f, nd = foot[y0:y1, x0:x1], ndl[y0:y1, x0:x1]
        shad = m & (v < 1.0) & (T > 0)
        if not shad.any():
            continue
        Hh, Ww = m.shape
        stretch_max = 1.0 / np.sqrt(0.3)
        Rs = int(min(rmax, max(1, np.ceil(T[shad].max() * tan_t * stretch_max / max(f[m].min(), 1e-12)))))
        S_c, S_t = sat(shad.astype(np.float64)), sat(np.where(shad, T, 0.0))
        S_m, S_v = sat(m.astype(np.float64)), sat(np.where(m, v, 0.0))
        yy, xx = np.nonzero(m)

        def box(S, r):
            ya, yb = np.clip(yy - r, 0, Hh), np.clip(yy + r + 1, 0, Hh)
            xa, xb = np.clip(xx - r, 0, Ww), np.clip(xx + r + 1, 0, Ww)
            return S[yb, xb] - S[ya, xb] - S[yb, xa] + S[ya, xa]
        rs = np.full(len(yy), Rs)
        cnt, sT = box(S_c, rs), box(S_t, rs)
        has = cnt > 0.5
        Tavg = np.where(has, sT / np.maximum(cnt, 1.0), 0.0)
        stretch = 1.0 / np.sqrt(np.maximum(nd[yy, xx], 0.3))
        rp = np.clip(np.rint(Tavg * tan_t * stretch / np.maximum(f[yy, xx], 1e-12)).astype(np.int64), 0, Rs)
        mean = box(S_v, rp) / np.maximum(box(S_m, rp), 1.0)
        res = np.where(has, mean * mean * (3.0 - 2.0 * mean), v[yy, xx])
        sub = out[y0:y1, x0:x1]
        sub[yy, xx] = res
    return out


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
    soft_r = float(S.SOFT_SHADOW)
    soft_fast = str(S.SOFT_METHOD) != "sampled"
    soft_on = soft_r > 0.0 and shadows and any(lt[3] for lt in lights) and (soft_fast or scene.count <= int(S.SOFT_MAX_TRIS))
    sample_dirs = {}                                         # ışık -> gölge örnek yönleri (0 = merkez); yumuşak gölgede ışık diski üzerinde
    for li_, lt_ in enumerate(lights):
        Ld_ = lt_[0]
        if not (soft_on and lt_[3]) or soft_fast:
            sample_dirs[li_] = [Ld_]
            continue
        K_ = max(4, min(48, int(S.SOFT_SAMPLES)))
        tn_ = np.tan(np.radians(min(soft_r, 30.0))) * max(0.1, float(S.SOFT_SCALE))
        u_ = np.cross(Ld_, np.array([0.0, 0.0, 1.0]) if abs(Ld_[2]) < 0.9 else np.array([1.0, 0.0, 0.0]))
        u_ = u_ / np.linalg.norm(u_)
        v_ = np.cross(Ld_, u_)
        ph_ = 0.7 * (li_ + 1)
        ds_ = [Ld_]
        for i_ in range(8):                                  # 8 sınır örneği: önce bunlar sınanır (hepsi aynıysa piksel yarı gölgede değildir)
            th_ = 2 * np.pi * i_ / 8.0 + ph_
            ds_.append(_norm(Ld_ + u_ * tn_ * np.cos(th_) + v_ * tn_ * np.sin(th_)))
        for i_ in range(max(0, K_ - 9)):                     # kalanı: Vogel (altın açı) deseniyle diskin içi
            rr_ = tn_ * np.sqrt((i_ + 0.5) / max(K_ - 9, 1)) * 0.92
            th_ = i_ * 2.399963 + ph_
            ds_.append(_norm(Ld_ + u_ * rr_ * np.cos(th_) + v_ * rr_ * np.sin(th_)))
        sample_dirs[li_] = ds_
    amb = float(S.AMBIENT) * np.array(S.AMBIENT_COLOR, dtype=np.float64) ** 2.2
    eps = scene.diag * 1e-5

    alpha_t = scene.alpha if S.GLASS else np.ones(scene.count)   # 1 = opak
    refl_on = bool(S.REFLECTIONS)
    r_glass = float(S.REFLECT_GLASS) if (S.GLASS and refl_on) else 0.0
    r_surf = float(S.REFLECT_SURF) if refl_on else 0.0
    bounces = int(S.BOUNCES)
    has_glass = bool((alpha_t < 0.999).any())
    ior = float(min(max(S.IOR, 1.0), 4.0)) if S.REFRACTION else 1.0
    # malzeme tabloları (indeks 0 = malzemesiz üçgen/zemin -> genel ayarlar)
    mt_ = scene.mtable
    dif_tab = np.array([1.0] + [m["diffuse"] for m in mt_])
    spec_tab = np.array([float(S.SPEC)] + [m["spec"] for m in mt_])
    shin_tab = np.array([float(S.SHININESS)] + [_shin(m["gloss"]) for m in mt_])
    metal_tab = np.array([0.0] + [m["metal"] for m in mt_])
    refl_tab = np.array([r_surf] + [m["refl"] if refl_on else 0.0 for m in mt_])
    ior_tab = np.array([ior] + [m["ior"] if S.REFRACTION else 1.0 for m in mt_])
    lum_tab = np.array([0.0] + [m["lum"] for m in mt_])
    has_mat = len(mt_) > 0
    # doku atanmış malzemeler: indeks (1 tabanlı, mid ile aynı) -> (Texture, tekrar genişliği, karışım)
    tex_mats = {}
    for i_, m_ in enumerate(mt_):
        if m_.get("tex"):
            t_ = load_texture(m_["tex"])
            if t_ is not None:
                w_ = float(m_.get("tex_scale", 0.0))
                w_ = w_ if w_ > 0 else t_.rel * scene.diag
                tex_mats[i_ + 1] = (t_, max(w_, 1e-6 * scene.diag), float(m_.get("tex_mix", 1.0)))
    pix_ang_g = 2.0 * (np.tan(cam["size"] / 2.0) if bool(cam["persp"]) else cam["size"] / 2.0) / max(h, 1)
    refr = bool(S.GLASS and has_glass and float(ior_tab.max()) > 1.0005)   # kırılma: Snell yasası, çıkışta tam iç yansıma
    f_on = bool(S.FLOOR)
    f_alpha = float(min(max(S.FLOOR_OPACITY, 0.0), 1.0))
    f_refl = float(min(max(S.FLOOR_REFLECT, 0.0), 1.0))
    if f_on and f_alpha <= S.INVISIBLE_ALPHA:
        f_on = False                                           # görünmez zemin
    secondary = has_glass or r_surf > 0.0 or float(refl_tab.max()) > 0.0 or (f_on and (f_refl > 0.0 or f_alpha < 0.999))
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
        mid_ext = np.concatenate([scene.mid, [0]])
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
        mid_ext = scene.mid

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
            say(T("yüzey normalleri yumuşatılıyor..."))
            zc2[vkey] = scene.smooth_normals(S.SMOOTH_ANGLE)
        vn = zc2[vkey]

    say(T("üçgenler ekran karolarına dağıtılıyor (%d üçgen)...") % scene.count)
    cache = scene.__dict__.setdefault("_cache", {})
    bkey = ("bins", pos.tobytes(), right.tobytes(), up.tobytes(), fwd.tobytes(), persp,
            float(half_x), float(half_y), int(w), int(h), int(tile))
    nx = (w + tile - 1) // tile
    ny = (h + tile - 1) // tile
    raster = not brute                                     # birincil ışınlar: görünürlük tamponu (z-buffer benzeri), tüm üçgenleri taramaz
    if raster:
        if cache.get("box_key") != bkey:
            cache.pop("boxes", None)
            cache["boxes"] = _screen_boxes(scene, pos, right, up, fwd, persp, half_x, half_y, w, h)
            cache["box_key"] = bkey
        boxes = cache["boxes"]
    # Kamera/ışık aynı kaldıysa önceki render'ın ön hesapları (ekran karoları, gölge ızgarası, küme ağacı)
    # sahne nesnesinde saklanır ve yeniden kullanılır; yalnız ışık/kalite ayarı değişince hesap tekrarlanmaz.
    # Ekran karoları yalnız cam/yansıma ışınlarının "birincil doğrultuda" ilerleyen kolları için gerekir.
    if secondary or brute:
        if cache.get("bins_key") == bkey:
            nx, ny, offs, sids, always = cache["bins"]
        else:
            cache.pop("bins", None)
            nx, ny, offs, sids, always = _screen_bins(scene, pos, right, up, fwd, persp,
                                                      half_x, half_y, w, h, tile)
            cache["bins_key"], cache["bins"] = bkey, (nx, ny, offs, sids, always)
    else:
        offs = sids = always = None
    tk()
    allids = np.arange(scene.count)
    # ön ışınlar için üçgen başına kamera derinliği alt sınırı (ön-arka sıralı erken çıkış)
    scene._sort_ctx = (pos, fwd)
    if (secondary or brute) and cache.get("smin_key") != bkey[:5]:
        cache["smin"] = ((scene.tri - pos) @ fwd).min(1)
        cache["smin_key"] = bkey[:5]
    smin = cache.get("smin")
    grids = {}
    if shadows and not brute and any(lt[3] for lt in lights):
        say(T("gölge ızgaraları hazırlanıyor..."))
        op_ids = np.nonzero(alpha_t >= 0.5)[0]
        gl_ids = np.nonzero(alpha_t < 0.5)[0]
        G_sh = int(S.SHADOW_GRID)
        if G_sh <= 0:       # çok seviyeli ızgara: en ince seviye üçgen boyutuna yakın olsun (2,8 M üçgende 2048)
            G_sh = int(min(2048, max(64, 2 ** round(np.log2(max(np.sqrt(scene.count) * 1.5, 1.0))))))
        gcache = cache.setdefault("grids", {})
        if len(gcache) > 160:
            gcache.clear()
        for li, lt in enumerate(lights):
            if lt[3]:
                for si, dsi in enumerate(sample_dirs[li]):
                    gk = (dsi.tobytes(), bool(S.GLASS), G_sh)
                    if gk not in gcache:
                        gcache[gk] = (_LightGrid(scene, dsi, G_sh, op_ids) if len(op_ids) else None,
                                      _LightGrid(scene, dsi, G_sh, gl_ids) if len(gl_ids) else None)
                    grids[(li, si)] = gcache[gk]
    clusters = None
    ao_on = bool(S.AO) and not brute and scene.count > 0 and int(S.AO_SAMPLES) > 0 and float(S.AO_STRENGTH) > 0.0
    if (secondary or ao_on) and not brute:
        say(T("yansıma/saydamlık hızlandırıcısı hazırlanıyor..."))
        if "clusters" not in cache:
            cache["clusters"] = _Clusters(scene)
        clusters = cache["clusters"]
    say(T("ışınlar izleniyor..."))

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

    def prim_rays(px, py, sx, sy):
        """Birincil ışınlar: piksel (px,py) içindeki (sx,sy) konumundan. Döner O ((3,) ya da (n,3)), D (n,3)."""
        X = (((px + sx) / w) * 2.0 - 1.0)[:, None] * half_x
        Y = (1.0 - ((py + sy) / h) * 2.0)[:, None] * half_y
        if persp:
            return pos, _norm(fwd + right * X + up * Y)
        return o_ortho + right * X + up * Y, np.tile(fwd, (len(px), 1))

    def mkbuf(dtype, fill):
        """(h, w) tampon; fork kullanılacaksa süreçler arası ortak bellekte."""
        if use_proc:
            import mmap
            b_ = mmap.mmap(-1, h * w * np.dtype(dtype).itemsize)
            a_ = np.frombuffer(b_, dtype=dtype).reshape(h, w)
            a_[:] = fill
            bufs_keep.append(b_)
            return a_
        return np.full((h, w), fill, dtype=dtype)

    bufs_keep = []
    vis = {}                                                   # (sx, sy) -> (t tamponu, üçgen tamponu)
    if raster:
        vis[(0.5, 0.5)] = (mkbuf(np.float64, np.inf), mkbuf(np.int64, -1))
    ao_on = ao_on and raster
    ss_lights = [li_ for li_, lt_ in enumerate(lights) if lt_[3]] if (soft_on and soft_fast and raster) else []
    ss_on = bool(ss_lights)
    pre_on = ao_on or ss_on                                    # görünürlük tamponu en baştan çıkarılsın
    oid_ext = np.concatenate([scene.oid, [-2]]) if f_on else scene.oid
    if ss_on:
        ss_buf = {li_: mkbuf(np.float64, 1.0) for li_ in ss_lights}     # son ışık görünürlüğü
        ss_v0 = {li_: mkbuf(np.float64, 1.0) for li_ in ss_lights}      # sert gölge maskesi
        ss_T = {li_: mkbuf(np.float64, 0.0) for li_ in ss_lights}       # engel mesafesi
        ss_N = {li_: mkbuf(np.float64, 0.0) for li_ in ss_lights}       # n.L
        ss_oid = mkbuf(np.int64, -3)
        ss_foot = mkbuf(np.float64, 1.0)
    else:
        ss_buf = None
    ao_buf = mkbuf(np.float64, 0.0) if ao_on else None
    ao_have = mkbuf(np.float64, 0.0) if ao_on else None        # AO ışını atılan pikseller (kalanlar süzgeçle doldurulur)
    ao_step = max(1, int(S.AO_STEP))

    def lights_blocked(Pl, li, si=0, want_t=False):
        """Yüzey noktalarından li. ışığın si. örnek yönüne giden yol: 0 = açık, 1 = opak engel, 2 = cam engel."""
        Ld = sample_dirs[li][si]
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
            return (out, np.full(len(Pl), np.inf)) if want_t else out
        gop, ggl = grids.get((li, si), (None, None))
        tmn = np.full(len(Pl), np.inf) if want_t else None
        if ggl is not None:
            if want_t:
                o_, t_ = ggl.shadowed(scene, Pl, Ld, tk, True)
                out[o_] = 2
                tmn = np.minimum(tmn, t_)
            else:
                out[ggl.shadowed(scene, Pl, Ld, tk)] = 2
        if gop is not None:
            if want_t:
                o_, t_ = gop.shadowed(scene, Pl, Ld, tk, True)
                out[o_] = 1
                tmn = np.minimum(tmn, t_)
            else:
                out[gop.shadowed(scene, Pl, Ld, tk)] = 1
        return (out, tmn) if want_t else out

    def floor_apply(RO, RD, tb, ti):
        """Analitik zemin düzlemi: nesnelerden yakınsa tb/ti (yerinde) zemin isabetiyle değiştirilir."""
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

    def trace(px, py, sx, sy):
        """px,py: piksel koordinatları (n,), sx,sy: piksel içi konum (0..1). Döner doğrusal renk (n,3)."""
        n = len(px)
        O0, D0 = prim_rays(px, py, sx, sy)
        O0 = np.tile(O0, (n, 1)) if O0.ndim == 1 else O0
        vb = vis.get((sx, sy))
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
            if depth == 0 and vb is not None:                  # birincil ışınlar: görünürlük tamponundan
                tb = vb[0][py, px].copy()
                ti = vb[1][py, px].copy()
            else:
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
                        t_, i_ = _closest_sorted(scene, RO[sel], RD[sel], ids, smin)
                        tb[sel], ti[sel] = t_, i_
                gm = np.nonzero(~RP)[0]
                if len(gm):
                    if brute:
                        t_, i_ = _closest(scene, RO[gm], RD[gm], allids)
                    else:
                        t_, i_ = _closest_general(scene, clusters, RO[gm], RD[gm], tk)
                    tb[gm], ti[gm] = t_, i_

            if f_on:                                           # analitik zemin düzlemi: nesnelerden yakınsa onun yerine
                floor_apply(RO, RD, tb, ti)

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
            sgn = np.where(_dot(ngeo, Dh) > 0, -1.0, 1.0)
            ngeo *= sgn[:, None]
            nrm = ngeo                                           # gölgeleme normali
            Psh = P                                              # gölge ışını çıkış noktası
            if vn is not None:
                sm = np.nonzero(tid < scene.count)[0]
                if len(sm):
                    ts = tid[sm]
                    Ps = P[sm]
                    bu = np.clip(_dot(Ps, scene.A[ts]) - scene.v0A[ts], 0.0, 1.0)
                    bv = np.clip(_dot(Ps, scene.B[ts]) - scene.v0B[ts], 0.0, 1.0)
                    bw = np.clip(1.0 - bu - bv, 0.0, 1.0)
                    vns = vn[ts] * sgn[sm][:, None, None]            # bakan tarafa dönük köşe normalleri
                    nsm = bw[:, None] * vns[:, 0] + bu[:, None] * vns[:, 1] + bv[:, None] * vns[:, 2]
                    ln = np.sqrt(_dot(nsm, nsm))[:, None]
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
            mt = mid_ext[tid]                                   # nokta başına malzeme indeksi
            if tex_mats:                                        # malzeme dokusu: UV'siz, dünya koordinatından üç düzlemli izdüşüm
                for k_, (tx, tw, mix) in tex_mats.items():
                    ix = np.nonzero(mt == k_)[0]
                    if len(ix) == 0:
                        continue
                    Pw = P[ix] + scene.center
                    wt3 = np.abs(ngeo[ix]) ** 4
                    wt3 /= wt3.sum(1, keepdims=True)
                    cosg = np.maximum(np.abs(_dot(ngeo[ix], Dh[ix])), 0.2)
                    dist = tb[hi][ix] if persp else np.ones(len(ix))
                    foot = dist * pix_ang_g / cosg * (1.0 + 3.0 * RN[hi][ix])
                    lod = np.log2(np.maximum(foot / (tw / tx.base_w), 1.0))
                    per = tw * tx.span
                    tcol = np.zeros((len(ix), 3))
                    wsum = np.zeros(len(ix))
                    for ax, (a_, b_) in enumerate(((1, 2), (0, 2), (0, 1))):
                        sl = np.nonzero(wt3[:, ax] > 0.02)[0]
                        if len(sl):
                            tcol[sl] += wt3[sl, ax][:, None] * tx.sample(Pw[sl, a_] / per, Pw[sl, b_] / (per * tx.aspect), lod[sl])
                            wsum[sl] += wt3[sl, ax]
                    tcol /= np.maximum(wsum, 1e-9)[:, None]
                    albedo[ix] = (1.0 - mix) * albedo[ix] + mix * tcol
            albedo_raw = albedo
            if has_mat:
                albedo = albedo * dif_tab[mt][:, None]
                spec_k, shin_k, metal_k = spec_tab[mt], shin_tab[mt], metal_tab[mt]
            else:
                spec_k, shin_k, metal_k = float(spec_tab[0]), float(shin_tab[0]), 0.0

            if ao_buf is not None and depth == 0:               # birincil isabetlerde ortam ışığı AO ile kısılır
                lit = amb[None, :] * (1.0 - float(S.AO_STRENGTH) * ao_buf[py[pix[hi]], px[pix[hi]]])[:, None]
            else:
                lit = np.tile(amb, (len(hi), 1))
            spec_sum = np.zeros((len(hi), 3))
            for li, (Ld, lcol, power, cast) in enumerate(lights):
                ndl = np.clip(_dot(nrm, Ld), 0, None)
                if cast:
                    lit_idx = np.nonzero(ndl > 0)[0]
                    if len(lit_idx):
                        ndl[lit_idx] *= light_vis(Psh[lit_idx] + ngeo[lit_idx] * eps, li)
                lit += (power * ndl)[:, None] * lcol
                Hh = _norm(Ld - Dh)
                sp = np.clip(_dot(nrm, Hh), 0, None) ** shin_k * (ndl > 0)
                spec_sum += (spec_k * min(power / 0.7, 1.5) * sp)[:, None] * lcol
            if has_mat:                                         # metal: vurgu yüzey renginde
                spec_sum = spec_sum * (1.0 - metal_k[:, None] + metal_k[:, None] * np.minimum(albedo_raw * 1.4, 1.0))
            surf = albedo * lit + spec_sum
            if has_mat:
                lm = lum_tab[mt]
                if lm.any():                                    # kendi ışığı: ışıktan bağımsız
                    surf = surf + lm[:, None] * albedo_raw * 1.5
            if f_on:
                isf = tid == fid
                if isf.any() and persp:                         # ufka doğru hafif sis (yalnız perspektif; ortografikte atmosfer derinliği yok) (kameraya göre sahne merkezinin gerisinde başlar)
                    depth_c = np.clip(((P[isf] - pos) * fwd).sum(1) - cam_dist, 0.0, None)
                    haze = (1.0 - np.exp(-depth_c / (S.FLOOR_HAZE * scene.diag)))[:, None]
                    surf[isf] = surf[isf] * (1.0 - haze) + bot_l * haze

            glass = a < 0.999
            cosv = np.clip(-_dot(nrm, Dh), 0, 1)
            rg_k = np.where(mt > 0, refl_tab[mt], r_glass) if has_mat else r_glass
            r_op = refl_tab[mt] if has_mat else r_surf
            if fresnel_on:                                      # opak parlak yüzey: yansıma kaydırma açısında artar (Schlick, F0 = malzeme yansıması)
                r_op = np.where(r_op > 0.0, np.clip(r_op + (1.0 - r_op) * (1 - cosv) ** 5, 0, 0.95), r_op)
            R = np.where(glass, np.clip(rg_k * (0.15 + 0.85 * (1 - cosv) ** 5), 0, 0.95), r_op)
            if f_on:
                f0 = 0.03 + 0.35 * f_refl                         # cilalı zemin: dik bakışta %4, kaydırıcı arttıkça aynaya yaklaşır
                R = np.where(tid == fid, np.clip(f0 + (1.0 - f0) * (1 - cosv) ** 5, 0, 0.95) if f_refl > 0 else 0.0, R)
            rm = None                                           # kırılan (cam) isabetler
            if refr:
                ior_k = ior_tab[mt]
                rm = glass & (tid < scene.count) & (ior_k > 1.0005)
                if rm.any():
                    entering = sgn > 0                           # yüz normalleri dışa bakar: dışarıdan giren ışın
                    eta = np.where(entering, 1.0 / ior_k, ior_k)
                    ci = np.clip(-_dot(nrm, Dh), 0.0, 1.0)
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
                Dr = Dh[sel] - 2.0 * _dot(Dh[sel], nrm[sel])[:, None] * nrm[sel]
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
                        cs = np.clip(-_dot(ns_, Di), 0.0, 1.0)
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

    fresnel_on = bool(S.FRESNEL)

    def _vis_of(blk):                                          # engel kodu -> ışık geçirgenliği (cam: yarı gölge)
        return np.where(blk == 1, 0.0, np.where(blk == 2, 0.55, 1.0))

    def light_vis(Pq, li):
        """Noktanın li. ışığı görme oranı (0..1). Yumuşak gölgede ışık diskinin örneklerinden; yalnız yarı gölge pikselleri tüm örneklerle."""
        dirs = sample_dirs[li]
        n = len(dirs)
        v0 = _vis_of(lights_blocked(Pq, li, 0))
        if n == 1:
            return v0
        npr = min(9, n)
        acc, vmin, vmax = v0.copy(), v0.copy(), v0.copy()
        for si in range(1, npr):
            v = _vis_of(lights_blocked(Pq, li, si))
            acc += v
            vmin = np.minimum(vmin, v)
            vmax = np.maximum(vmax, v)
        res = acc / npr
        need = np.nonzero(vmax - vmin > 1e-9)[0]
        if len(need):
            Pn = Pq[need]
            an = acc[need]
            for si in range(npr, n):
                an += _vis_of(lights_blocked(Pn, li, si))
            vn = an / n
            # basamak genişliğinde konuma bağlı ince titreşim: katmanlar (banding) yerine görünmeyen ince doku
            hsh = np.sin(Pn @ np.array([12.9898, 78.233, 37.719]) / max(scene.diag, 1e-9) * 1000.0) * 43758.5453
            vn = vn + (hsh - np.floor(hsh) - 0.5) / n
            res[need] = np.clip(vn, 0.0, 1.0)
        return res
    tm_mode = str(S.TONEMAP)
    exposure = float(S.EXPOSURE)

    def to_srgb(lin):
        if exposure != 1.0:
            lin = lin * exposure
        if tm_mode == "soft":                      # Reinhard (beyaz nokta 2): parlak yerler yumuşakça sıkışır
            lin = lin * (1.0 + lin * 0.25) / (1.0 + lin)
        elif tm_mode == "aces":                    # ACES filmik (Narkowicz)
            lin = (lin * (2.51 * lin + 0.03)) / (lin * (2.43 * lin + 0.59) + 0.14)
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
                            sys.stderr.write(T("RayTrace işçi süreç hatası:\n") + traceback.format_exc())
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
                            raise RuntimeError(T("işçi süreç hata ile bitti (Report View'a / terminale bak)"))
                if not alive and done_n < len(items) and not all(flags[i] for i in range(done_n, len(items))):
                    raise RuntimeError(T("işçi süreçler işi bitirmeden çıktı"))
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

    # ---- 0. geçiş (AO açıksa): görünürlük tamponu -> piksel başına AO ışınları -> bilateral süzgeç ----
    if pre_on:
        tmax_ao = float(S.AO_RADIUS) * scene.diag
        m_ao = max(1, int(S.AO_SAMPLES))

        def vis_band(ty):
            r0, r1 = ty * tile, min(ty * tile + tile, h)
            vt_, vi_ = raster_rows(scene, boxes, r0, r1, w, 0.5, 0.5, prim_rays)
            vis[(0.5, 0.5)][0][r0:r1] = vt_
            vis[(0.5, 0.5)][1][r0:r1] = vi_

        say(T("görünürlük tamponu hazırlanıyor..."))
        if run_parallel(list(range(ny)), vis_band,
                        lambda n_: True if progress is None else progress(img, 0, n_ / float(ny), T("görünürlük"))) is False:
            return None

        if ss_on:
            tan_soft = float(np.tan(np.radians(min(float(S.SOFT_SHADOW), 30.0)))) * max(0.1, float(S.SOFT_SCALE))

            def ss_band(ty):
                r0, r1 = ty * tile, min(ty * tile + tile, h)
                nrow = r1 - r0
                px = np.tile(np.arange(w), nrow)
                py = np.repeat(np.arange(r0, r1), w)
                O, D = prim_rays(px, py, 0.5, 0.5)
                O = np.broadcast_to(O, D.shape)
                tb = vis[(0.5, 0.5)][0][r0:r1].ravel().copy()
                ti = vis[(0.5, 0.5)][1][r0:r1].ravel().copy()
                if f_on:
                    floor_apply(O, D, tb, ti)
                hitm = ti >= 0
                ss_oid[r0:r1] = np.where(hitm, oid_ext[np.maximum(ti, 0)], -3).reshape(nrow, w)
                ss_foot[r0:r1] = ((np.where(hitm, tb, 0.0) * pix_ang_g) if persp else np.full(nrow * w, pix_ang_g)).reshape(nrow, w)
                idx = np.nonzero(hitm)[0]
                if len(idx) == 0:
                    return
                Dh = D[idx]
                P = O[idx] + Dh * tb[idx][:, None]
                nn = n_ext[ti[idx]].copy()
                nn *= np.where(_dot(nn, Dh) > 0, -1.0, 1.0)[:, None]
                for li_ in ss_lights:
                    nd = _dot(nn, lights[li_][0])
                    v0 = np.where(nd > 0, 1.0, 0.0)
                    Tt = np.zeros(len(idx))
                    lit = np.nonzero(nd > 0)[0]
                    if len(lit):
                        blk, tm = lights_blocked(P[lit] + nn[lit] * eps, li_, 0, True)
                        v0[lit] = _vis_of(blk)
                        Tt[lit] = np.where(np.isfinite(tm), tm, 0.0)
                    for buf_, val_, fill_ in ((ss_v0, v0, 1.0), (ss_T, Tt, 0.0), (ss_N, nd, 0.0)):
                        full = np.full(nrow * w, fill_)
                        full[idx] = val_
                        buf_[li_][r0:r1] = full.reshape(nrow, w)

            say(T("gölge tamponu hazırlanıyor..."))
            if run_parallel(list(range(ny)), ss_band,
                            lambda n_: True if progress is None else progress(img, 0, n_ / float(ny), T("gölge tamponu"))) is False:
                return None
            oid_a, foot_a = np.array(ss_oid), np.array(ss_foot)
            for li_ in ss_lights:
                nd_a = np.array(ss_N[li_])
                valid_a = (oid_a != -3) & (nd_a > 0)
                v0_a = np.array(ss_v0[li_])
                v0_a = np.where(oid_a == -3, 1.0, v0_a)
                ss_buf[li_][:] = _soft_blur(v0_a, np.array(ss_T[li_]), valid_a, oid_a, foot_a, nd_a, tan_soft, max(48, int(0.12 * w)))

        def ao_band(ty):
            r0, r1 = ty * tile, min(ty * tile + tile, h)
            nrow = r1 - r0
            px = np.tile(np.arange(w), nrow)
            py = np.repeat(np.arange(r0, r1), w)
            O, D = prim_rays(px, py, 0.5, 0.5)
            O = np.broadcast_to(O, D.shape)
            tb = vis[(0.5, 0.5)][0][r0:r1].ravel().copy()
            ti = vis[(0.5, 0.5)][1][r0:r1].ravel().copy()
            if f_on:
                floor_apply(O, D, tb, ti)
            idx = np.nonzero((ti >= 0) & (px % ao_step == 0) & (py % ao_step == 0))[0]
            out = np.zeros(nrow * w)
            hv = np.zeros(nrow * w)
            hv[idx] = 1.0
            ao_have[r0:r1] = hv.reshape(nrow, w)
            if len(idx):
                Dh = D[idx]
                P = O[idx] + Dh * tb[idx][:, None]
                nn = n_ext[ti[idx]].copy()
                nn *= np.where(_dot(nn, Dh) > 0, -1.0, 1.0)[:, None]
                helper = np.where(np.abs(nn[:, :1]) < 0.9, np.array([[1.0, 0.0, 0.0]]), np.array([[0.0, 1.0, 0.0]]))
                t1 = _norm(np.cross(nn, helper))
                t2 = np.cross(nn, t1)
                hsh = np.sin(px[idx] * 12.9898 + py[idx] * 78.233) * 43758.5453
                rot = hsh - np.floor(hsh)                                   # piksel başına sabit, rastgele dönüş
                Po = P + nn * eps
                occ = np.zeros(len(idx))
                chunks_o, chunks_d = [], []
                for j in range(m_ao):
                    u = (j + 0.5) / m_ao
                    rr_, ph = np.sqrt(u), 2.0 * np.pi * (((j * 0.7548776662466927) + rot) % 1.0)
                    d_ = (rr_ * np.cos(ph))[:, None] * t1 + (rr_ * np.sin(ph))[:, None] * t2 + np.sqrt(1.0 - u) * nn
                    chunks_o.append(Po)
                    chunks_d.append(d_)
                Ao = np.concatenate(chunks_o)
                Ad = np.concatenate(chunks_d)
                t_, i_ = _closest_general(scene, clusters, Ao, Ad, tk, tmax_ao)
                v_ = np.where(i_ >= 0, 1.0 - np.minimum(t_ / tmax_ao, 1.0), 0.0)
                occ = v_.reshape(m_ao, len(idx)).mean(0)
                out[idx] = occ
            ao_buf[r0:r1] = out.reshape(nrow, w)

        if ao_on:
          say(T("ortam tıkanıklığı hesaplanıyor..."))
          if run_parallel(list(range(ny)), ao_band,
                          lambda n_: True if progress is None else progress(img, 0, n_ / float(ny), T("ortam tıkanıklığı"))) is False:
              return None
          ao_buf[:] = _ao_blur(np.array(ao_buf), np.array(ao_have), np.array(vis[(0.5, 0.5)][1]), np.array(vis[(0.5, 0.5)][0]), n_ext,
                             fid if f_on else -1, scene.oid, 2 * ao_step + 1)
        say(T("ışınlar izleniyor..."))

    # ---- 1. geçiş: piksel başına 1 örnek (piksel merkezi), bant bant ----
    def band(ty):
        r0, r1 = ty * tile, min(ty * tile + tile, h)
        nrow = r1 - r0
        px = np.tile(np.arange(w), nrow)
        py = np.repeat(np.arange(r0, r1), w)
        if raster and not ao_on:
            vt_, vi_ = raster_rows(scene, boxes, r0, r1, w, 0.5, 0.5, prim_rays)
            vis[(0.5, 0.5)][0][r0:r1] = vt_
            vis[(0.5, 0.5)][1][r0:r1] = vi_
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
        say(T("kenarlar aranıyor..."))
        gx = np.zeros((h, w))
        d = np.abs(img[:, 1:] - img[:, :-1]).max(2)
        gx[:, 1:] = np.maximum(gx[:, 1:], d)
        gx[:, :-1] = np.maximum(gx[:, :-1], d)
        d = np.abs(img[1:, :] - img[:-1, :]).max(2)
        gx[1:, :] = np.maximum(gx[1:, :], d)
        gx[:-1, :] = np.maximum(gx[:-1, :], d)
        ey, ex_ = np.nonzero(gx > S.AA_THRESH)
        ne = len(ey)
        say(T("kenar yumuşatma: %d piksel x %d örnek...") % (ne, k * k))
        offs_s = (np.arange(k) + 0.5) / k
        chunk = 3000 if nthr > 1 else 6000
        starts = list(range(0, ne, chunk))
        if raster and ne:
            emask = np.zeros((h, w), dtype=bool)
            emask[ey, ex_] = True
            aa_keys = [(ox, oy) for oy in offs_s for ox in offs_s]
            for key_ in aa_keys:
                vis[key_] = (mkbuf(np.float64, np.inf), mkbuf(np.int64, -1))

            def aa_vis(ty):
                r0, r1 = ty * tile, min(ty * tile + tile, h)
                if not emask[r0:r1].any():
                    return
                sel_ = band_sel(boxes, r0, r1, w)
                for (ox, oy) in aa_keys:
                    bt, bi = vis[(ox, oy)]
                    vt_, vi_ = raster_rows(scene, boxes, r0, r1, w, ox, oy, prim_rays, mask=emask, sel=sel_)
                    bt[r0:r1] = vt_
                    bi[r0:r1] = vi_

            if run_parallel(list(range(ny)), aa_vis, lambda n_: True) is False:
                return None

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
                return progress(img, h, min(1.0, n * chunk / float(max(ne, 1))), T("kenar yumuşatma"))
            return True

        if run_parallel(starts, aa_job, aa_done) is False:
            return None
    return (np.clip(img, 0, 1) * 255.0 + 0.5).astype(np.uint8)
