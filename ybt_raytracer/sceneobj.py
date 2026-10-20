# -*- coding: utf-8 -*-
"""YBT sahne nesnesi: ağaçta "YBTray01" gibi bir grup; ışık nesneleri onun altında durur.

Bir belgede birden çok sahne olabilir (ör. gündüz / gece ışık düzeni); `Active` olan sahnenin ışıkları render edilir.
Sahne yokken eklenen ışık için otomatik "YBTray01" yaratılır. Sahnesiz (serbest) ışıklar yalnız belgede hiç sahne yoksa geçerlidir.
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
MARK = "YBTSceneMark"


def icon(active=True):
    return os.path.join(_HERE, "icons", "scene.svg" if active else "scene_off.svg")


def is_scene(o):
    try:
        return MARK in o.PropertiesList
    except Exception:
        return False


def scenes_in(doc):
    return [o for o in (doc.Objects if doc is not None else []) if is_scene(o)]


def active_scene(doc):
    sc = scenes_in(doc)
    for s in sc:
        if bool(s.Active):
            return s
    return sc[0] if sc else None


def scene_of(obj):
    """Işık nesnesinin bağlı olduğu sahne (yoksa None)."""
    try:
        for p in obj.InList:
            if is_scene(p):
                return p
    except Exception:
        pass
    return None


def _next_label(doc):
    used = {o.Label for o in scenes_in(doc)}
    i = 1
    while "YBTray%02d" % i in used:
        i += 1
    return "YBTray%02d" % i


class _Scene(object):
    def __init__(self, obj):
        obj.Proxy = self
        self.add_props(obj)

    @staticmethod
    def add_props(obj):
        if MARK not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", MARK, "Scene", "YBT sahne işareti")
            setattr(obj, MARK, "1")
            obj.setEditorMode(MARK, 2)
        if "Active" not in obj.PropertiesList:
            obj.addProperty("App::PropertyBool", "Active", "Scene", "Etkin sahne: render bu sahnenin ışıklarını kullanır")
            obj.Active = False

    def execute(self, obj):
        pass

    def onChanged(self, obj, prop):
        if prop != "Active" or not getattr(obj, "Active", False):
            return
        try:                                                  # tek etkin sahne: diğerleri kapanır
            for o in scenes_in(obj.Document):
                if o is not obj and o.Active:
                    o.Active = False
        except Exception:
            pass

    def onDocumentRestored(self, obj):
        obj.Proxy = self

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None

    def dumps(self):
        return None

    def loads(self, state):
        return None


class _SceneView(object):
    def __init__(self, vobj):
        vobj.Proxy = self
        self.Object = vobj.Object

    def attach(self, vobj):
        self.Object = vobj.Object

    def updateData(self, obj, prop):
        if prop == "Active":
            try:
                self.Object.ViewObject.signalChangeIcon()
            except Exception:
                pass

    def getIcon(self):
        return icon(bool(getattr(self.Object, "Active", True)))

    def setupContextMenu(self, vobj, menu):
        from PySide import QtGui
        from .i18n import T
        act = QtGui.QAction(T("Etkin sahne yap"), menu)
        act.triggered.connect(lambda *_a: setattr(self.Object, "Active", True))
        menu.addAction(act)

    def doubleClicked(self, vobj):
        return False                                          # grup davranışı (aç/kapa) kalsın

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None

    def dumps(self):
        return None

    def loads(self, state):
        return None


def create(doc, make_active=True):
    """Yeni "YBTray0N" sahnesi yaratır. Belgenin ilk sahnesiyse, sahnesiz ışıklar onun altına alınır."""
    from . import lightobj
    first = not scenes_in(doc)
    loose = [o for o in lightobj.lights_in(doc) if scene_of(o) is None] if first else []
    obj = doc.addObject("App::DocumentObjectGroupPython", "YBTray")
    _Scene(obj)
    obj.Label = _next_label(doc)
    try:
        if obj.ViewObject is not None:
            _SceneView(obj.ViewObject)
    except Exception:
        pass
    for o in loose:
        obj.addObject(o)
    if make_active or first:
        obj.Active = True
    doc.recompute()
    return obj


def target_scene(doc):
    """Yeni ışığın gireceği sahne: seçili sahne / seçili ışığın sahnesi, yoksa etkin sahne, o da yoksa yeni yaratılan."""
    try:
        import FreeCADGui as Gui
        for o in Gui.Selection.getSelection():
            if is_scene(o):
                return o
            s = scene_of(o)
            if s is not None:
                return s
    except Exception:
        pass
    return active_scene(doc) or create(doc)
