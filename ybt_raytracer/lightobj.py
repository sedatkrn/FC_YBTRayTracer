# -*- coding: utf-8 -*-
"""Işık nesneleri: sahneye eklenen, belgeyle birlikte saklanan FreeCAD nesneleri.

Türler: Distant (güneş tipi, sonsuz uzaktan paralel ışık), Point (konumlu, her yöne yayılan) ve Spot (konumlu, koni içine yayılan).
Nesne bir App::GeometryPython'dır; konumu/yönü FreeCAD'in Yerleşim (Placement) özelliğidir. Işık yerel -Z yönünde YAYILIR
(dönüşsüz nesne = aşağı bakan güneş). Özellikler:
  Enabled        açık / kapalı
  Color          ışık rengi
  Intensity      şiddet, % (100 = ışığa dik yüzeyi malzeme rengiyle tam aydınlatır; varsayılan 80, ortam ışığıyla patlamasın)
  AffectDiffuse / AffectSpecular  yüzeyi aydınlatsın / parlama versin
  Shadows        gölge düşürsün
  Softness       (Distant) gölge yumuşaklığı: ışığın görünür açısı (derece; güneş ~0,5; 0 = sert gölge)
  Falloff        (Point/Spot) uzaklıkla sönme: InverseSquare (ters kare) / Linear / None
  ReferenceDistance  (Point/Spot) şiddetin tam değerinde olduğu uzaklık (mm); sönme bu uzaklığa göre ölçülür; 0 = otomatik (ışığın sahne merkezine uzaklığı)
  ShadowRadius   (Point/Spot) ışığın boyutu (mm): gölge kenarı yumuşaklığı; 0 = sert gölge
  ConeAngle / EdgeAngle  (Spot) koninin tam açısı ve kenarındaki yumuşak geçiş açısı (derece)
Render, `collect(doc)` ile bu nesneleri okur; `apply_to_settings(doc)` sonucu settings._OBJ_LIGHTS'a yazar.
Işık modu (settings.LIGHT_MODE): "objects" = yeni sistem, "legacy" = makro dönemi aydınlatma (paneldeki 3 ışık + FreeCAD ışıkları).
"""
import os

from . import settings as S

TYPES = {
    "distant": dict(label="Distant Light", icon="distant_light.png"),
    "point": dict(label="Point Light", icon="point_light.png"),
    "spot": dict(label="Spot Light", icon="spot_light.png"),
}
FALLOFFS = ("InverseSquare", "Linear", "None")
_FALL_KEY = {"InverseSquare": "inverse_square", "Linear": "linear", "None": "none"}


def is_positional(kind):
    return kind in ("point", "spot")
_HERE = os.path.dirname(os.path.abspath(__file__))
PROP_TYPE = "YBTLightType"


def icon(kind):
    p = os.path.join(_HERE, "icons", TYPES.get(kind, TYPES["distant"])["icon"])
    return p


def _is_light(o):
    return getattr(o, PROP_TYPE, None) in TYPES


def lights_in(doc):
    """Belgedeki ışık nesneleri (silinmişler hariç)."""
    out = []
    for o in (doc.Objects if doc is not None else []):
        try:
            if _is_light(o):
                out.append(o)
        except Exception:
            pass
    return out


def lights_in_scene(scene):
    return [o for o in getattr(scene, "Group", []) if _is_light(o)]


def active_lights(doc):
    """Render'ın kullanacağı ışık nesneleri: belgede YBT sahnesi varsa etkin sahnenin ışıkları, yoksa tüm (serbest) ışıklar."""
    from . import sceneobj
    allv = lights_in(doc)
    sc = sceneobj.active_scene(doc)
    if sc is None:
        return allv
    return [o for o in allv if sceneobj.scene_of(o) is sc]


