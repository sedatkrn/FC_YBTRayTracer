# -*- coding: utf-8 -*-
import numpy as np
import time
from . import settings as S
from .i18n import T
from .core import Scene


# ============================ FREECAD KISMI ============================
def _visible_chain(chain):
    """Yoldaki (kök .. yaprak) tüm nesneler görünür olmalı."""
    for x in chain:
        try:
            if not x.Visibility:
                return False
        except Exception:
            pass
    return True


def _is_body(x):
    try:
        return x.TypeId == "PartDesign::Body"
    except Exception:
        return False


_MAX_EXTENT = 1e8      # mm; bundan büyük sınır kutusu = sonsuz düzlem gibi geçersiz şekil


def _is_origin_feature(x):
    try:
        if x.TypeId in ("App::Origin", "App::Plane", "App::Line", "App::Point"):
            return True
        return bool(x.isDerivedFrom("App::OriginFeature"))
    except Exception:
        return False


def _sane_bbox(shp):
    """Sonlu ve makul boyutlu mu? (NaN/inf karşılaştırması False döner)"""
    try:
        return shp.BoundBox.DiagonalLength < _MAX_EXTENT
    except Exception:
        return False


def _rgb(c):
    """FreeCAD renk değerini (tuple, Base.Color, ...) (r, g, b) float üçlüsüne çevir."""
    try:
        return (float(c[0]), float(c[1]), float(c[2]))
    except Exception:
        return (float(c.r), float(c.g), float(c.b))


def _vo_colors(vo, nfaces):
    """
    Bir ViewObject'in renklerini oku. Döner (taban_renk, yüz_başına_liste | None, kaynak).
    Sıra: ShapeAppearance (FreeCAD >= 1.0) -> DiffuseColor -> ShapeColor.
    """
    try:                                                  # FreeCAD 1.x: gerçek kaynak ShapeAppearance
        cols = [_rgb(m.DiffuseColor) for m in vo.ShapeAppearance]
        if cols:
            if nfaces > 1 and len(cols) == nfaces:
                return cols[0], cols, "ShapeAppearance+yüz"
            return cols[0], None, "ShapeAppearance"
    except Exception:
        pass
    base = None
    try:
        base = _rgb(vo.ShapeColor)
    except Exception:
        pass
    try:                                                  # eski sürümler / eski dosyalar
        d = [_rgb(c) for c in vo.DiffuseColor]
        if nfaces > 1 and len(d) == nfaces:
            return (base or d[0]), d, "DiffuseColor+yüz"
        if base is None and d:
            base = d[0]
    except Exception:
        pass
    if base is not None:
        return base, None, "ShapeColor"
    return (0.8, 0.8, 0.8), None, "varsayılan"


def _display_colors(o, tgt, nfaces):
    """
    Ekranda görünen rengi bul. Döner (taban_renk, yüz_başına_renk_listesi | None, kaynak_etiketi).
    Link'in kendi ViewObject'inde yüz rengi yoktur: OverrideMaterial kapalıyken renk bağlı olduğu
    (hedef) nesneden gelir; açıksa Link'in ShapeMaterial rengi geçerlidir.
    """
    try:
        if o is not tgt:
            lvo = o.ViewObject
            if lvo is not None and getattr(lvo, "OverrideMaterial", False):
                return _rgb(lvo.ShapeMaterial.DiffuseColor), None, "link-override"
        src = tgt
        if _is_body(src) and getattr(src, "Tip", None) is not None:
            src = src.Tip                                 # Body rengi Tip özelliğinden gelir
        vo = src.ViewObject
        if vo is not None:
            base, dc, how = _vo_colors(vo, nfaces)
            return base, dc, ("hedef:" if o is not tgt else "") + how
    except Exception:
        pass
    return (0.8, 0.8, 0.8), None, "varsayılan"


