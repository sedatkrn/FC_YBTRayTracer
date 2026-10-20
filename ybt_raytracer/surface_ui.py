# -*- coding: utf-8 -*-
"""Surface (yüzey/malzeme) penceresi: nesne listesi + malzeme kütüphanesi + parametre düzenleyici + canlı önizleme küresi."""
import os
import time
import numpy as np
from . import settings as S
from . import materials as M
from .i18n import T
from .core import Scene
from . import theme as _theme
from . import textures as _tex
from . import paths as _paths
from . import procedural as _proc

PREVIEW_DELAY_MS = 1000     # parametre (sürgü/sayı) değişiminden sonra önizleme bu kadar sessizlik beklenince yenilenir

_PARAMS = [  # (anahtar, etiket, alt, üst, ipucu)
    ("diffuse", "Yayılı (diffuse)", 0.0, 1.0, "Mat ışık çarpanı"),
    ("spec", "Parlaklık şiddeti (specular)", 0.0, 1.0, "Işık vurgusunun gücü"),
    ("gloss", "Parlaklık keskinliği (glossiness)", 0.0, 1.0, "Düşük = geniş yumuşak vurgu, yüksek = küçük keskin vurgu"),
    ("metal", "Metal", 0.0, 1.0, "Vurguyu yüzey rengine boyar, yayılı ışığı azaltır"),
    ("refl", "Yansıma", 0.0, 1.0, "Çevrenin yüzeyde görünmesi"),
    ("transp", "Saydamlık", 0.0, 1.0, "0 = opak, 1 = tam saydam"),
    ("ior", "Kırılma indisi (IOR)", 1.0, 3.0, "Saydam malzemede ışığın bükülmesi: cam 1.5, su 1.33, elmas 2.4; 1 = düz geçiş"),
    ("lum", "Kendi ışığı (luminosity)", 0.0, 1.0, "Işıktan bağımsız parlama"),
]


_preset_keys = {p_[0] for p_ in _tex.PRESETS}                      # hazır doku anahtarları (klasör dosyalarından ayırmak için)
_LAST_DIR = {}                                                # son görüntü klasörü
_LAYER_CLIP = {}                                             # doku katmanı panosu (kanallar ve malzemeler arasında ortak)
_T_CSS = "QPushButton { padding: 0px; margin: 0px; min-width: 28px; max-width: 28px; min-height: 14px; max-height: 14px; font-size: 9px; font-weight: bold; }"
_T_CSS_ON = "QPushButton { background-color: #5b7fa6; color: white; }"
_CH_KEYS = ("diffuse", "spec", "gloss", "refl", "transp", "lum")      # doku (T) alabilen sayısal kanallar


# ---------------------------------------------------------------- önizleme sahnesi
def _cube_tris(side=1.7, rot=np.radians(32.0)):
    """Zemine oturan, z ekseninde döndürülmüş küp: 12 üçgen, dışa bakan sarım."""
    h = side / 2.0
    c, s_ = np.cos(rot), np.sin(rot)
    V = []
    for x in (-h, h):
        for y in (-h, h):
            for z in (0.0, side):
                V.append((c * x - s_ * y, s_ * x + c * y, z))
    V = np.array(V)
    cen = np.array([0.0, 0.0, h])
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    out = []
    for q in quads:
        for tri in ((q[0], q[1], q[2]), (q[0], q[2], q[3])):
            a, b, d = V[tri[0]], V[tri[1]], V[tri[2]]
            n = np.cross(b - a, d - a)
            if np.dot(n, (a + b + d) / 3.0 - cen) < 0:
                b, d = d, b
            out.append((a, b, d))
    return np.array(out)


def _preview_scene(mat, shape="sphere"):
    """Zemin üstünde bir küre (ya da küp); zemin dama deseni (yansıma/kırılma/saydamlık görünsün)."""
    mat = dict(mat)
    mat["tex_layers"] = {k: [dict(L) for L in ls] for k, ls in (mat.get("tex_layers") or {}).items()}
    for _ls in mat["tex_layers"].values():                   # önizleme nesnesi ~2 birim: doku tekrarı 1 birim (ya da mm/100)
        for _L in _ls:
            _L["tex_scale"] = (1.0 if _L.get("type") == "image" else 0.0) if _L.get("tex_scale", 0.0) <= 0 else _L["tex_scale"] / 100.0
            for _k in ("tex_px", "tex_py", "tex_pz"):
                _L[_k] = _L.get(_k, 0.0) / 100.0
    nu, nv = 48, 24
    th = np.linspace(0, 2 * np.pi, nu + 1)
    ph = np.linspace(0, np.pi, nv + 1)
    P = np.zeros((nv + 1, nu + 1, 3))
    P[..., 0] = np.sin(ph)[:, None] * np.cos(th)[None, :]
    P[..., 1] = np.sin(ph)[:, None] * np.sin(th)[None, :]
    P[..., 2] = np.cos(ph)[:, None] + 1.0
    tris = []
    for i in range(nv):
        for j in range(nu):
            a, b, c, d = P[i, j], P[i, j + 1], P[i + 1, j + 1], P[i + 1, j]
            tris += [(a, c, b), (a, d, c)]            # dışa bakan sarım (FreeCAD ile aynı)
    sph = np.array(tris) if shape != "cube" else _cube_tris()
    cols = [np.tile((0.7, 0.7, 0.72) if mat["color"] is None else mat["color"], (len(sph), 1))]
    alps = [np.full(len(sph), 1.0 - mat["transp"])]
    mids = [np.ones(len(sph), dtype=np.int32)]
    ntile = 10
    half = 5.0
    gt, gc = [], []
    for i in range(ntile):
        for j in range(ntile):
            x0, x1 = -half + i * 2 * half / ntile, -half + (i + 1) * 2 * half / ntile
            y0, y1 = -half + j * 2 * half / ntile, -half + (j + 1) * 2 * half / ntile
            c = (0.85, 0.85, 0.85) if (i + j) % 2 == 0 else (0.25, 0.30, 0.38)
            gt += [((x0, y0, 0), (x1, y0, 0), (x1, y1, 0)), ((x0, y0, 0), (x1, y1, 0), (x0, y1, 0))]
            gc += [c, c]
    tris = np.concatenate([sph, np.array(gt, dtype=float)])
    cols = np.concatenate(cols + [np.array(gc)])
    alps = np.concatenate(alps + [np.ones(len(gt))])
    mids = np.concatenate(mids + [np.zeros(len(gt), dtype=np.int32)])
    oids = np.concatenate([np.zeros(len(sph), dtype=np.int32), np.full(len(gt), -1, dtype=np.int32)])
    return Scene(tris, cols, alps, mids, [mat], oid=oids, onames=["preview"])


def render_preview(mat, w=280, h=210, shape="sphere"):
    """Malzemeyi küre (shape="cube": küp) üzerinde çizer. Döner: (h,w,3) uint8. Genel ayarlar geçici olarak değiştirilip geri yüklenir."""
    from .render import render
    sc = _preview_scene(mat, shape)
    saved = {k: getattr(S, k) for k in ("LIGHTS", "AMBIENT", "AMBIENT_COLOR", "FLOOR", "AA", "BOUNCES", "GLASS", "SMOOTH",
                                        "THREADS", "REFLECT_GLASS", "REFLECT_SURF", "IOR", "REFLECTIONS", "REFRACTION", "SPEC", "SHININESS",
                                        "AO", "SOFT_SHADOW", "TONEMAP", "EXPOSURE", "ENV_MODE")}
    try:
        S.LIGHTS = [dict(on=True, h=-35.0, v=45.0, color=(1, 1, 1), power=0.85, shadow=True),
                    dict(on=True, h=50.0, v=-5.0, color=(1, 1, 1), power=0.25, shadow=False),
                    dict(on=True, h=180.0, v=25.0, color=(1, 1, 1), power=0.4, shadow=False)]
        S.AMBIENT, S.AMBIENT_COLOR = 0.3, (1.0, 1.0, 1.0)
        S.ENV_MODE = "off"
        S.AO, S.SOFT_SHADOW, S.TONEMAP, S.EXPOSURE = False, 0.0, "none", 1.0      # önizleme hep hızlı: ana pencerenin AO / yumuşak gölge ayarları yansımasın
        S.FLOOR, S.AA, S.BOUNCES, S.GLASS, S.SMOOTH, S.THREADS = False, 0, 3, True, True, 1
        S.REFLECT_GLASS, S.REFLECT_SURF, S.IOR = 1.0, 0.0, 1.5
        S.REFLECTIONS, S.REFRACTION = True, True
        pos = np.array([0.0, -5.2, 2.6])
        tgt = np.array([0.0, 0.0, 0.85])
        cam = dict(pos=pos, fwd=(tgt - pos), up=np.array([0.0, 0.0, 1.0]), persp=True, size=np.radians(38))
        return render(sc, cam, w, h, shadows=True, tile=S.TILE)
    finally:
        for k, v in saved.items():
            setattr(S, k, v)


# ---------------------------------------------------------------- pencere
def _signature(shp):
    """Benzerlik imzası (ucuz; Area/Volume 877 parçada ~22 sn sürüyordu): şekil türü, yüz/kenar sayısı ve YEREL sınır kutusu
    (üst yerleşim sıfırlanır: aynı parçanın konum/dönmesi farklı kopyaları aynı imzayı verir). Mesh için üçgen sayısı.
    Not: shp bu işlev için gezilen geçici bir şekildir; yerleşimi değiştirmek güvenlidir."""
    try:
        if getattr(shp, "is_mesh", False):
            return ("m", len(shp.tri))
        import FreeCAD
        shp.Placement = FreeCAD.Placement()
        bb = shp.BoundBox
        return ("s", shp.ShapeType, shp.countElement("Face"), shp.countElement("Edge"),
                float("%.3g" % bb.XLength), float("%.3g" % bb.YLength), float("%.3g" % bb.ZLength))
    except Exception:
        return None