def collect(doc):
    """Etkin sahnenin açık ışık nesnelerini render'ın ışık sözlüklerine çevirir (dünya uzayında)."""
    import FreeCAD
    res = []
    for o in active_lights(doc):
        try:
            if not bool(o.Enabled):
                continue
            try:
                rot = o.getGlobalPlacement().Rotation
            except Exception:
                rot = o.Placement.Rotation
            to_light = rot.multVec(FreeCAD.Vector(0, 0, 1))              # ışık -Z'ye yayılır; yüzeyden ışığa doğru +Z
            col = tuple(float(c) for c in tuple(o.Color)[:3])
            power = max(0.0, float(o.Intensity)) / 100.0
            if power <= 0.0:
                continue
            kind = o.getPropertyByName(PROP_TYPE)
            d = dict(on=True, kind=kind, wdir=(to_light.x, to_light.y, to_light.z), color=col, power=power,
                     diffuse=bool(o.AffectDiffuse), spec=bool(o.AffectSpecular), shadow=bool(o.Shadows),
                     name=o.Label, type=kind)
            if is_positional(kind):
                try:
                    pl = o.getGlobalPlacement()
                except Exception:
                    pl = o.Placement
                d["wpos"] = (pl.Base.x, pl.Base.y, pl.Base.z)
                d["axis"] = (-to_light.x, -to_light.y, -to_light.z)           # ışığın gittiği yön
                d["falloff"] = _FALL_KEY.get(str(o.Falloff), "inverse_square")
                d["ref"] = max(0.0, float(getattr(o.ReferenceDistance, "Value", o.ReferenceDistance)))
                d["radius"] = max(0.0, float(getattr(o.ShadowRadius, "Value", o.ShadowRadius)))
                if kind == "spot":
                    d["cone"] = float(getattr(o.ConeAngle, "Value", o.ConeAngle))
                    d["edge"] = float(getattr(o.EdgeAngle, "Value", o.EdgeAngle))
            else:
                d["soft"] = max(0.0, float(getattr(o.Softness, "Value", o.Softness)))
            res.append(d)
        except Exception:
            continue
    return res


def apply_to_settings(doc):
    """Render öncesi: ışık modu "objects" ise ışıkları nesnelerden al (yoksa panelin ışıkları geçerli kalır).
    Döner: (mod, nesne sayısı, kullanılan ışık sayısı)."""
    n = len(active_lights(doc))
    if str(getattr(S, "LIGHT_MODE", "objects")) != "objects":
        S._OBJ_LIGHTS = None
        return "legacy", n, 0
    lst = collect(doc)
    S._OBJ_LIGHTS = lst if lst else None
    return "objects", n, len(lst)


class _Light(object):
    """Işık nesnesinin Python vekili (belgeye adıyla kaydedilir; eklenti yoksa nesne düz FeaturePython olarak açılır)."""

    def __init__(self, obj, kind="distant"):
        obj.Proxy = self
        self.add_props(obj, kind)

    @staticmethod
    def add_props(obj, kind):
        def add(typ, name, grp, doc, val=None, hid=False):
            if name in obj.PropertiesList:
                return
            obj.addProperty(typ, name, grp, doc)
            if val is not None:
                setattr(obj, name, val)
            if hid:
                obj.setEditorMode(name, 2)                        # özellik düzenleyicide gizli
        add("App::PropertyString", PROP_TYPE, "Light", "Işık türü", kind, hid=True)
        add("App::PropertyBool", "Enabled", "Light", "Işık açık / kapalı", True)
        add("App::PropertyColor", "Color", "Light", "Işık rengi", (1.0, 1.0, 1.0))
        add("App::PropertyFloat", "Intensity", "Light", "Şiddet (%). 100 = beyaz yüzeyi ışığa dik tam aydınlatır (ortam ışığıyla birlikte parlayabilir)", 80.0)
        add("App::PropertyBool", "Shadows", "Light", "Gölge düşürsün", True)
        add("App::PropertyBool", "AffectDiffuse", "Light", "Yüzey rengini aydınlatır", True)
        add("App::PropertyBool", "AffectSpecular", "Light", "Parlama (specular) verir", True)
        if kind == "distant":
            add("App::PropertyAngle", "Softness", "Light", "Gölge yumuşaklığı: ışığın görünür açısı (derece; 0 = sert gölge)", 0.5)
        else:
            if "Falloff" not in obj.PropertiesList:
                obj.addProperty("App::PropertyEnumeration", "Falloff", "Light", "Uzaklıkla sönme: ters kare (gerçekçi), doğrusal ya da yok")
                obj.Falloff = list(FALLOFFS)
                obj.Falloff = "InverseSquare"
            add("App::PropertyLength", "ReferenceDistance", "Light", "Şiddetin tam değerinde olduğu uzaklık (sönme buna göre ölçülür). 0 = otomatik: ışığın sahne merkezine uzaklığı (ışığı yaklaştırınca sahne patlamaz)", 0.0)
            add("App::PropertyLength", "ShadowRadius", "Light", "Işık kaynağının boyu: gölge kenarı yumuşaklığı (0 = sert gölge)", 0.0)
        if kind == "spot":
            add("App::PropertyAngle", "ConeAngle", "Light", "Koninin tam açısı", 45.0)
            add("App::PropertyAngle", "EdgeAngle", "Light", "Koni kenarındaki yumuşak geçiş açısı", 10.0)
        add("App::PropertyLength", "SymbolSize", "View", "Görünümdeki ışık simgesinin boyu", 400.0)

    def execute(self, obj):
        pass

    def onDocumentRestored(self, obj):
        obj.Proxy = self
        try:
            self.add_props(obj, getattr(obj, PROP_TYPE, "distant") or "distant")      # eski sürümde eksik özellikler tamamlansın
        except Exception:
            pass

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None

    def dumps(self):
        return None

    def loads(self, state):
        return None