def _display_opacity(o, tgt, nfaces):
    """
    Opaklık (1 = opak). Döner (taban, yüz_başına_liste | None).
    Kaynaklar: ViewObject.Transparency (0..100) ve ShapeAppearance[i].Transparency (0..1).
    """
    try:
        src = tgt
        if _is_body(src) and getattr(src, "Tip", None) is not None:
            src = src.Tip
        vo = src.ViewObject
        if vo is None:
            return 1.0, None
        vt = 0.0
        try:
            vt = float(vo.Transparency) / 100.0
        except Exception:
            pass
        mats = []
        try:
            mats = [float(m.Transparency) for m in vo.ShapeAppearance]
        except Exception:
            mats = []
        if nfaces > 1 and len(mats) == nfaces:
            per = [max(0.0, min(1.0, 1.0 - max(vt, t))) for t in mats]
            return per[0], per
        t0 = mats[0] if mats else 0.0
        return max(0.0, min(1.0, 1.0 - max(vt, t0))), None
    except Exception:
        return 1.0, None


def _color_props(o, tgt):
    """Tanılama: renkle ilgili özellik adları ve değerleri (Report View'a yazılır)."""
    out = []
    try:
        for label, obj in (("link", o if o is not tgt else None), ("hedef", tgt)):
            vo = getattr(obj, "ViewObject", None) if obj is not None else None
            if vo is None:
                continue
            names = [p for p in vo.PropertiesList
                     if any(k in p for k in ("Color", "Material", "Appearance", "Override"))]
            parts = []
            for p in names:
                try:
                    v = getattr(vo, p)
                    s = repr(v)
                    parts.append("%s=%s" % (p, s if len(s) < 60 else s[:57] + "..."))
                except Exception:
                    parts.append(p)
            out.append("%s.ViewObject: %s" % (label, "; ".join(parts)))
    except Exception:
        pass
    return out


def _nostatus(msg, force=False, frac=None):
    pass


def _gather(doc, log, status=_nostatus):
    """
    Görünür, yüzeyli tüm nesneleri dünya koordinatında toplar (Link, Assembly, App::Part, Body dahil).
    Döner: [(nesne, hedef_nesne, shape, subname)]
    """
    import Part
    items, seen, keys = [], set(), set()
    ntot = max(1, len(doc.Objects))

    def dup(tgt, shp):
        """Aynı nesne aynı yerde ikinci kez (örn. iki farklı grup yolu) gelirse atla."""
        try:
            b = shp.BoundBox
            k = (tgt.Name, len(shp.Faces), round(b.XMin, 2), round(b.XMax, 2), round(b.YMin, 2),
                 round(b.YMax, 2), round(b.ZMin, 2), round(b.ZMax, 2))
        except Exception:
            return False
        if k in keys:
            return True
        keys.add(k)
        return False

    def rec(root, subname, depth, known=None):
        """known: nesne doğrudan belge ağacından biliniyorsa (Group listesi) yol çözümlemesi atlanır.
        (Arch BuildingPart içinde getSubObjectList yanlış nesne döndürüp üstel döngüye yol açıyordu.)"""
        status(T("sahne taranıyor... %d nesne") % len(items), frac=min(1.0, len(seen) / float(ntot)))
        if known is not None:
            seen.add(known.Name)
            if not _visible_chain([known]):
                return
            obj = known
        else:
            try:
                chain = root.getSubObjectList(subname) if subname else [root]
            except Exception as ex:
                log("! %s / %s: yol çözülemedi (%s)" % (root.Name, subname, ex))
                return
            for x in chain:
                seen.add(x.Name)
            if not _visible_chain(chain):
                return
            obj = chain[-1]
        if S.DEBUG:
            import FreeCAD as _FC
            _FC.Console.PrintMessage("  [tara] %s%s (%s)\n" % ("  " * depth, obj.Name, getattr(obj, "TypeId", "?")))
            status("taranıyor: " + str(getattr(obj, "Label", obj.Name))[:30], True)
        try:
            tgt = obj.getLinkedObject(True) or obj
        except Exception:
            tgt = obj
        if _is_origin_feature(tgt):
            return                                        # Origin / eksen / düzlem: sonsuz "şekil", çizme
        if depth < 8 and not _is_body(tgt):
            subs = []
            grp = getattr(tgt, "Group", None)
            if obj is tgt and isinstance(grp, (list, tuple)) and grp and \
                    all(hasattr(g, "Name") for g in grp):
                # Arch/Draft kapsayıcıları (Site, Building, Floor, klasör): çocuklara doğrudan in,
                # kapsayıcının kendi (tüm çocukları birleştiren, çok yavaş) şeklini ASLA isteme.
                for g in grp:
                    rec(root, subname + g.Name + ".", depth + 1, known=g)
                return
            elif not (obj is tgt and hasattr(tgt, "Shape")):
                try:
                    subs = tgt.getSubObjects()
                except Exception:
                    subs = []
            if subs:                                      # kapsayıcı (grup / App::Part / Assembly / Link->Part)
                for s in subs:
                    rec(root, subname + s, depth + 1)
                return
        if not (hasattr(tgt, "Shape") or obj is not tgt):
            return                                        # şekli olmayan nesne (Origin, Joint, ...)
        try:
            if known is not None and obj is tgt and hasattr(obj, "Shape") and hasattr(obj, "getGlobalPlacement"):
                shp = obj.Shape
                if shp.isNull() or not shp.Faces:
                    return
                shp = shp.copy()
                shp.Placement = obj.getGlobalPlacement()
            else:
                shp = Part.getShape(root, subname=subname, needSubElement=False, transform=True)
            if shp.isNull() or not shp.Faces:
                return
            if not _sane_bbox(shp):
                log("! %s / %s: sınır kutusu geçersiz/devasa, atlandı" % (root.Name, subname))
                return
        except Exception as ex:
            log("! %s / %s: şekil alınamadı (%s)" % (root.Name, subname, ex))
            return
        if dup(tgt, shp):
            return
        items.append((obj, tgt, shp, subname))

    for r in doc.RootObjects:
        rec(r, "", 0)

    # Yedek: yukarıdaki gezintide hiç uğranmayan görünür nesneler (gruba bağlı olmayanlar)
    for o in doc.Objects:
        if o.Name in seen or not hasattr(o, "Shape"):
            continue
        status(T("yedek tarama... %d nesne") % len(items))
        try:
            if not o.Visibility:
                continue
            vo = o.ViewObject
            if vo is not None and hasattr(vo, "Visibility") and not vo.Visibility:
                continue
            par = o.getParentGeoFeatureGroup()
            if par is not None and _is_body(par):
                continue                                  # Body kendi şeklini zaten çiziyor
            if _is_origin_feature(o):
                continue
            grp = getattr(o, "Group", None)
            if not _is_body(o) and isinstance(grp, (list, tuple)) and any(hasattr(g, "Shape") for g in grp):
                continue                                  # Assembly/Arch kapsayıcısı: kendi birleşik şekli çocuklarının kopyası
            shp = o.Shape
            if shp.isNull() or not shp.Faces or not _sane_bbox(shp):
                continue
            shp = shp.copy()
            if hasattr(o, "getGlobalPlacement"):
                shp.Placement = o.getGlobalPlacement()
        except Exception as ex:
            log("! %s: yedek tarama hatası (%s)" % (o.Name, ex))
            continue
        if dup(o, shp):
            continue
        items.append((o, o, shp, ""))
    return items


