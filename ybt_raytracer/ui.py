# -*- coding: utf-8 -*-
import os
import numpy as np
import time
from . import settings as S
from .i18n import T
from . import textures as _textures
from .parallel import _Cancelled
from .render import render
from .output import pick_out_path, write_png
from .freecad_scene import collect_scene, read_camera, read_freecad_lights


_QUALITY = [("Low", 0.012), ("Hızlı", 0.004), ("Normal", 0.0015), ("İnce", 0.0008)]   # Low: çok büyük montajlar için


def main(lang=None):
    """Ayar paneli olan, kapanmayan (modeless) bir pencere açar. Render, 'Render' düğmesine basınca başlar."""
    import FreeCAD
    import FreeCADGui as Gui
    from PySide import QtGui, QtCore

    from . import i18n
    if lang:
        i18n.set_lang(lang)
    else:
        i18n.init_lang()
    doc = FreeCAD.ActiveDocument
    if doc is None or Gui.ActiveDocument is None:
        FreeCAD.Console.PrintError(T("RayTrace: açık belge yok.\n"))
        return
    old = getattr(FreeCAD, "_raytrace_dlg", None)          # önceki pencere açıksa kapat
    if old is not None:
        try:
            old.close()
        except Exception:
            pass
    g = vars(S)                      # ayarlar settings modülünde durur

    dlg = QtGui.QDialog(Gui.getMainWindow())
    dlg.setWindowTitle("FC YBT Raytracer")
    try:
        _ic = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")
        if os.path.exists(_ic):
            dlg.setWindowIcon(QtGui.QIcon(_ic))
    except Exception:
        pass
    outer = QtGui.QHBoxLayout(dlg)

    def spin(lo, hi, val, step=1, suffix=""):
        sp = QtGui.QSpinBox()
        sp.setRange(lo, hi)
        sp.setSingleStep(step)
        sp.setValue(int(round(val)))
        if suffix:
            sp.setSuffix(suffix)
        return sp

    # ================= SOL: Settings =================
    left = QtGui.QWidget()
    lv = QtGui.QVBoxLayout(left)
    lv.setContentsMargins(0, 0, 0, 0)

    # ---- Kalite Ayarları ----
    qbox = QtGui.QGroupBox(T("Kalite Ayarları"))
    qg = QtGui.QGridLayout(qbox)
    sp_w = spin(160, 4000, S.WIDTH, 80, " px")
    cb_q = QtGui.QComboBox()
    for name, _f in _QUALITY:
        cb_q.addItem(T(name))
    cb_q.setCurrentIndex(min(range(len(_QUALITY)), key=lambda i: abs(_QUALITY[i][1] - S.TESS_FACTOR)))
    cb_aa = QtGui.QComboBox()
    for name in (T("Kapalı"), "2x2", "3x3", "4x4"):
        cb_aa.addItem(name)
    cb_aa.setCurrentIndex(0 if int(S.AA) < 2 else min(3, int(S.AA) - 1))
    sp_bn = spin(0, 3, S.BOUNCES)
    cb_th = QtGui.QComboBox()
    _TH = [0, 1, 2, 4]
    for name in (T("Otomatik"), "1", "2", "4"):
        cb_th.addItem(name)
    cb_th.setCurrentIndex(_TH.index(int(S.THREADS)) if int(S.THREADS) in _TH else 0)
    cb_th.setToolTip(T("Render için kullanılacak çekirdek (iş parçacığı) sayısı; Otomatik = işlemci çekirdek sayısı"))
    sp_rg = spin(0, 200, S.REFLECT_GLASS * 100, 10, " %")
    sp_rs = spin(0, 60, S.REFLECT_SURF * 100, 5, " %")
    ck_sh = QtGui.QCheckBox(T("Gölgeler"))
    ck_sh.setChecked(bool(S.SHADOWS))
    ck_gl = QtGui.QCheckBox(T("Saydamlık (cam)"))
    ck_gl.setChecked(bool(S.GLASS))
    sp_ior = QtGui.QDoubleSpinBox()
    sp_ior.setRange(1.0, 3.0)
    sp_ior.setSingleStep(0.05)
    sp_ior.setDecimals(2)
    sp_ior.setValue(float(S.IOR))
    sp_ior.setSpecialValueText(T("Kapalı"))
    sp_ior.setToolTip(T("Cam kırılma indisi (Snell yasası): cam 1.5, su 1.33, elmas 2.4. Kapalı = ışık düz geçer (en hızlı). "
                      "Kırılma için nesne saydam olmalı; küre/silindir gibi kapalı gövdelerde en iyi sonuç."))
    ck_sm = QtGui.QCheckBox(T("Yumuşak yüzeyler"))
    ck_sm.setChecked(bool(S.SMOOTH))
    ck_sm.setToolTip(T("Eğri yüzeyleri (küre, simit, silindir) pürüzsüz gölgeler; keskin kenarlar (küp, plaka) korunur. Kapalıysa üçgenler görünür."))
    ck_sv = QtGui.QCheckBox(T("Bitince otomatik kaydet"))
    ck_sv.setChecked(True)
    sp_w.setToolTip(T("Çıktı genişliği; yükseklik 3B görünümün oranından gelir"))
    cb_q.setToolTip(T("Yüzey pürüzsüzlüğü (üçgenleme inceliği). Değişince sahne yeniden okunur"))
    cb_aa.setToolTip(T("Kenar yumuşatma: yalnız kenar piksellerinde çoklu örnekleme yapar"))
    ck_gl.setToolTip(T("Nesnenin Transparency (saydamlık) özelliğine göre arkası görünür"))
    sp_rg.setToolTip(T("Cam yüzeylerin yansıması (Fresnel: eğik bakışta daha çok)"))
    sp_rs.setToolTip(T("Opak yüzeylerin sabit yansıması; 0 = kapalı (en hızlı)"))
    sp_bn.setToolTip(T("Bir ışının en çok kaç kez yansıyacağı"))
    qrows = [(T("Genişlik"), sp_w, T("Kalite"), cb_q),
             (T("Kenar yumuşatma"), cb_aa, T("Yansıma sayısı"), sp_bn),
             (T("Cam yansıması"), sp_rg, T("Yüzey yansıması"), sp_rs),
             (T("Çekirdek"), cb_th, T("Kırılma (IOR)"), sp_ior)]
    for r, (l1, w1, l2, w2) in enumerate(qrows):
        qg.addWidget(QtGui.QLabel(l1), r * 2, 0)
        qg.addWidget(QtGui.QLabel(l2), r * 2, 1)
        qg.addWidget(w1, r * 2 + 1, 0)
        if w2 is not None:
            qg.addWidget(w2, r * 2 + 1, 1)
    qg.addWidget(ck_sh, 8, 0)
    qg.addWidget(ck_gl, 8, 1)
    qg.addWidget(ck_sm, 9, 0, 1, 2)
    qg.addWidget(ck_sv, 10, 0, 1, 2)
    lv.addWidget(qbox)

    # ---- Işık Ayarları: ortam + en çok 3 ışık ----
    lbox = QtGui.QGroupBox(T("Işık Ayarları"))
    lvb = QtGui.QVBoxLayout(lbox)
    colors = {}

    def color_button(key, rgb, title=T("Işık rengi")):
        colors[key] = tuple(rgb)
        bt = QtGui.QPushButton("")
        bt.setFixedWidth(54)

        def paint():
            r, g_, b_ = [int(round(max(0.0, min(1.0, v)) * 255)) for v in colors[key]]
            bt.setStyleSheet("background-color: rgb(%d,%d,%d);" % (r, g_, b_))

        def pick(*_a):
            r, g_, b_ = [int(round(max(0.0, min(1.0, v)) * 255)) for v in colors[key]]
            col = QtGui.QColorDialog.getColor(QtGui.QColor(r, g_, b_), dlg, title)
            if col.isValid():
                colors[key] = (col.red() / 255.0, col.green() / 255.0, col.blue() / 255.0)
                paint()
        bt.clicked.connect(pick)
        paint()
        return bt

    ck_fc = QtGui.QCheckBox(T("FreeCAD ışık ayarlarını kullan"))
    ck_fc.setChecked(bool(getattr(S, "USE_FC_LIGHTS", False)))
    ck_fc.setToolTip(T("İşaretliyse Tercihler > Display > Light Sources ayarları kullanılır; aşağıdaki ayarlar devre dışı kalır"))
    lvb.addWidget(ck_fc)
    lrows = []
    names = (T("Ana ışık"), T("Dolgu ışığı"), T("Arka ışık"))
    for i in range(3):
        lt = S.LIGHTS[i] if i < len(S.LIGHTS) else dict(on=False, h=0.0, v=0.0, color=(1, 1, 1), power=0.3, shadow=False)
        frame = QtGui.QFrame()
        frame.setFrameShape(QtGui.QFrame.StyledPanel)
        fg = QtGui.QGridLayout(frame)
        fg.setContentsMargins(6, 4, 6, 4)
        ck = QtGui.QCheckBox(names[i])
        ck.setChecked(bool(lt["on"]))
        cbn = color_button("l%d" % i, lt["color"])
        sp_ = spin(0, 200, float(lt["power"]) * 100, 5, " %")
        sp_.setToolTip(T("Işık gücü"))
        sh = spin(-180, 180, lt["h"], 5, " °")
        sh.setToolTip(T("Yatay açı (kameraya göre; eksi = sol, artı = sağ, 180 = arkadan)"))
        sv = spin(-90, 90, lt["v"], 5, " °")
        sv.setToolTip(T("Dikey açı (artı = yukarıdan)"))
        cs = QtGui.QCheckBox(T("Gölge"))
        cs.setChecked(bool(lt["shadow"]))
        cs.setToolTip(T("Bu ışık gölge düşürsün (her gölgeli ışık süreyi artırır)"))
        fg.addWidget(ck, 0, 0, 1, 2)
        fg.addWidget(cbn, 0, 2)
        fg.addWidget(sp_, 0, 3)
        fg.addWidget(QtGui.QLabel(T("Yatay")), 1, 0)
        fg.addWidget(sh, 1, 1)
        fg.addWidget(QtGui.QLabel(T("Dikey")), 1, 2)
        fg.addWidget(sv, 1, 3)
        fg.addWidget(cs, 2, 0, 1, 4)
        lvb.addWidget(frame)
        lrows.append((ck, sh, sv, cbn, sp_, cs))
    arow = QtGui.QHBoxLayout()
    arow.addWidget(QtGui.QLabel(T("Ortam ışığı")))
    cb_amb = color_button("amb", S.AMBIENT_COLOR)
    sp_amb = spin(0, 100, S.AMBIENT * 100, 5, " %")
    arow.addWidget(cb_amb)
    arow.addWidget(sp_amb)
    lvb.addLayout(arow)
    lv.addWidget(lbox)
    light_widgets = [wd for row in lrows for wd in row] + [cb_amb, sp_amb]

    # ---- Sanal Zemin ----
    fbox = QtGui.QGroupBox(T("Sanal Zemin"))
    fgl = QtGui.QGridLayout(fbox)
    ck_fl = QtGui.QCheckBox(T("Sanal zemin ekle"))
    ck_fl.setChecked(bool(S.FLOOR))
    ck_fl.setToolTip(T("Sahnenin en alt noktasına (+ ofset) yatay, sonsuz bir zemin koyar. FreeCAD'de Z yukarı kabul edilir."))
    cb_fl = color_button("floor", S.FLOOR_COLOR, T("Zemin rengi"))
    sp_fo = spin(0, 100, S.FLOOR_OPACITY * 100, 10, " %")
    sp_fo.setToolTip(T("Zemin opaklığı; 100 = opak, düşünce zemin saydamlaşır"))
    sp_fr = spin(0, 100, S.FLOOR_REFLECT * 100, 10, " %")
    sp_fr.setToolTip(T("Zemin yansıması (eğik bakışta güçlenir); 0 = yansımasız, en hızlı"))
    sp_fz = spin(-1000000, 1000000, S.FLOOR_OFFSET, 10, " mm")
    sp_fz.setToolTip(T("Zemin yüksekliği: sahnenin en alt z değerine göre ofset (eksi = aşağı, artı = yukarı)"))
    fgl.addWidget(ck_fl, 0, 0, 1, 4)
    fgl.addWidget(QtGui.QLabel(T("Renk")), 1, 0)
    fgl.addWidget(cb_fl, 1, 1)
    fgl.addWidget(QtGui.QLabel(T("Opaklık")), 1, 2)
    fgl.addWidget(sp_fo, 1, 3)
    fgl.addWidget(QtGui.QLabel(T("Yansıma")), 2, 0)
    fgl.addWidget(sp_fr, 2, 1)
    fgl.addWidget(QtGui.QLabel(T("Ofset")), 2, 2)
    fgl.addWidget(sp_fz, 2, 3)
    # doku seçimi: düz renk / hazır dokular / kendi görüntü dosyanız
    cb_ft = QtGui.QComboBox()
    cb_ft.addItem(T("Düz renk"), "")
    for k, name, _fn, _mode, _rel in _textures.PRESETS:
        cb_ft.addItem(T(name), k)
    cb_ft.addItem(T("Dosyadan…"), "__file__")
    cb_ft.setToolTip(T("Zemin dokusu. 'Dosyadan…' ile kendi PNG/JPG görüntünüzü seçebilirsiniz."))
    sp_fs = spin(0, 1000000, S.FLOOR_TEX_SCALE, 100, " mm")
    sp_fs.setSpecialValueText(T("Otomatik"))
    sp_fs.setToolTip(T("Dokunun zemindeki genişliği (mm). Otomatik = doku türüne göre sahne büyüklüğüyle orantılı"))
    ft_state = {"key": S.FLOOR_TEXTURE or "", "last": 0}
    for i in range(cb_ft.count()):
        if cb_ft.itemData(i) == ft_state["key"]:
            cb_ft.setCurrentIndex(i)
    fgl.addWidget(QtGui.QLabel(T("Doku")), 3, 0)
    fgl.addWidget(cb_ft, 3, 1)
    fgl.addWidget(QtGui.QLabel(T("Doku boyu")), 3, 2)
    fgl.addWidget(sp_fs, 3, 3)
    lv.insertWidget(1, fbox)                                    # Kalite ile Işık arasına
    floor_widgets = [cb_fl, sp_fo, sp_fr, sp_fz, cb_ft, sp_fs]

    def sync_floor(*_a):
        on = ck_fl.isChecked()
        for wd in floor_widgets:
            wd.setEnabled(on)
        cb_fl.setEnabled(on and not ft_state["key"])             # doku seçiliyken renk kullanılmaz
        sp_fs.setEnabled(on and bool(ft_state["key"]))

    def on_tex(idx):
        data = cb_ft.itemData(idx)
        if data == "__file__":
            res = QtGui.QFileDialog.getOpenFileName(dlg, T("Zemin dokusu seç"), os.path.expanduser("~"),
                                                    T("Görüntü (*.png *.jpg *.jpeg *.bmp)"))
            path = res[0] if isinstance(res, (tuple, list)) else res
            img = QtGui.QImage(path) if path else None
            if not path or img is None or img.isNull():
                cb_ft.blockSignals(True)
                cb_ft.setCurrentIndex(ft_state["last"])           # vazgeçildi: öncekine dön
                cb_ft.blockSignals(False)
                return
            if max(img.width(), img.height()) > 1024:             # bellek/hız: en çok 1024 px
                img = img.scaled(1024, 1024, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            img = img.convertToFormat(QtGui.QImage.Format_RGB888)
            w_, h_ = img.width(), img.height()
            bpl = img.bytesPerLine()
            buf = np.frombuffer(bytes(img.constBits()), dtype=np.uint8)[:bpl * h_].reshape(h_, bpl)[:, :w_ * 3]
            _textures.register_custom(path, buf.reshape(h_, w_, 3), "mirror")
            cb_ft.blockSignals(True)
            cb_ft.setItemText(cb_ft.count() - 1, T("Dosya: ") + os.path.basename(path))
            cb_ft.setItemData(cb_ft.count() - 1, path)
            cb_ft.blockSignals(False)
            ft_state["key"] = path
        else:
            ft_state["key"] = data or ""
        ft_state["last"] = cb_ft.currentIndex()
        sync_floor()
    cb_ft.currentIndexChanged.connect(on_tex)
    ck_fl.toggled.connect(sync_floor)
    sync_floor()

    def sync_lights(*_a):
        for wd in light_widgets:
            wd.setEnabled(not ck_fc.isChecked())
    ck_fc.toggled.connect(sync_lights)

    # ---- düğmeler ----
    btn_r = QtGui.QPushButton("Render")
    btn_r.setStyleSheet("font-weight: bold;")
    btn_s = QtGui.QPushButton(T("Durdur"))
    btn_s.setEnabled(False)
    btn_k = QtGui.QPushButton(T("Farklı kaydet..."))
    btn_k.setEnabled(False)
    btn_y = QtGui.QPushButton(T("Sahneyi yenile"))
    btn_y.setToolTip(T("Model değiştiyse sahneyi bir sonraki Render'da yeniden okur"))
    b1 = QtGui.QHBoxLayout()
    b1.addWidget(btn_r)
    b1.addWidget(btn_s)
    b2 = QtGui.QHBoxLayout()
    b2.addWidget(btn_k)
    b2.addWidget(btn_y)
    lv.addStretch(1)

    sc_left = QtGui.QScrollArea()                     # ekran küçükse sol panel kaydırılır
    sc_left.setWidget(left)
    sc_left.setWidgetResizable(True)
    sc_left.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)   # içerik sığmazsa kırpmak yerine kaydır
    lcol = QtGui.QVBoxLayout()                        # üstte sabit: başlık + düğmeler, altta kaydırılabilir ayarlar
    head = QtGui.QLabel("Settings")
    head.setStyleSheet("font-weight: bold; font-size: 14px;")
    cb_lang = QtGui.QComboBox()
    cb_lang.addItem("Türkçe", "tr")
    cb_lang.addItem("English", "en")
    cb_lang.setCurrentIndex(1 if i18n.LANG == "en" else 0)
    cb_lang.setToolTip("Dil / Language")

    def on_lang(_i):
        new = cb_lang.itemData(cb_lang.currentIndex())
        if new == i18n.LANG or state["busy"]:
            cb_lang.blockSignals(True)
            cb_lang.setCurrentIndex(1 if i18n.LANG == "en" else 0)
            cb_lang.blockSignals(False)
            return
        apply_all()                                   # ayarlar yeni pencereye taşınsın
        i18n.set_lang(new)
        QtCore.QTimer.singleShot(0, lambda: (dlg.close(), main(new)))
    cb_lang.currentIndexChanged.connect(on_lang)
    hrow = QtGui.QHBoxLayout()
    hrow.addWidget(head)
    hrow.addStretch(1)
    hrow.addWidget(QtGui.QLabel("Dil / Language:"))
    hrow.addWidget(cb_lang)
    lcol.addLayout(hrow)
    lcol.addLayout(b1)
    lcol.addLayout(b2)
    lcol.addWidget(sc_left, 1)
    lw = QtGui.QWidget()
    lw.setLayout(lcol)
    lw.setMinimumWidth(360)
    outer.setContentsMargins(6, 6, 6, 6)
    split = QtGui.QSplitter(QtCore.Qt.Horizontal)       # ayar paneli ile ön izleme arasındaki çubuk sürüklenebilir
    split.setChildrenCollapsible(False)
    split.addWidget(lw)

    # ================= SAĞ: Ön izleme ekranı (ortalanmış) =================
    right = QtGui.QVBoxLayout()
    title = QtGui.QLabel("FC YBT Raytracer")
    title.setAlignment(QtCore.Qt.AlignCenter)
    title.setStyleSheet("font-weight: bold; font-size: 16px;")
    right.addWidget(title)

    class _Preview(QtGui.QLabel):
        """Görüntüyü kutuya sığdırıp ortalar (en-boy oranı korunur)."""

        def __init__(self):
            QtGui.QLabel.__init__(self, T("Ön izleme ekranı"))
            self.pm = None
            self.setAlignment(QtCore.Qt.AlignCenter)
            self.setMinimumSize(320, 240)
            self.setSizePolicy(QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Ignored)
            self.setFrameShape(QtGui.QFrame.StyledPanel)

        def set_pixmap_full(self, pm):
            self.pm = pm
            self.refit()

        def refit(self):
            if self.pm is not None:
                sz = self.size()
                self.setPixmap(self.pm.scaled(max(1, sz.width() - 6), max(1, sz.height() - 6),
                                              QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))

        def resizeEvent(self, ev):
            QtGui.QLabel.resizeEvent(self, ev)
            self.refit()

    lbl = _Preview()
    right.addWidget(lbl, 1)
    # ---- işlem çubuğu: ön izlemeyle aynı genişlikte; içinde yapılan işin adı, sağda yüzde ----
    pframe = QtGui.QFrame()
    pframe.setFrameShape(QtGui.QFrame.StyledPanel)
    ph = QtGui.QHBoxLayout(pframe)
    ph.setContentsMargins(2, 2, 6, 2)
    bar = QtGui.QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(0)
    bar.setTextVisible(True)
    bar.setAlignment(QtCore.Qt.AlignCenter)
    bar.setMinimumHeight(26)
    pct = QtGui.QLabel("")
    pct.setMinimumWidth(48)
    pct.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
    ph.addWidget(bar, 1)
    ph.addWidget(pct)
    right.addWidget(pframe)

    class _St(object):
        """Eski 'etiket' arayüzü (setText/text) + çubuk ilerlemesi (frac: 0..1 ya da None)."""

        def __init__(self):
            self.t = ""

        def set(self, text, frac=None):
            self.t = text
            bar.setFormat(text.replace("%p", "").replace("%v", "").replace("%m", ""))
            bar.setToolTip(text)
            if frac is None:
                bar.setValue(0)
                pct.setText("")
            else:
                v = int(round(max(0.0, min(1.0, frac)) * 100))
                bar.setValue(v)
                pct.setText("%%%d" % v)

        def setText(self, text):                   # bitiş / hata / iptal mesajı: çubuk değerine dokunma
            self.t = text
            bar.setFormat(text.replace("%p", "").replace("%v", "").replace("%m", ""))
            bar.setToolTip(text)

        def text(self):
            return self.t

    lbl_st = _St()
    lbl_st.setText(T("Hazır. Ayarları seç, 3B görünümü çevir ve Render'a bas."))
    rw = QtGui.QWidget()
    rw.setLayout(right)
    split.addWidget(rw)
    split.setStretchFactor(0, 0)
    split.setStretchFactor(1, 1)
    outer.addWidget(split, 1)
    # ayar paneli, içeriğinin gerçek genişliğine (+ kaydırma çubuğu) göre açılır; kullanıcı çubukla değiştirebilir
    pw = max(460, left.sizeHint().width() + sc_left.verticalScrollBar().sizeHint().width() + 24)
    pw = min(pw, 620)
    dlg.resize(pw + 880, 820)
    split.setSizes([pw, 880])

    def sync_enabled(*_a):
        gl = ck_gl.isChecked()
        sp_rg.setEnabled(gl)
        sp_ior.setEnabled(gl)
        sp_bn.setEnabled(gl or sp_rs.value() > 0)
    ck_gl.toggled.connect(sync_enabled)
    sp_rs.valueChanged.connect(sync_enabled)
    sync_enabled()

    state = {"scene": None, "key": None, "busy": False, "cancel": False, "last": 0.0,
             "out": None, "path": None}

    def alive():
        return dlg.isVisible() and not state["cancel"]

    def status(msg, force=False, frac=None):
        now = time.time()
        if force or now - state["last"] > 0.15:
            state["last"] = now
            lbl_st.set(msg, frac)
            QtCore.QCoreApplication.processEvents()
        if not alive():
            raise _Cancelled()

    def tick():
        QtCore.QCoreApplication.processEvents()
        return alive()

    def put(arr, w, h):
        a = np.ascontiguousarray(arr)
        qi = QtGui.QImage(a.data, w, h, 3 * w, QtGui.QImage.Format_RGB888).copy()
        lbl.set_pixmap_full(QtGui.QPixmap.fromImage(qi))

    def show(img, rows, frac=None, label=T("ışınlar izleniyor")):
        h, w = img.shape[:2]
        put(np.clip(img * 255.0, 0, 255).astype(np.uint8), w, h)
        lbl_st.set(label, (rows / float(h)) if frac is None else frac)
        QtCore.QCoreApplication.processEvents()
        return alive()

    def busy(on):
        state["busy"] = on
        for wd in light_widgets + floor_widgets + [ck_fl, ck_fc, btn_r, btn_y, sp_w, cb_q, cb_aa, ck_sh, ck_gl, ck_sm, sp_ior, sp_rg, sp_rs, sp_bn, cb_th, ck_sv]:
            wd.setEnabled(not on)
        btn_s.setEnabled(on)
        if not on:
            sync_enabled()
            sync_lights()
            sync_floor()
            btn_k.setEnabled(state["out"] is not None)

    def apply_basic():
        g["WIDTH"] = sp_w.value()
        g["TESS_FACTOR"] = _QUALITY[cb_q.currentIndex()][1]
        g["SHADOWS"] = ck_sh.isChecked()
        g["GLASS"] = ck_gl.isChecked()
        g["SMOOTH"] = ck_sm.isChecked()
        g["IOR"] = float(sp_ior.value())
        g["REFLECT_GLASS"] = sp_rg.value() / 100.0
        g["REFLECT_SURF"] = sp_rs.value() / 100.0
        g["BOUNCES"] = sp_bn.value()
        g["THREADS"] = _TH[cb_th.currentIndex()]
        g["FLOOR"] = ck_fl.isChecked()
        g["FLOOR_COLOR"] = colors["floor"]
        g["FLOOR_OPACITY"] = sp_fo.value() / 100.0
        g["FLOOR_REFLECT"] = sp_fr.value() / 100.0
        g["FLOOR_OFFSET"] = float(sp_fz.value())
        g["FLOOR_TEXTURE"] = ft_state["key"]
        g["FLOOR_TEX_SCALE"] = float(sp_fs.value())

    def apply_manual_lights():
        g["AMBIENT"] = sp_amb.value() / 100.0
        g["AMBIENT_COLOR"] = colors["amb"]
        g["LIGHTS"] = [dict(on=r[0].isChecked(), h=float(r[1].value()), v=float(r[2].value()),
                            color=colors["l%d" % i], power=r[4].value() / 100.0, shadow=r[5].isChecked())
                       for i, r in enumerate(lrows)]

    def apply_all():
        apply_basic()
        apply_manual_lights()
        g["AA"] = 0 if cb_aa.currentIndex() == 0 else cb_aa.currentIndex() + 1
        g["USE_FC_LIGHTS"] = ck_fc.isChecked()

    def do_render(*_a):
        if state["busy"]:
            return
        state["cancel"] = False
        busy(True)
        t0 = time.time()
        try:
            if Gui.ActiveDocument is None:
                lbl_st.setText(T("Açık belge yok."))
                return
            d = Gui.ActiveDocument.Document
            view = Gui.ActiveDocument.ActiveView
            cam, aspect = read_camera(view)
            apply_basic()
            fc_info = ""
            fc = None
            if ck_fc.isChecked():
                try:
                    fc = read_freecad_lights(lambda m: FreeCAD.Console.PrintMessage("RayTrace: " + m + "\n"))
                except Exception as ex:
                    FreeCAD.Console.PrintWarning(T("RayTrace: FreeCAD ışık ayarları okunamadı (%s); kendi ayarlar kullanılıyor.\n") % ex)
            if fc is not None:
                g["LIGHTS"], g["AMBIENT"], g["AMBIENT_COLOR"], fc_info = fc
            else:
                apply_manual_lights()
            g["AA"] = 0 if cb_aa.currentIndex() == 0 else cb_aa.currentIndex() + 1
            g["USE_FC_LIGHTS"] = ck_fc.isChecked()
            w = int(S.WIDTH)
            h = max(1, int(round(w / aspect)))
            key = (d.Name, len(d.Objects), S.TESS_FACTOR)
            if state["scene"] is None or state["key"] != key:
                state["scene"], nobj = collect_scene(d, status)
                state["key"] = key
                FreeCAD.Console.PrintMessage(T("RayTrace: %d nesne, %d üçgen (hazırlık %.1f sn)\n")
                                             % (nobj, state["scene"].count, time.time() - t0))
            t1 = time.time()
            out = render(state["scene"], cam, w, h, shadows=S.SHADOWS, progress=show, tile=S.TILE,
                         tick=tick, stage=lambda s: status(s, True, None))
            if out is None:
                raise _Cancelled()
            state["out"] = out
            put(out, w, h)
            msg = ""
            if ck_sv.isChecked():
                path = pick_out_path(d.FileName)
                try:
                    write_png(path, out)
                    state["path"] = path
                    msg = T(" | kaydedildi: %s") % path
                except Exception as ex:
                    msg = T(" | KAYDEDİLEMEDİ (%s)") % ex
            dt = time.time() - t0
            lbl_st.set(T("bitti: %dx%d | %d üçgen | render %.1f sn | toplam %.1f sn")
                       % (w, h, state["scene"].count, time.time() - t1, dt), 1.0)
            bar.setToolTip((T("kaydedildi: %s") % state["path"]) if ck_sv.isChecked() and state["path"] else msg.strip(" |"))
            FreeCAD.Console.PrintMessage(T("RayTrace: render %.1f sn, toplam %.1f sn%s\n")
                                         % (time.time() - t1, dt, msg))
        except _Cancelled:
            lbl_st.setText(T("iptal edildi."))
            FreeCAD.Console.PrintMessage(T("RayTrace: iptal edildi.\n"))
        except Exception:
            import traceback
            FreeCAD.Console.PrintError(T("RayTrace hatası:\n") + traceback.format_exc())
            lbl_st.setText(T("HATA: Report View'a bak."))
        finally:
            busy(False)

    def do_stop(*_a):
        state["cancel"] = True

    def do_save(*_a):
        if state["out"] is None:
            return
        try:
            start = state["path"] or pick_out_path(FreeCAD.ActiveDocument.FileName if FreeCAD.ActiveDocument else "")
        except Exception:
            start = "render.png"
        res = QtGui.QFileDialog.getSaveFileName(dlg, T("Render'ı kaydet"), start, "PNG (*.png)")
        path = res[0] if isinstance(res, (tuple, list)) else res
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        try:
            write_png(path, state["out"])
            state["path"] = path
            lbl_st.setText(T("kaydedildi: %s") % path)
        except Exception as ex:
            lbl_st.setText(T("KAYDEDİLEMEDİ (%s)") % ex)

    def do_refresh(*_a):
        state["scene"] = None
        lbl_st.setText(T("Sahne bir sonraki Render'da yeniden okunacak."))

    btn_r.clicked.connect(do_render)
    btn_s.clicked.connect(do_stop)
    btn_k.clicked.connect(do_save)
    btn_y.clicked.connect(do_refresh)

    FreeCAD._raytrace_dlg = dlg
    dlg._raytrace_handlers = (do_render, do_stop, do_save, do_refresh, status, tick, show)  # referansları canlı tut
    dlg.show()
    # test/otomasyon için dışarıdan tetikleme
    dlg._raytrace_api = dict(render=do_render, widgets=dict(width=sp_w, quality=cb_q, shadows=ck_sh, glass=ck_gl, smooth=ck_sm, ior=sp_ior,
                                                            rglass=sp_rg, rsurf=sp_rs, bounces=sp_bn, autosave=ck_sv, aa=cb_aa, threads=cb_th, floor=ck_fl, floor_color=cb_fl, floor_opacity=sp_fo, floor_reflect=sp_fr, floor_offset=sp_fz, floor_texture=cb_ft, floor_tex_scale=sp_fs, lights=lrows, ambient=sp_amb, fclights=ck_fc),
                             status=lbl_st, bar=bar, pct=pct, state=state)
