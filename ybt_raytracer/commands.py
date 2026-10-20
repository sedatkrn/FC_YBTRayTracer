# -*- coding: utf-8 -*-
"""FreeCAD komutları (eklenti girişi): Render, Malzemeler, Seçenekler.

InitGui.py bu modülü içe aktarıp `register()` çağırır. Komutlar:
  YBT_Render      ayar panelini açar (render panelin 'Render' düğmesiyle başlar)
  YBT_NewScene    ağaçta yeni "YBTray0N" sahnesi yaratır (ışıklar altında durur)
  YBT_DistantLight  sahneye Distant (güneş tipi) ışık nesnesi ekler
  YBT_LightProperties  Işık Özellikleri panelini açar
  YBT_Materials   Malzemeler (Surface) penceresini açar
  YBT_Options    panelin 'Seçenekler' penceresini açar (gerekirse paneli de açar)

Komutların asıl yeri tezgâh listesindeki "YBT Raytracer" tezgâhıdır (kendi araç çubuğu ve menüsüyle, InitGui.py içinde
tanımlanır; `separate_workbench_enabled`, varsayılan açık). Her tezgâhtan erişilebilmesi için ayrıca FreeCAD 1.0+
`Gui.addWorkbenchManipulator` ile standart "Macro" araç çubuğuna ve "Macro" menüsüne eklenir (manipulator yeni araç
çubuğu yaratamaz, yalnız var olanlara ekler; `ShowInAllWorkbenches`, varsayılan açık).
Kullanıcı JSON dosyaları ve nesne özellikleri (YBTMaterial / YBTInclude) bu katmandan etkilenmez.
"""
import os

COMMANDS = ("YBT_Render", "YBT_NewScene", "YBT_DistantLight", "YBT_LightProperties", "YBT_Materials", "YBT_Options")
TOOLBAR = "YBT Raytracer"
MENU = "YBT Raytracer"
_PARAM = "User parameter:BaseApp/Preferences/Mod/FCYBTRayTracer"      # i18n.py ile aynı grup
_HERE = os.path.dirname(os.path.abspath(__file__))
_ICONS = os.path.join(_HERE, "icons")

_state = {"registered": False, "manipulator": False}


def icon_path():
    """Tezgâh / ana komut ikonu (InitGui.py sınıf gövdesinden çağrılır)."""
    return os.path.join(_HERE, "icon.png")


def _tr(s):
    from .i18n import T
    return T(s)


def _icon(name):
    p = os.path.join(_ICONS, name)
    return p if os.path.exists(p) else os.path.join(_HERE, "icon.png")


def _doc_ready():
    try:
        import FreeCAD
        import FreeCADGui as Gui
        return FreeCAD.ActiveDocument is not None and Gui.ActiveDocument is not None
    except Exception:
        return False


def _panel():
    """Açık render paneli (kapatılmış / silinmiş Qt nesnesi ise None)."""
    import FreeCAD
    dlg = getattr(FreeCAD, "_raytrace_dlg", None)
    if dlg is None:
        return None
    try:
        if dlg.isVisible():
            return dlg
    except Exception:                                  # silinmiş Qt nesnesi
        pass
    return None


def open_panel():
    """Ayar panelini açar; zaten açıksa öne getirir. Paneli döndürür (açılamadıysa None)."""
    dlg = _panel()
    if dlg is not None:
        dlg.raise_()
        dlg.activateWindow()
        return dlg
    from . import ui
    ui.main()
    return _panel()


def open_materials():
    api = getattr(_panel(), "_raytrace_api", None)
    if api and api.get("open_mats"):
        api["open_mats"]()                              # panel açıksa onun geri çağrılarıyla (sahne önbelleği sıfırlanır)
        return
    from .i18n import init_lang
    init_lang()
    from .surface_ui import open_surface
    open_surface()


def open_options():
    dlg = open_panel()                                  # Seçenekler penceresi panelin değerlerine dayanır
    api = getattr(dlg, "_raytrace_api", None)
    if api and api.get("open_options"):
        api["open_options"]()


def add_light(kind):
    """Etkin belgeye ışık nesnesi ekler. Belge eski (makro dönemi) aydınlatmadaysa yeni sisteme geçirilir."""
    import FreeCAD
    from . import lightobj, settings as S
    doc = FreeCAD.ActiveDocument
    if doc is None:
        return None
    from . import sceneobj
    doc.openTransaction("Add light")
    try:
        sc = sceneobj.target_scene(doc)                  # seçili / etkin sahne; yoksa YBTray01 yaratılır
        obj = lightobj.create(doc, kind)
        sc.addObject(obj)
    finally:
        doc.commitTransaction()
    if str(S.LIGHT_MODE) != "objects":
        S.LIGHT_MODE = "objects"
        FreeCAD.Console.PrintMessage(_tr("YBT: ışık nesnesi eklendi; bu belge artık ışık nesneleriyle aydınlatılır (eski aydınlatma kapandı).\n"))
        dlg = _panel()
        api = getattr(dlg, "_raytrace_api", None)
        if api and api.get("refresh_light_mode"):
            api["refresh_light_mode"]()
    try:
        from . import light_ui
        light_ui.open_panel(select=obj)                 # yeni ışık hemen düzenlenebilsin
    except Exception:
        pass
    return obj


