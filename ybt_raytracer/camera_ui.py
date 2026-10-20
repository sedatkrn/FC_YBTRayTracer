# -*- coding: utf-8 -*-
"""Kamera Özellikleri paneli: sahnedeki kamera nesnelerini tek pencerede düzenler (Işık Özellikleri paneliyle aynı düzen).

Açılış: araç çubuğundaki "YBT Kamera Özellikleri", kamera nesnesine çift tıklama ya da yeni kamera eklenince.
Panel kalıcıdır (modal değil); değişiklikler doğrudan nesnenin özelliklerine yazılır (Özellik düzenleyicisiyle aynı değerler).
"""
import math

import FreeCAD

from .i18n import T
from . import cameraobj as C
from . import theme as _theme

_KEY = "_ybt_camera_dlg"
ASPECTS = (("16:9", 16.0 / 9.0), ("21:9", 21.0 / 9.0), ("2:1", 2.0), ("3:2", 1.5), ("4:3", 4.0 / 3.0), ("1:1", 1.0),
           ("3:4", 3.0 / 4.0), ("2:3", 2.0 / 3.0), ("9:16", 9.0 / 16.0))
LENSES = (14, 24, 35, 50, 85, 135, 200)


def _qt():
    from PySide import QtCore, QtGui
    return QtCore, QtGui


def _doc():
    return FreeCAD.ActiveDocument


def open_panel(select=None):
    """Paneli açar (açıksa öne getirir); `select` verilirse o kamera seçilir."""
    QtCore, QtGui = _qt()
    dlg = getattr(FreeCAD, _KEY, None)
    try:
        if dlg is not None and dlg.isVisible():
            dlg.raise_()
            dlg.activateWindow()
            if select is not None:
                dlg._api["select"](select)
            return dlg
    except Exception:
        pass
    dlg = _build(QtCore, QtGui)
    setattr(FreeCAD, _KEY, dlg)
    dlg.show()
    if select is not None:
        dlg._api["select"](select)
    return dlg


