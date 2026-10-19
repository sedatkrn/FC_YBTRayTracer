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
from . import materials as _mats
from . import theme as _theme
from . import lightpresets as _lp
from . import userdefaults as _ud
from . import __version__ as _VER


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
    if not getattr(FreeCAD, "_ybt_defaults_applied", False):     # kayıtlı varsayılanlar oturumda bir kez yüklenir
        FreeCAD._ybt_defaults_applied = True
        try:
            _ud.apply_saved()
        except Exception as ex:
            FreeCAD.Console.PrintWarning("RayTrace: defaults: %s\n" % ex)

    dlg = QtGui.QDialog(Gui.getMainWindow())
    dlg.setWindowTitle("FC YBT Raytracer v%s" % _VER)
    _theme.apply(dlg)                                           # koyu gri palet (theme.py)
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
    ck_sh = QtGui.QCheckBox(T("Gölgeler"))
    ck_sh.setChecked(bool(S.SHADOWS))
    ck_gl = QtGui.QCheckBox(T("Saydamlık (cam)"))
    ck_gl.setChecked(bool(S.GLASS))
    ck_rf = QtGui.QCheckBox(T("Yansımalar"))
    ck_rf.setChecked(bool(S.REFLECTIONS))
    ck_rf.setToolTip(T("Malzemelerin yansıma değerlerini uygular (krom, cam, boya...). Kapalıysa yansıma yoktur (en hızlı)."))
    ck_rr = QtGui.QCheckBox(T("Kırılma"))
    ck_rr.setChecked(bool(S.REFRACTION))
    ck_rr.setToolTip(T("Saydam malzemelerde ışığı kırar (Snell yasası, malzemenin IOR değeriyle). Kapalıysa ışık düz geçer (daha hızlı). "
                       "Malzemesi olmayan saydam nesneler cam (IOR 1.5) sayılır."))
    ck_sm = QtGui.QCheckBox(T("Yumuşak yüzeyler"))
    ck_sm.setChecked(bool(S.SMOOTH))
    ck_sm.setToolTip(T("Eğri yüzeyleri (küre, simit, silindir) pürüzsüz gölgeler; keskin kenarlar (küp, plaka) korunur. Kapalıysa üçgenler görünür."))
    ck_cull = QtGui.QCheckBox(T("Kadraj dışındaki nesneleri atla"))
    ck_cull.setChecked(bool(S.CULL_OFFSCREEN))
    ck_cull.setToolTip(T("Kadrajın dışında kalan nesneler sahneye hiç alınmaz: üçgenlenmez, gölge/yansıma vermez, "
                         "sahne boyutuna ve sanal zemin yüksekliğine katılmaz. Büyük modellerde kadraj yakınken hızlandırır. "
                         "Kamera değişince sahne yeniden okunur."))
    ck_sv = QtGui.QCheckBox(T("Bitince otomatik kaydet"))
    ck_sv.setChecked(True)
    sp_w.setToolTip(T("Çıktı genişliği; yükseklik 3B görünümün oranından gelir"))
    cb_q.setToolTip(T("Yüzey pürüzsüzlüğü (üçgenleme inceliği). Değişince sahne yeniden okunur"))
    cb_aa.setToolTip(T("Kenar yumuşatma: yalnız kenar piksellerinde çoklu örnekleme yapar"))
    ck_gl.setToolTip(T("Nesnenin Transparency (saydamlık) özelliğine göre arkası görünür"))
    sp_bn.setToolTip(T("Bir ışının en çok kaç kez yansıyacağı"))
    qrows = [(T("Genişlik"), sp_w, T("Kalite"), cb_q),
             (T("Kenar yumuşatma"), cb_aa, T("Yansıma sayısı"), sp_bn),
             (T("Çekirdek"), cb_th, None, None)]
    for r, (l1, w1, l2, w2) in enumerate(qrows):
        qg.addWidget(QtGui.QLabel(l1), r * 2, 0)
        if l2 is not None:
            qg.addWidget(QtGui.QLabel(l2), r * 2, 1)
        qg.addWidget(w1, r * 2 + 1, 0)
        if w2 is not None:
            qg.addWidget(w2, r * 2 + 1, 1)
    qg.addWidget(ck_sh, 8, 0)
    qg.addWidget(ck_gl, 8, 1)
    qg.addWidget(ck_rf, 9, 0)
    qg.addWidget(ck_rr, 9, 1)
    qg.addWidget(ck_sm, 10, 0, 1, 2)
    qg.addWidget(ck_cull, 11, 0, 1, 2)
    qg.addWidget(ck_sv, 12, 0, 1, 2)
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
        bt._paint = paint
        bt._key = key
        bt._after = []
        _orig = pick

        def pick2(*_a):
            _orig()
            for f in bt._after:
                f()
        bt.clicked.disconnect(pick)
        bt.clicked.connect(pick2)
        return bt

    ck_fc = QtGui.QCheckBox(T("FreeCAD ışık ayarlarını kullan"))
    ck_fc.setChecked(bool(getattr(S, "USE_FC_LIGHTS", False)))
    ck_fc.setToolTip(T("İşaretliyse Tercihler > Display > Light Sources ayarları kullanılır; aşağıdaki ayarlar devre dışı kalır"))
    lvb.addWidget(ck_fc)
    cb_pre = QtGui.QComboBox()
    for p in _lp.PRESETS:
        cb_pre.addItem(T(p[1]))
        cb_pre.setItemData(cb_pre.count() - 1, T(p[5]), QtCore.Qt.ToolTipRole)
    cb_pre.addItem(T("Özel"))
    cb_pre.setToolTip(T("Hazır aydınlatma düzenleri (stüdyo ve ürün çekimi). Ayrıntıları değiştirirseniz düzen 'Özel' olur."))
    prow = QtGui.QHBoxLayout()
    prow.addWidget(QtGui.QLabel(T("Aydınlatma")))
    prow.addWidget(cb_pre, 1)
    bt_cust = QtGui.QPushButton(T("Özel ayarlar") + " \u25b8")
    bt_cust.setCheckable(True)
    bt_cust.setToolTip(T("Üç ışığın açı, renk, güç ve gölge ayarlarını göster / gizle"))
    prow.addWidget(bt_cust)
    lvb.addLayout(prow)
    cust = QtGui.QWidget()
    cust_l = QtGui.QVBoxLayout(cust)
    cust_l.setContentsMargins(0, 0, 0, 0)
    lvb.addWidget(cust)
    cust.setVisible(False)
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
        cust_l.addWidget(frame)
        lrows.append((ck, sh, sv, cbn, sp_, cs))
    arow = QtGui.QHBoxLayout()
    arow.addWidget(QtGui.QLabel(T("Ortam ışığı")))
    cb_amb = color_button("amb", S.AMBIENT_COLOR)
    sp_amb = spin(0, 100, S.AMBIENT * 100, 5, " %")
    arow.addWidget(cb_amb)
    arow.addWidget(sp_amb)
    lvb.addLayout(arow)
    ck_ao = QtGui.QCheckBox(T("Ortam tıkanıklığı (AO)"))
    _pre_busy = [False]

    def to_custom(*_a):
        if not _pre_busy[0] and cb_pre.currentIndex() != len(_lp.PRESETS):
            cb_pre.blockSignals(True)
            cb_pre.setCurrentIndex(len(_lp.PRESETS))
            cb_pre.blockSignals(False)
            if not bt_cust.isChecked():
                pass

    def on_cust(on):
        cust.setVisible(on)
        bt_cust.setText(T("Özel ayarlar") + (" \u25be" if on else " \u25b8"))
        QtCore.QTimer.singleShot(0, fix_left_height)
    bt_cust.toggled.connect(on_cust)

    def set_color(key, rgb, btn):
        colors[key] = tuple(rgb)
        btn._paint()

    def apply_preset(i):
        if i >= len(_lp.PRESETS):
            bt_cust.setChecked(True)
            return
        _k, _n, lts, amb, ambc, _d = _lp.get(i)
        _pre_busy[0] = True
        try:
            for j, r in enumerate(lrows):
                lt = lts[j]
                r[0].setChecked(bool(lt["on"]))
                r[1].setValue(lt["h"])
                r[2].setValue(lt["v"])
                set_color("l%d" % j, lt["color"], r[3])
                r[4].setValue(int(round(lt["power"] * 100)))
                r[5].setChecked(bool(lt["shadow"]))
            sp_amb.setValue(int(round(amb * 100)))
            set_color("amb", ambc, cb_amb)
        finally:
            _pre_busy[0] = False
    cb_pre.currentIndexChanged.connect(apply_preset)
    for r in lrows:
        r[0].toggled.connect(to_custom)
        for wd in (r[1], r[2], r[4]):
            wd.valueChanged.connect(to_custom)
        r[5].toggled.connect(to_custom)
        r[3]._after.append(to_custom)
    sp_amb.valueChanged.connect(to_custom)
    cb_amb._after.append(to_custom)
    # başlangıç: ayarlar hangi düzene uyuyorsa onu seç, hiçbirine uymuyorsa 'Özel'
    _cur = None
    for _i, _p in enumerate(_lp.PRESETS):
        _same = abs(_p[3] - S.AMBIENT) < 1e-6 and all(
            _p[2][j]["on"] == bool(S.LIGHTS[j]["on"]) and abs(_p[2][j]["power"] - S.LIGHTS[j]["power"]) < 1e-6
            and abs(_p[2][j]["h"] - S.LIGHTS[j]["h"]) < 1e-6 and abs(_p[2][j]["v"] - S.LIGHTS[j]["v"]) < 1e-6
            for j in range(min(3, len(S.LIGHTS))))
        if _same:
            _cur = _i
            break
    cb_pre.blockSignals(True)
    cb_pre.setCurrentIndex(_cur if _cur is not None else len(_lp.PRESETS))
    cb_pre.blockSignals(False)
    ck_ao.setChecked(bool(S.AO))
    ck_ao.setToolTip(T("Köşeler, girintiler ve nesnelerin zemine değdiği yerler ortam ışığını daha az alır (temas gölgesi). "
                       "Gerçekçilik katar; süreyi artırır. Ortam ışığı çok düşükse etkisi az görünür."))
    sp_aos = spin(0, 100, S.AO_STRENGTH * 100, 5, " %")
    sp_aos.setToolTip(T("AO şiddeti: ortam ışığının ne kadarının kısılacağı"))
    sp_aor = spin(1, 50, S.AO_RADIUS * 100, 1, " %")
    sp_aor.setToolTip(T("AO erişimi: sahne boyutunun yüzdesi (büyük = geniş, yumuşak gölgelenme)"))
    sp_aon = spin(2, 64, S.AO_SAMPLES, 2)
    sp_aon.setToolTip(T("Piksel başına AO ışını (çok = daha temiz, daha yavaş)"))
    aor = QtGui.QHBoxLayout()
    aor.addWidget(ck_ao)
    aor.addStretch(1)
    aor.addWidget(sp_aos)
    lvb.addLayout(aor)
    aor2 = QtGui.QHBoxLayout()
    aor2.addWidget(QtGui.QLabel(T("AO erişimi")))
    aor2.addWidget(sp_aor)
    aor2.addWidget(QtGui.QLabel(T("Işın sayısı")))
    aor2.addWidget(sp_aon)
    lvb.addLayout(aor2)

    def sync_ao(*_a):
        for wd in (sp_aos, sp_aor, sp_aon):
            wd.setEnabled(ck_ao.isChecked())
    ck_ao.toggled.connect(sync_ao)
    sync_ao()
    # ---- Ortam / HDRI ----
    env_state = {"file": str(S.ENV_FILE or "")}
    cb_env = QtGui.QComboBox()
    cb_env.addItems([T("Ortam: kapalı"), T("Ortam: hazır gökyüzü"), T("Ortam: HDRI dosyası")])
    cb_env.setCurrentIndex({"off": 0, "sky": 1, "hdri": 2}.get(str(S.ENV_MODE), 0))
    cb_env.setToolTip(T("Küresel ortam ışığı: gökyüzü/HDRI haritası arka planı, yansımaları ve sahnenin ışığını verir; haritadaki güneş gölgeli ışık olur. "
                        "Açıkken sahne ışıkları ve ortam ışığı yerine bu kullanılır."))
    btn_envf = QtGui.QPushButton(T("HDRI seç..."))
    lbl_envf = QtGui.QLabel(os.path.basename(env_state["file"]) if env_state["file"] else "")
    sp_ei = spin(10, 500, S.ENV_INTENSITY * 100, 10, " %")
    sp_ei.setToolTip(T("Ortam ışığı ve güneş şiddeti"))
    sp_er = spin(-180, 180, S.ENV_ROT, 5, " °")
    sp_er.setToolTip(T("Haritayı dikey eksen etrafında döndürür (güneşin yönü de döner)"))
    sp_ee = spin(1, 85, S.ENV_SUN_ELEV, 5, " °")
    sp_ee.setToolTip(T("Hazır gökyüzü: güneş yüksekliği"))
    sp_ea = spin(-180, 360, S.ENV_SUN_AZ, 5, " °")
    sp_ea.setToolTip(T("Hazır gökyüzü: güneşin yönü (0° = +X, 90° = +Y)"))
    sp_en = spin(4, 128, S.ENV_SAMPLES, 4)
    sp_en.setToolTip(T("Piksel başına gökyüzü görünürlük ışını (çok = daha temiz, daha yavaş; pencereden giren ışıkta daha çok gerekir)"))
    ck_ebg = QtGui.QCheckBox(T("Arka planda göster"))
    ck_ebg.setChecked(bool(S.ENV_BACKGROUND))
    ck_eli = QtGui.QCheckBox(T("Aydınlat"))
    ck_eli.setChecked(bool(S.ENV_LIGHT))
    ck_ere = QtGui.QCheckBox(T("Yansıt"))
    ck_ere.setChecked(bool(S.ENV_REFLECT))
    ck_esu = QtGui.QCheckBox(T("Güneşi ayır"))
    ck_esu.setChecked(bool(S.ENV_SUN))
    ck_ekl = QtGui.QCheckBox(T("Sahne ışıkları kalsın"))
    ck_ekl.setChecked(bool(S.ENV_KEEP_LIGHTS))
    er1 = QtGui.QHBoxLayout()
    er1.addWidget(cb_env, 1)
    er1.addWidget(btn_envf)
    lvb.addLayout(er1)
    lvb.addWidget(lbl_envf)
    er2 = QtGui.QHBoxLayout()
    for t_, w_ in ((T("Şiddet"), sp_ei), (T("Dönüş"), sp_er), (T("Işın"), sp_en)):
        er2.addWidget(QtGui.QLabel(t_))
        er2.addWidget(w_)
    lvb.addLayout(er2)
    er3 = QtGui.QHBoxLayout()
    for t_, w_ in ((T("Güneş yüksekliği"), sp_ee), (T("yönü"), sp_ea)):
        er3.addWidget(QtGui.QLabel(t_))
        er3.addWidget(w_)
    lvb.addLayout(er3)
    er4 = QtGui.QHBoxLayout()
    for w_ in (ck_ebg, ck_eli, ck_ere):
        er4.addWidget(w_)
    lvb.addLayout(er4)
    er5 = QtGui.QHBoxLayout()
    er5.addWidget(ck_esu)
    er5.addWidget(ck_ekl)
    lvb.addLayout(er5)

    def sync_env(*_a):
        i_ = cb_env.currentIndex()
        on_ = i_ > 0
        btn_envf.setVisible(i_ == 2)
        lbl_envf.setVisible(i_ == 2)
        for wd in (sp_ei, sp_er, sp_en, ck_ebg, ck_eli, ck_ere, ck_esu, ck_ekl):
            wd.setEnabled(on_)
        sp_ee.setEnabled(i_ == 1)
        sp_ea.setEnabled(i_ == 1)

    def pick_env():
        res = QtGui.QFileDialog.getOpenFileName(dlg, T("HDRI / ortam haritası seç"), os.path.dirname(env_state["file"]) or os.path.expanduser("~"),
                                                T("Ortam haritası (*.hdr *.pic *.png *.jpg *.jpeg)"))
        path = res[0] if isinstance(res, (tuple, list)) else res
        if path:
            env_state["file"] = path
            lbl_envf.setText(os.path.basename(path))
    btn_envf.clicked.connect(pick_env)
    cb_env.currentIndexChanged.connect(sync_env)
    sync_env()
    ck_soft = QtGui.QCheckBox(T("Yumuşak gölge"))
    ck_soft.setChecked(float(S.SOFT_SHADOW) > 0.0)
    ck_soft.setToolTip(T("Gölge kenarları yumuşar (alan ışığı). Gölgeli her ışık için birkaç gölge ızgarası kurulur; küçük ve orta sahnelerde ucuzdur, çok büyük modelde atlanır."))
    sp_softr = spin(1, 30, S.SOFT_SHADOW if S.SOFT_SHADOW > 0 else 4, 1, " °")
    sp_softr.setToolTip(T("Işığın görünür boyutu (derece): güneş ~0,3°, softbox 5-15°. Büyük = daha geniş yarı gölge"))
    srow = QtGui.QHBoxLayout()
    srow.addWidget(ck_soft)
    srow.addStretch(1)
    srow.addWidget(sp_softr)
    sp_softk = spin(10, 1000, int(round(float(S.SOFT_SCALE) * 100)), 10, " %")
    sp_softk.setToolTip(T("Yarı gölge genişlik çarpanı: 100 % = ışık açısına göre, 300 % = 3 kat daha geniş (daha büyük ışık kaynağı görünümü)"))
    srow.addWidget(sp_softk)
    lvb.addLayout(srow)

    def sync_soft(*_a):
        sp_softr.setEnabled(ck_soft.isChecked())
        sp_softk.setEnabled(ck_soft.isChecked())
    ck_soft.toggled.connect(sync_soft)
    sync_soft()
    cb_tm = QtGui.QComboBox()
    for _t in (T("Yok (kırp)"), T("Yumuşak (Reinhard)"), T("Filmik (ACES)")):
        cb_tm.addItem(_t)
    cb_tm.setCurrentIndex({"none": 0, "soft": 1, "aces": 2}.get(str(S.TONEMAP), 0))
    cb_tm.setToolTip(T("Ton eşleme: çok parlak alanlar patlamak yerine yumuşakça sıkışır. Pozlamayı artırıp ton eşleme açmak daha sinematik görünüm verir."))
    sp_exp = spin(25, 400, S.EXPOSURE * 100, 5, " %")
    sp_exp.setToolTip(T("Pozlama: 100 % = değişiklik yok"))
    trow = QtGui.QHBoxLayout()
    trow.addWidget(QtGui.QLabel(T("Ton eşleme")))
    trow.addWidget(cb_tm, 1)
    trow.addWidget(QtGui.QLabel(T("Pozlama")))
    trow.addWidget(sp_exp)
    lvb.addLayout(trow)
    ck_fr = QtGui.QCheckBox(T("Fresnel yansıması"))
    ck_fr.setChecked(bool(S.FRESNEL))
    ck_fr.setToolTip(T("Parlak opak yüzeylerde (boya, plastik, seramik) yansıma, yüzeye eğik bakıldıkça güçlenir"))
    lvb.addWidget(ck_fr)
    lv.addWidget(lbox)
    light_widgets = [wd for row in lrows for wd in row] + [cb_amb, sp_amb, cb_pre, bt_cust]

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
    btn_m = QtGui.QPushButton(T("Malzemeler (Surface)..."))
    btn_m.setToolTip(T("Nesnelere malzeme ata, malzeme kütüphanesini düzenle"))
    b3 = QtGui.QHBoxLayout()
    b3.addWidget(btn_m)
    def fix_left_height():
        """Sol panel içeriği, kaydırma alanında sıkışmasın: yeterli yüksekliği korur, taşarsa kaydırma çubuğu çıkar."""
        try:
            left.setMinimumHeight(0)
            lv.activate()
            left.setMinimumHeight(lv.sizeHint().height())
        except Exception:
            pass

    def collapsible(box, title, start_open=False):
        """Grup kutusunu, başlığına tıklayınca açılıp kapanan bölüme çevirir (yer kaplamasın)."""
        idx = lv.indexOf(box)
        lv.removeWidget(box)
        box.setTitle("")
        box.setStyleSheet("QGroupBox { border: none; margin-top: 0px; padding-top: 0px; }")
        wrap = QtGui.QWidget()
        wl = QtGui.QVBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(0)
        hb = QtGui.QToolButton()
        hb.setCheckable(True)
        hb.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        hb.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Fixed)
        hb.setStyleSheet("QToolButton { text-align: left; background-color: %s; border: 1px solid %s; border-radius: 3px; padding: 4px 8px; }"
                         "QToolButton:hover { background-color: %s; }" % (_theme.HEADER, _theme.BORDER, _theme.BTN))
        hb.setToolTip(T("Tıklayınca açılır / kapanır"))

        def upd(on):
            hb.setText(("\u25be  " if on else "\u25b8  ") + title)
            box.setVisible(on)
            QtCore.QTimer.singleShot(0, fix_left_height)
        hb.toggled.connect(upd)
        wl.addWidget(hb)
        wl.addWidget(box)
        hb.setChecked(start_open)
        upd(start_open)
        lv.insertWidget(idx, wrap)
        return hb

    collapsible(qbox, T("Kalite Ayarları"), start_open=True)
    collapsible(fbox, T("Sanal Zemin"))
    collapsible(lbox, T("Işık Ayarları"))
    lv.addStretch(1)

    sc_left = QtGui.QScrollArea()                     # ekran küçükse sol panel kaydırılır
    sc_left.setWidget(left)
    sc_left.setWidgetResizable(True)
    sc_left.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)   # içerik sığmazsa kırpmak yerine kaydır
    lcol = QtGui.QVBoxLayout()                        # üstte sabit: başlık + düğmeler, altta kaydırılabilir ayarlar
    head = QtGui.QLabel(T("Settings"))
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
    def rebuild():
        QtCore.QTimer.singleShot(0, lambda: (dlg.close(), main(i18n.LANG)))

    def open_defaults():
        if state["busy"]:
            return
        apply_all()                                   # panelin şu anki değerleri settings'e alınsın
        dd = QtGui.QDialog(dlg)
        dd.setWindowTitle(T("Varsayılan ayarlar"))
        _theme.apply(dd)
        dd.setMinimumWidth(520)
        vl = QtGui.QVBoxLayout(dd)
        info = QtGui.QLabel(T("Panelin şu anki değerlerini varsayılan olarak kaydedebilir, önceki kayıtlara dönebilirsiniz. "
                              "● işaretli kayıt, FreeCAD her açıldığında yüklenen varsayılandır."))
        info.setWordWrap(True)
        vl.addWidget(info)
        vl.addWidget(QtGui.QLabel(T("Mevcut ayarlar (değer sütununu düzenleyebilirsin):")))
        tbl = QtGui.QTableWidget()
        tbl.setColumnCount(2)
        tbl.setHorizontalHeaderLabels([T("Ayar"), T("Değer")])
        tbl.verticalHeader().setVisible(False)
        tbl.horizontalHeader().setStretchLastSection(True)
        tbl.setMinimumHeight(230)
        trows = []                                    # (anahtar, öğe, orijinal metin)
        _keys = [k for k in _ud._keys() if k != "LIGHTS"]
        tbl.setRowCount(len(_keys) + 1)

        def _fmt(v):
            if isinstance(v, tuple):
                return ", ".join("%g" % x for x in v)
            return str(v)

        def fill_table():
            trows.clear()
            tbl.blockSignals(True)
            for r, k in enumerate(_keys):
                v = g[k]
                a = QtGui.QTableWidgetItem(k)
                a.setFlags(QtCore.Qt.ItemIsEnabled)
                tbl.setItem(r, 0, a)
                b = QtGui.QTableWidgetItem()
                if isinstance(v, bool):
                    b.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable)
                    b.setCheckState(QtCore.Qt.Checked if v else QtCore.Qt.Unchecked)
                else:
                    b.setText(_fmt(v))
                tbl.setItem(r, 1, b)
                trows.append((k, b, _fmt(v)))
            r = len(_keys)
            a = QtGui.QTableWidgetItem("LIGHTS")
            a.setFlags(QtCore.Qt.ItemIsEnabled)
            tbl.setItem(r, 0, a)
            b = QtGui.QTableWidgetItem(T("%d ışık (Işık Ayarları bölümünden)") % len(g["LIGHTS"]))
            b.setFlags(QtCore.Qt.ItemIsEnabled)
            tbl.setItem(r, 1, b)
            tbl.blockSignals(False)
            tbl.resizeColumnToContents(0)

        def read_table():
            """Tabloda değiştirilen değerleri döndürür (geçersiz girişler atlanır)."""
            out = {}
            for k, it, orig in trows:
                cur = g[k]
                try:
                    if isinstance(cur, bool):
                        nv = it.checkState() == QtCore.Qt.Checked
                    else:
                        t = it.text().strip()
                        if t == orig:
                            continue
                        if isinstance(cur, int):
                            nv = int(float(t))
                        elif isinstance(cur, float):
                            nv = float(t)
                        elif isinstance(cur, tuple):
                            nv = tuple(float(x) for x in t.replace(";", ",").split(","))
                            if len(nv) != len(cur):
                                continue
                        else:
                            nv = t
                    if nv != cur:
                        out[k] = nv
                except Exception:
                    continue
            return out
        fill_table()
        vl.addWidget(tbl)
        row = QtGui.QHBoxLayout()
        ed = QtGui.QLineEdit()
        ed.setPlaceholderText(T("Kayıt adı (isteğe bağlı)"))
        b_save = QtGui.QPushButton(T("Şu anki ayarları varsayılan olarak kaydet"))
        b_save.setStyleSheet("font-weight: bold;")
        b_app = QtGui.QPushButton(T("Tablodaki değişiklikleri panele uygula"))
        b_app.setToolTip(T("Kaydetmeden, tabloda düzenlenen değerleri panele aktarır"))
        row.addWidget(ed, 1)
        row.addWidget(b_save)
        vl.addLayout(row)
        vl.addWidget(b_app)
        vl.addWidget(QtGui.QLabel(T("Geçmiş (en yeni üstte, son %d kayıt):") % _ud.MAX_HIST))
        lst = QtGui.QListWidget()
        lst.setMinimumHeight(190)
        vl.addWidget(lst)
        b_load = QtGui.QPushButton(T("Seçili kaydı panele yükle"))
        b_def = QtGui.QPushButton(T("Seçili kaydı varsayılan yap"))
        b_del = QtGui.QPushButton(T("Seçili kaydı sil"))
        b_fac = QtGui.QPushButton(T("Fabrika ayarlarını panele yükle"))
        b_off = QtGui.QPushButton(T("Kayıtlı varsayılanı kapat"))
        b_off.setToolTip(T("Kayıtlar silinmez; FreeCAD bir sonraki açılışta fabrika ayarlarıyla başlar"))
        b_cl = QtGui.QPushButton(T("Kapat"))
        g1 = QtGui.QHBoxLayout()
        g1.addWidget(b_load)
        g1.addWidget(b_def)
        g1.addWidget(b_del)
        g2 = QtGui.QHBoxLayout()
        g2.addWidget(b_fac)
        g2.addWidget(b_off)
        g2.addStretch(1)
        g2.addWidget(b_cl)
        vl.addLayout(g1)
        vl.addLayout(g2)
        st = QtGui.QLabel("")
        st.setStyleSheet("color: #85858a;")
        vl.addWidget(st)

        def refill():
            d = _ud.load()
            lst.clear()
            for i in reversed(range(len(d["hist"]))):
                h = d["hist"][i]
                it = QtGui.QListWidgetItem(("● " if i == d.get("current", -1) else "    ") + h.get("ts", "") +
                                           (("   –   " + h["name"]) if h.get("name") else ""))
                it.setData(QtCore.Qt.UserRole, i)
                lst.addItem(it)
            has = lst.count() > 0
            if has:
                lst.setCurrentRow(0)
            else:
                it = QtGui.QListWidgetItem(T("Henüz kayıt yok. Panelde ayarları yapıp yukarıdaki düğmeyle ilk kaydı oluştur."))
                it.setFlags(QtCore.Qt.NoItemFlags)
                lst.addItem(it)
            for b in (b_load, b_def, b_del):
                b.setEnabled(has)
            b_off.setEnabled(d.get("current", -1) >= 0)

        def sel():
            it = lst.currentItem()
            return None if it is None else it.data(QtCore.Qt.UserRole)

        def do_save_def():
            try:
                ch = read_table()
                if ch:
                    _ud.apply(ch)
                _ud.save_current(ed.text())
                ed.clear()
                st.setText(T("Kaydedildi: ") + _ud.path())
            except Exception as ex:
                st.setText(T("Kaydedilemedi: ") + str(ex))
            refill()

        def do_load():
            i = sel()
            if i is None:
                return
            _ud.apply(_ud.load()["hist"][i]["values"])
            dd.accept()
            rebuild()

        def do_make():
            i = sel()
            if i is not None:
                _ud.make_default(i)
                st.setText(T("Seçili kayıt varsayılan yapıldı (açılışta yüklenir)."))
                refill()

        def do_del():
            i = sel()
            if i is not None:
                _ud.delete(i)
                refill()

        def do_fac():
            _ud.apply(_ud.FACTORY)
            dd.accept()
            rebuild()

        def do_off():
            _ud.clear_default()
            st.setText(T("Kayıtlı varsayılan kapatıldı; sonraki açılışta fabrika ayarları kullanılır."))
            refill()
        def do_apply_tbl():
            ch = read_table()
            if not ch:
                st.setText(T("Tabloda değişiklik yok."))
                return
            _ud.apply(ch)
            dd.accept()
            rebuild()
        b_app.clicked.connect(do_apply_tbl)
        b_save.clicked.connect(do_save_def)
        b_load.clicked.connect(do_load)
        b_def.clicked.connect(do_make)
        b_del.clicked.connect(do_del)
        b_fac.clicked.connect(do_fac)
        b_off.clicked.connect(do_off)
        b_cl.clicked.connect(dd.accept)
        lst.itemDoubleClicked.connect(lambda _i: do_load())
        refill()
        _theme.fix_combos(dd)
        (dd.exec_ if hasattr(dd, "exec_") else dd.exec)()

    btn_def = QtGui.QPushButton(T("⚙ Varsayılanlar…"))
    btn_def.setToolTip(T("Varsayılan ayarları kaydet, geçmiş kayıtlara dön, fabrika ayarlarına dön"))
    btn_def.clicked.connect(open_defaults)
    hrow = QtGui.QHBoxLayout()
    hrow.addWidget(head)
    hrow.addStretch(1)
    hrow.addWidget(btn_def)
    hrow.addWidget(QtGui.QLabel("Dil / Language:"))
    hrow.addWidget(cb_lang)
    lcol.addLayout(hrow)
    lcol.addLayout(b1)
    lcol.addLayout(b2)
    lcol.addLayout(b3)
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
    title = QtGui.QLabel(T("Önizleme ve Seçim Ekranı"))
    title.setAlignment(QtCore.Qt.AlignCenter)
    title.setStyleSheet("font-weight: bold; font-size: 15px; color: #e8e8ea;")
    right.addWidget(title)
    vrow = QtGui.QHBoxLayout()
    btn_fit = QtGui.QPushButton(T("Otomatik ortala"))
    btn_fit.setToolTip(T("Görüntüyü pencereye sığdırıp ortalar (çift tıklama da aynı işi yapar)"))
    btn_11 = QtGui.QPushButton("1:1")
    btn_11.setToolTip(T("Gerçek boyut: görüntünün bir pikseli ekranda bir piksel"))
    lbl_zoom = QtGui.QLabel("")
    lbl_zoom.setMinimumWidth(52)
    lbl_hint = QtGui.QLabel(T("Tekerlek: yakınlaştır / uzaklaştır  ·  Sürükle: kaydır  ·  Tıkla: parçayı seç"))
    lbl_hint.setStyleSheet("color: #85858a;")
    vrow.addWidget(btn_fit)
    vrow.addWidget(btn_11)
    vrow.addWidget(lbl_zoom)
    vrow.addStretch(1)
    vrow.addWidget(lbl_hint)
    right.addLayout(vrow)

    class _Preview(QtGui.QWidget):
        """Önizleme/seçim ekranı: çerçeveli, fare tekerleğiyle yakınlaştırılır, sürüklenerek kaydırılır, tıklamayla nesne seçer.
        Görüntü yakınlaştırılınca (>= 2 kat) pikseller yumuşatılmadan gösterilir."""

        def __init__(self):
            QtGui.QWidget.__init__(self)
            self.pm = None
            self.on_click = None                      # f(u, v, ctrl): u,v = görüntü içinde 0..1 konum
            self.on_view = None                       # f(ölçek): görünüm değişince
            self.scale = 1.0                          # ekran pikseli / görüntü pikseli
            self.ox = self.oy = 0.0                   # görüntünün sol-üst köşesi (widget koordinatı)
            self.fitted = True
            self._press = None
            self.setMinimumSize(320, 240)
            self.setSizePolicy(QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Ignored)
            self.setMouseTracking(False)

        # --- geometri
        def _fit_scale(self):
            if self.pm is None:
                return 1.0
            return max(1e-3, min((self.width() - 8) / float(self.pm.width()), (self.height() - 8) / float(self.pm.height())))

        def fit(self):
            self.fitted = True
            self._apply_fit()
            self.update()

        def _apply_fit(self):
            if self.pm is None:
                return
            self.scale = self._fit_scale()
            self.ox = (self.width() - self.pm.width() * self.scale) / 2.0
            self.oy = (self.height() - self.pm.height() * self.scale) / 2.0
            self._notify()

        def actual_size(self):
            self._zoom_to(1.0, self.width() / 2.0, self.height() / 2.0)

        def _clamp(self):
            if self.pm is None:
                return
            iw, ih = self.pm.width() * self.scale, self.pm.height() * self.scale
            for attr, size, win in (("ox", iw, self.width()), ("oy", ih, self.height())):
                v = getattr(self, attr)
                if size <= win:
                    v = (win - size) / 2.0                      # küçükse ortala
                else:
                    v = min(0.0, max(win - size, v))            # büyükse kenar boşluk bırakma
                setattr(self, attr, v)

        def _notify(self):
            if self.on_view is not None:
                self.on_view(self.scale)

        def _zoom_to(self, new_scale, ax, ay):
            if self.pm is None:
                return
            fs = self._fit_scale()
            new_scale = min(max(new_scale, fs), 64.0)
            ix, iy = (ax - self.ox) / self.scale, (ay - self.oy) / self.scale     # imlecin altındaki görüntü noktası
            self.scale = new_scale
            self.ox, self.oy = ax - ix * new_scale, ay - iy * new_scale
            self._clamp()
            self.fitted = abs(new_scale - fs) < 1e-6
            self._notify()
            self.update()

        # --- içerik
        def set_pixmap_full(self, pm):
            first = self.pm is None or self.pm.size() != pm.size()
            self.pm = pm
            if first or self.fitted:
                self.fitted = True
                self._apply_fit()
            self.update()

        def pixmap(self):
            return self.pm

        def image_rect(self):
            return (self.ox, self.oy, self.pm.width() * self.scale, self.pm.height() * self.scale) if self.pm is not None else None

        def resizeEvent(self, ev):
            QtGui.QWidget.resizeEvent(self, ev)
            if self.fitted:
                self._apply_fit()
            else:
                self._clamp()

        def paintEvent(self, ev):
            p = QtGui.QPainter(self)
            p.fillRect(self.rect(), QtGui.QColor(_theme.PREVIEW_BG))
            if self.pm is None:
                p.setPen(QtGui.QColor(_theme.TEXT_DIS))
                p.drawText(self.rect(), QtCore.Qt.AlignCenter, T("Ön izleme ekranı"))
            else:
                p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, self.scale < 2.0)
                p.drawPixmap(QtCore.QRectF(self.ox, self.oy, self.pm.width() * self.scale, self.pm.height() * self.scale),
                             self.pm, QtCore.QRectF(self.pm.rect()))
            p.setPen(QtGui.QColor(_theme.PREVIEW_BORDER))
            p.drawRect(self.rect().adjusted(0, 0, -1, -1))
            p.end()

        # --- fare
        def wheelEvent(self, ev):
            if self.pm is None:
                return
            try:
                pt = ev.position()
                ax, ay = pt.x(), pt.y()
            except AttributeError:
                ax, ay = ev.x(), ev.y()
            d = ev.angleDelta().y()
            if d:
                self._zoom_to(self.scale * (1.2 ** (d / 120.0)), ax, ay)
            ev.accept()

        def _pos(self, ev):
            try:
                pt = ev.position()
                return pt.x(), pt.y()
            except AttributeError:
                return float(ev.x()), float(ev.y())

        def mousePressEvent(self, ev):
            if ev.button() in (QtCore.Qt.LeftButton, QtCore.Qt.MiddleButton) and self.pm is not None:
                x, y = self._pos(ev)
                self._press = (ev.button(), x, y, self.ox, self.oy, False)
            QtGui.QWidget.mousePressEvent(self, ev)

        def mouseMoveEvent(self, ev):
            if self._press is None:
                return
            btn, x0, y0, ox0, oy0, moved = self._press
            x, y = self._pos(ev)
            if not moved and (abs(x - x0) + abs(y - y0)) < 5:
                return
            if not moved:
                self.setCursor(QtCore.Qt.ClosedHandCursor)
            self._press = (btn, x0, y0, ox0, oy0, True)
            self.ox, self.oy = ox0 + (x - x0), oy0 + (y - y0)
            self._clamp()
            self.fitted = False if self.scale > self._fit_scale() + 1e-6 else self.fitted
            self.update()

        def mouseReleaseEvent(self, ev):
            pr, self._press = self._press, None
            self.unsetCursor()
            QtGui.QWidget.mouseReleaseEvent(self, ev)
            if pr is None or pr[5] or pr[0] != QtCore.Qt.LeftButton or self.on_click is None or self.pm is None:
                return                                              # kaydırma ya da orta tuş: seçme yok
            x, y = self._pos(ev)
            u = (x - self.ox) / (self.pm.width() * self.scale)
            v = (y - self.oy) / (self.pm.height() * self.scale)
            if 0.0 <= u < 1.0 and 0.0 <= v < 1.0:
                self.on_click(u, v, bool(ev.modifiers() & QtCore.Qt.ControlModifier))

        def mouseDoubleClickEvent(self, ev):
            if self.pm is not None:
                self.fit()

    lbl = _Preview()
    lbl.on_view = lambda sc_: lbl_zoom.setText("%d%%" % int(round(sc_ * 100)))
    btn_fit.clicked.connect(lambda *_a: lbl.fit())
    btn_11.clicked.connect(lambda *_a: lbl.actual_size())
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
        ck_rr.setEnabled(gl)
        sp_bn.setEnabled(gl or ck_rf.isChecked())
    ck_gl.toggled.connect(sync_enabled)
    ck_rf.toggled.connect(sync_enabled)
    sync_enabled()

    state = {"scene": None, "key": None, "busy": False, "cancel": False, "last": 0.0,
             "out": None, "path": None, "pick": None}

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
        for wd in light_widgets + floor_widgets + [ck_fl, ck_fc, btn_r, btn_y, sp_w, cb_q, cb_aa, ck_sh, ck_gl, ck_sm, ck_rf, ck_rr, ck_cull, sp_bn, cb_th, ck_sv, ck_ao, cb_pre, bt_cust, ck_soft, sp_softr, sp_softk, cb_tm, sp_exp, ck_fr]:
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
        g["CULL_OFFSCREEN"] = ck_cull.isChecked()
        g["SOFT_SHADOW"] = float(sp_softr.value()) if ck_soft.isChecked() else 0.0
        g["SOFT_SCALE"] = sp_softk.value() / 100.0
        g["TONEMAP"] = ("none", "soft", "aces")[cb_tm.currentIndex()]
        g["EXPOSURE"] = sp_exp.value() / 100.0
        g["FRESNEL"] = ck_fr.isChecked()
        g["AO"] = ck_ao.isChecked()
        g["AO_STRENGTH"] = sp_aos.value() / 100.0
        g["AO_RADIUS"] = sp_aor.value() / 100.0
        g["AO_SAMPLES"] = sp_aon.value()
        g["ENV_MODE"] = ("off", "sky", "hdri")[cb_env.currentIndex()]
        g["ENV_FILE"] = env_state["file"]
        g["ENV_INTENSITY"] = sp_ei.value() / 100.0
        g["ENV_ROT"] = float(sp_er.value())
        g["ENV_SUN_ELEV"] = float(sp_ee.value())
        g["ENV_SUN_AZ"] = float(sp_ea.value())
        g["ENV_SAMPLES"] = sp_en.value()
        g["ENV_BACKGROUND"] = ck_ebg.isChecked()
        g["ENV_LIGHT"] = ck_eli.isChecked()
        g["ENV_REFLECT"] = ck_ere.isChecked()
        g["ENV_SUN"] = ck_esu.isChecked()
        g["ENV_KEEP_LIGHTS"] = ck_ekl.isChecked()
        g["REFLECTIONS"] = ck_rf.isChecked()
        g["REFRACTION"] = ck_rr.isChecked()
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
        lbl.fit()
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
            key = (d.Name, len(d.Objects), S.TESS_FACTOR, bool(S.CULL_OFFSCREEN),
                   tuple(sorted(o.Name for o in d.Objects if not _mats.included(o))))   # hariç tutulanlar (elle değişse de yakalanır)
            if S.CULL_OFFSCREEN:                          # kadraj dışı atma kameraya bağlıdır: kamera değişince sahne yenilenir
                key += (tuple(np.round(cam["pos"], 3)), tuple(np.round(cam["fwd"], 4)), tuple(np.round(cam["up"], 4)),
                        bool(cam["persp"]), round(float(cam["size"]), 5), round(float(aspect), 4))
            if state["scene"] is None or state["key"] != key:
                state["scene"], nobj = collect_scene(d, status, camera=cam, aspect=aspect)
                state["key"] = key
                FreeCAD.Console.PrintMessage(T("RayTrace: %d nesne, %d üçgen (hazırlık %.1f sn)\n")
                                             % (nobj, state["scene"].count, time.time() - t0))
            t1 = time.time()
            out = render(state["scene"], cam, w, h, shadows=S.SHADOWS, progress=show, tile=S.TILE,
                         tick=tick, stage=lambda s: status(s, True, None))
            if out is None:
                raise _Cancelled()
            state["out"] = out
            state["pick"] = (state["scene"], cam, w, h)     # tıkla-seç: gösterilen görüntüye ait sahne/kamera (sahne sonradan sıfırlansa da)
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

    def open_mats(*_a):
        """Malzemeler penceresi zaten açıksa yalnızca öne getirir (kapatıp yeniden taramaz); değilse açar."""
        sd = getattr(FreeCAD, "_ybt_surface_dlg", None)
        try:
            if sd is not None and sd.isVisible():
                sd.raise_()
                sd.activateWindow()
                return
        except Exception:                                 # kapanmış (silinmiş) Qt nesnesi
            pass
        from .surface_ui import open_surface
        txt = btn_m.text()
        btn_m.setText(T("Açılıyor..."))
        btn_m.setEnabled(False)
        QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        QtGui.QApplication.processEvents()                # basılı/pasif görünüm hemen çizilsin
        try:
            open_surface(on_change=lambda: state.__setitem__("scene", None), is_busy=lambda: state["busy"])
        finally:
            QtGui.QApplication.restoreOverrideCursor()
            btn_m.setText(txt)
            btn_m.setEnabled(True)
    btn_m.clicked.connect(open_mats)

    def on_preview_click(u, v, ctrl):
        """Önizlemede tıklanan nesneyi bul; Malzemeler penceresinde seç (boya kovası açıksa malzemeyi ata)."""
        if state["busy"]:
            return
        pk = state["pick"]
        if pk is None:
            lbl_st.setText(T("Önce bir render alın; sonra önizlemede parçaya tıklayabilirsiniz."))
            return
        sc, cam_, w_, h_ = pk
        try:
            from .pick import pick as _pick
            hit = _pick(sc, cam_, w_, h_, u * w_, v * h_)
        except Exception:
            import traceback
            FreeCAD.Console.PrintError(T("RayTrace hatası:\n") + traceback.format_exc())
            return
        if hit is None:
            lbl_st.setText(T("Tıklanan yerde nesne yok (arka plan ya da zemin)."))
            return
        sd = getattr(FreeCAD, "_ybt_surface_dlg", None)
        try:
            alive_ = sd is not None and sd.isVisible()
        except Exception:                             # pencere kapanmış (silinmiş Qt nesnesi)
            alive_ = False
        if not alive_:
            open_mats()
            sd = getattr(FreeCAD, "_ybt_surface_dlg", None)
        if sd is None:
            return
        sd._ybt_api["pick"](hit[0], ctrl)
        o = FreeCAD.ActiveDocument.getObject(hit[0]) if FreeCAD.ActiveDocument else None
        lbl_st.setText(T("Tıklanan: %s") % (o.Label if o is not None else hit[0]))
    lbl.on_click = on_preview_click
    lbl.setToolTip(T("Render aldıktan sonra bir parçaya tıklayın: Malzemeler penceresinde seçilir (Ctrl: seçime ekle)"))

    FreeCAD._raytrace_dlg = dlg
    dlg._raytrace_handlers = (do_render, do_stop, do_save, do_refresh, status, tick, show)  # referansları canlı tut
    _theme.fix_combos(dlg)
    dlg.show()
    # test/otomasyon için dışarıdan tetikleme
    dlg._raytrace_api = dict(render=do_render, widgets=dict(width=sp_w, quality=cb_q, ao=ck_ao, soft=ck_soft, soft_radius=sp_softr, soft_scale=sp_softk, tonemap=cb_tm, exposure=sp_exp, fresnel=ck_fr, ao_strength=sp_aos, ao_radius=sp_aor, ao_samples=sp_aon, shadows=ck_sh, glass=ck_gl, smooth=ck_sm, cull=ck_cull, reflections=ck_rf,
                                                            refraction=ck_rr, bounces=sp_bn, autosave=ck_sv, aa=cb_aa, threads=cb_th, floor=ck_fl, floor_color=cb_fl, floor_opacity=sp_fo, floor_reflect=sp_fr, floor_offset=sp_fz, floor_texture=cb_ft, floor_tex_scale=sp_fs, lights=lrows, ambient=sp_amb, fclights=ck_fc),
                             status=lbl_st, bar=bar, pct=pct, state=state)