def new_scene():
    """Ağaçta yeni YBT sahnesi (YBTray01, 02...) yaratır ve etkin yapar."""
    import FreeCAD
    from . import sceneobj
    doc = FreeCAD.ActiveDocument
    if doc is None:
        return None
    doc.openTransaction("New YBT scene")
    try:
        from . import lightobj
        obj = sceneobj.create(doc, make_active=True)
        if not lightobj.lights_in_scene(obj):             # yeni sahne boş başlamasın: bir Distant Light ile gelir
            obj.addObject(lightobj.create(doc, "distant"))
    finally:
        doc.commitTransaction()
    try:
        import FreeCADGui as Gui
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(obj)
    except Exception:
        pass
    return obj


def open_light_properties():
    from . import light_ui
    light_ui.open_panel()


def add_distant_light():
    return add_light("distant")


class _Cmd(object):
    def __init__(self, icon, text, tip, action, needs_doc=True):
        self._icon, self._text, self._tip, self._action, self._needs_doc = icon, text, tip, action, needs_doc

    def GetResources(self):
        return {"Pixmap": _icon(self._icon), "MenuText": _tr(self._text), "ToolTip": _tr(self._tip)}

    def Activated(self):
        import FreeCAD
        try:
            self._action()
        except Exception:
            import traceback
            FreeCAD.Console.PrintError(_tr("RayTrace hatası:\n") + traceback.format_exc())

    def IsActive(self):
        return _doc_ready() if self._needs_doc else True


def _commands():
    return {
        "YBT_Render": _Cmd("icon.png", "YBT Raytracer", "Render ayar panelini açar (Render düğmesiyle görüntü alınır)", open_panel),
        "YBT_NewScene": _Cmd("scene.svg", "YBT Yeni Sahne", "Ağaçta yeni bir YBT sahnesi (YBTray01...) yaratır; ışıklar bunun altına eklenir", new_scene),
        "YBT_DistantLight": _Cmd("distant_light.svg", "YBT Distant Light", "Sahneye güneş tipi (paralel) ışık ekler", add_distant_light),
        "YBT_LightProperties": _Cmd("light_props.svg", "YBT Işık Özellikleri", "Işık nesnelerinin özelliklerini düzenler (renk, şiddet, gölge)", open_light_properties),
        "YBT_Materials": _Cmd("materials.svg", "YBT Malzemeler", "Malzemeler (Surface) penceresini açar", open_materials),
        "YBT_Options": _Cmd("options.svg", "YBT Seçenekler", "İçerik klasörü ve varsayılan ayarlar", open_options),
    }


class _Manipulator(object):
    """Komutları her tezgâhın Macro araç çubuğuna ve Macro menüsüne ekler (FreeCAD 1.0+)."""

    def modifyToolBars(self):
        return [{"append": c, "toolBar": "Macro"} for c in COMMANDS]

    def modifyMenuBar(self):
        return [{"append": c, "menuItem": "Std_DlgMacroExecute"} for c in COMMANDS]


def separate_workbench_enabled():
    """Ayrı "YBT Raytracer" tezgâhı: kullanıcı parametresi 'SeparateWorkbench' (varsayılan AÇIK; kapatmak için false).
    FreeCAD'de manipulator yoksa (0.21) tezgâh zorunlu açık."""
    try:
        import FreeCAD
        import FreeCADGui as Gui
        if not hasattr(Gui, "addWorkbenchManipulator"):
            return True
        return bool(FreeCAD.ParamGet(_PARAM).GetBool("SeparateWorkbench", True))
    except Exception:
        return True


def global_toolbar_enabled():
    """Macro araç çubuğu / menüsüne ekleme: kullanıcı parametresi 'ShowInAllWorkbenches' (varsayılan açık)."""
    try:
        import FreeCAD
        return bool(FreeCAD.ParamGet(_PARAM).GetBool("ShowInAllWorkbenches", True))
    except Exception:
        return True


def register():
    """Komutları kaydeder, istenirse her tezgâha ekler. Tekrar çağrılırsa bir şey yapmaz."""
    if _state["registered"]:
        return
    import FreeCAD
    import FreeCADGui as Gui
    from .i18n import init_lang
    init_lang()
    for name, cmd in _commands().items():
        Gui.addCommand(name, cmd)
    _state["registered"] = True
    try:
        from . import viewlight
        viewlight.start()                                 # görünümde ışık önizlemesi (YBT sahnesi olan belgede)
    except Exception:
        pass
    if global_toolbar_enabled() and hasattr(Gui, "addWorkbenchManipulator"):
        try:
            Gui.addWorkbenchManipulator(_Manipulator())
            _state["manipulator"] = True
        except Exception as ex:
            FreeCAD.Console.PrintWarning("YBT Raytracer: workbench manipulator: %s\n" % ex)