_scan_cache = {}     # doc imzası -> [(nesne, hedef, imza)]; "Yenile" düğmesi önbelleği atlar


def _renderable(doc):
    """Render motorunun gerçekten çizeceği nesneler (aynı tarama): görünür, yüzeyli gerçek şekiller.
    Origin/düzlem/eksen, Joint, boş kapsayıcılar ve gizli nesneler listede yer almaz.
    Döner: [(nesne, hedef, imza)] (kopyalar elenmiş). imza: _signature (benzer nesneleri bulmak için)."""
    from .freecad_scene import _gather
    out, seen = [], set()
    for o, tgt, shp, _sub in _gather(doc, lambda *_a: None):
        if o.Name in seen:
            continue
        seen.add(o.Name)
        out.append((o, tgt, _signature(shp)))
    return out


def open_surface(on_change=None, is_busy=None):
    import FreeCAD
    import FreeCADGui as Gui
    from PySide import QtGui, QtCore

    old = getattr(FreeCAD, "_ybt_surface_dlg", None)
    if old is not None:
        try:
            old.close()
        except Exception:
            pass
    doc = FreeCAD.ActiveDocument
    if doc is None:
        FreeCAD.Console.PrintError(T("RayTrace: açık belge yok.\n"))
        return None

    prm = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/FCYBTRayTracer")
    main_dlg = getattr(FreeCAD, "_raytrace_dlg", None)
    try:
        if main_dlg is not None and not main_dlg.isVisible():
            main_dlg = None
    except Exception:                                   # kapanmış (silinmiş) Qt nesnesi
        main_dlg = None
    pin0 = bool(prm.GetBool("SurfaceOnTop", True))
    # "en üstte": render penceresinin çocuğu (transient) olur; pencere yöneticisi onu her zaman ebeveyninin üstünde tutar
    # (Wayland'de de çalışır). Kapalıyken FreeCAD ana penceresinin çocuğudur: render penceresi onu örtebilir.
    dlg = QtGui.QDialog(main_dlg if (pin0 and main_dlg is not None) else None)
    dlg.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowMinimizeButtonHint | QtCore.Qt.WindowCloseButtonHint)
    dlg.setWindowTitle(T("Yüzey / Malzeme Düzenleyici"))
    dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

    def _save_doc(*_a):
        try:
            from . import docstore
            docstore.save(FreeCAD.ActiveDocument)               # kullanılan malzeme tanımları belgeyle birlikte saklanır
        except Exception:
            pass
    dlg.finished.connect(_save_doc)
    _theme.apply(dlg)                                           # koyu gri palet (ana pencereyle aynı)
    st = {"mat": M.normalize({}), "name": "", "lock": False, "items": []}
    widgets = {}

    root = QtGui.QHBoxLayout(dlg)
    # ---------- sol: nesneler + kütüphane
    left = QtGui.QVBoxLayout()
    hrow = QtGui.QHBoxLayout()
    hrow.addWidget(QtGui.QLabel("<b>%s</b>" % T("Nesneler")))
    hrow.addStretch(1)
    btn_pin = QtGui.QCheckBox(T("Her zaman üstte"))
    btn_pin.setChecked(pin0 and main_dlg is not None)
    btn_pin.setEnabled(main_dlg is not None)
    btn_pin.setToolTip(T("Açıkken bu pencere render penceresinin üstünde kalır (önizlemede tıklayınca arkaya kaçmaz). Kapatınca normal pencere gibi davranır."))
    hrow.addWidget(btn_pin)
    left.addLayout(hrow)
    frow = QtGui.QHBoxLayout()
    ed_filter = QtGui.QLineEdit()
    ed_filter.setPlaceholderText(T("Ara..."))
    ed_filter.setClearButtonEnabled(True)
    btn_scan = QtGui.QPushButton(T("Yenile"))
    btn_scan.setToolTip(T("Nesne listesini belgeden yeniden oku"))
    frow.addWidget(ed_filter, 1)
    frow.addWidget(btn_scan)
    left.addLayout(frow)
    tree = QtGui.QTreeWidget()
    tree.setColumnCount(3)
    tree.setHeaderLabels([T("Nesne"), T("Malzeme"), T("Benzer")])
    tree.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
    tree.setRootIsDecorated(False)
    tree.setMinimumWidth(300)
    tree.headerItem().setToolTip(2, T("Aynı şekle sahip nesne sayısı (aynı parçanın kopyaları / Link'ler)"))
    tree.headerItem().setToolTip(0, T("İşaretli nesneler render'a dahil edilir; işareti kaldırılanlar sahneye hiç alınmaz"))
    left.addWidget(tree, 3)
    inc_row = QtGui.QHBoxLayout()
    btn_inc = QtGui.QPushButton(T("Seçilileri dahil et"))
    btn_exc = QtGui.QPushButton(T("Seçilileri hariç tut"))
    btn_inc.setToolTip(T("Seçili nesnelerin kutusunu işaretler: render'a girerler"))
    btn_exc.setToolTip(T("Seçili nesnelerin işaretini kaldırır: render'a girmezler (gölge ve yansıma da vermezler)"))
    inc_row.addWidget(btn_inc)
    inc_row.addWidget(btn_exc)
    left.addLayout(inc_row)
    hint = QtGui.QLabel(T("Kutusu işaretli olmayan nesneler render'a girmez."))
    hint.setStyleSheet("color: gray;")
    left.addWidget(hint)
    ck_sim = QtGui.QCheckBox(T("Benzerleri birlikte seç"))
    ck_sim.setToolTip(T("Bir nesneyi seçince aynı şekle sahip tüm nesneler (kopyalar, Link'ler) de seçilir; "
                        "atama / dahil-hariç işlemleri hepsine uygulanır"))
    ck_grp = QtGui.QCheckBox(T("Benzerleri yan yana diz"))
    ck_grp.setToolTip(T("Listeyi şekle göre gruplar: aynı parçanın kopyaları art arda gelir"))
    btn_sim = QtGui.QPushButton(T("Benzerlerini seç"))
    btn_sim.setToolTip(T("Seçili nesnelerle aynı şekle sahip tüm nesneleri de seçer (bir kerelik)"))
    sim_row = QtGui.QHBoxLayout()
    sim_row.addWidget(ck_sim)
    sim_row.addWidget(ck_grp)
    sim_row.addWidget(btn_sim)
    left.addLayout(sim_row)
    btn_paint = QtGui.QPushButton(T("Boya kovası: önizlemeye tıkla"))
    btn_paint.setCheckable(True)
    btn_paint.setToolTip(T("Açıkken ana penceredeki render önizlemesinde bir parçaya tıklayınca, aşağıda düzenlenen malzeme "
                           "o parçaya atanır. Kapalıyken tıklama yalnızca parçayı listede seçer."))
    left.addWidget(btn_paint)
    left.addWidget(QtGui.QLabel("<b>%s</b>" % T("Malzeme kütüphanesi")))
    lst = QtGui.QListWidget()
    left.addWidget(lst, 3)
    ck_auto = QtGui.QCheckBox(T("Değişiklikleri seçili nesnelere otomatik uygula"))
    ck_auto.setToolTip(T("Sağdaki malzeme özelliklerini değiştirince, soldaki listede seçili nesnelere kendiliğinden atanır (ayrıca 'Seçili nesnelere ata' gerekmez)"))
    try:
        ck_auto.setChecked(bool(prm.GetBool("AutoApply", True)))
    except Exception:
        ck_auto.setChecked(True)
    ck_auto.toggled.connect(lambda on: prm.SetBool("AutoApply", bool(on)))
    left.addWidget(ck_auto)
    b_row = QtGui.QHBoxLayout()
    btn_assign = QtGui.QPushButton(T("Seçili nesnelere ata"))
    btn_clear = QtGui.QPushButton(T("Atamayı kaldır"))
    b_row.addWidget(btn_assign)
    b_row.addWidget(btn_clear)
    left.addLayout(b_row)
    root.addLayout(left, 0)

    # ---------- sağ: önizleme + parametreler
    right = QtGui.QVBoxLayout()
    prev = QtGui.QLabel()
    prev.setFixedSize(280, 210)
    prev.setAlignment(QtCore.Qt.AlignCenter)
    prev.setFrameShape(QtGui.QFrame.StyledPanel)
    right.addWidget(prev, 0, QtCore.Qt.AlignHCenter)
    shape_row = QtGui.QHBoxLayout()
    shape_row.addStretch(1)
    shape_row.addWidget(QtGui.QLabel(T("Önizleme şekli")))
    cb_shape = QtGui.QComboBox()
    cb_shape.addItem(T("Küre"), "sphere")
    cb_shape.addItem(T("Küp"), "cube")
    try:
        cb_shape.setCurrentIndex(1 if prm.GetString("PreviewShape", "sphere") == "cube" else 0)
    except Exception:
        pass
    shape_row.addWidget(cb_shape)
    shape_row.addStretch(1)
    right.addLayout(shape_row)
    t_buttons = {}                                         # kanal -> "T" (doku) düğmesi
    name_row = QtGui.QHBoxLayout()
    name_row.addWidget(QtGui.QLabel(T("Ad")))
    ed_name = QtGui.QLineEdit()
    name_row.addWidget(ed_name, 1)
    btn_color = QtGui.QPushButton("")
    btn_color.setFixedWidth(54)
    ck_fc = QtGui.QCheckBox(T("Renk: nesnenin FreeCAD rengi"))
    name_row.addWidget(btn_color)
    t_buttons["color"] = QtGui.QPushButton("T")
    name_row.addWidget(t_buttons["color"])
    right.addLayout(name_row)
    right.addWidget(ck_fc)
    grid = QtGui.QGridLayout()
    for r, (key, label, lo, hi, tip) in enumerate(_PARAMS):
        lb = QtGui.QLabel(T(label))
        lb.setToolTip(T(tip))
        sl = QtGui.QSlider(QtCore.Qt.Horizontal)
        sl.setRange(0, 1000)
        sp = QtGui.QDoubleSpinBox()
        sp.setRange(lo, hi)
        sp.setSingleStep(0.05)
        sp.setDecimals(2)
        sp.setToolTip(T(tip))
        grid.addWidget(lb, r, 0)
        grid.addWidget(sl, r, 1)
        grid.addWidget(sp, r, 2)
        if key in _CH_KEYS:
            t_buttons[key] = QtGui.QPushButton("T")
            grid.addWidget(t_buttons[key], r, 3, QtCore.Qt.AlignCenter)
        widgets[key] = (sl, sp, lo, hi)
    lb = QtGui.QLabel(T("Bump (yükseklik haritası)"))
    lb.setToolTip(T("Gri tonlu bir dokuyu kabartı olarak okur: yüzey normalini eğer, geometri değişmez"))
    grid.addWidget(lb, len(_PARAMS), 0, 1, 3)
    t_buttons["bump"] = QtGui.QPushButton("T")
    grid.addWidget(t_buttons["bump"], len(_PARAMS), 3, QtCore.Qt.AlignCenter)
    for _b in t_buttons.values():
        _b.setFixedSize(28, 14)                              # yükseklik 1 : genişlik 2
        _b.setSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
        _b.setStyleSheet(_T_CSS)
    right.addLayout(grid)
    b2 = QtGui.QHBoxLayout()
    btn_save = QtGui.QPushButton(T("Kütüphaneye kaydet"))
    btn_del = QtGui.QPushButton(T("Kütüphaneden sil"))
    btn_new = QtGui.QPushButton(T("Yeni surface"))
    btn_new.setToolTip(T("Gri, varsayılan değerli yeni bir yüzey oluşturur (LightWave'deki gibi) ve kütüphaneye ekler"))
    b2.addWidget(btn_new)
    b2.addWidget(btn_save)
    b2.addWidget(btn_del)
    right.addLayout(b2)
    class _Log(QtGui.QPlainTextEdit):
        """Konsol tarzı işlem günlüğü: her işlem zaman damgasıyla bir satır olarak eklenir."""

        def __init__(self):
            QtGui.QPlainTextEdit.__init__(self)
            self.setReadOnly(True)
            self.setMaximumBlockCount(500)
            self.setMinimumHeight(110)
            self.setLineWrapMode(QtGui.QPlainTextEdit.WidgetWidth)
            f = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
            self.setFont(f)
            self.setPlaceholderText(T("İşlem günlüğü"))
            self.last = ""

        def setText(self, t):
            self.last = t
            self.appendPlainText("[%s] %s" % (time.strftime("%H:%M:%S"), t))
            sb = self.verticalScrollBar()
            sb.setValue(sb.maximum())

        def text(self):
            return self.last
    lbl_msg = _Log()
    right.addWidget(lbl_msg, 1)
    root.addLayout(right, 1)

    # ---------- yardımcılar
    def msg(t):
        lbl_msg.setText(t)

    def color_css(c):
        if c is None:
            return ""
        return "background-color: rgb(%d,%d,%d);" % tuple(int(round(v * 255)) for v in c)

    timer = QtCore.QTimer(dlg)
    timer.setSingleShot(True)

    def do_preview():
        if is_busy is not None and is_busy():
            return
        try:
            img = render_preview(M.normalize(st["mat"]), 280, 210, cb_shape.currentData() or "sphere")
        except Exception as ex:
            msg("önizleme: %s" % ex)
            return
        a = np.ascontiguousarray(img)
        qi = QtGui.QImage(a.data, a.shape[1], a.shape[0], 3 * a.shape[1], QtGui.QImage.Format_RGB888).copy()
        prev.setPixmap(QtGui.QPixmap.fromImage(qi))

    timer.timeout.connect(do_preview)

    auto_timer = QtCore.QTimer(dlg)
    auto_timer.setSingleShot(True)
    auto_timer.timeout.connect(lambda: do_auto_apply())

    def schedule(delay=150, user=True):
        timer.start(delay)
        if user and not st["lock"]:                      # kullanıcı bir değer değiştirdi: seçili nesnelere otomatik uygula
            st["auto_names"] = [it.data(0, QtCore.Qt.UserRole) for it in tree.selectedItems()]   # hedef: değişiklik anındaki seçim
            auto_timer.start(600)

    def fill_editor(name, mat):
        st["lock"] = True
        st["name"], st["mat"] = name, M.normalize(mat)
        ed_name.setText(name)
        for key, (sl, sp, lo, hi) in widgets.items():
            v = st["mat"][key]
            sp.setValue(v)
            sl.setValue(int(round((v - lo) / (hi - lo) * 1000)))
        refresh_tex_buttons()
        ck_fc.setChecked(st["mat"]["color"] is None)
        btn_color.setStyleSheet(color_css(st["mat"]["color"] or (0.7, 0.7, 0.72)))
        btn_color.setEnabled(st["mat"]["color"] is not None)
        st["lock"] = False
        refill_pops()
        schedule(user=False)

    def make_param_handlers(key, sl, sp, lo, hi):
        def from_slider(v):
            if st["lock"]:
                return
            val = lo + v / 1000.0 * (hi - lo)
            st["lock"] = True
            sp.setValue(val)
            st["lock"] = False
            st["mat"][key] = val
            schedule(PREVIEW_DELAY_MS)

        def from_spin(val):
            if st["lock"]:
                return
            st["lock"] = True
            sl.setValue(int(round((val - lo) / (hi - lo) * 1000)))
            st["lock"] = False
            st["mat"][key] = float(val)
            schedule(PREVIEW_DELAY_MS)
        sl.valueChanged.connect(from_slider)
        sp.valueChanged.connect(from_spin)

    for key, (sl, sp, lo, hi) in widgets.items():
        make_param_handlers(key, sl, sp, lo, hi)

    pops = {}
    _CH_TITLE = dict(color="Renk", diffuse="Yayılı (diffuse)", spec="Parlaklık şiddeti (specular)", gloss="Parlaklık keskinliği (glossiness)",
                     refl="Yansıma", transp="Saydamlık", lum="Kendi ışığı (luminosity)", bump="Bump (yükseklik haritası)")

    def refresh_tex_buttons():
        for chn, b in t_buttons.items():
            b.setStyleSheet(_T_CSS + (_T_CSS_ON if M.has_layers(st["mat"], chn) else ""))
            b.setToolTip(T("Doku düzenleyici: ") + T(_CH_TITLE[chn]))

    def refill_pops():
        refresh_tex_buttons()
        for _c, (_d, _rf) in pops.items():
            _rf()

    def open_tex(chan):
        """LightWave tarzı doku düzenleyici: katman listesi + katman ayarları (görüntü / prosedürel)."""
        if chan in pops:
            d_, rf_ = pops[chan]
            rf_()
            d_.show()
            d_.raise_()
            return
        cur = {"i": 0, "lock": False}
        d = QtGui.QDialog(dlg)
        d.setWindowTitle(T("Doku Düzenleyici") + " - " + T(_CH_TITLE[chan]))
        _theme.apply(d)
        d.setMinimumSize(520, 400)
        hl = QtGui.QHBoxLayout(d)

        # ---------------- sol: katman listesi
        left_ = QtGui.QVBoxLayout()
        row1 = QtGui.QHBoxLayout()
        b_add = QtGui.QToolButton()
        b_add.setText(T("Katman ekle") + " ▾")
        b_add.setPopupMode(QtGui.QToolButton.InstantPopup)
        b_add.setStyleSheet("QToolButton { background-color: #58575c; border: 1px solid #26262a; border-radius: 3px; padding: 4px 10px; color: #d6d6d8; font-weight: normal; }"
                            "QToolButton::menu-indicator { image: none; }")
        mn = QtGui.QMenu(b_add)
        act_img = mn.addAction(T("Görüntü dokusu"))
        act_prc = mn.addAction(T("Prosedürel doku"))
        b_add.setMenu(mn)
        b_rm = QtGui.QPushButton(T("Katmanı kaldır"))
        row1.addWidget(b_add, 1)
        row1.addWidget(b_rm, 1)
        left_.addLayout(row1)
        row2 = QtGui.QHBoxLayout()
        b_cp = QtGui.QPushButton(T("Kopyala"))
        b_cp.setToolTip(T("Seçili katmanı panoya alır (başka kanallara ve malzemelere de yapıştırılabilir)"))
        b_ps = QtGui.QPushButton(T("Yapıştır"))
        b_ps.setToolTip(T("Panodaki katmanı seçili katmanın üstüne ekler"))
        b_up = QtGui.QPushButton("▲")
        b_dn = QtGui.QPushButton("▼")
        b_up.setToolTip(T("Katmanı üste taşı"))
        b_dn.setToolTip(T("Katmanı alta taşı"))
        for _w in (b_cp, b_ps):
            row2.addWidget(_w, 2)
        for _w in (b_up, b_dn):
            _w.setFixedWidth(32)
            row2.addWidget(_w)
        left_.addLayout(row2)
        tree_l = QtGui.QTreeWidget()
        tree_l.setHeaderLabels([T("Katman adı"), T("Opak"), "B"])
        tree_l.setRootIsDecorated(False)
        tree_l.setColumnWidth(0, 150)
        tree_l.setColumnWidth(1, 46)
        tree_l.setColumnWidth(2, 24)
        tree_l.setMinimumWidth(120)
        left_.addWidget(tree_l, 1)
        lb_hint = QtGui.QLabel(T("Üstteki katman üstte işlenir; her katman altındakinin üzerine blend moduyla karışır."))
        lb_hint.setWordWrap(True)
        lb_hint.setStyleSheet("color: #85858a;")
        left_.addWidget(lb_hint)
        left_w = QtGui.QWidget()                                  # sol bölüm yatayda daralabilsin (sağ panel öncelikli)
        left_w.setLayout(left_)
        left_w.setMinimumWidth(140)
        left_w.setSizePolicy(QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Preferred)
        left_.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(left_w, 2)

        # ---------------- sağ: katman ayarları
        right_ = QtGui.QVBoxLayout()
        right_.setSpacing(4)
        form = QtGui.QGridLayout()
        form.setColumnStretch(1, 1)
        form.setVerticalSpacing(4)

        def lab(t_):
            q = QtGui.QLabel(T(t_))
            q.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            return q

        form.addWidget(lab("Katman türü"), 0, 0)
        cb_type = QtGui.QComboBox()
        cb_type.addItem(T("Görüntü dokusu"), "image")
        cb_type.addItem(T("Prosedürel doku"), "proc")
        form.addWidget(cb_type, 0, 1, 1, 2)
        form.addWidget(lab("Blend modu"), 1, 0)
        cb_blend = QtGui.QComboBox()
        for k_, nm_ in M.BLENDS:
            cb_blend.addItem(T(nm_), k_)
        form.addWidget(cb_blend, 1, 1, 1, 2)
        form.addWidget(lab("Katman opaklığı"), 2, 0)
        sp_op = QtGui.QDoubleSpinBox()
        sp_op.setRange(0.0, 100.0)
        sp_op.setDecimals(1)
        sp_op.setSuffix(" %")
        form.addWidget(sp_op, 2, 1, 1, 2)
        b_inv = QtGui.QPushButton(T("Katmanı ters çevir"))
        b_inv.setCheckable(True)
        form.addWidget(b_inv, 3, 1, 1, 2)
        lb_pv = QtGui.QLabel()
        lb_pv.setFixedSize(100, 100)
        lb_pv.setAlignment(QtCore.Qt.AlignCenter)
        lb_pv.setFrameShape(QtGui.QFrame.StyledPanel)
        lb_pv.setStyleSheet("background-color: #2a2a2c; border: 1px solid #6b7e92;")
        lb_pv.setToolTip(T("Katman önizlemesi: dokunun bir tekrarı (ayarlar değişince güncellenir)"))
        form.addWidget(lb_pv, 5, 1, 1, 2, QtCore.Qt.AlignHCenter)
        lb_bh = lab("Bump yüksekliği")
        sp_bh = QtGui.QDoubleSpinBox()
        sp_bh.setRange(0.0, 2000.0)
        sp_bh.setDecimals(0)
        sp_bh.setSuffix(" %")
        sp_bh.setToolTip(T("Kabartı yüksekliği: %100 = doku boyunun yaklaşık %3'ü (tüm bump katmanları için)"))
        form.addWidget(lb_bh, 4, 0)
        form.addWidget(sp_bh, 4, 1, 1, 2)
        lb_bh.setVisible(chan == "bump")
        sp_bh.setVisible(chan == "bump")
        right_.addLayout(form)

        # katmana özgü bölüm
        stk = QtGui.QStackedWidget()
        pg_img = QtGui.QWidget()
        gi = QtGui.QGridLayout(pg_img)
        gi.setContentsMargins(0, 4, 0, 4)
        gi.setColumnStretch(1, 1)
        gi.addWidget(lab("Projeksiyon"), 0, 0)
        cb_proj = QtGui.QComboBox()
        for k_, nm_ in (("cubic", "Küp (3 yönlü)"), ("planar", "Düzlemsel"), ("cylindrical", "Silindirik"), ("spherical", "Küresel")):
            cb_proj.addItem(T(nm_), k_)
        cb_proj.setToolTip(T("Küp: üç yönden izdüşüm (UV gerekmez). Düzlemsel: tek eksen boyunca. Silindirik/Küresel: nesne merkezi etrafında sarar."))
        gi.addWidget(cb_proj, 0, 1)
        gi.addWidget(lab("Görüntü"), 1, 0)
        cb_img = QtGui.QComboBox()
        cb_img.addItem(T("(yok)"), "")
        for k_, nm_, _fn, _md, _rl in _tex.PRESETS:
            cb_img.addItem(T(nm_), k_)
        _tdir = _paths.texture_dir()
        for n_ in _paths.list_files(_tdir, _paths.IMG_EXT):          # doku klasöründeki görüntüler
            cb_img.addItem(T("Klasör: ") + n_, os.path.join(_tdir, n_))
        cb_img.addItem(T("Dosyadan yükle..."), "__file__")
        gi.addWidget(cb_img, 1, 1)
        b_load = QtGui.QPushButton(T("Görüntü yükle..."))
        b_load.setToolTip(T("Bilgisayardan bir görüntü dosyası (PNG, JPG, BMP) seç ve bu katmanın dokusu yap"))
        gi.addWidget(b_load, 2, 1)
        stk.addWidget(pg_img)

        pg_prc = QtGui.QWidget()
        gp = QtGui.QGridLayout(pg_prc)
        gp.setContentsMargins(0, 4, 0, 4)
        gp.setColumnStretch(1, 1)
        gp.addWidget(lab("Prosedürel tür"), 0, 0)
        cb_pt = QtGui.QComboBox()
        for k_, nm_ in _proc.TYPES:
            cb_pt.addItem(T(nm_), k_)
        gp.addWidget(cb_pt, 0, 1, 1, 2)
        pw = {}

        def padd(row_, key, label, lo_, hi_, step_, dec_, tip="", suf=""):
            gp.addWidget(lab(label), row_, 0)
            sp_ = QtGui.QDoubleSpinBox()
            sp_.setRange(lo_, hi_)
            sp_.setSingleStep(step_)
            sp_.setDecimals(dec_)
            if suf:
                sp_.setSuffix(suf)
            if tip:
                sp_.setToolTip(T(tip))
            gp.addWidget(sp_, row_, 1, 1, 2)
            pw[key] = sp_
        padd(1, "pvalue", "Doku değeri", 0.0, 1.0, 0.05, 2, "Desenin en büyük değeri (genlik)")
        padd(2, "pfreq", "Frekanslar", 1, 8, 1, 0, "Gürültü katman (oktav) sayısı: arttıkça ince ayrıntı artar")
        padd(3, "pcontrast", "Kontrast", -100.0, 100.0, 5.0, 0, "Desenin kontrastı", " %")
        padd(4, "ppower", "Küçük güç", 0.05, 0.95, 0.05, 2, "İnce ayrıntı katmanlarının payı (düşük = yumuşak)")
        padd(5, "pstripes", "Desen sıklığı", 0.1, 500.0, 0.5, 1, "Mermer/ahşap/dalga: çizgi sayısı; dama/ızgara/nokta/tuğla: hücre sayısı (doku boyu başına)")
        padd(6, "pseed", "Tohum", 0, 9999, 1, 0, "Aynı ayarlarla farklı bir desen")
        lb_c1, lb_c2 = lab("Renk 1 (koyu)"), lab("Renk 2 (açık)")
        b_c1, b_c2 = QtGui.QPushButton(""), QtGui.QPushButton("")
        gp.addWidget(lb_c1, 7, 0)
        gp.addWidget(b_c1, 7, 1, 1, 2)
        gp.addWidget(lb_c2, 8, 0)
        gp.addWidget(b_c2, 8, 1, 1, 2)
        for _w in (lb_c1, lb_c2, b_c1, b_c2):
            _w.setVisible(chan == "color")
        stk.addWidget(pg_prc)

        def fit_stack(*_a):                                       # yığın en yüksek sayfaya göre değil, görünen sayfaya göre boy alsın (görüntü sayfasında boşluk kalmasın)
            for i_ in range(stk.count()):
                pg_ = stk.widget(i_)
                pg_.setSizePolicy(QtGui.QSizePolicy.Preferred,
                                  QtGui.QSizePolicy.Preferred if i_ == stk.currentIndex() else QtGui.QSizePolicy.Ignored)
            stk.updateGeometry()
        stk.currentChanged.connect(fit_stack)
        fit_stack()
        right_.addWidget(stk)

        # ortak yerleşim
        gp2 = QtGui.QGridLayout()
        gp2.addWidget(lab("Doku ekseni"), 0, 0)
        ax_b = []
        for i_, nm_ in enumerate("XYZ"):
            bb = QtGui.QPushButton(nm_)
            bb.setCheckable(True)
            ax_b.append(bb)
            gp2.addWidget(bb, 0, 1 + i_)
        ax_b[2].setToolTip(T("Düzlemsel: dokunun baktığı eksen. Silindirik/Küresel: kutup ekseni. Prosedürel: çizgi/halka ekseni."))
        b_world = QtGui.QPushButton(T("Dünya koordinatları"))
        b_world.setCheckable(True)
        b_world.setToolTip(T("Kapalı: doku nesnenin merkezine bağlıdır, nesneyle birlikte gider. Açık: doku sabit uzayda durur (nesne hareket edince kayar)."))
        b_auto = QtGui.QPushButton(T("Otomatik boyutlandır"))
        b_auto.setCheckable(True)
        b_auto.setToolTip(T("Açıkken görüntü nesnenin yüzüne tam oturur (tek kez, nesnenin boyutuna gerilir). Kapalıyken doku döşenir (tekrar eder). Açınca ölçek 1, konum 0 olur."))
        cb_tile = QtGui.QComboBox()
        for k_, nm_ in (("auto", "Otomatik (dokunun kendi modu)"), ("repeat", "Tekrar (düz döşeme)"), ("mirror", "Ayna (kenarlar aynalanır)")):
            cb_tile.addItem(T(nm_), k_)
        cb_tile.setToolTip(T("Döşeme: Tekrar = doku aynen yan yana (dikiş görünebilir); Ayna = her ikinci karo ters çevrilir (dikiş görünmez). Otomatik: hazır dokunun kendi ayarı, kendi dosyalarda ayna. 'Otomatik boyutlandır' açıkken döşeme yoktur."))
        gp2.addWidget(lab("Döşeme"), 3, 0)
        gp2.addWidget(cb_tile, 3, 1, 1, 3)
        gp2.addWidget(b_world, 1, 1, 1, 3)
        gp2.addWidget(b_auto, 2, 1, 1, 3)
        gp2.setColumnStretch(1, 1)
        gp2.setColumnStretch(2, 1)
        gp2.setColumnStretch(3, 1)
        right_.addLayout(gp2)
        tabs = QtGui.QTabWidget()
        tsp = {}
        sp_size = QtGui.QDoubleSpinBox()
        sp_size.setRange(0.0, 100000.0)
        sp_size.setDecimals(1)
        sp_size.setSingleStep(10.0)
        sp_size.setToolTip(T("Dokunun bir tekrarının nesne üzerindeki genişliği (belge birimi, mm). 0 = otomatik"))
        for ti_, (ttl, pref, lo_, hi_, stp_, dec_, suf_) in enumerate((
                (T("Ölçek"), "tex_s", 0.01, 1000.0, 0.1, 2, ""),
                (T("Konum"), "tex_p", -1e6, 1e6, 10.0, 1, " mm"),
                (T("Dönme"), "tex_r", -360.0, 360.0, 5.0, 1, "°"))):
            pgw = QtGui.QWidget()
            pgw.setObjectName("ybtpage")
            tg = QtGui.QGridLayout(pgw)
            tg.setColumnStretch(1, 1)
            r0 = 0
            if ti_ == 0:
                tg.addWidget(lab("Doku boyu (mm; 0 = otomatik)"), 0, 0)
                tg.addWidget(sp_size, 0, 1)
                r0 = 1
            for c_, ax_ in enumerate("xyz"):
                lb_ = QtGui.QLabel(ax_.upper())
                lb_.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                sp_ = QtGui.QDoubleSpinBox()
                sp_.setRange(lo_, hi_)
                sp_.setSingleStep(stp_)
                sp_.setDecimals(dec_)
                if suf_:
                    sp_.setSuffix(suf_)
                tg.addWidget(lb_, r0 + c_, 0)
                tg.addWidget(sp_, r0 + c_, 1)
                tsp[pref + ax_] = sp_
            tabs.addTab(pgw, ttl)
        right_.addWidget(tabs)
        right_.addStretch(1)
        b_clr = QtGui.QPushButton(T("Tüm katmanları kaldır"))
        b_close = QtGui.QPushButton(T("Kapat"))
        brow = QtGui.QHBoxLayout()
        brow.addWidget(b_clr)
        brow.addWidget(b_close)
        right_.addLayout(brow)
        right_w = QtGui.QWidget()
        right_w.setObjectName("ybtpage")
        right_w.setLayout(right_)
        right_sc = QtGui.QScrollArea()                            # pencere küçülünce üst üste binmesin: kaydırma çubuğu
        right_sc.setWidgetResizable(True)
        right_sc.setFrameShape(QtGui.QFrame.NoFrame)
        right_sc.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        right_sc.setWidget(right_w)
        right_sc.viewport().setAutoFillBackground(False)
        right_sc.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        right_w.setAutoFillBackground(False)
        right_w.setStyleSheet("QWidget#ybtpage { background: transparent; }")
        hl.addWidget(right_sc, 3)

        common = [cb_type, cb_blend, sp_op, b_inv, sp_bh, cb_proj, cb_tile, cb_img, cb_pt, b_c1, b_c2, b_world, b_auto, sp_size] + ax_b + \
            list(pw.values()) + list(tsp.values())
        BL_LETTER = dict(normal="N", add="+", sub="-", mul="x", div="/", diff="D", screen="S", max="L", min="K")

        def lays():
            return M.layers_of(st["mat"], chan)

        def layer_preview(L, n=132):
            """Katmanın tek tekrarlık küçük önizlemesi (n,n,3 uint8). Prosedürel: desen; görüntü: dosyanın kendisi."""
            rgb = None
            if L["type"] == "proc":
                g = (np.arange(n) + 0.5) / n - 0.5
                U, Vv = np.meshgrid(g, g)
                ax = int(L["tex_axis"])
                a_, b_ = ((1, 2), (0, 2), (0, 1))[ax]
                p = np.zeros((n * n, 3))
                p[:, a_] = U.ravel()
                p[:, b_] = -Vv.ravel()
                q = dict(L)
                q["axis"] = ax
                v = _proc.evaluate(L["ptype"], p, q, np.full(n * n, 0.5 / n)).reshape(n, n)
                if L["invert"]:
                    v = 1.0 - v
                if chan == "color":
                    c1 = np.array(L["pcolor1"], dtype=float)
                    c2 = np.array(L["pcolor2"], dtype=float)
                    rgb = c1[None, None, :] + (c2 - c1)[None, None, :] * v[:, :, None]
                else:
                    rgb = np.repeat(v[:, :, None], 3, axis=2)
            else:
                tx = _tex.load(L["tex"], L.get("tile")) if L.get("tex") else None
                if tx is not None:
                    a = tx.levels[0]
                    hh, ww = a.shape[:2]
                    if tx.span == 2:
                        hh, ww = hh // 2, ww // 2
                    ys = np.minimum((np.arange(n) + 0.5) / n * hh, hh - 1).astype(int)
                    xs = np.minimum((np.arange(n) + 0.5) / n * ww, ww - 1).astype(int)
                    rgb = np.clip(a[ys][:, xs][:, :, :3], 0.0, 1.0) ** (1.0 / 2.2)
                    if L["invert"]:
                        rgb = 1.0 - rgb
                    if chan != "color":
                        gy = rgb.mean(axis=2, keepdims=True)
                        rgb = np.repeat(gy, 3, axis=2)
            if rgb is None:
                yy, xx = np.mgrid[0:n, 0:n]
                chk = (((yy // 12) + (xx // 12)) & 1).astype(float) * 0.12 + 0.12
                rgb = np.repeat(chk[:, :, None], 3, axis=2)
            return np.ascontiguousarray((np.clip(rgb, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8))

        def update_preview():
            ls = lays()
            if not ls:
                lb_pv.clear()
                return
            try:
                a = layer_preview(cur_layer())
                qi = QtGui.QImage(a.data, a.shape[1], a.shape[0], 3 * a.shape[1], QtGui.QImage.Format_RGB888).copy()
                lb_pv.setPixmap(QtGui.QPixmap.fromImage(qi))
            except Exception as ex:
                msg("önizleme: %s" % ex)

        def cur_layer():
            ls = lays()
            if not ls:
                return None
            cur["i"] = min(max(cur["i"], 0), len(ls) - 1)
            return ls[cur["i"]]

        def layer_label(L, i):
            if L.get("name"):
                return L["name"]
            if L.get("type") == "proc":
                return T("P: ") + T(dict(_proc.TYPES).get(L.get("ptype"), ""))
            return T("I: ") + (T(dict((k_, n_) for k_, n_, _f, _m, _r in _tex.PRESETS).get(L.get("tex"), ""))
                                 or os.path.basename(L.get("tex", "")) or T("(yok)"))

        def fill_tree():
            ls = lays()
            tree_l.blockSignals(True)
            tree_l.clear()
            for r_ in range(len(ls)):                            # üstteki katman listenin başında
                i = len(ls) - 1 - r_
                L = ls[i]
                it = QtGui.QTreeWidgetItem([layer_label(L, i), "%d%%" % round(L["opacity"] * 100), BL_LETTER.get(L["blend"], "N")])
                it.setData(0, QtCore.Qt.UserRole, i)
                it.setFlags(it.flags() | QtCore.Qt.ItemIsUserCheckable)
                it.setCheckState(0, QtCore.Qt.Checked if L.get("on", True) else QtCore.Qt.Unchecked)
                tree_l.addTopLevelItem(it)
                if i == cur["i"]:
                    tree_l.setCurrentItem(it)
            tree_l.blockSignals(False)

        def update_row():
            L = cur_layer()
            it = tree_l.currentItem()
            if L is None or it is None:
                return
            tree_l.blockSignals(True)
            it.setText(0, layer_label(L, cur["i"]))
            it.setText(1, "%d%%" % round(L["opacity"] * 100))
            it.setText(2, BL_LETTER.get(L["blend"], "N"))
            tree_l.blockSignals(False)

        def paint_color_btn(b, c):
            b.setStyleSheet(color_css(c))

        def load_layer():
            L = cur_layer()
            en = L is not None
            for w_ in common:
                w_.setEnabled(en)
            sp_bh.setValue(round(float(st["mat"].get("bump_height", 1.0)) * 100))
            b_rm.setEnabled(en)
            b_cp.setEnabled(en)
            b_up.setEnabled(en and cur["i"] < len(lays()) - 1)
            b_dn.setEnabled(en and cur["i"] > 0)
            b_ps.setEnabled(bool(_LAYER_CLIP))
            b_clr.setEnabled(en)
            if not en:
                lb_pv.clear()
                return
            for w_ in common:
                w_.blockSignals(True)
            cb_type.setCurrentIndex(1 if L["type"] == "proc" else 0)
            stk.setCurrentIndex(1 if L["type"] == "proc" else 0)
            cb_blend.setCurrentIndex(max(0, cb_blend.findData(L["blend"])))
            sp_op.setValue(L["opacity"] * 100.0)
            b_inv.setChecked(L["invert"])
            cb_proj.setCurrentIndex(max(0, cb_proj.findData(L["tex_proj"])))
            cb_tile.setCurrentIndex(max(0, cb_tile.findData(L.get("tile", "auto"))))
            k = cb_img.findData(L["tex"])
            if k < 0 and L["tex"]:                               # kullanıcı dosyası: listede göster
                cb_img.insertItem(cb_img.count() - 1, T("Dosya: ") + os.path.basename(L["tex"]), L["tex"])
                k = cb_img.findData(L["tex"])
            cb_img.setCurrentIndex(max(0, k))
            cb_pt.setCurrentIndex(max(0, cb_pt.findData(L["ptype"])))
            for k_, sp_ in pw.items():
                sp_.setValue(float(L[k_]))
            paint_color_btn(b_c1, L["pcolor1"])
            paint_color_btn(b_c2, L["pcolor2"])
            for i_, bb in enumerate(ax_b):
                bb.setChecked(L["tex_axis"] == i_)
            b_world.setChecked(L["tex_world"])
            b_auto.setChecked(L["tex_fit"])
            sp_size.setValue(float(L["tex_scale"]))
            for k_, sp_ in tsp.items():
                sp_.setValue(float(L[k_]))
            for w_ in common:
                w_.blockSignals(False)
            pl_axis = L["tex_proj"] != "cubic" or L["type"] == "proc"
            for bb in ax_b:
                bb.setEnabled(pl_axis)
            update_preview()

        def refill():
            cur["lock"] = True
            fill_tree()
            load_layer()
            cur["lock"] = False

        def changed_layers():
            fill_tree()
            load_layer()
            refresh_tex_buttons()
            schedule(PREVIEW_DELAY_MS)

        def on_edit(*_a):
            if cur["lock"]:
                return
            L = cur_layer()
            if L is None:
                return
            newtype = "proc" if cb_type.currentData() == "proc" else "image"
            L["type"] = newtype
            L["blend"] = cb_blend.currentData() or "normal"
            L["opacity"] = sp_op.value() / 100.0
            L["invert"] = b_inv.isChecked()
            L["tex_proj"] = cb_proj.currentData() or "cubic"
            L["tile"] = cb_tile.currentData() or "auto"
            if cb_img.currentData() != "__file__":
                L["tex"] = cb_img.currentData() or ""
            L["ptype"] = cb_pt.currentData() or "turbulence"
            for k_, sp_ in pw.items():
                L[k_] = int(round(sp_.value())) if k_ in ("pfreq", "pseed") else float(sp_.value())
            ax_now = next((i_ for i_, bb in enumerate(ax_b) if bb.isChecked() and i_ != L["tex_axis"]), L["tex_axis"])
            L["tex_axis"] = ax_now
            L["tex_world"] = b_world.isChecked()
            L["tex_scale"] = float(sp_size.value())
            for k_, sp_ in tsp.items():
                L[k_] = float(sp_.value())
            st["mat"]["bump_height"] = sp_bh.value() / 100.0
            if newtype != ("proc" if stk.currentIndex() == 1 else "image"):
                stk.setCurrentIndex(1 if newtype == "proc" else 0)
            for i_, bb in enumerate(ax_b):
                bb.blockSignals(True)
                bb.setChecked(L["tex_axis"] == i_)
                bb.blockSignals(False)
            update_row()
            refresh_tex_buttons()
            for bb in ax_b:
                bb.setEnabled(L["tex_proj"] != "cubic" or L["type"] == "proc")
            update_preview()
            schedule(PREVIEW_DELAY_MS)

        def load_external(path=None):
            """Bilgisayardan (path verilmişse o dosyayı, yoksa seçtirerek) görüntü al ve seçili katmanın dokusu yap."""
            L = cur_layer()
            if L is None:
                return
            if path is None:
                start = _paths.texture_dir() or (os.path.dirname(L["tex"]) if L.get("tex") and os.path.isfile(L["tex"])
                                                 else _LAST_DIR.get("p", os.path.expanduser("~")))
                res = QtGui.QFileDialog.getOpenFileName(d, T("Doku görüntüsü seç"), start,
                                                        T("Görüntü (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.gif *.webp)"))
                path = res[0] if isinstance(res, (tuple, list)) else res
            ok = False
            if path:
                _LAST_DIR["p"] = os.path.dirname(path)
                _tex._CACHE.pop(path, None)
                ok = _tex.load(path) is not None
                if ok:
                    L["tex"] = path
                    L["type"] = "image"
                    L["tex_fit"] = True                               # kullanıcı görüntüsü: varsayılan olarak nesneye sığdır
                    L["tex_scale"] = 0.0
                else:
                    msg(T("Görüntü okunamadı: ") + path)
            cur["lock"] = True
            load_layer()                                          # seçimi (yeni dosya ya da önceki) yeniden göster
            cur["lock"] = False
            if ok:
                update_row()
                refresh_tex_buttons()
                schedule(PREVIEW_DELAY_MS)

        def on_img(_i):
            if cur["lock"]:
                return
            data_ = cb_img.currentData()
            if data_ == "__file__":
                load_external()
                return
            if data_ and data_ not in _preset_keys and os.path.isabs(str(data_)):     # doku klasöründeki dosya: kendi görüntüsü gibi yüklenir
                load_external(data_)
                return
            on_edit()

        def pick_pcolor(key, btn):
            L = cur_layer()
            if L is None:
                return
            c0 = L[key]
            col = QtGui.QColorDialog.getColor(QtGui.QColor(*[int(round(v * 255)) for v in c0]), d, T("Renk"))
            if col.isValid():
                L[key] = (col.red() / 255.0, col.green() / 255.0, col.blue() / 255.0)
                paint_color_btn(btn, L[key])
                update_preview()
                refresh_tex_buttons()
                schedule(PREVIEW_DELAY_MS)

        def add_layer(kind):
            ls = lays()
            ls.append(M.new_layer(kind))
            cur["i"] = len(ls) - 1
            changed_layers()

        def del_layer():
            ls = lays()
            if ls:
                del ls[cur["i"]]
                cur["i"] = min(cur["i"], len(ls) - 1)
                if not ls:
                    st["mat"].get("tex_layers", {}).pop(chan, None)
                changed_layers()

        def clear_layers():
            st["mat"].get("tex_layers", {}).pop(chan, None)
            cur["i"] = 0
            changed_layers()

        def copy_layer():
            L = cur_layer()
            if L is not None:
                _LAYER_CLIP.clear()
                _LAYER_CLIP.update(dict(L))
                for _c, (_d, _rf) in pops.items():
                    _rf()
                msg(T("Katman kopyalandı: ") + T(_CH_TITLE[chan]))

        def paste_layer():
            if not _LAYER_CLIP:
                return
            ls = lays()
            pos = (cur["i"] + 1) if ls else 0
            ls.insert(pos, M.norm_layer(dict(_LAYER_CLIP)))
            cur["i"] = pos
            changed_layers()
            msg(T("Katman yapıştırıldı: ") + T(_CH_TITLE[chan]))

        def move(delta):
            ls = lays()
            j = cur["i"] + delta
            if 0 <= j < len(ls):
                ls[cur["i"]], ls[j] = ls[j], ls[cur["i"]]
                cur["i"] = j
                changed_layers()

        def on_tree_sel():
            if cur["lock"]:
                return
            it = tree_l.currentItem()
            if it is not None:
                cur["i"] = int(it.data(0, QtCore.Qt.UserRole))
                cur["lock"] = True
                load_layer()
                cur["lock"] = False

        def on_tree_check(it, col):
            if cur["lock"] or col != 0:
                return
            ls = lays()
            i = int(it.data(0, QtCore.Qt.UserRole))
            if 0 <= i < len(ls):
                ls[i]["on"] = it.checkState(0) == QtCore.Qt.Checked
                refresh_tex_buttons()
                schedule(PREVIEW_DELAY_MS)

        def on_auto(on):
            if cur["lock"]:
                return
            L = cur_layer()
            if L is None:
                return
            L["tex_fit"] = bool(on)
            if on:                                                # LightWave "Automatic Sizing": ölçek 1, konum 0, nesneye sığdır
                L["tex_scale"] = 0.0
                for k_ in ("tex_sx", "tex_sy", "tex_sz"):
                    L[k_] = 1.0
                for k_ in ("tex_px", "tex_py", "tex_pz"):
                    L[k_] = 0.0
            cur["lock"] = True
            load_layer()
            cur["lock"] = False
            update_row()
            schedule(PREVIEW_DELAY_MS)

        for w_ in (cb_type, cb_blend, cb_proj, cb_pt, cb_tile):
            w_.currentIndexChanged.connect(on_edit)
        cb_img.currentIndexChanged.connect(on_img)
        b_load.clicked.connect(lambda *_a: load_external())
        for w_ in [sp_op, sp_bh, sp_size] + list(pw.values()) + list(tsp.values()):
            w_.valueChanged.connect(on_edit)
        for w_ in [b_inv, b_world] + ax_b:
            w_.toggled.connect(on_edit)
        b_c1.clicked.connect(lambda *_a: pick_pcolor("pcolor1", b_c1))
        b_c2.clicked.connect(lambda *_a: pick_pcolor("pcolor2", b_c2))
        act_img.triggered.connect(lambda *_a: add_layer("image"))
        act_prc.triggered.connect(lambda *_a: add_layer("proc"))
        b_rm.clicked.connect(del_layer)
        b_clr.clicked.connect(clear_layers)
        b_cp.clicked.connect(copy_layer)
        b_ps.clicked.connect(paste_layer)
        b_up.clicked.connect(lambda *_a: move(1))
        b_dn.clicked.connect(lambda *_a: move(-1))
        b_auto.toggled.connect(on_auto)
        b_close.clicked.connect(d.hide)
        tree_l.currentItemChanged.connect(lambda *_a: on_tree_sel())
        tree_l.itemChanged.connect(on_tree_check)
        pops[chan] = (d, refill)
        refill()
        _theme.fix_combos(d)
        d.show()

    for _chn, _b in t_buttons.items():
        _b.clicked.connect(lambda _c=False, c=_chn: open_tex(c))

    def on_shape_changed(_i):
        try:
            prm.SetString("PreviewShape", cb_shape.currentData() or "sphere")
        except Exception:
            pass
        schedule(user=False)
    cb_shape.currentIndexChanged.connect(on_shape_changed)

    def on_fc_toggle(on):
        if st["lock"]:
            return
        if on:
            st["mat"]["color"] = None
        else:
            st["mat"]["color"] = (0.7, 0.7, 0.72)
        btn_color.setEnabled(not on)
        btn_color.setStyleSheet(color_css(st["mat"]["color"] or (0.7, 0.7, 0.72)))
        schedule()
    ck_fc.toggled.connect(on_fc_toggle)

    def pick_color():
        c0 = st["mat"]["color"] or (0.7, 0.7, 0.72)
        col = QtGui.QColorDialog.getColor(QtGui.QColor(*[int(round(v * 255)) for v in c0]), dlg, T("Malzeme rengi"))
        if col.isValid():
            st["mat"]["color"] = (col.red() / 255.0, col.green() / 255.0, col.blue() / 255.0)
            btn_color.setStyleSheet(color_css(st["mat"]["color"]))
            schedule()
    btn_color.clicked.connect(pick_color)

    def display_name(n):
        return T(n) if n in M.BUILTIN else n

    def doc_key():
        return (doc.Name, len(doc.Objects), hash(tuple((o.Name, bool(getattr(o, "Visibility", True))) for o in doc.Objects)))

    def rescan(force=False):
        """Gerçekten çizilecek nesneleri tarar; belge değişmediyse önbellekten alır (büyük montajlarda açılış hızlı)."""
        k = doc_key()
        if not force and k in _scan_cache:
            st["items"] = _scan_cache[k]
            return True
        try:
            st["items"] = _renderable(doc)
            _scan_cache.clear()
            _scan_cache[k] = st["items"]
        except Exception as ex:
            st["items"] = []
            msg("tarama: %s" % ex)
        return False

    def style_item(it, inc):
        """Hariç tutulan nesne soluk gösterilir."""
        try:
            brush = QtGui.QBrush(QtGui.QColor(128, 128, 128)) if not inc else QtGui.QBrush()
            for c in (0, 1, 2):
                it.setForeground(c, brush)
        except Exception:
            pass

    def sim_info():
        """nesne adı -> benzerlik grubu (aynı imza); grup boyutları ve ilk görülme sırası."""
        grp, size, order = {}, {}, {}
        for o, _tgt, sig in st["items"]:
            key = sig if sig is not None else ("u", o.Name)      # imzası olmayan tek başına
            grp[o.Name] = key
            size[key] = size.get(key, 0) + 1
            order.setdefault(key, len(order))
        return grp, size, order

    def similar_names(names):
        """Verilen nesnelerle aynı gruptaki tüm nesne adları (kendileri dahil)."""
        grp, _size, _order = sim_info()
        keys = {grp[n] for n in names if n in grp}
        return {n for n, k in grp.items() if k in keys} | set(names)

    def refresh_tree():
        sel = {it.data(0, QtCore.Qt.UserRole) for it in tree.selectedItems()}
        flt = ed_filter.text().strip().lower()
        grp, size, order = sim_info()
        rows = list(st["items"])
        if ck_grp.isChecked():
            rows.sort(key=lambda r: (order.get(grp.get(r[0].Name), 0), r[0].Label.lower()))
        st["tlock"] = True                          # onay kutusu değişim sinyali yeniden doldururken çalışmasın
        try:
            tree.clear()
            for o, tgt, _sig in rows:
                label = o.Label
                if flt and flt not in label.lower() and flt not in M.assigned(o).lower():
                    continue
                mn = M.assigned(o)
                n_sim = size.get(grp.get(o.Name), 1)
                it = QtGui.QTreeWidgetItem([label, display_name(mn) if mn else "—", ("×%d" % n_sim) if n_sim > 1 else ""])
                it.setData(0, QtCore.Qt.UserRole, o.Name)
                it.setFlags(it.flags() | QtCore.Qt.ItemIsUserCheckable)
                inc = M.included(o)
                it.setCheckState(0, QtCore.Qt.Checked if inc else QtCore.Qt.Unchecked)
                style_item(it, inc)
                tree.addTopLevelItem(it)
                if o.Name in sel:
                    it.setSelected(True)
            tree.resizeColumnToContents(0)
        finally:
            st["tlock"] = False

    def refresh_lib(select=None):
        lst.clear()
        lib = M.library()
        user = M.load_user()
        shown = set()

        def add_item(n, indent=True):
            label = display_name(n) + ("" if n in M.BUILTIN and n not in user else "  ★")
            it = QtGui.QListWidgetItem(("   " if indent else "") + label)
            it.setData(QtCore.Qt.UserRole, n)
            lst.addItem(it)
            shown.add(n)
            if n == select:
                lst.setCurrentItem(it)

        def add_header(t):
            it = QtGui.QListWidgetItem(t)
            it.setFlags(QtCore.Qt.ItemIsEnabled)                 # seçilemez başlık
            f = it.font()
            f.setBold(True)
            it.setFont(f)
            it.setForeground(QtGui.QBrush(QtGui.QColor(_theme.ACCENT_LIGHT)))
            lst.addItem(it)

        for cat, names in M.CATEGORIES:
            have = [n for n in names if n in lib]
            if have:
                add_header(T(cat))
                for n in have:
                    add_item(n)
        mine = [n for n in lib if n not in shown]
        if mine:
            add_header(T("Benim malzemelerim"))
            for n in mine:
                add_item(n)

    def sel_objects():
        return [o for o in (doc.getObject(it.data(0, QtCore.Qt.UserRole)) for it in tree.selectedItems()) if o is not None]

    def changed():
        refresh_tree()
        if on_change is not None:
            on_change()

    def commit_current():
        """Düzenleyicideki malzemeyi kütüphanede güncel tut; döner: ad."""
        name = ed_name.text().strip()
        if not name:
            msg(T("Önce malzemeye bir ad verin."))
            return None
        cur = M.normalize(st["mat"])
        lib = M.library()
        if name in lib and M.normalize(lib[name]) == cur:
            return name
        if name in M.BUILTIN:                       # hazır malzemenin üzerine yazma: kopya adıyla kaydet
            name = name + " (" + T("özel") + ")"
            ed_name.setText(name)
        user = M.load_user()
        user[name] = cur
        M.save_user(user)
        refresh_lib(name)
        return name

    def do_assign():
        objs = sel_objects()
        if not objs:
            msg(T("Önce soldaki listeden nesne seçin."))
            return
        name = commit_current()
        if name is None:
            return
        for o in objs:
            M.assign(o, name)
        changed()
        msg(T("%d nesneye atandı: %s") % (len(objs), display_name(name)))

    def do_auto_apply():
        """Düzenleyicide değişiklik yapıldı: malzemeyi kütüphanede güncelle ve seçili nesnelere ata (sessizce)."""
        if not ck_auto.isChecked() or st["lock"]:
            return
        objs = [o for o in (doc.getObject(n) for n in st.get("auto_names", [])) if o is not None]
        if not objs or not ed_name.text().strip():
            return
        name = commit_current()
        if name is None:
            return
        for o in objs:
            M.assign(o, name)
        changed()
        msg(T("%d nesneye otomatik uygulandı: %s") % (len(objs), display_name(name)))

    def do_clear():
        objs = sel_objects()
        for o in objs:
            M.assign(o, "")
        changed()
        msg(T("%d nesnenin ataması kaldırıldı.") % len(objs))

    def on_item_changed(it, col):
        """Onay kutusu: nesneyi render'a dahil et / hariç tut."""
        if st.get("tlock") or col != 0:
            return
        o = doc.getObject(it.data(0, QtCore.Qt.UserRole))
        if o is None:
            return
        flag = it.checkState(0) == QtCore.Qt.Checked
        try:
            M.set_included(o, flag)
        except Exception as ex:
            msg("%s" % ex)
            return
        st["tlock"] = True                          # soluk renk ataması da itemChanged tetikler: yeniden girmesin
        try:
            style_item(it, flag)
        finally:
            st["tlock"] = False
        if on_change is not None:
            on_change()
        msg((T("Render'a dahil: %s") if flag else T("Render'dan hariç tutuldu: %s")) % o.Label)

    _MAT_CLIP = {"name": ""}

    def tree_menu(pos):
        it = tree.itemAt(pos)
        if it is not None and not it.isSelected():
            tree.clearSelection()
            it.setSelected(True)
        objs = sel_objects()
        mn = M.assigned(objs[0]) if objs else ""
        mnu = QtGui.QMenu(tree)
        a_cp = mnu.addAction(T("Malzemeyi kopyala"))
        a_cp.setEnabled(bool(mn) and it is not None)
        a_ps = mnu.addAction(T("Yapıştır") + ((": " + display_name(_MAT_CLIP["name"])) if _MAT_CLIP["name"] else ""))
        a_ps.setEnabled(bool(_MAT_CLIP["name"]) and bool(objs))
        mnu.addSeparator()
        a_cl = mnu.addAction(T("Atamayı kaldır"))
        a_cl.setEnabled(bool(objs))
        act = mnu.exec_(tree.viewport().mapToGlobal(pos)) if hasattr(mnu, "exec_") else mnu.exec(tree.viewport().mapToGlobal(pos))
        if act is None:
            return
        if act is a_cp:
            _MAT_CLIP["name"] = mn
            msg(T("Malzeme kopyalandı: %s") % display_name(mn))
        elif act is a_ps:
            for o in objs:
                M.assign(o, _MAT_CLIP["name"])
            changed()
            msg(T("%d nesneye yapıştırıldı: %s") % (len(objs), display_name(_MAT_CLIP["name"])))
        elif act is a_cl:
            do_clear()

    def set_selected_included(flag):
        objs = sel_objects()
        if not objs:
            msg(T("Önce soldaki listeden nesne seçin."))
            return
        for o in objs:
            M.set_included(o, flag)
        changed()
        msg((T("%d nesne render'a dahil edildi.") if flag else T("%d nesne render'dan hariç tutuldu.")) % len(objs))

    def do_save():
        n = commit_current()
        if n:
            msg(T("Kütüphaneye kaydedildi: %s") % n)

    def do_new():
        """LightWave 'New Surface': gri (%70), yayılı %100, parlaklık yok, yansıma/saydamlık yok, dokusuz yeni yüzey."""
        lib = M.library()
        base = T("Yeni yüzey")
        n, k = base, 1
        while n in lib:
            k += 1
            n = "%s %d" % (base, k)
        mat = M.normalize(dict(M.DEFAULT, color=(0.7, 0.7, 0.7), diffuse=1.0, spec=0.0, gloss=0.4, metal=0.0, refl=0.0,
                               transp=0.0, ior=1.0, lum=0.0, tex_layers={}))
        user = M.load_user()
        user[n] = mat
        M.save_user(user)
        refresh_lib(n)
        fill_editor(n, mat)
        msg(T("Yeni yüzey oluşturuldu: %s") % n)

    def do_del():
        n = ed_name.text().strip()
        user = M.load_user()
        if n in user:
            del user[n]
            M.save_user(user)
            refresh_lib()
            msg(T("Silindi: %s") % n)
        else:
            msg(T("Yalnız kullanıcı malzemeleri (★) silinebilir."))

    def on_lib_click(it, *_a):
        n = it.data(QtCore.Qt.UserRole)
        if n is None:                                       # kategori başlığı
            return
        m = M.get(n)
        if m is not None:
            fill_editor(n, m)
            msg(T("Malzeme yüklendi: %s") % display_name(n))

    def select_names(names, add=False):
        """Listede verilen adlı nesneleri seç (add=True: mevcut seçime ekle) ve ilkine kaydır."""
        names = set(names)
        st["sellock"] = True
        try:
            if not add:
                tree.clearSelection()
            first = None
            for i in range(tree.topLevelItemCount()):
                it = tree.topLevelItem(i)
                if it.data(0, QtCore.Qt.UserRole) in names:
                    it.setSelected(True)
                    if first is None:
                        first = it
            if first is not None:
                tree.scrollToItem(first)
        finally:
            st["sellock"] = False
        on_tree_sel(expand=False)
        return len(tree.selectedItems())

    def expand_similar():
        names = {it.data(0, QtCore.Qt.UserRole) for it in tree.selectedItems()}
        if not names:
            return 0
        alln = similar_names(names)
        if alln != names:
            select_names(alln, add=True)
        return len(alln)

    def do_select_similar():
        if not tree.selectedItems():
            msg(T("Önce soldaki listeden nesne seçin."))
            return
        n = expand_similar()
        msg(T("%d benzer nesne seçildi.") % n)

    def on_pick(name, add=False):
        """Render önizlemesinde tıklanan nesne (ana pencereden çağrılır). Boya kovası açıksa malzemeyi atar."""
        o = doc.getObject(name)
        if o is None:
            return
        names = {name} | (similar_names({name}) if ck_sim.isChecked() else set())
        if not any(it.data(0, QtCore.Qt.UserRole) == name for it in (tree.topLevelItem(i) for i in range(tree.topLevelItemCount()))):
            ed_filter.clear()                                   # süzgeç nesneyi gizliyorsa kaldır
            refresh_tree()
        try:
            import FreeCADGui as _Gui
            _Gui.Selection.clearSelection()
            _Gui.Selection.addSelection(o)                      # 3B görünümde de vurgula
        except Exception:
            pass
        if btn_paint.isChecked():
            mname = commit_current()
            if mname is None:
                return
            objs = [x for x in (doc.getObject(n) for n in names) if x is not None]
            for x in objs:
                M.assign(x, mname)
            changed()
            select_names(names)
            msg(T("%d nesneye boyandı: %s — sonucu görmek için yeniden Render'a basın.") % (len(objs), display_name(mname)))
        else:
            select_names(names, add=add)
            msg(T("Seçildi: %s") % o.Label + ((" (+%d benzer)" % (len(names) - 1)) if len(names) > 1 else ""))
        if btn_pin.isChecked():
            dlg.raise_()                                        # önizlemeye tıklayınca ana pencere öne geçip bunu örtmesin

    def on_tree_sel(expand=True):
        if st.get("sellock"):
            return
        if expand and ck_sim.isChecked() and tree.selectedItems():
            expand_similar()
        its = tree.selectedItems()
        if len(its) == 1:
            o = doc.getObject(its[0].data(0, QtCore.Qt.UserRole))
            n = M.assigned(o) if o is not None else ""
            m = M.get(n) if n else None
            if m is not None:
                fill_editor(n, m)
                for i in range(lst.count()):
                    if lst.item(i).data(QtCore.Qt.UserRole) == n:
                        lst.setCurrentRow(i)

    btn_assign.clicked.connect(do_assign)
    btn_clear.clicked.connect(do_clear)
    btn_inc.clicked.connect(lambda *_a: set_selected_included(True))
    btn_exc.clicked.connect(lambda *_a: set_selected_included(False))
    tree.itemChanged.connect(on_item_changed)
    tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    tree.customContextMenuRequested.connect(tree_menu)
    btn_save.clicked.connect(do_save)
    btn_new.clicked.connect(do_new)
    btn_del.clicked.connect(do_del)
    lst.itemClicked.connect(on_lib_click)
    lst.itemDoubleClicked.connect(lambda it: (on_lib_click(it), do_assign()))
    def on_tree_sel_user():
        on_tree_sel()
        if st.get("tlock") or st.get("sellock"):
            return
        its = tree.selectedItems()
        key = tuple(sorted(it.data(0, QtCore.Qt.UserRole) for it in its))
        if key and key != st.get("lastsel"):
            lab = [it.text(0) for it in its]
            msg(T("Seçim: %d nesne") % len(its) + " (" + ", ".join(lab[:3]) + (", ..." if len(lab) > 3 else "") + ")")
        st["lastsel"] = key
    tree.itemSelectionChanged.connect(on_tree_sel_user)
    btn_sim.clicked.connect(lambda *_a: do_select_similar())
    ck_grp.toggled.connect(lambda on: (refresh_tree(), msg(T("Benzerleri yan yana diz: %s") % (T("açık") if on else T("kapalı")))))
    ck_sim.toggled.connect(lambda on: (msg(T("Benzerleri birlikte seç: %s") % (T("açık") if on else T("kapalı"))),
                                       expand_similar() if on else None))
    btn_paint.toggled.connect(lambda on: msg(T("Boya kovası: %s") % (T("açık — önizlemede parçaya tıklayın") if on else T("kapalı"))))
    ed_name.textEdited.connect(lambda _t: None)
    ed_filter.textChanged.connect(lambda _t: refresh_tree())
    def do_rescan(*_a):
        QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        btn_scan.setEnabled(False)
        msg(T("Nesneler taranıyor..."))
        QtGui.QApplication.processEvents()
        t0 = time.time()
        try:
            rescan(force=True)
            refresh_tree()
        finally:
            btn_scan.setEnabled(True)
            QtGui.QApplication.restoreOverrideCursor()
        msg(T("Liste yenilendi: %d nesne") % len(st["items"]) + " (%.1f %s)" % (time.time() - t0, T("sn")))
    btn_scan.clicked.connect(do_rescan)

    refresh_lib()
    fill_editor("", M.normalize(dict(color=(0.7, 0.7, 0.72))))
    dlg.resize(900, 760)

    def place_near_main():
        """Render penceresinin soluna, üst kenarları hizalı; sığmazsa sağına; ekran dışına taşmaz."""
        try:
            if main_dlg is None:
                return
            mg = main_dlg.frameGeometry()
            scr = main_dlg.screen().availableGeometry()
            w, h = dlg.width(), dlg.height()
            x = mg.left() - w
            if x < scr.left():
                x = mg.right() + 1
                if x + w > scr.right():
                    x = scr.left()
            y = max(scr.top(), min(mg.top(), scr.bottom() - h))
            dlg.move(x, y)
        except Exception:
            pass

    def set_pin(on):
        """Her zaman üstte: render penceresinin (açık) ya da FreeCAD ana penceresinin çocuğu olur."""
        prm.SetBool("SurfaceOnTop", bool(on))
        pos = dlg.pos()
        dlg.setParent(main_dlg if on else Gui.getMainWindow(), dlg.windowFlags())
        dlg.show()
        dlg.move(pos)
        msg(T("Her zaman üstte: %s") % (T("açık") if on else T("kapalı")))
    btn_pin.toggled.connect(set_pin)
    FreeCAD._ybt_surface_dlg = dlg
    dlg._ybt_api = dict(tree=tree, lib=lst, name=ed_name, widgets=widgets, state=st, assign=do_assign, clear=do_clear,
                        save=do_save, preview=do_preview, fill=fill_editor, refresh=refresh_tree, msg=lbl_msg, prev=prev,
                        include=set_selected_included, pick=on_pick, select=select_names, similar=similar_names,
                        sim_check=ck_sim, paint=btn_paint)
    _theme.fix_combos(dlg)
    place_near_main()
    dlg.show()
    msg(T("Nesneler taranıyor..."))
    QtGui.QApplication.processEvents()                          # pencere hemen görünsün; tarama (büyük montajda saniyeler) arkasından

    def finish_open():
        QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        t0 = time.time()
        try:
            cached = rescan()
            refresh_tree()
            timer.stop()                                        # açılışta bekleyen önizleme zamanlayıcısı varsa ikinci kez çizme
            do_preview()
        finally:
            QtGui.QApplication.restoreOverrideCursor()
        msg(T("Hazır: %d nesne listelendi.") % len(st["items"]) + " (%.1f %s%s)" % (time.time() - t0, T("sn"), ", " + T("önbellek") if cached else ""))
    QtCore.QTimer.singleShot(0, finish_open)
    return dlg
