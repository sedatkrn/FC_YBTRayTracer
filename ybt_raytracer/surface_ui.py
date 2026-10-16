# -*- coding: utf-8 -*-
"""Surface (yüzey/malzeme) penceresi: nesne listesi + malzeme kütüphanesi + parametre düzenleyici + canlı önizleme küresi."""
import numpy as np
from . import settings as S
from . import materials as M
from .i18n import T
from .core import Scene

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


# ---------------------------------------------------------------- önizleme sahnesi
def _preview_scene(mat):
    """Zemin üstünde bir küre; zemin dama deseni (yansıma/kırılma/saydamlık görünsün)."""
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
    sph = np.array(tris)
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
    return Scene(tris, cols, alps, mids, [mat])


def render_preview(mat, w=280, h=210):
    """Malzemeyi küre üzerinde çizer. Döner: (h,w,3) uint8. Genel ayarlar geçici olarak değiştirilip geri yüklenir."""
    from .render import render
    sc = _preview_scene(mat)
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
def _renderable(doc):
    """Listede gösterilecek görünür, yüzeyli nesneler."""
    out = []
    for o in doc.Objects:
        try:
            if not hasattr(o, "Shape") or o.Shape.isNull() or not o.Shape.Faces:
                continue
            vo = getattr(o, "ViewObject", None)
            if vo is not None and not vo.Visibility:
                continue
            out.append(o)
        except Exception:
            continue
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

    dlg = QtGui.QDialog(Gui.getMainWindow())
    dlg.setWindowTitle(T("Yüzey / Malzeme Düzenleyici"))
    dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
    st = {"mat": M.normalize({}), "name": "", "lock": False}
    widgets = {}

    root = QtGui.QHBoxLayout(dlg)
    # ---------- sol: nesneler + kütüphane
    left = QtGui.QVBoxLayout()
    left.addWidget(QtGui.QLabel("<b>%s</b>" % T("Nesneler")))
    tree = QtGui.QTreeWidget()
    tree.setColumnCount(2)
    tree.setHeaderLabels([T("Nesne"), T("Malzeme")])
    tree.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
    tree.setRootIsDecorated(False)
    tree.setMinimumWidth(300)
    left.addWidget(tree, 3)
    left.addWidget(QtGui.QLabel("<b>%s</b>" % T("Malzeme kütüphanesi")))
    lst = QtGui.QListWidget()
    left.addWidget(lst, 3)
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
    name_row = QtGui.QHBoxLayout()
    name_row.addWidget(QtGui.QLabel(T("Ad")))
    ed_name = QtGui.QLineEdit()
    name_row.addWidget(ed_name, 1)
    btn_color = QtGui.QPushButton("")
    btn_color.setFixedWidth(54)
    ck_fc = QtGui.QCheckBox(T("Renk: nesnenin FreeCAD rengi"))
    name_row.addWidget(btn_color)
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
        widgets[key] = (sl, sp, lo, hi)
    right.addLayout(grid)
    b2 = QtGui.QHBoxLayout()
    btn_save = QtGui.QPushButton(T("Kütüphaneye kaydet"))
    btn_del = QtGui.QPushButton(T("Kütüphaneden sil"))
    b2.addWidget(btn_save)
    b2.addWidget(btn_del)
    right.addLayout(b2)
    lbl_msg = QtGui.QLabel("")
    lbl_msg.setWordWrap(True)
    right.addWidget(lbl_msg)
    right.addStretch(1)
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
            img = render_preview(M.normalize(st["mat"]), 280, 210)
        except Exception as ex:
            msg("önizleme: %s" % ex)
            return
        a = np.ascontiguousarray(img)
        qi = QtGui.QImage(a.data, a.shape[1], a.shape[0], 3 * a.shape[1], QtGui.QImage.Format_RGB888).copy()
        prev.setPixmap(QtGui.QPixmap.fromImage(qi))

    timer.timeout.connect(do_preview)

    def schedule():
        timer.start(150)

    def fill_editor(name, mat):
        st["lock"] = True
        st["name"], st["mat"] = name, M.normalize(mat)
        ed_name.setText(name)
        for key, (sl, sp, lo, hi) in widgets.items():
            v = st["mat"][key]
            sp.setValue(v)
            sl.setValue(int(round((v - lo) / (hi - lo) * 1000)))
        ck_fc.setChecked(st["mat"]["color"] is None)
        btn_color.setStyleSheet(color_css(st["mat"]["color"] or (0.7, 0.7, 0.72)))
        btn_color.setEnabled(st["mat"]["color"] is not None)
        st["lock"] = False
        schedule()

    def make_param_handlers(key, sl, sp, lo, hi):
        def from_slider(v):
            if st["lock"]:
                return
            val = lo + v / 1000.0 * (hi - lo)
            st["lock"] = True
            sp.setValue(val)
            st["lock"] = False
            st["mat"][key] = val
            schedule()

        def from_spin(val):
            if st["lock"]:
                return
            st["lock"] = True
            sl.setValue(int(round((val - lo) / (hi - lo) * 1000)))
            st["lock"] = False
            st["mat"][key] = float(val)
            schedule()
        sl.valueChanged.connect(from_slider)
        sp.valueChanged.connect(from_spin)

    for key, (sl, sp, lo, hi) in widgets.items():
        make_param_handlers(key, sl, sp, lo, hi)

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

    def refresh_tree():
        sel_names = {it.data(0, QtCore.Qt.UserRole) for it in tree.selectedItems()}
        tree.clear()
        for o in _renderable(doc):
            it = QtGui.QTreeWidgetItem([o.Label, display_name(M.assigned(o)) if M.assigned(o) else "—"])
            it.setData(0, QtCore.Qt.UserRole, o.Name)
            tree.addTopLevelItem(it)
            if o.Name in sel_names:
                it.setSelected(True)
        tree.resizeColumnToContents(0)

    def refresh_lib(select=None):
        lst.clear()
        lib = M.library()
        user = M.load_user()
        for n in lib:
            label = display_name(n) + ("" if n in M.BUILTIN and n not in user else "  ★")
            it = QtGui.QListWidgetItem(label)
            it.setData(QtCore.Qt.UserRole, n)
            lst.addItem(it)
            if n == select:
                lst.setCurrentItem(it)

    def sel_objects():
        return [doc.getObject(it.data(0, QtCore.Qt.UserRole)) for it in tree.selectedItems()]

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
        doc.recompute()
        changed()
        msg(T("%d nesneye atandı: %s") % (len(objs), display_name(name)))

    def do_clear():
        objs = sel_objects()
        for o in objs:
            M.assign(o, "")
        changed()
        msg(T("%d nesnenin ataması kaldırıldı.") % len(objs))

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
        m = M.get(n)
        if m is not None:
            fill_editor(n, m)

    def on_tree_sel():
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
    btn_save.clicked.connect(do_save)
    btn_del.clicked.connect(do_del)
    lst.itemClicked.connect(on_lib_click)
    lst.itemDoubleClicked.connect(lambda it: (on_lib_click(it), do_assign()))
    tree.itemSelectionChanged.connect(on_tree_sel)
    ed_name.textEdited.connect(lambda _t: None)

    refresh_tree()
    refresh_lib()
    fill_editor("", M.normalize(dict(color=(0.7, 0.7, 0.72))))
    dlg.resize(760, 640)
    FreeCAD._ybt_surface_dlg = dlg
    dlg._ybt_api = dict(tree=tree, lib=lst, name=ed_name, widgets=widgets, state=st, assign=do_assign, clear=do_clear,
                        save=do_save, preview=do_preview, fill=fill_editor, refresh=refresh_tree, msg=lbl_msg, prev=prev)
    dlg.show()
    do_preview()
    return dlg
