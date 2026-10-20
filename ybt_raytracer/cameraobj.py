# -*- coding: utf-8 -*-
"""Kamera nesneleri: sahneye (YBTray) eklenen, belgeyle saklanan, 3B görünümden bağımsız kameralar.

Nesne bir App::GeometryPython'dır; konum/yön FreeCAD Yerleşimi (Placement): kamera yerel -Z yönüne bakar, yerel +Y yukarıdır (Coin ile aynı).
Özellikler:
  Active          sahnede etkin kamera: render bu kameradan alınır (sahnede tek etkin kamera; hiçbiri etkin değilse render 3B görünümden alınır)
  Projection      Perspective / Orthographic
  FocalLength     odak uzaklığı (mm) ve SensorWidth (mm; 36 = tam kare): yatay görüş açısı = 2 atan(SensorWidth / 2 / FocalLength)
  OrthoWidth      ortografik kamerada görüntünün yatay genişliği (mm, model birimi)
  Aspect          kadraj oranı (en / boy); render'ın yüksekliğini belirler (genişlik panelden)
  DepthOfField    alan derinliği açık / kapalı; FocusDistance (mm) ya da FocusObject (nesnenin kamera eksenindeki uzaklığı), FStop (diyafram sayısı)
Render, `active_camera(doc)` ile etkin kamerayı bulur, `render_camera(obj)` ile render'ın kamera sözlüğünü alır.
"""
import math
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
MARK = "YBTCameraMark"
PROJECTIONS = ("Perspective", "Orthographic")


def icon(active=True):
    return os.path.join(_HERE, "icons", "camera.png" if active else "camera_off.png")


def is_camera(o):
    try:
        return MARK in o.PropertiesList
    except Exception:
        return False


def cameras_in(doc):
    return [o for o in (doc.Objects if doc is not None else []) if is_camera(o)]


def cameras_in_scene(doc, scene):
    from . import sceneobj
    return [o for o in cameras_in(doc) if sceneobj.scene_of(o) is scene]


def scene_cameras(doc):
    """Etkin sahnenin kameraları (sahne yoksa serbest tüm kameralar)."""
    from . import sceneobj
    allc = cameras_in(doc)
    sc = sceneobj.active_scene(doc)
    if sc is None:
        return allc
    return [o for o in allc if sceneobj.scene_of(o) is sc]


def active_camera(doc):
    """Render'ın kullanacağı kamera nesnesi (yok = 3B görünümün kamerası)."""
    for o in scene_cameras(doc):
        try:
            if bool(o.Active):
                return o
        except Exception:
            pass
    return None


# ------------------------------------------------------------------ kamera hesapları
def _placement(o):
    try:
        return o.getGlobalPlacement()
    except Exception:
        return o.Placement


def _val(v, default=0.0):
    try:
        return float(getattr(v, "Value", v))
    except Exception:
        return default


def half_extent_x(o):
    """Birim uzaklıkta (perspektif) ya da mm (ortografik) yatay yarı genişlik."""
    if str(o.Projection) == "Orthographic":
        return max(1e-6, _val(o.OrthoWidth, 1000.0)) / 2.0
    return max(1e-6, _val(o.SensorWidth, 36.0)) / (2.0 * max(1e-6, _val(o.FocalLength, 50.0)))


def frame_aspect(o):
    return max(0.05, min(20.0, _val(o.Aspect, 16.0 / 9.0)))


def size_for_aspect(hx, aspect, persp=True):
    """Render'ın `size` değeri: küçük kenara uygulanır (Coin gibi). hx: yatay yarı genişlik."""
    base = hx / aspect if aspect >= 1.0 else hx
    return 2.0 * math.atan(base) if persp else 2.0 * base


def focus_distance(o, pos, fwd):
    """Odak mesafesi (mm): FocusObject varsa nesnenin merkezinin kamera ekseni boyunca uzaklığı, yoksa FocusDistance."""
    fo = getattr(o, "FocusObject", None)
    if fo is not None:
        try:
            c = fo.Shape.BoundBox.Center
            d = (c.x - pos.x) * fwd.x + (c.y - pos.y) * fwd.y + (c.z - pos.z) * fwd.z
            if d > 1e-6:
                return d
        except Exception:
            pass
    return max(1e-3, _val(o.FocusDistance, 3000.0))


