# -*- coding: utf-8 -*-
"""Surface (yüzey/malzeme) penceresi: nesne listesi + malzeme kütüphanesi + parametre düzenleyici + canlı önizleme küresi."""
import time
import numpy as np
from . import settings as S
from . import materials as M
from .i18n import T
from .core import Scene
from . import theme as _theme
from . import textures as _tex

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
    mat["tex_ch"] = {k: dict(v) for k, v in (mat.get("tex_ch") or {}).items()}
    for _sp in [mat] + list(mat["tex_ch"].values()):         # önizleme nesnesi ~2 birim: doku tekrarı 1 birim (ya da mm/100)
        if _sp.get("tex"):
            _sp["tex_scale"] = 1.0 if _sp.get("tex_scale", 0.0) <= 0 else _sp["tex_scale"] / 100.0
            for _k in ("tex_px", "tex_py", "tex_pz"):
                _sp[_k] = _sp.get(_k, 0.0) / 100.0
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
                                        "THREADS", "REFLECT_GLASS", "REFLECT_SURF", "IOR", "REFLECTIONS", "REFRACTION", "SPEC", "SHININESS")}
    try:
        S.LIGHTS = [dict(on=True, h=-35.0, v=45.0, color=(1, 1, 1), power=0.85, shadow=True),
                    dict(on=True, h=50.0, v=-5.0, color=(1, 1, 1), power=0.25, shadow=False),
                    dict(on=True, h=180.0, v=25.0, color=(1, 1, 1), power=0.4, shadow=False)]
        S.AMBIENT, S.AMBIENT_COLOR = 0.3, (1.0, 1.0, 1.0)
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
    dlg = QtGui.QDialog(main_dlg if (pin0 and main_dlg is not None) else Gui.getMainWindow())
    dlg.setWindowTitle(T("Yüzey / Malzeme Düzenleyici"))
    dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
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
            grid.addWidget(t_buttons[key], r, 3)
        widgets[key] = (sl, sp, lo, hi)
    lb = QtGui.QLabel(T("Bump (yükseklik haritası)"))
    lb.setToolTip(T("Gri tonlu bir dokuyu kabartı olarak okur: yüzey normalini eğer, geometri değişmez"))
    grid.addWidget(lb, len(_PARAMS), 0, 1, 3)
    t_buttons["bump"] = QtGui.QPushButton("T")
    grid.addWidget(t_buttons["bump"], len(_PARAMS), 3)
    for _b in t_buttons.values():
        _b.setFixedWidth(30)
    right.addLayout(grid)
    b2 = QtGui.QHBoxLayout()
    btn_save = QtGui.QPushButton(T("Kütüphaneye kaydet"))
    btn_del = QtGui.QPushButton(T("Kütüphaneden sil"))
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

    def _spec_get(chan):
        """Kanalın doku ayarı (yalnız okuma; oluşturmaz)."""
        if chan == "color":
            return st["mat"]
        return (st["mat"].get("tex_ch") or {}).get(chan) or {}

    def refresh_tex_buttons():
        for chn, b in t_buttons.items():
            b.setStyleSheet("font-weight: bold; background: #3b6ea5; color: white;" if _spec_get(chn).get("tex") else "")
            b.setToolTip(T("Doku ayarları: ") + T(_CH_TITLE[chn]))

    def refill_pops():
        refresh_tex_buttons()
        for _c, (_d, _rf) in pops.items():
            _rf()

    def open_tex(chan):
        if chan in pops:
            d_, rf_ = pops[chan]
            rf_()
            d_.show()
            d_.raise_()
            return
        d = QtGui.QDialog(dlg)
        d.setWindowTitle(T("Doku") + ": " + T(_CH_TITLE[chan]))
        _theme.apply(d)
        d.setMinimumWidth(440)
        vl = QtGui.QVBoxLayout(d)
        top = QtGui.QGridLayout()
        top.addWidget(QtGui.QLabel(T("Doku")), 0, 0)
        cb_t = QtGui.QComboBox()
        cb_t.addItem(T("(yok)"), "")
        for k_, nm_, _fn, _md, _rl in _tex.PRESETS:
            cb_t.addItem(T(nm_), k_)
        cb_t.setToolTip(T("Doku UV gerektirmez; aşağıdaki projeksiyonla nesneye yerleştirilir."))
        top.addWidget(cb_t, 0, 1, 1, 3)
        row = 1
        sp_mix = QtGui.QDoubleSpinBox()
        sp_mix.setRange(0.0, 100.0)
        sp_mix.setDecimals(0)
        sp_mix.setSuffix(" %")
        top.addWidget(QtGui.QLabel(T("Karışım (doku payı)") if chan == "color" else T("Doku payı (opaklık)")), row, 0)
        top.addWidget(sp_mix, row, 1)
        sp_tw = QtGui.QDoubleSpinBox()
        sp_tw.setRange(0.0, 20000.0)
        sp_tw.setDecimals(1)
        sp_tw.setSingleStep(10.0)
        sp_tw.setToolTip(T("Dokunun bir tekrarının nesne üzerindeki genişliği (belge birimi, mm). 0 = sahne boyutuna göre otomatik"))
        top.addWidget(QtGui.QLabel(T("Doku boyu (mm; 0 = otomatik)")), row, 2)
        top.addWidget(sp_tw, row, 3)
        row += 1
        ck_inv = QtGui.QCheckBox(T("Ters çevir"))
        ck_inv.setToolTip(T("Gri tonlu haritayı tersine çevirir (parlak ile koyu yer değiştirir)"))
        top.addWidget(ck_inv, row, 0, 1, 2)
        sp_str = QtGui.QDoubleSpinBox()
        sp_str.setRange(0.0, 2000.0)
        sp_str.setDecimals(0)
        sp_str.setSuffix(" %")
        sp_str.setToolTip(T("Kabartı yüksekliği: %100 = doku tekrarının yaklaşık %3'ü"))
        lb_str = QtGui.QLabel(T("Bump yüksekliği"))
        top.addWidget(lb_str, row, 2)
        top.addWidget(sp_str, row, 3)
        ck_inv.setVisible(chan != "color")
        lb_str.setVisible(chan == "bump")
        sp_str.setVisible(chan == "bump")
        vl.addLayout(top)
        gb = QtGui.QGroupBox(T("Doku yönü ve yerleşimi"))
        tgl = QtGui.QGridLayout(gb)
        tgl.addWidget(QtGui.QLabel(T("Projeksiyon")), 0, 0)
        cb_proj = QtGui.QComboBox()
        for k_, nm_ in (("cubic", "Küp (3 yönlü)"), ("planar", "Düzlemsel"), ("cylindrical", "Silindirik"), ("spherical", "Küresel")):
            cb_proj.addItem(T(nm_), k_)
        cb_proj.setToolTip(T("Küp: üç yönden izdüşüm (UV gerekmez). Düzlemsel: tek eksen boyunca. Silindirik/Küresel: nesne merkezi etrafında sarar."))
        tgl.addWidget(cb_proj, 0, 1, 1, 3)
        tgl.addWidget(QtGui.QLabel(T("Eksen")), 0, 4)
        cb_axis = QtGui.QComboBox()
        for i_, nm_ in enumerate(("X", "Y", "Z")):
            cb_axis.addItem(nm_, i_)
        cb_axis.setToolTip(T("Düzlemsel: dokunun baktığı eksen. Silindirik/Küresel: kutup ekseni."))
        tgl.addWidget(cb_axis, 0, 5, 1, 2)
        ck_world = QtGui.QCheckBox(T("Dünya koordinatları"))
        ck_world.setToolTip(T("Kapalı: doku nesnenin merkezine bağlıdır, nesneyle birlikte gider. Açık: doku sabit uzayda durur (nesne hareket edince kayar)."))
        tgl.addWidget(ck_world, 1, 0, 1, 4)
        btn_trst = QtGui.QPushButton(T("Sıfırla"))
        btn_trst.setToolTip(T("Doku ölçek, konum ve dönmesini varsayılana döndürür"))
        tgl.addWidget(btn_trst, 1, 4, 1, 3)
        tsp = {}
        for r_, (ttl, pref, lo_, hi_, stp_, dec_, suf_) in enumerate((
                (T("Ölçek"), "tex_s", 0.01, 1000.0, 0.1, 2, ""),
                (T("Konum (mm)"), "tex_p", -1e6, 1e6, 10.0, 1, ""),
                (T("Dönme"), "tex_r", -360.0, 360.0, 5.0, 1, "°"))):
            tgl.addWidget(QtGui.QLabel(ttl), 2 + r_, 0)
            for c_, ax_ in enumerate("xyz"):
                lb_ = QtGui.QLabel(ax_.upper())
                lb_.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                sp_ = QtGui.QDoubleSpinBox()
                sp_.setRange(lo_, hi_)
                sp_.setSingleStep(stp_)
                sp_.setDecimals(dec_)
                if suf_:
                    sp_.setSuffix(suf_)
                tgl.addWidget(lb_, 2 + r_, 1 + 2 * c_)
                tgl.addWidget(sp_, 2 + r_, 2 + 2 * c_)
                tsp[pref + ax_] = sp_
        for c_ in range(3):
            tgl.setColumnStretch(2 + 2 * c_, 1)
        vl.addWidget(gb)
        b_cl = QtGui.QPushButton(T("Kapat"))
        b_cl.clicked.connect(d.hide)
        vl.addWidget(b_cl)
        allw = [cb_t, sp_mix, sp_tw, ck_inv, sp_str, cb_proj, cb_axis, ck_world] + list(tsp.values())

        def refill():
            sp = _spec_get(chan)
            for w_ in allw:
                w_.blockSignals(True)
            cb_t.setCurrentIndex(max(0, cb_t.findData(sp.get("tex", ""))))
            sp_mix.setValue(round(float(sp.get("tex_mix", 1.0)) * 100))
            sp_tw.setValue(float(sp.get("tex_scale", 0.0)))
            ck_inv.setChecked(bool(sp.get("tex_invert", False)))
            sp_str.setValue(round(float(sp.get("tex_strength", 1.0)) * 100))
            cb_proj.setCurrentIndex(max(0, cb_proj.findData(sp.get("tex_proj", "cubic"))))
            cb_axis.setCurrentIndex(int(sp.get("tex_axis", 2)))
            ck_world.setChecked(bool(sp.get("tex_world", False)))
            for k_, sp_ in tsp.items():
                sp_.setValue(float(sp.get(k_, 1.0 if k_.startswith("tex_s") else 0.0)))
            for w_ in allw:
                w_.blockSignals(False)
            has = bool(sp.get("tex"))
            for w_ in (sp_mix, sp_tw, ck_inv, sp_str, gb):
                w_.setEnabled(has)
            cb_axis.setEnabled(has and cb_proj.currentData() != "cubic")

        def on_edit(*_a):
            sp = M.spec_of(st["mat"], chan)
            sp["tex"] = cb_t.currentData() or ""
            sp["tex_mix"] = sp_mix.value() / 100.0
            sp["tex_scale"] = float(sp_tw.value())
            sp["tex_invert"] = ck_inv.isChecked()
            sp["tex_strength"] = sp_str.value() / 100.0
            sp["tex_proj"] = cb_proj.currentData() or "cubic"
            sp["tex_axis"] = int(cb_axis.currentData() or 0)
            sp["tex_world"] = ck_world.isChecked()
            for k_, sp_ in tsp.items():
                sp[k_] = float(sp_.value())
            has = bool(sp["tex"])
            for w_ in (sp_mix, sp_tw, ck_inv, sp_str, gb):
                w_.setEnabled(has)
            cb_axis.setEnabled(has and sp["tex_proj"] != "cubic")
            refresh_tex_buttons()
            schedule(PREVIEW_DELAY_MS)

        def reset_place():
            for k_, sp_ in tsp.items():
                sp_.blockSignals(True)
                sp_.setValue(1.0 if k_.startswith("tex_s") else 0.0)
                sp_.blockSignals(False)
            on_edit()
        cb_t.currentIndexChanged.connect(on_edit)
        for w_ in (sp_mix, sp_tw, sp_str) + tuple(tsp.values()):
            w_.valueChanged.connect(on_edit)
        ck_inv.toggled.connect(on_edit)
        cb_proj.currentIndexChanged.connect(on_edit)
        cb_axis.currentIndexChanged.connect(on_edit)
        ck_world.toggled.connect(on_edit)
        btn_trst.clicked.connect(reset_place)
        pops[chan] = (d, refill)
        refill()
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
    btn_save.clicked.connect(do_save)
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
            do_preview()
        finally:
            QtGui.QApplication.restoreOverrideCursor()
        msg(T("Hazır: %d nesne listelendi.") % len(st["items"]) + " (%.1f %s%s)" % (time.time() - t0, T("sn"), ", " + T("önbellek") if cached else ""))
    QtCore.QTimer.singleShot(0, finish_open)
    return dlg
