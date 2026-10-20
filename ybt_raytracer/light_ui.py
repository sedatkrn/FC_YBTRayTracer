# -*- coding: utf-8 -*-
"""Işık Özellikleri paneli (LightWave "Light Properties" tarzı): sahnedeki ışık nesnelerini tek pencerede düzenler.

Açılış: araç çubuğundaki "YBT Işık Özellikleri", ışık nesnesine çift tıklama ya da yeni ışık eklenince.
Panel kalıcıdır (modal değil): FreeCAD'de ışık seçilince panel o ışığa geçer, panelden yapılan değişiklik nesnenin özelliğine yazılır
(Özellik düzenleyicisiyle aynı değerler; ikisi birbirini yansıtır).
"""
import FreeCAD

from .i18n import T
from . import lightobj as L
from . import theme as _theme
from . import settings as S

_KEY = "_ybt_light_dlg"


def _qt():
    from PySide import QtCore, QtGui
    return QtCore, QtGui


def _doc():
    return FreeCAD.ActiveDocument


def open_panel(select=None):
    """Paneli açar (açıksa öne getirir); `select` verilirse o ışık nesnesi seçilir. Paneli döndürür."""
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
    dlg.setWindowTitle(T("Işık Özellikleri"))
    _theme.apply(dlg)
    dlg.setMinimumWidth(380)
    st = {"obj": None, "busy": False, "snap": None, "names": None}

    root = QtGui.QVBoxLayout(dlg)
    top = QtGui.QHBoxLayout()
    b_clear = QtGui.QPushButton(T("Tüm ışıkları sil"))
    b_clear.setToolTip(T("Belgedeki tüm ışık nesnelerini siler (Geri Al ile geri gelir)"))
    lb_count = QtGui.QLabel("")
    lb_count.setStyleSheet("padding: 4px 8px; background-color: #3b3b3f; border-radius: 3px;")
    top.addWidget(b_clear)
    top.addWidget(lb_count, 1)
    root.addLayout(top)

    form = QtGui.QGridLayout()
    form.setColumnStretch(1, 1)

    def lab(t):
        q = QtGui.QLabel(T(t))
        q.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        return q

    cb_cur = QtGui.QComboBox()
    ck_on = QtGui.QCheckBox(T("Açık"))
    ck_on.setToolTip(T("Işığı aç / kapat"))
    form.addWidget(lab("Geçerli ışık"), 0, 0)
    form.addWidget(cb_cur, 0, 1)
    form.addWidget(ck_on, 0, 2)
    cb_type = QtGui.QComboBox()
    for k, v in L.TYPES.items():
        cb_type.addItem(T(v["label"]), k)
    cb_type.setToolTip(T("Işık türü; değiştirince türe özgü ayarlar eklenir / kalkar"))
    form.addWidget(lab("Işık türü"), 1, 0)
    form.addWidget(cb_type, 1, 1, 1, 2)
    # renk: düğme + R G B
    bt_col = QtGui.QPushButton("")
    bt_col.setFixedWidth(44)
    bt_col.setToolTip(T("Işık rengi"))
    sp_rgb = []
    crow = QtGui.QHBoxLayout()
    crow.addWidget(bt_col)
    for nm in "RGB":
        s = QtGui.QSpinBox()
        s.setRange(0, 255)
        s.setPrefix(nm + " ")
        sp_rgb.append(s)
        crow.addWidget(s, 1)
    form.addWidget(lab("Işık rengi"), 2, 0)
    form.addLayout(crow, 2, 1, 1, 2)
    sp_int = QtGui.QDoubleSpinBox()
    sp_int.setRange(0.0, 10000.0)
    sp_int.setDecimals(1)
    sp_int.setSingleStep(5.0)
    sp_int.setSuffix(" %")
    sp_int.setToolTip(T("Işık şiddeti. %100 = ışığa dik beyaz yüzeyi tam aydınlatır"))
    form.addWidget(lab("Işık şiddeti"), 3, 0)
    form.addWidget(sp_int, 3, 1, 1, 2)
    root.addLayout(form)

    tabs = QtGui.QTabWidget()
    pg_basic, pg_shadow = QtGui.QWidget(), QtGui.QWidget()
    tabs.addTab(pg_basic, T("Temel"))
    tabs.addTab(pg_shadow, T("Gölgeler"))
    bl = QtGui.QVBoxLayout(pg_basic)
    ck_dif = QtGui.QCheckBox(T("Yüzey rengini aydınlat (Diffuse)"))
    ck_spc = QtGui.QCheckBox(T("Parlama versin (Specular)"))
    ck_dif.setToolTip(T("Kapalıyken ışık yüzeyleri aydınlatmaz, yalnız parlama bırakır"))
    ck_spc.setToolTip(T("Kapalıyken ışık parlama/vurgu bırakmaz"))
    bl.addWidget(ck_dif)
    bl.addWidget(ck_spc)
    bl.addStretch(1)
    sl = QtGui.QGridLayout(pg_shadow)
    ck_sh = QtGui.QCheckBox(T("Gölge düşür"))
    sp_soft = QtGui.QDoubleSpinBox()
    sp_soft.setRange(0.0, 30.0)
    sp_soft.setDecimals(2)
    sp_soft.setSingleStep(0.25)
    sp_soft.setSuffix(" °")
    sp_soft.setToolTip(T("Gölge yumuşaklığı: ışığın görünür açısı (güneş ~0,5°; 0 = sert gölge)"))
    sl.addWidget(ck_sh, 0, 0, 1, 2)
    lb_soft = lab("Yumuşaklık (açı)")
    sl.addWidget(lb_soft, 1, 0)
    sl.addWidget(sp_soft, 1, 1)
    sp_rad = QtGui.QDoubleSpinBox()
    sp_rad.setRange(0.0, 100000.0)
    sp_rad.setDecimals(1)
    sp_rad.setSingleStep(5.0)
    sp_rad.setSuffix(" mm")
    sp_rad.setToolTip(T("Işık kaynağının boyu: büyüdükçe gölge kenarı yumuşar (0 = sert gölge)"))
    lb_rad = lab("Işık boyu (yarıçap)")
    sl.addWidget(lb_rad, 2, 0)
    sl.addWidget(sp_rad, 2, 1)
    sl.setRowStretch(3, 1)
    # Falloff sekmesi (Point / Spot)
    pg_fall = QtGui.QWidget()
    fl = QtGui.QGridLayout(pg_fall)
    cb_fall = QtGui.QComboBox()
    for key, txt in (("InverseSquare", "Ters kare (gerçekçi)"), ("Linear", "Doğrusal"), ("None", "Yok (sönmez)")):
        cb_fall.addItem(T(txt), key)
    sp_ref = QtGui.QDoubleSpinBox()
    sp_ref.setRange(0.0, 1000000.0)
    sp_ref.setSpecialValueText(T("Otomatik"))
    sp_ref.setDecimals(1)
    sp_ref.setSingleStep(50.0)
    sp_ref.setSuffix(" mm")
    sp_ref.setToolTip(T("Işığın şiddetinin tam değerinde olduğu uzaklık. Daha yakında parlar, daha uzakta söner. Otomatik (0) = ışığın sahne merkezine uzaklığı"))
    sp_cone = QtGui.QDoubleSpinBox()
    sp_cone.setRange(1.0, 178.0)
    sp_cone.setDecimals(1)
    sp_cone.setSuffix(" °")
    sp_cone.setToolTip(T("Spot koninin tam açısı"))
    sp_edge = QtGui.QDoubleSpinBox()
    sp_edge.setRange(0.0, 90.0)
    sp_edge.setDecimals(1)
    sp_edge.setSuffix(" °")
    sp_edge.setToolTip(T("Koninin kenarındaki yumuşak geçiş (0 = keskin kenar)"))
    lb_cone, lb_edge = lab("Koni açısı"), lab("Kenar yumuşaklığı")
    fl.addWidget(lab("Sönme"), 0, 0)
    fl.addWidget(cb_fall, 0, 1)
    fl.addWidget(lab("Referans uzaklık"), 1, 0)
    fl.addWidget(sp_ref, 1, 1)
    fl.addWidget(lb_cone, 2, 0)
    fl.addWidget(sp_cone, 2, 1)
    fl.addWidget(lb_edge, 3, 0)
    fl.addWidget(sp_edge, 3, 1)
    fl.setRowStretch(4, 1)
    tabs.addTab(pg_fall, T("Sönme / Koni"))
    root.addWidget(tabs)
    ck_view = QtGui.QCheckBox(T("3B görünümü bu ışıklarla aydınlat"))
    ck_view.setToolTip(T("Açıkken YBT sahnesi olan belgelerde FreeCAD'in kendi görünüm ışıkları kapanır ve ışık nesneleri 3B görünümde önizlenir "
                         "(gölge ve yumuşaklık yalnız render'da). Kapanınca FreeCAD'in ayarları geri gelir."))
    ck_view.setChecked(bool(getattr(S, "VIEW_LIGHTS", True)))
    ck_view.toggled.connect(lambda v: setattr(S, "VIEW_LIGHTS", bool(v)))
    root.addWidget(ck_view)
    hint = QtGui.QLabel(T("Konum ve yön: ışık nesnesinin Yerleşim (Placement) özelliği. Işık yerel -Z yönüne yayılır (Point ışıkta yön önemsizdir)."))
    hint.setWordWrap(True)
    hint.setStyleSheet("color: #85858a;")
    root.addWidget(hint)

    inputs = [cb_type, ck_on, bt_col, sp_int, ck_dif, ck_spc, ck_sh, sp_soft, sp_rad, cb_fall, sp_ref, sp_cone, sp_edge] + sp_rgb

    def paint_color(rgb):
        bt_col.setStyleSheet("background-color: rgb(%d,%d,%d); border: 1px solid #26262a;" % tuple(rgb))

    def alive():
        o = st["obj"]
        try:
            return o is not None and o.Document is not None and o in o.Document.Objects
        except Exception:
            return False

    def kind_of(o):
        return getattr(o, L.PROP_TYPE, "distant")

    def val(o, name, default=0.0):
        try:
            v = getattr(o, name)
            return float(getattr(v, "Value", v))
        except Exception:
            return default

    def snapshot(o):
        try:
            return (bool(o.Enabled), tuple(o.Color)[:3], float(o.Intensity), bool(o.Shadows), val(o, "Softness"),
                    bool(o.AffectDiffuse), bool(o.AffectSpecular), val(o, "ShadowRadius"), str(getattr(o, "Falloff", "")),
                    val(o, "ReferenceDistance"), val(o, "ConeAngle"), val(o, "EdgeAngle"), kind_of(o))
        except Exception:
            return None

    def show_for(kind):
        """Işık türüne göre alanları göster / gizle."""
        pos = L.is_positional(kind)
        for w in (lb_soft, sp_soft):
            w.setVisible(not pos)
        for w in (lb_rad, sp_rad):
            w.setVisible(pos)
        tabs.setTabEnabled(tabs.indexOf(pg_fall), pos)
        for w in (lb_cone, sp_cone, lb_edge, sp_edge):
            w.setVisible(kind == "spot")
        if not pos and tabs.currentWidget() is pg_fall:
            tabs.setCurrentIndex(0)

    def load():
        """Nesnenin özelliklerini araç gereçlere yazar."""
        o = st["obj"]
        has = alive()
        for w in inputs:
            w.setEnabled(has)
        if not has:
            return
        st["busy"] = True
        try:
            ck_on.setChecked(bool(o.Enabled))
            rgb = [int(round(max(0.0, min(1.0, c)) * 255)) for c in tuple(o.Color)[:3]]
            for s, v in zip(sp_rgb, rgb):
                s.setValue(v)
            paint_color(rgb)
            sp_int.setValue(float(o.Intensity))
            ck_sh.setChecked(bool(o.Shadows))
            kd = kind_of(o)
            show_for(kd)
            sp_soft.setValue(val(o, "Softness"))
            sp_rad.setValue(val(o, "ShadowRadius"))
            k2 = cb_fall.findData(str(getattr(o, "Falloff", "InverseSquare")))
            if k2 >= 0:
                cb_fall.setCurrentIndex(k2)
            sp_ref.setValue(val(o, "ReferenceDistance", 1000.0))
            sp_cone.setValue(val(o, "ConeAngle", 45.0))
            sp_edge.setValue(val(o, "EdgeAngle", 10.0))
            ck_dif.setChecked(bool(o.AffectDiffuse))
            ck_spc.setChecked(bool(o.AffectSpecular))
            k = cb_type.findData(getattr(o, L.PROP_TYPE, "distant"))
            if k >= 0:
                cb_type.setCurrentIndex(k)
            st["snap"] = snapshot(o)
        finally:
            st["busy"] = False

    def refill(keep=None):
        """Işık listesini belgeden yeniler."""
        d = _doc()
        objs = L.active_lights(d) if d is not None else []
        names = [(o.Name, o.Label) for o in objs]
        keep = keep or (st["obj"].Name if alive() else None)
        st["busy"] = True
        try:
            cb_cur.clear()
            for o in objs:
                cb_cur.addItem(o.Label, o.Name)
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
        lb_count.setText(T("Sahnedeki ışıklar: %d") % len(objs))
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

    def put(name, value):
        if st["busy"] or not alive():
            return
        o = st["obj"]
        try:
            setattr(o, name, value)
            st["snap"] = snapshot(o)
        except Exception as ex:
            FreeCAD.Console.PrintWarning("YBT light: %s\n" % ex)

    ck_on.toggled.connect(lambda v: put("Enabled", bool(v)))
    ck_sh.toggled.connect(lambda v: put("Shadows", bool(v)))
    ck_dif.toggled.connect(lambda v: put("AffectDiffuse", bool(v)))
    ck_spc.toggled.connect(lambda v: put("AffectSpecular", bool(v)))
    sp_int.valueChanged.connect(lambda v: put("Intensity", float(v)))
    sp_soft.valueChanged.connect(lambda v: put("Softness", float(v)))
    sp_rad.valueChanged.connect(lambda v: put("ShadowRadius", float(v)))
    sp_ref.valueChanged.connect(lambda v: put("ReferenceDistance", float(v)))
    sp_cone.valueChanged.connect(lambda v: put("ConeAngle", float(v)))
    sp_edge.valueChanged.connect(lambda v: put("EdgeAngle", float(v)))
    cb_fall.currentIndexChanged.connect(lambda i: put("Falloff", str(cb_fall.itemData(i))))

    def type_changed(i):
        """Işık türünü değiştirir: yeni türün özellikleri eklenir, Placement ve ortak ayarlar korunur."""
        if st["busy"] or not alive():
            return
        o = st["obj"]
        k = cb_type.itemData(i)
        if k == kind_of(o) or k not in L.TYPES:
            return
        d = o.Document
        d.openTransaction("Change light type")
        try:
            L.change_type(o, k)
        finally:
            d.commitTransaction()
        d.recompute()
        load()
    cb_type.currentIndexChanged.connect(type_changed)

    def rgb_changed(*_a):
        if st["busy"]:
            return
        rgb = [s.value() for s in sp_rgb]
        paint_color(rgb)
        put("Color", tuple(c / 255.0 for c in rgb) + (1.0,))
    for s in sp_rgb:
        s.valueChanged.connect(rgb_changed)

    def pick_color():
        if not alive():
            return
        c0 = QtGui.QColor(*[s.value() for s in sp_rgb])
        c = QtGui.QColorDialog.getColor(c0, dlg, T("Işık rengi"))
        if c.isValid():
            for s, v in zip(sp_rgb, (c.red(), c.green(), c.blue())):
                s.setValue(v)
    bt_col.clicked.connect(pick_color)

    def clear_all():
        d = _doc()
        objs = L.active_lights(d) if d is not None else []
        if not objs:
            return
        if QtGui.QMessageBox.question(dlg, T("Tüm ışıkları sil"), T("%d ışık nesnesi silinsin mi?") % len(objs),
                                      QtGui.QMessageBox.Yes | QtGui.QMessageBox.No) != QtGui.QMessageBox.Yes:
            return
        d.openTransaction("Clear lights")
        try:
            for o in objs:
                d.removeObject(o.Name)
        finally:
            d.commitTransaction()
        d.recompute()
        refill()
    b_clear.clicked.connect(clear_all)

    # -- belge / seçim eşitleme: ışık seçilince panel ona geçer; özellik düzenleyicide değişen değer panele yansır
    def tick():
        d = _doc()
        objs = L.active_lights(d) if d is not None else []
        names = [(o.Name, o.Label) for o in objs]
        if names != st["names"]:
            refill()
        elif alive():
            sn = snapshot(st["obj"])
            if sn != st["snap"] and not any(w.hasFocus() for w in inputs):
                load()
        try:
            import FreeCADGui as Gui
            sel = [o for o in Gui.Selection.getSelection() if L._is_light(o)]
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
    dlg._api = dict(select=select, refill=refill, widgets=dict(current=cb_cur, enabled=ck_on, type=cb_type, rgb=sp_rgb, intensity=sp_int,
                                                               diffuse=ck_dif, specular=ck_spc, shadows=ck_sh, softness=sp_soft,
                                                               radius=sp_rad, falloff=cb_fall, refdist=sp_ref, cone=sp_cone, edge=sp_edge, tabs=tabs,
                                                               clear=b_clear, count=lb_count))
    _theme.fix_combos(dlg)
    refill()
    return dlg