def render_camera(o):
    """Kamera nesnesinden render'ın kamera sözlüğü ve kadraj oranı: (cam, aspect)."""
    import numpy as np
    pl = _placement(o)
    rot = pl.Rotation
    fwd = rot.multVec(_vec(0, 0, -1))
    up = rot.multVec(_vec(0, 1, 0))
    aspect = frame_aspect(o)
    persp = str(o.Projection) != "Orthographic"
    hx = half_extent_x(o)
    cam = dict(pos=np.array([pl.Base.x, pl.Base.y, pl.Base.z], dtype=np.float64),
               fwd=np.array([fwd.x, fwd.y, fwd.z], dtype=np.float64),
               up=np.array([up.x, up.y, up.z], dtype=np.float64),
               persp=persp, size=float(size_for_aspect(hx, aspect, persp)))
    if persp and bool(o.DepthOfField):
        cam["dof"] = dict(focus=float(focus_distance(o, pl.Base, fwd)), focal=_val(o.FocalLength, 50.0),
                          fstop=max(0.1, _val(o.FStop, 4.0)), sensor=_val(o.SensorWidth, 36.0))
    return cam, aspect


def _vec(x, y, z):
    import FreeCAD
    return FreeCAD.Vector(x, y, z)


# ------------------------------------------------------------------ nesne
class _Camera(object):
    def __init__(self, obj):
        obj.Proxy = self
        self.add_props(obj)

    @staticmethod
    def add_props(obj):
        def add(typ, name, grp, doc, val=None, hid=False):
            if name in obj.PropertiesList:
                return
            obj.addProperty(typ, name, grp, doc)
            if val is not None:
                setattr(obj, name, val)
            if hid:
                obj.setEditorMode(name, 2)
        add("App::PropertyString", MARK, "Camera", "YBT kamera işareti", "1", hid=True)
        add("App::PropertyBool", "Active", "Camera", "Etkin kamera: render bu kameradan alınır", False)
        if "Projection" not in obj.PropertiesList:
            obj.addProperty("App::PropertyEnumeration", "Projection", "Camera", "Perspektif ya da ortografik")
            obj.Projection = list(PROJECTIONS)
            obj.Projection = "Perspective"
        add("App::PropertyFloat", "FocalLength", "Camera", "Odak uzaklığı (mm)", 50.0)
        add("App::PropertyFloat", "SensorWidth", "Camera", "Sensör genişliği (mm; 36 = tam kare)", 36.0)
        add("App::PropertyLength", "OrthoWidth", "Camera", "Ortografik kamerada görüntünün yatay genişliği", 1000.0)
        add("App::PropertyFloat", "Aspect", "Camera", "Kadraj oranı (en / boy); render yüksekliğini belirler", 16.0 / 9.0)
        add("App::PropertyBool", "DepthOfField", "Depth of Field", "Alan derinliği (yalnız perspektif)", False)
        add("App::PropertyLength", "FocusDistance", "Depth of Field", "Odak mesafesi (kameradan, mm)", 3000.0)
        add("App::PropertyLink", "FocusObject", "Depth of Field", "İsteğe bağlı: bu nesneye odaklan (merkezinin kamera eksenindeki uzaklığı)")
        add("App::PropertyFloat", "FStop", "Depth of Field", "Diyafram sayısı (küçük = daha çok bulanıklık)", 4.0)
        add("App::PropertyLength", "SymbolSize", "View", "Görünümdeki kamera simgesinin boyu", 500.0)

    def execute(self, obj):
        pass

    def onChanged(self, obj, prop):
        if prop != "Active":
            return
        try:
            if not bool(obj.Active):
                return
            from . import sceneobj
            sc = sceneobj.scene_of(obj)
            for o in cameras_in(obj.Document):                # sahnede tek etkin kamera
                if o is not obj and o.Active and sceneobj.scene_of(o) is sc:
                    o.Active = False
        except Exception:
            pass

    def onDocumentRestored(self, obj):
        obj.Proxy = self
        try:
            self.add_props(obj)
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


