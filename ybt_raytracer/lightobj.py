# -*- coding: utf-8 -*-
"""Işık nesneleri: sahneye eklenen, belgeyle birlikte saklanan FreeCAD nesneleri.

1. aşama: Distant (güneş tipi, sonsuz uzaktan paralel ışık). Point / Spot sonraki aşamada.
Nesne bir App::GeometryPython'dır; konumu/yönü FreeCAD'in Yerleşim (Placement) özelliğidir. Işık yerel -Z yönünde YAYILIR
(dönüşsüz nesne = aşağı bakan güneş). Özellikler:
  Enabled        açık / kapalı
  Color          ışık rengi
  Intensity      şiddet, % (100 = ışığa dik yüzeyi malzeme rengiyle tam aydınlatır; varsayılan 80, ortam ışığıyla patlamasın)
  Shadows        gölge düşürsün
  Softness       gölge yumuşaklığı: ışığın görünür açısı (derece; güneş ~0,5; 0 = sert gölge)
Render, `collect(doc)` ile bu nesneleri okur; `apply_to_settings(doc)` sonucu settings._OBJ_LIGHTS'a yazar.
Işık modu (settings.LIGHT_MODE): "objects" = yeni sistem, "legacy" = makro dönemi aydınlatma (paneldeki 3 ışık + FreeCAD ışıkları).
"""
import os

from . import settings as S

TYPES = {
    "distant": dict(label="Distant Light", icon="distant_light.svg"),
}
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


def collect(doc):
    """Açık ışık nesnelerini render'ın ışık sözlüklerine çevirir (dünya uzayında)."""
    import FreeCAD
    res = []
    for o in lights_in(doc):
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
            res.append(dict(on=True, wdir=(to_light.x, to_light.y, to_light.z), color=col, power=power,
                            shadow=bool(o.Shadows), soft=max(0.0, float(getattr(o.Softness, "Value", o.Softness))),
                            name=o.Label, type=o.getPropertyByName(PROP_TYPE)))
        except Exception:
            continue
    return res


def apply_to_settings(doc):
    """Render öncesi: ışık modu "objects" ise ışıkları nesnelerden al (yoksa panelin ışıkları geçerli kalır).
    Döner: (mod, nesne sayısı, kullanılan ışık sayısı)."""
    n = len(lights_in(doc))
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
        add("App::PropertyAngle", "Softness", "Light", "Gölge yumuşaklığı: ışığın görünür açısı (derece; 0 = sert gölge)", 0.5)
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
        try:
            L = float(getattr(self.Object.SymbolSize, "Value", self.Object.SymbolSize)) or 400.0
            c = tuple(self.Object.Color)[:3]
            self.col.rgb.setValue(float(c[0]), float(c[1]), float(c[2]))
        except Exception:
            L = 400.0
        r = L * 0.12
        a = L * 0.10
        pts = [(0, 0, 0), (0, 0, -L),                                  # 0,1: ışık ekseni
               (a, 0, -L + a * 1.6), (-a, 0, -L + a * 1.6), (0, a, -L + a * 1.6), (0, -a, -L + a * 1.6),   # 2-5: ok ucu
               (r, 0, 0), (-r, 0, 0), (0, r, 0), (0, -r, 0),           # 6-9: güneş çarpısı
               (r * .7, r * .7, 0), (-r * .7, -r * .7, 0), (r * .7, -r * .7, 0), (-r * .7, r * .7, 0)]
        idx = [0, 1, -1, 1, 2, -1, 1, 3, -1, 1, 4, -1, 1, 5, -1, 6, 7, -1, 8, 9, -1, 10, 11, -1, 12, 13, -1]
        self.coords.point.setValues(0, len(pts), pts)
        self.lines.coordIndex.setValues(0, len(idx), idx)

    def updateData(self, obj, prop):
        if prop in ("Color", "SymbolSize") and hasattr(self, "coords"):
            self._rebuild()

    def getDisplayModes(self, vobj):
        return ["Symbol"]

    def getDefaultDisplayMode(self):
        return "Symbol"

    def setDisplayMode(self, mode):
        return mode

    def getIcon(self):
        return icon(getattr(self.Object, PROP_TYPE, "distant"))

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


def create(doc, kind="distant"):
    """Belgeye bir ışık nesnesi ekler (varsayılan: modelin üstünde, hafif eğik, aşağıya bakan)."""
    import FreeCAD
    names = dict(distant="DistantLight")
    obj = doc.addObject("App::GeometryPython", names.get(kind, "Light"))
    _Light(obj, kind)
    obj.Label = TYPES[kind]["label"]
    pos, diag = _scene_anchor(doc)
    rot = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 35.0) * FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 40.0)
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