def _build(QtCore, QtGui):
    dlg = QtGui.QDialog(None)
    dlg.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowMinimizeButtonHint | QtCore.Qt.WindowCloseButtonHint)
    dlg.setWindowTitle(T("Kamera Özellikleri"))
    _theme.apply(dlg)
    dlg.setMinimumWidth(400)
    st = {"obj": None, "busy": False, "snap": None, "names": None}

    root = QtGui.QVBoxLayout(dlg)
    top = QtGui.QHBoxLayout()
    b_new = QtGui.QPushButton(T("Yeni kamera"))
    b_new.setToolTip(T("Sahneye 3B görünümün bakışıyla kamera ekler"))
    b_del = QtGui.QPushButton(T("Kamerayı sil"))
    lb_count = QtGui.QLabel("")
    lb_count.setStyleSheet("padding: 4px 8px; background-color: #3b3b3f; border-radius: 3px;")
    top.addWidget(b_new)
    top.addWidget(b_del)
    top.addWidget(lb_count, 1)
    root.addLayout(top)

    form = QtGui.QGridLayout()
    form.setColumnStretch(1, 1)

    def lab(t):
        q = QtGui.QLabel(T(t))
        q.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        return q

    def dspin(lo, hi, dec=1, step=1.0, suffix=""):
        s = QtGui.QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setDecimals(dec)
        s.setSingleStep(step)
        if suffix:
            s.setSuffix(suffix)
        return s

    cb_cur = QtGui.QComboBox()
    ck_act = QtGui.QCheckBox(T("Etkin"))
    ck_act.setToolTip(T("Etkin kameradan render alınır (sahnede tek etkin kamera olur). Hiçbiri etkin değilse render 3B görünümden alınır"))
    form.addWidget(lab("Geçerli kamera"), 0, 0)
    form.addWidget(cb_cur, 0, 1)
    form.addWidget(ck_act, 0, 2)
    cb_proj = QtGui.QComboBox()
    cb_proj.addItem(T("Perspektif"), "Perspective")
    cb_proj.addItem(T("Ortografik"), "Orthographic")
    form.addWidget(lab("Projeksiyon"), 1, 0)
    form.addWidget(cb_proj, 1, 1, 1, 2)
    cb_asp = QtGui.QComboBox()
    for n, v in ASPECTS:
        cb_asp.addItem(n, v)
    cb_asp.addItem(T("Özel"), -1.0)
    sp_asp = dspin(0.1, 10.0, 3, 0.05)
    sp_asp.setToolTip(T("Kadraj oranı (en / boy)"))
    arow = QtGui.QHBoxLayout()
    arow.addWidget(cb_asp, 1)
    arow.addWidget(sp_asp, 1)
    form.addWidget(lab("Kadraj oranı"), 2, 0)
    form.addLayout(arow, 2, 1, 1, 2)
    root.addLayout(form)

    tabs = QtGui.QTabWidget()
    pg_lens, pg_dof = QtGui.QWidget(), QtGui.QWidget()
    tabs.addTab(pg_lens, T("Lens"))
    tabs.addTab(pg_dof, T("Alan derinliği"))
    ll = QtGui.QGridLayout(pg_lens)
    sp_focal = dspin(1.0, 2000.0, 1, 5.0, " mm")
    sp_focal.setToolTip(T("Odak uzaklığı: küçük = geniş açı, büyük = yakınlaştırma"))
    cb_lens = QtGui.QComboBox()
    cb_lens.addItem(T("Hazır..."), 0)
    for f in LENSES:
        cb_lens.addItem("%d mm" % f, f)
    sp_sensor = dspin(1.0, 200.0, 1, 1.0, " mm")
    sp_sensor.setToolTip(T("Sensör genişliği (36 mm = tam kare)"))
    lb_fov = QtGui.QLabel("")
    lb_fov.setStyleSheet("color: #85858a;")
    sp_ortho = dspin(1.0, 1000000.0, 1, 50.0, " mm")
    sp_ortho.setToolTip(T("Ortografik kamerada görüntünün yatay genişliği"))
    lb_focal, lb_lens, lb_sensor = lab("Odak uzaklığı"), lab("Hazır lens"), lab("Sensör genişliği")
    lb_ortho = lab("Görüntü genişliği")
    ll.addWidget(lb_focal, 0, 0)
    ll.addWidget(sp_focal, 0, 1)
    ll.addWidget(lb_lens, 1, 0)
    ll.addWidget(cb_lens, 1, 1)
    ll.addWidget(lb_sensor, 2, 0)
    ll.addWidget(sp_sensor, 2, 1)
    ll.addWidget(lb_fov, 3, 0, 1, 2)
    ll.addWidget(lb_ortho, 4, 0)
    ll.addWidget(sp_ortho, 4, 1)
    ll.setRowStretch(5, 1)

    dl = QtGui.QGridLayout(pg_dof)
    ck_dof = QtGui.QCheckBox(T("Alan derinliği (bulanıklık) açık"))
    ck_dof.setToolTip(T("Yalnız perspektif kamerada çalışır"))
    cb_fobj = QtGui.QComboBox()
    b_pick = QtGui.QPushButton(T("Seçili nesneye odakla"))
    b_pick.setToolTip(T("Ağaçta seçili nesneyi odak nesnesi yapar"))
    sp_focus = dspin(1.0, 10000000.0, 1, 100.0, " mm")
    sp_focus.setToolTip(T("Odak mesafesi: kameradan bu uzaklıktaki şeyler keskin olur. Odak nesnesi seçiliyse o kullanılır"))
    sp_fstop = dspin(0.7, 64.0, 1, 0.2)
    sp_fstop.setToolTip(T("Diyafram sayısı: küçük sayı (1.4-2.8) çok bulanıklık, büyük sayı (11+) az bulanıklık"))
    lb_dfocus, lb_fobj, lb_fstop = lab("Odak mesafesi"), lab("Odak nesnesi"), lab("Diyafram (f/)")
    dl.addWidget(ck_dof, 0, 0, 1, 2)
    dl.addWidget(lb_fobj, 1, 0)
    dl.addWidget(cb_fobj, 1, 1)
    dl.addWidget(b_pick, 2, 1)
    dl.addWidget(lb_dfocus, 3, 0)
    dl.addWidget(sp_focus, 3, 1)
    dl.addWidget(lb_fstop, 4, 0)
    dl.addWidget(sp_fstop, 4, 1)
    dl.setRowStretch(5, 1)
    root.addWidget(tabs)

    brow = QtGui.QHBoxLayout()
    b_look = QtGui.QPushButton(T("Kameradan bak"))
    b_look.setToolTip(T("3B görünümü bu kameranın bakışına getirir"))
    b_upd = QtGui.QPushButton(T("Görünümü kameraya aktar"))
    b_upd.setToolTip(T("Kamerayı şu anki 3B görünümle aynı yapar (konum, yön, görüş açısı)"))
    brow.addWidget(b_look)
    brow.addWidget(b_upd)
    root.addLayout(brow)
    hint = QtGui.QLabel(T("Konum ve yön: kamera nesnesinin Yerleşim (Placement) özelliği. Kamera yerel -Z yönüne bakar."))
    hint.setWordWrap(True)
    hint.setStyleSheet("color: #85858a;")
    root.addWidget(hint)

    inputs = [cb_cur, ck_act, cb_proj, cb_asp, sp_asp, sp_focal, cb_lens, sp_sensor, sp_ortho, ck_dof, cb_fobj, b_pick,
              sp_focus, sp_fstop, b_look, b_upd, b_del]

    def alive():
        o = st["obj"]
        try:
            return o is not None and o.Document is not None and o in o.Document.Objects
        except Exception:
            return False

    def val(o, name, default=0.0):
        try:
            v = getattr(o, name)
            return float(getattr(v, "Value", v))
        except Exception:
            return default

    def snapshot(o):
        try:
            fo = getattr(o, "FocusObject", None)
            return (bool(o.Active), str(o.Projection), val(o, "FocalLength"), val(o, "SensorWidth"), val(o, "OrthoWidth"), val(o, "Aspect"),
                    bool(o.DepthOfField), val(o, "FocusDistance"), val(o, "FStop"), fo.Name if fo is not None else "")
        except Exception:
            return None

    def fov_text(o):
        try:
            asp = C.frame_aspect(o)
            if str(o.Projection) == "Orthographic":
                return ""
            hx = C.half_extent_x(o)
            h = math.degrees(2.0 * math.atan(hx))
            v = math.degrees(2.0 * math.atan(hx / asp))
            return T("Görüş açısı: yatay %.1f°, dikey %.1f°") % (h, v)
        except Exception:
            return ""

    def show_for(persp):
        for w in (lb_focal, sp_focal, lb_lens, cb_lens, lb_sensor, sp_sensor, lb_fov):
            w.setVisible(persp)
        for w in (lb_ortho, sp_ortho):
            w.setVisible(not persp)
        tabs.setTabEnabled(tabs.indexOf(pg_dof), persp)
        if not persp and tabs.currentWidget() is pg_dof:
            tabs.setCurrentIndex(0)

    def fill_fobj(o):
        d = o.Document
        cb_fobj.clear()
        cb_fobj.addItem(T("(Yok - mesafe)"), "")
        from . import lightobj
        for ob in d.Objects:
            try:
                if getattr(ob, "Shape", None) is None or ob.Shape.isNull() or lightobj._is_light(ob) or C.is_camera(ob):
                    continue
                if not ob.Shape.BoundBox.isValid():
                    continue
            except Exception:
                continue
            cb_fobj.addItem(ob.Label, ob.Name)

    def load():
        o = st["obj"]
        has = alive()
        for w in inputs:
            w.setEnabled(has)
        if not has:
            return
        st["busy"] = True
        try:
            ck_act.setChecked(bool(o.Active))
            k = cb_proj.findData(str(o.Projection))
            if k >= 0:
                cb_proj.setCurrentIndex(k)
            show_for(str(o.Projection) != "Orthographic")
            asp = val(o, "Aspect", 16 / 9.0)
            sp_asp.setValue(asp)
            idx = -1
            for i in range(cb_asp.count() - 1):
                if abs(cb_asp.itemData(i) - asp) < 1e-3:
                    idx = i
                    break
            cb_asp.setCurrentIndex(idx if idx >= 0 else cb_asp.count() - 1)
            sp_asp.setVisible(idx < 0)
            sp_focal.setValue(val(o, "FocalLength", 50.0))
            cb_lens.setCurrentIndex(0)
            sp_sensor.setValue(val(o, "SensorWidth", 36.0))
            sp_ortho.setValue(val(o, "OrthoWidth", 1000.0))
            lb_fov.setText(fov_text(o))
            ck_dof.setChecked(bool(o.DepthOfField))
            fill_fobj(o)
            fo = getattr(o, "FocusObject", None)
            k2 = cb_fobj.findData(fo.Name if fo is not None else "")
            cb_fobj.setCurrentIndex(max(0, k2))
            sp_focus.setValue(val(o, "FocusDistance", 3000.0))
            sp_focus.setEnabled(fo is None)
            sp_fstop.setValue(val(o, "FStop", 4.0))
            st["snap"] = snapshot(o)
        finally:
            st["busy"] = False

    def refill(keep=None):
        d = _doc()
        objs = C.scene_cameras(d) if d is not None else []
        names = [(o.Name, o.Label) for o in objs]
        keep = keep or (st["obj"].Name if alive() else None)
        st["busy"] = True
        try:
            cb_cur.clear()
            for o in objs:
                cb_cur.addItem(o.Label + (" *" if o.Active else ""), o.Name)
            k = cb_cur.findData(keep) if keep else -1
            if k < 0 and objs:
                k = 0
            if k >= 0:
                cb_cur.setCurrentIndex(k)
                st["obj"] = d.getObject(cb_cur.itemData(k))
            else:
                st["obj"] = None
        finally:
            st["busy"] = False
        st["names"] = names
        lb_count.setText(T("Sahnedeki kameralar: %d") % len(objs))
        load()

    def on_cur(i):
        if st["busy"]:
            return
        d = _doc()
        name = cb_cur.itemData(i)
        st["obj"] = d.getObject(name) if (d is not None and name) else None
        load()
        try:
            import FreeCADGui as Gui
            if st["obj"] is not None:
                Gui.Selection.clearSelection()
                Gui.Selection.addSelection(st["obj"])
        except Exception:
            pass
    cb_cur.currentIndexChanged.connect(on_cur)

    def put(name, value, reload=False):
        if st["busy"] or not alive():
            return
        o = st["obj"]
        try:
            setattr(o, name, value)
            st["snap"] = snapshot(o)
            lb_fov.setText(fov_text(o))
            if reload:
                load()
        except Exception as ex:
            FreeCAD.Console.PrintWarning("YBT camera: %s\n" % ex)

    ck_act.toggled.connect(lambda v: (put("Active", bool(v)), refill()))
    cb_proj.currentIndexChanged.connect(lambda i: put("Projection", str(cb_proj.itemData(i)), True))
    ck_dof.toggled.connect(lambda v: put("DepthOfField", bool(v)))
    sp_focal.valueChanged.connect(lambda v: put("FocalLength", float(v)))
    sp_sensor.valueChanged.connect(lambda v: put("SensorWidth", float(v)))
    sp_ortho.valueChanged.connect(lambda v: put("OrthoWidth", float(v)))
    sp_focus.valueChanged.connect(lambda v: put("FocusDistance", float(v)))
    sp_fstop.valueChanged.connect(lambda v: put("FStop", float(v)))
    sp_asp.valueChanged.connect(lambda v: put("Aspect", float(v)))

    def asp_changed(i):
        if st["busy"] or not alive():
            return
        v = cb_asp.itemData(i)
        if v is not None and v > 0:
            put("Aspect", float(v), True)
        else:
            sp_asp.setVisible(True)
    cb_asp.currentIndexChanged.connect(asp_changed)

    def lens_changed(i):
        v = cb_lens.itemData(i)
        if v and not st["busy"]:
            put("FocalLength", float(v), True)
    cb_lens.currentIndexChanged.connect(lens_changed)

    def fobj_changed(i):
        if st["busy"] or not alive():
            return
        name = cb_fobj.itemData(i)
        d = st["obj"].Document
        put("FocusObject", d.getObject(name) if name else None, True)
    cb_fobj.currentIndexChanged.connect(fobj_changed)

    def pick_selected():
        if not alive():
            return
        try:
            import FreeCADGui as Gui
            for ob in Gui.Selection.getSelection():
                if getattr(ob, "Shape", None) is not None and not C.is_camera(ob):
                    put("FocusObject", ob, True)
                    return
        except Exception:
            pass
        QtGui.QMessageBox.information(dlg, T("Kamera Özellikleri"), T("Önce ağaçta ya da 3B görünümde odaklanılacak nesneyi seçin."))
    b_pick.clicked.connect(pick_selected)

    def new_cam():
        from . import commands
        o = commands.add_camera()
        refill(o.Name if o is not None else None)
    b_new.clicked.connect(new_cam)

    def del_cam():
        if not alive():
            return
        o = st["obj"]
        d = o.Document
        d.openTransaction("Delete camera")
        try:
            d.removeObject(o.Name)
        finally:
            d.commitTransaction()
        d.recompute()
        refill()
    b_del.clicked.connect(del_cam)

    b_look.clicked.connect(lambda: alive() and C.look_through(st["obj"]))

    def upd():
        if not alive():
            return
        o = st["obj"]
        d = o.Document
        d.openTransaction("Update camera from view")
        try:
            C.update_from_view(o)
        finally:
            d.commitTransaction()
        d.recompute()
        load()
    b_upd.clicked.connect(upd)

    def tick():
        d = _doc()
        objs = C.scene_cameras(d) if d is not None else []
        names = [(o.Name, o.Label) for o in objs]
        if names != st["names"]:
            refill()
        elif alive():
            sn = snapshot(st["obj"])
            if sn != st["snap"] and not any(w.hasFocus() for w in inputs):
                load()
        try:
            import FreeCADGui as Gui
            sel = [o for o in Gui.Selection.getSelection() if C.is_camera(o)]
            if len(sel) == 1 and sel[0] is not st["obj"] and sel[0].Document is d and not dlg.isActiveWindow():
                refill(sel[0].Name)
        except Exception:
            pass
    timer = QtCore.QTimer(dlg)
    timer.setInterval(400)
    timer.timeout.connect(tick)
    timer.start()

    def select(obj):
        refill(obj.Name)

    def on_close(*_a):
        timer.stop()
        if getattr(FreeCAD, _KEY, None) is dlg:
            setattr(FreeCAD, _KEY, None)
    dlg.finished.connect(on_close)
    dlg.destroyed.connect(on_close)
    dlg._api = dict(select=select, refill=refill, widgets=dict(
        current=cb_cur, active=ck_act, projection=cb_proj, aspect_combo=cb_asp, aspect=sp_asp, focal=sp_focal, lens=cb_lens, sensor=sp_sensor,
        ortho=sp_ortho, dof=ck_dof, focus_obj=cb_fobj, focus=sp_focus, fstop=sp_fstop, tabs=tabs, fov=lb_fov, new=b_new, delete=b_del,
        look=b_look, update=b_upd, pick=b_pick, count=lb_count))
    _theme.fix_combos(dlg)
    refill()
    return dlg
