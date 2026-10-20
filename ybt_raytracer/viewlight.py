# -*- coding: utf-8 -*-
"""3B görünümde ışık önizlemesi: belgede YBT sahnesi varsa FreeCAD'in kendi ışıkları (Headlight / Backlight / FillLight) kapanır,
ortam ışığı bizim ortam değerimizi izler ve etkin sahnenin ışık nesneleri görünüme Coin yönlü ışığı olarak eklenir.

FreeCAD'in ışık ayarları Tercihler > Display > Light Sources ile aynı parametre grubundadır (View/LightSources); bu ayarlar tüm FreeCAD için
geçerlidir, bu yüzden değişmeden önceki değerler `ViewLightBackup` parametresine saklanır ve şu durumlarda geri yazılır: önizleme kapanınca
(YBT sahnesi olmayan belgeye geçilince ya da ışık modu değişince), FreeCAD kapanırken ve (çökme sonrası) bir sonraki açılışta.
Görünüm Coin aydınlatmasıdır: yön, renk ve şiddet yaklaşık görünür; gölge ve yumuşaklık yalnız render'da.
"""
import json

from . import settings as S

_PARAM_VIEW = "User parameter:BaseApp/Preferences/View/LightSources"
_PARAM_MOD = "User parameter:BaseApp/Preferences/Mod/FCYBTRayTracer"
_ENABLE = ("EnableHeadlight", "EnableBacklight", "EnableFillLight")
_AMB_I, _AMB_C = "AmbientLightIntensity", "AmbientLightColor"
_NAME = "YBTViewLights"
_st = {"active": False, "timer": None, "sg": None, "sep": None, "sig": None, "amb": None}


def _grp(path):
    import FreeCAD
    return FreeCAD.ParamGet(path)


def _backup_get():
    try:
        raw = _grp(_PARAM_MOD).GetString("ViewLightBackup", "")
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _save_state():
    g = _grp(_PARAM_VIEW)
    have = {c[1] for c in (g.GetContents() or [])}
    bk = {}
    for k in _ENABLE:
        bk[k] = g.GetBool(k, True) if k in have else None
    bk[_AMB_I] = g.GetInt(_AMB_I, 12) if _AMB_I in have else None
    bk[_AMB_C] = g.GetUnsigned(_AMB_C, 0xFFFFFFFF) if _AMB_C in have else None
    _grp(_PARAM_MOD).SetString("ViewLightBackup", json.dumps(bk))
    return bk


def _restore(bk):
    g = _grp(_PARAM_VIEW)
    for k, v in bk.items():
        try:
            if v is None:                                   # önceden hiç yazılı değildi: kaldır (FreeCAD varsayılanına dönsün)
                for rem in ("RemBool", "RemInt", "RemUnsigned"):
                    try:
                        getattr(g, rem)(k)
                    except Exception:
                        pass
            elif k in _ENABLE:
                g.SetBool(k, bool(v))
            elif k == _AMB_I:
                g.SetInt(k, int(v))
            else:
                g.SetUnsigned(k, int(v))
        except Exception:
            pass
    try:
        _grp(_PARAM_MOD).SetString("ViewLightBackup", "")
    except Exception:
        pass


def recover():
    """Önceki oturum önizleme açıkken kapandıysa (çökme) FreeCAD'in ışık ayarlarını geri yazar."""
    bk = _backup_get()
    if bk:
        _restore(bk)
        _st["active"] = False


def _pack(rgb):
    r, g, b = [int(round(max(0.0, min(1.0, c)) * 255)) for c in tuple(rgb)[:3]]
    return (r << 24) | (g << 16) | (b << 8) | 255


def _ambient():
    return int(round(float(S.AMBIENT) * 100)), _pack(S.AMBIENT_COLOR)


def _sync_ambient():
    key = _ambient()
    if key == _st["amb"]:
        return
    g = _grp(_PARAM_VIEW)
    g.SetInt(_AMB_I, key[0])
    g.SetUnsigned(_AMB_C, key[1])
    _st["amb"] = key


def _activate():
    _save_state()
    g = _grp(_PARAM_VIEW)
    for k in _ENABLE:
        g.SetBool(k, False)
    _st["amb"] = None
    _sync_ambient()
    _st["active"] = True


def _remove_nodes():
    sg, sep = _st["sg"], _st["sep"]
    if sg is not None and sep is not None:
        try:
            sg.removeChild(sep)
        except Exception:
            pass
    _st["sg"] = _st["sep"] = _st["sig"] = None


def _deactivate():
    _remove_nodes()
    bk = _backup_get()
    if bk:
        _restore(bk)
    _st["active"] = False
    _st["amb"] = None


def _desired():
    import FreeCAD
    import FreeCADGui as Gui
    from . import sceneobj
    if not bool(getattr(S, "VIEW_LIGHTS", True)) or str(S.LIGHT_MODE) != "objects":
        return False
    doc = FreeCAD.ActiveDocument
    if doc is None or Gui.ActiveDocument is None or getattr(Gui.ActiveDocument, "ActiveView", None) is None:
        return False
    return sceneobj.active_scene(doc) is not None


def _sync_nodes():
    import FreeCAD
    import FreeCADGui as Gui
    from pivy import coin
    from . import lightobj
    sg = Gui.ActiveDocument.ActiveView.getSceneGraph()
    lst = lightobj.collect(FreeCAD.ActiveDocument)[:6]
    sig = tuple((tuple(round(x, 4) for x in lt["wdir"]), tuple(round(x, 3) for x in lt["color"]), round(lt["power"], 3)) for lt in lst
                if lt.get("diffuse", True))
    if sg is not _st["sg"]:
        _remove_nodes()
        sep = coin.SoSeparator()
        sep.setName(_NAME)
        sg.insertChild(sep, 0)
        _st["sg"], _st["sep"], _st["sig"] = sg, sep, None
    if sig == _st["sig"]:
        return
    sep = _st["sep"]
    sep.removeAllChildren()
    for wdir, col, power in sig:
        li = coin.SoDirectionalLight()
        li.direction.setValue(-wdir[0], -wdir[1], -wdir[2])       # Coin: ışığın gittiği yön (wdir ışığa doğru)
        li.color.setValue(*col)
        li.intensity.setValue(min(1.0, max(0.0, power)))
        sep.addChild(li)
    _st["sig"] = sig


def tick():
    try:
        want = _desired()
        if want and not _st["active"]:
            _activate()
        elif not want and _st["active"]:
            _deactivate()
        if _st["active"]:
            _sync_ambient()
            _sync_nodes()
    except Exception:
        pass


def shutdown(*_a):
    try:
        if _st["active"]:
            _deactivate()
    except Exception:
        pass


def start():
    """Eklenti açılışında bir kez: çökme kurtarma + yoklama zamanlayıcısı (500 ms; yalnız hafif denetim yapar)."""
    if _st["timer"] is not None:
        return
    try:
        recover()
        import FreeCADGui as Gui
        from PySide import QtCore, QtGui
        mw = Gui.getMainWindow()
        t = QtCore.QTimer(mw)
        t.setInterval(500)
        t.timeout.connect(tick)
        t.start()
        _st["timer"] = t
        QtGui.QApplication.instance().aboutToQuit.connect(shutdown)
    except Exception:
        pass