def collect_scene(doc, status=_nostatus):
    """Görünür nesneleri üçgenlere çevirir. Döner: Scene, nesne sayısı."""
    import FreeCAD

    if S.DEBUG:
        def log(s):
            FreeCAD.Console.PrintMessage("  " + s + "\n")
    else:
        def log(s):
            pass

    t0 = time.time()
    status(T("sahne taranıyor..."), True)
    items = _gather(doc, log, status)
    if not items:
        raise RuntimeError(T("Görünür, yüzeyi olan nesne bulunamadı."))
    bb = FreeCAD.BoundBox()
    for it in items:
        bb.add(it[2].BoundBox)
    t1 = time.time()

    tol = max(bb.DiagonalLength * S.TESS_FACTOR, 1e-6)
    if S.DEBUG:
        FreeCAD.Console.PrintMessage(
            T("RayTrace: %d nesne bulundu (%.1f sn), sahne köşegeni %.1f mm, tessellate toleransı %.3f mm\n")
            % (len(items), t1 - t0, bb.DiagonalLength, tol))
    tris, cols, alps = [], [], []
    invisible = []
    ntri = 0
    diag_left = [2]
    for k, (o, tgt, shp, sub) in enumerate(items):
        name = (sub.rstrip(".") or o.Name)
        n_before = ntri
        base, dc, how = _display_colors(o, tgt, len(shp.Faces))
        abase, ad = _display_opacity(o, tgt, len(shp.Faces))
        if (ad is None and abase <= S.INVISIBLE_ALPHA) or (ad is not None and max(ad) <= S.INVISIBLE_ALPHA):
            invisible.append(name)                      # %100 saydam = FreeCAD'de görünmez; cam gibi yansıtmasın
            continue
        if S.DEBUG and diag_left[0] > 0:
            diag_left[0] -= 1
            for line in _color_props(o, tgt):
                log("[renk özellikleri] " + name + " -> " + line)
        # Tek renkli/tek saydamlıklı nesne: tüm şekil tek çağrıyla üçgenlenir (yüz yüz çağırmaktan ~2 kat hızlı)
        uniform = ((dc is None or all(tuple(c) == tuple(dc[0]) for c in dc)) and
                   (ad is None or all(a == ad[0] for a in ad)))
        if uniform and len(shp.Faces) > 1:
            try:
                verts, facets = shp.tessellate(tol)
                if facets:
                    V = np.array([(p.x, p.y, p.z) for p in verts], dtype=np.float64)
                    F = np.array(facets, dtype=np.int64)
                    tris.append(V[F])
                    ntri += len(F)
                    c = dc[0] if dc is not None else base
                    cols.append(np.tile(np.array(c, dtype=np.float64), (len(F), 1)))
                    alps.append(np.full(len(F), ad[0] if ad is not None else abase))
                    status(T("üçgenleniyor %d/%d: %s (%d üçgen)") % (k + 1, len(items), name[:24], ntri),
                           frac=(k + 1) / float(len(items)))
                    continue
            except Exception:
                pass                                    # olmadı: yüz yüz yönteme düş
        for i, face in enumerate(shp.Faces):
            if ad is not None and ad[i] <= S.INVISIBLE_ALPHA:
                continue                                # tek yüzü %100 saydam: atla
            if i % 100 == 0:
                status(T("üçgenleniyor %d/%d: %s (%d üçgen)") % (k + 1, len(items), name[:24], ntri),
                       frac=(k + i / float(max(len(shp.Faces), 1))) / float(len(items)))
            try:
                verts, facets = face.tessellate(tol)
            except Exception:
                continue
            if not facets:
                continue
            V = np.array([(p.x, p.y, p.z) for p in verts], dtype=np.float64)
            F = np.array(facets, dtype=np.int64)
            tris.append(V[F])
            ntri += len(F)
            c = dc[i] if dc is not None else base
            cols.append(np.tile(np.array(c, dtype=np.float64), (len(F), 1)))
            alps.append(np.full(len(F), ad[i] if ad is not None else abase))
        if S.DEBUG:
            b = shp.BoundBox
            FreeCAD.Console.PrintMessage(
                "  %-30s yüz:%4d üçgen:%6d renk:(%.2f %.2f %.2f) opak:%.2f %-12s x[%.0f..%.0f] y[%.0f..%.0f] z[%.0f..%.0f]\n"
                % (name[:30], len(shp.Faces), ntri - n_before,
                   base[0], base[1], base[2], (min(ad) if ad is not None else abase), how,
                   b.XMin, b.XMax, b.YMin, b.YMax, b.ZMin, b.ZMax))
    if invisible:
        FreeCAD.Console.PrintMessage(T("RayTrace: %d tamamen saydam (görünmez) nesne atlandı: %s\n")
                                     % (len(invisible), ", ".join(invisible[:8]) + (" ..." if len(invisible) > 8 else "")))
    if not tris:
        raise RuntimeError(T("Tessellation üçgen üretmedi."))
    t2 = time.time()
    status(T("ışın izleme ön hesapları (%d üçgen)...") % ntri, True)
    sc = Scene(np.concatenate(tris), np.concatenate(cols), np.concatenate(alps))
    FreeCAD.Console.PrintMessage(T("RayTrace: hazırlık: tarama %.1f sn, üçgenleme %.1f sn, ön hesap %.1f sn\n")
                                 % (t1 - t0, t2 - t1, time.time() - t2))
    return sc, len(items)