class _CameraView(object):
    """Görünüm vekili: kamera simgesi (görüş piramidi + yukarı üçgeni), etkin kamera turuncu."""

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
        for n in (self.col, st, self.coords, self.lines):
            self.root.addChild(n)
        vobj.addDisplayMode(self.root, "Symbol")
        self._rebuild()

    def _rebuild(self):
        o = self.Object
        try:
            L = _val(o.SymbolSize, 500.0) or 500.0
            if bool(o.Active):
                self.col.rgb.setValue(1.0, 0.55, 0.1)
            else:
                self.col.rgb.setValue(0.75, 0.78, 0.82)
            hx = half_extent_x(o)
            asp = frame_aspect(o)
            persp = str(o.Projection) != "Orthographic"
        except Exception:
            L, hx, asp, persp = 500.0, 0.36, 16.0 / 9.0, True
        if persp:
            a = min(hx, 1.2) * L                       # yarı genişlik, L uzaklıkta
            b = a / asp
            z = -L
            pts = [(0, 0, 0), (-a, -b, z), (a, -b, z), (a, b, z), (-a, b, z),                 # 0 tepe, 1-4 çerçeve
                   (-a * 0.5, b * 1.08, z), (a * 0.5, b * 1.08, z), (0, b * 1.6, z)]          # 5-7 "yukarı" üçgeni
            idx = [0, 1, -1, 0, 2, -1, 0, 3, -1, 0, 4, -1, 1, 2, 3, 4, 1, -1, 5, 6, 7, 5, -1]
        else:                                           # ortografik: kameranın yerinde gerçek boyutlu çerçeve, L boyunda prizma
            a = hx
            b = a / asp
            z = -L
            pts = [(-a, -b, 0), (a, -b, 0), (a, b, 0), (-a, b, 0),
                   (-a, -b, z), (a, -b, z), (a, b, z), (-a, b, z),
                   (-a * 0.5, b * 1.08, 0), (a * 0.5, b * 1.08, 0), (0, b * 1.6, 0)]
            idx = [0, 1, 2, 3, 0, -1, 4, 5, 6, 7, 4, -1, 0, 4, -1, 1, 5, -1, 2, 6, -1, 3, 7, -1, 8, 9, 10, 8, -1]
        self.coords.point.setValues(0, len(pts), pts)
        self.lines.coordIndex.setValues(0, len(idx), idx)

    def updateData(self, obj, prop):
        if prop in ("Active", "SymbolSize", "FocalLength", "SensorWidth", "OrthoWidth", "Aspect", "Projection") and hasattr(self, "coords"):
            self._rebuild()
            if prop == "Active":
                try:
                    self.Object.ViewObject.signalChangeIcon()
                except Exception:
                    pass

    def getDisplayModes(self, vobj):
        return ["Symbol"]

    def getDefaultDisplayMode(self):
        return "Symbol"

    def setDisplayMode(self, mode):
        return mode

    def getIcon(self):
        return icon(bool(getattr(self.Object, "Active", True)))

    def setupContextMenu(self, vobj, menu):
        from PySide import QtGui
        from .i18n import T
        a1 = QtGui.QAction(T("Etkin kamera yap"), menu)
        a1.triggered.connect(lambda *_a: setattr(self.Object, "Active", True))
        menu.addAction(a1)
        a2 = QtGui.QAction(T("Kameradan bak"), menu)
        a2.triggered.connect(lambda *_a: look_through(self.Object))
        menu.addAction(a2)
        a3 = QtGui.QAction(T("Kamerayı 3B görünüme eşitle"), menu)
        a3.triggered.connect(lambda *_a: update_from_view(self.Object))
        menu.addAction(a3)

    def doubleClicked(self, vobj):
        """Ağaçta çift tıklama: Kamera Özellikleri panelini bu kamerayla açar."""
        try:
            from . import camera_ui
            camera_ui.open_panel(select=vobj.Object)
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


# ------------------------------------------------------------------ 3B görünüm ile bağlantı
def _view():
    import FreeCADGui as Gui
    if Gui.ActiveDocument is None:
        return None
    return getattr(Gui.ActiveDocument, "ActiveView", None)


def _read_view():
    """3B görünümün kamerası: (konum, dönüş (FreeCAD.Rotation), perspektif?, yatay yarı genişlik (persp: tan, ortho: mm), görünüm oranı)."""
    import FreeCAD
    v = _view()
    if v is None:
        raise RuntimeError("3B görünüm yok")
    node = v.getCameraNode()
    from pivy import coin
    p = node.position.getValue().getValue()
    q = node.orientation.getValue().getValue()
    persp = node.isOfType(coin.SoPerspectiveCamera.getClassTypeId())
    try:
        sw, sh = v.getSize()
        asp = float(sw) / float(sh)
    except Exception:
        asp = 4.0 / 3.0
    if persp:
        base = math.tan(node.heightAngle.getValue() / 2.0)
    else:
        base = node.height.getValue() / 2.0
    hx = base * asp if asp >= 1.0 else base
    return FreeCAD.Vector(*p), FreeCAD.Rotation(q[0], q[1], q[2], q[3]), persp, hx, asp