class _LightView(object):
    """Görünüm vekili: ikon + 3B simge (ışık yönünü gösteren ok ve güneş çarpısı)."""

    def __init__(self, vobj):
        vobj.Proxy = self
        self.Object = vobj.Object

    def attach(self, vobj):
        from pivy import coin
        self.Object = vobj.Object
        self.vobj = vobj
        self.root = coin.SoSeparator()
        self.col = coin.SoBaseColor()
        self.coords = coin.SoCoordinate3()
        self.lines = coin.SoIndexedLineSet()
        st = coin.SoDrawStyle()
        st.lineWidth = 2.0
        self.root.addChild(self.col)
        self.root.addChild(st)
        self.root.addChild(self.coords)
        self.root.addChild(self.lines)
        vobj.addDisplayMode(self.root, "Symbol")
        self._rebuild()

    def _rebuild(self):
        import math
        try:
            L = float(getattr(self.Object.SymbolSize, "Value", self.Object.SymbolSize)) or 400.0
            c = tuple(self.Object.Color)[:3]
            self.col.rgb.setValue(float(c[0]), float(c[1]), float(c[2]))
        except Exception:
            L = 400.0
        kind = getattr(self.Object, PROP_TYPE, "distant")
        if kind == "distant":
            r = L * 0.12
            a = L * 0.10
            pts = [(0, 0, 0), (0, 0, -L),                                  # 0,1: ışık ekseni
                   (a, 0, -L + a * 1.6), (-a, 0, -L + a * 1.6), (0, a, -L + a * 1.6), (0, -a, -L + a * 1.6),   # 2-5: ok ucu
                   (r, 0, 0), (-r, 0, 0), (0, r, 0), (0, -r, 0),           # 6-9: güneş çarpısı
                   (r * .7, r * .7, 0), (-r * .7, -r * .7, 0), (r * .7, -r * .7, 0), (-r * .7, r * .7, 0)]
            idx = [0, 1, -1, 1, 2, -1, 1, 3, -1, 1, 4, -1, 1, 5, -1, 6, 7, -1, 8, 9, -1, 10, 11, -1, 12, 13, -1]
        else:
            r = L * 0.18                                                 # nokta ışığı: küçük yıldız (3 eksen + köşegenler)
            q = r * 0.7
            pts = [(r, 0, 0), (-r, 0, 0), (0, r, 0), (0, -r, 0), (0, 0, r), (0, 0, -r),
                   (q, q, q), (-q, -q, -q), (q, -q, q), (-q, q, -q), (q, q, -q), (-q, -q, q), (-q, q, q), (q, -q, -q)]
            idx = [0, 1, -1, 2, 3, -1, 4, 5, -1, 6, 7, -1, 8, 9, -1, 10, 11, -1, 12, 13, -1]
            if kind == "spot":                                           # koni: tepe (0,0,0), -Z'ye açılır
                try:
                    half = math.radians(max(1.0, min(89.0, float(getattr(self.Object.ConeAngle, "Value", self.Object.ConeAngle)) / 2.0)))
                except Exception:
                    half = math.radians(22.5)
                ln = L
                rr = ln * math.tan(half)
                b = len(pts)
                ring = [(rr * math.cos(2 * math.pi * k / 24), rr * math.sin(2 * math.pi * k / 24), -ln) for k in range(24)]
                pts += [(0, 0, -ln)] + ring
                idx += [0, b, -1]                                         # eksen
                for k in (0, 6, 12, 18):
                    idx += [0, b + 1 + k, -1]                             # koni kenar çizgileri
                idx += [b + 1 + k for k in range(24)] + [b + 1, -1]       # taban çemberi
            else:
                idx += []
        self.coords.point.setValues(0, len(pts), pts)
        self.lines.coordIndex.setValues(0, len(idx), idx)

    def updateData(self, obj, prop):
        if prop in ("Color", "SymbolSize", "ConeAngle") and hasattr(self, "coords"):
            self._rebuild()

    def getDisplayModes(self, vobj):
        return ["Symbol"]

    def getDefaultDisplayMode(self):
        return "Symbol"

    def setDisplayMode(self, mode):
        return mode

    def getIcon(self):
        return icon(getattr(self.Object, PROP_TYPE, "distant"))

    def doubleClicked(self, vobj):
        """Ağaçta çift tıklama: Işık Özellikleri panelini bu ışıkla açar."""
        try:
            from . import light_ui
            light_ui.open_panel(select=vobj.Object)
        except Exception:
            import traceback
            import FreeCAD
            FreeCAD.Console.PrintError(traceback.format_exc())
        return True

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None

    def dumps(self):
        return None

    def loads(self, state):
        return None