def read_camera(view):
    """Aktif 3B görünümün kamerasını okur. Döner: (cam dict, ekran en/boy oranı)."""
    from pivy import coin
    cam = view.getCameraNode()
    pos = np.array(cam.position.getValue().getValue(), dtype=np.float64)
    rot = cam.orientation.getValue()
    fwd = np.array(rot.multVec(coin.SbVec3f(0, 0, -1)).getValue(), dtype=np.float64)
    up = np.array(rot.multVec(coin.SbVec3f(0, 1, 0)).getValue(), dtype=np.float64)
    persp = cam.isOfType(coin.SoPerspectiveCamera.getClassTypeId())
    size = cam.heightAngle.getValue() if persp else cam.height.getValue()
    try:
        sw, sh = view.getSize()
        aspect = float(sw) / float(sh)
    except Exception:
        aspect = 4.0 / 3.0
    return dict(pos=pos, fwd=fwd, up=up, persp=persp, size=float(size)), aspect


_FC_LIGHT_DEFAULTS = (            # (ad, açı-yatay, açı-dikey, renk RRGGBBAA, güç %)  -- FreeCAD kaynağındaki varsayılanlar
    ("Headlight", 100.0, -46.0, 0xFFFFFFFF, 90),
    ("Backlight", -130.0, -10.0, 0xF5F5EEFF, 60),
    ("FillLight", -40.0, 5.0, 0xE6FAFFFF, 40),
)