def update_from_view(obj, aspect_from_view=False):
    """Kamerayı şu anki 3B görünüme eşitler (konum, yön, görüş açısı)."""
    import FreeCAD
    pos, rot, persp, hx, asp = _read_view()
    keep_aspect = frame_aspect(obj)
    obj.Placement = FreeCAD.Placement(pos, rot)
    obj.Projection = "Perspective" if persp else "Orthographic"
    if persp:
        obj.FocalLength = max(1.0, _val(obj.SensorWidth, 36.0) / (2.0 * hx))
    else:
        obj.OrthoWidth = 2.0 * hx
    if aspect_from_view:
        obj.Aspect = asp
    else:
        # kadraj oranı korunur; görüntünün yatay genişliği görünümdekiyle aynı kalsın (kenar kırpılabilir)
        obj.Aspect = keep_aspect
    return obj


def look_through(obj):
    """3B görünümü kameranın bakışına getirir (kadrajın tamamı görünümde kalacak şekilde)."""
    from pivy import coin
    v = _view()
    if v is None:
        return
    persp = str(obj.Projection) != "Orthographic"
    v.setCameraType("Perspective" if persp else "Orthographic")
    node = v.getCameraNode()
    pl = _placement(obj)
    node.position.setValue(pl.Base.x, pl.Base.y, pl.Base.z)
    q = pl.Rotation.Q
    node.orientation.setValue(coin.SbRotation(q[0], q[1], q[2], q[3]))
    try:
        sw, sh = v.getSize()
        av = float(sw) / float(sh)
    except Exception:
        av = 4.0 / 3.0
    ar = frame_aspect(obj)
    hx = half_extent_x(obj)
    if persp:
        fx = hx
        fy = hx / ar
        base = max(fy / (1.0 if av >= 1.0 else 1.0 / av), fx / (av if av >= 1.0 else 1.0))
        node.heightAngle.setValue(2.0 * math.atan(base))
    else:
        fx = hx
        fy = hx / ar
        base = max(fy / (1.0 if av >= 1.0 else 1.0 / av), fx / (av if av >= 1.0 else 1.0))
        node.height.setValue(2.0 * base)


def create(doc, from_view=True):
    """Belgeye kamera ekler; varsayılan olarak şu anki 3B görünümün bakışıyla. Etkin kamera olur."""
    import FreeCAD
    obj = doc.addObject("App::GeometryPython", "Camera")
    _Camera(obj)
    n = len(cameras_in(doc))
    obj.Label = "Camera" if n <= 1 else "Camera %d" % n
    pos, diag = _anchor(doc)
    obj.SymbolSize = max(50.0, diag * 0.15)
    got = False
    if from_view:
        try:
            pos_v, rot_v, persp, hx, asp = _read_view()
            obj.Placement = FreeCAD.Placement(pos_v, rot_v)
            obj.Aspect = asp
            obj.Projection = "Perspective" if persp else "Orthographic"
            if persp:
                obj.FocalLength = max(1.0, 36.0 / (2.0 * hx))
            else:
                obj.OrthoWidth = 2.0 * hx
            # odak mesafesi: modelin merkezine uzaklık
            c = FreeCAD.Vector(*[0.0, 0.0, 0.0])
            try:
                c = _model_center(doc)
                d = (c - pos_v).dot(rot_v.multVec(FreeCAD.Vector(0, 0, -1)))
                if d > 1.0:
                    obj.FocusDistance = d
            except Exception:
                pass
            got = True
        except Exception:
            got = False
    if not got:
        obj.Placement = FreeCAD.Placement(FreeCAD.Vector(pos.x, pos.y - diag * 1.5, pos.z), FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 90))
        obj.FocusDistance = diag * 1.5
    try:
        import FreeCADGui as Gui
        if obj.ViewObject is not None:
            _CameraView(obj.ViewObject)
            obj.ViewObject.DisplayMode = "Symbol"
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(obj)
    except Exception:
        pass
    obj.Active = True
    doc.recompute()
    return obj


def _model_bbox(doc):
    import FreeCAD
    from . import lightobj
    bb = None
    for o in doc.Objects:
        sh = getattr(o, "Shape", None)
        if sh is None or lightobj._is_light(o) or is_camera(o):
            continue
        try:
            if sh.isNull() or not sh.BoundBox.isValid():
                continue
            bb = sh.BoundBox if bb is None else bb.united(sh.BoundBox)
        except Exception:
            continue
    return bb


def _model_center(doc):
    bb = _model_bbox(doc)
    if bb is None:
        raise RuntimeError("model yok")
    return bb.Center


def _anchor(doc):
    import FreeCAD
    bb = _model_bbox(doc)
    if bb is None:
        return FreeCAD.Vector(0, 0, 0), 1000.0
    return bb.Center, bb.DiagonalLength