def _scene_anchor(doc):
    """Yeni ışık için başlangıç konumu: modellerin kutusunun üstü ve ortası; (merkez, boy)."""
    import FreeCAD
    bb = None
    for o in doc.Objects:
        sh = getattr(o, "Shape", None)
        if sh is None or _is_light(o):
            continue
        try:
            if sh.isNull() or not sh.BoundBox.isValid():
                continue
            bb = sh.BoundBox if bb is None else bb.united(sh.BoundBox)
        except Exception:
            continue
    if bb is None:
        return FreeCAD.Vector(0, 0, 1000), 1000.0
    return FreeCAD.Vector(bb.Center.x, bb.Center.y, bb.ZMax + bb.DiagonalLength * 0.5), bb.DiagonalLength


def change_type(obj, kind):
    """Işığın türünü değiştirir (Placement, renk, şiddet vb. korunur); yeni türün özellikleri eklenir.
    Distant -> Point/Spot: konum ve uzaklık sönmesi modele göre ayarlanır, Point/Spot -> Distant: yön korunur."""
    doc = obj.Document
    was = getattr(obj, PROP_TYPE, "distant")
    obj.setEditorMode(PROP_TYPE, 0)
    setattr(obj, PROP_TYPE, kind)
    obj.setEditorMode(PROP_TYPE, 2)
    _Light.add_props(obj, kind)
    if is_positional(kind) and not is_positional(was):
        _, diag = _scene_anchor(doc)
        obj.ReferenceDistance = 0.0
        obj.ShadowRadius = diag * 0.02
        obj.SymbolSize = max(50.0, diag * (0.3 if kind == "spot" else 0.12))
    elif not is_positional(kind) and is_positional(was):
        obj.SymbolSize = max(100.0, _scene_anchor(doc)[1] * 0.4)
    if obj.Label in [v["label"] for v in TYPES.values()]:
        obj.Label = TYPES[kind]["label"]
    try:
        vp = obj.ViewObject.Proxy
        vp._rebuild()
    except Exception:
        pass
    return obj


def create(doc, kind="distant"):
    """Belgeye bir ışık nesnesi ekler (varsayılan: modelin üstünde, hafif eğik, aşağıya bakan)."""
    import FreeCAD
    names = dict(distant="DistantLight", point="PointLight", spot="SpotLight")
    obj = doc.addObject("App::GeometryPython", names.get(kind, "Light"))
    _Light(obj, kind)
    obj.Label = TYPES[kind]["label"]
    pos, diag = _scene_anchor(doc)
    rot = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 35.0) * FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 40.0)
    if is_positional(kind):
        # konumlu ışık: modelin üstünde, biraz yanında; spot model merkezine bakar, uzaklık sönmesi modele göre ayarlı gelir
        center = FreeCAD.Vector(pos.x, pos.y, pos.z - diag * 0.5)
        lp = FreeCAD.Vector(center.x + diag * 0.35, center.y - diag * 0.35, center.z + diag * 0.9)
        v = center - lp
        rot = FreeCAD.Rotation(FreeCAD.Vector(0, 0, -1), v)                  # yerel -Z, merkeze doğru
        obj.Placement = FreeCAD.Placement(lp, rot)
        obj.ReferenceDistance = 0.0                                          # otomatik
        obj.ShadowRadius = diag * 0.02
        obj.SymbolSize = max(50.0, diag * (0.3 if kind == "spot" else 0.12))
    else:
        obj.Placement = FreeCAD.Placement(pos, rot)
        obj.SymbolSize = max(100.0, diag * 0.4)
    try:
        import FreeCADGui as Gui
        if obj.ViewObject is not None:
            _LightView(obj.ViewObject)
            obj.ViewObject.DisplayMode = "Symbol"
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(obj)
    except Exception:
        pass
    doc.recompute()
    return obj