def read_freecad_lights(log=None):
    """
    FreeCAD'in Tercihler > Display > Light Sources ayarlarını okur (FreeCAD 1.1+: View/LightSources grubu).
    Döner: (LIGHTS listesi, ortam gücü 0..1, ortam rengi, bilgi metni). Okunamazsa None.
    Yön: kamera uzayında vektör (FreeCAD açıdan şöyle üretir: (sin az cos el, cos az cos el, sin el)).
    """
    import re
    import FreeCAD
    pre = "User parameter:BaseApp/Preferences/View"
    grp, used, keys = None, None, []
    for path in (pre + "/LightSources", pre):
        try:
            g = FreeCAD.ParamGet(path)
            names = [c[1] for c in (g.GetContents() or [])]
        except Exception:
            continue
        hit = [n for n in names if n.startswith(("Headlight", "Backlight", "FillLight", "AmbientLight"))]
        if hit:
            grp, used, keys = g, path, hit
            break
    info = T("ayarlar: %s (%d anahtar)") % (used.split(":")[-1], len(keys)) if grp is not None \
        else T("FreeCAD ışık parametreleri bulunamadı, varsayılan değerler kullanıldı")
    if grp is None:
        try:
            gv = FreeCAD.ParamGet(pre)
            info += " | View grubu: alt gruplar=%s" % list(gv.GetGroups())[:12]
        except Exception:
            pass
        grp = FreeCAD.ParamGet(pre + "/LightSources")
    num = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
    lights = []
    for i, (nm, az, el, rgba, pw) in enumerate(_FC_LIGHT_DEFAULTS):
        try:
            on = bool(grp.GetBool("Enable" + nm, True))
            col = int(grp.GetUnsigned(nm + "Color", rgba))
            power = int(grp.GetInt(nm + "Intensity", pw)) / 100.0
            txt = grp.GetString(nm + "Direction", "")
        except Exception:
            on, col, power, txt = True, rgba, pw / 100.0, ""
        v = [float(x) for x in num.findall(txt)][:3]
        if len(v) < 3:
            a, e = np.radians(az), np.radians(el)
            v = [np.sin(a) * np.cos(e), np.cos(a) * np.cos(e), np.sin(e)]
        n = float(np.linalg.norm(v)) or 1.0
        lights.append(dict(on=on, dir=(v[0] / n, v[1] / n, v[2] / n),
                           color=(((col >> 24) & 255) / 255.0, ((col >> 16) & 255) / 255.0, ((col >> 8) & 255) / 255.0),
                           power=power, shadow=(i == 0)))
    try:
        ac = int(grp.GetUnsigned("AmbientLightColor", 0xFFFFFFFF))
        ap = int(grp.GetInt("AmbientLightIntensity", 20)) / 100.0
    except Exception:
        ac, ap = 0xFFFFFFFF, 0.2
    amb_col = (((ac >> 24) & 255) / 255.0, ((ac >> 16) & 255) / 255.0, ((ac >> 8) & 255) / 255.0)
    info += T(" | ışıklar: ") + ", ".join("%s %s %d%%" % (n, T("açık") if l["on"] else T("kapalı"), round(l["power"] * 100))
                                        for n, l in zip(("ana", "arka", "dolgu"), lights)) + T(", ortam %d%%") % round(ap * 100)
    if log:
        log(info)
    return lights, ap, amb_col, info
