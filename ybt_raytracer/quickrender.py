# -*- coding: utf-8 -*-
"""Hızlı Render: render'ı panel açmadan, doğrudan 3B görünümün üzerinde, kameranın kadrajında yapar.

Akış: etkin kamera nesnesi varsa 3B görünüm o kameranın bakışına getirilir (kadraj görünümün içine sığar); render bu kadraj dikdörtgeninin
üzerine çizilir. Etkin kamera yoksa şu anki 3B görünümün kamerası ve tüm görünüm alanı kullanılır. İki geçiş: önce küçük ve hızlı (kaba önizleme),
sonra panelde ayarlı kalite ve genişlikte. Ayarlar (kalite, ışık, AO, HDRI...) render panelindekilerle aynıdır: panel açıksa
paneldeki değerler, kapalıysa belgede saklı ayarlar kullanılır. Esc ya da ✕: iptal / kapat; Kaydet: PNG olarak kaydeder.
"""
import time

import numpy as np

from . import settings as S
from .i18n import T

_KEY = "_ybt_quick_overlay"
_running = {"on": False}


def _qt():
    from PySide import QtCore, QtGui
    return QtCore, QtGui


def _view_widget():
    """Etkin 3B görünümün Qt bileşeni (üzerine yer paylaşımı eklenecek)."""
    import FreeCADGui as Gui
    QtCore, QtGui = _qt()
    import FreeCAD
    mw = Gui.getMainWindow()
    mdi = mw.findChild(QtGui.QMdiArea)
    if mdi is None:
        return None
    sub = mdi.currentSubWindow() or mdi.activeSubWindow()
    if sub is None:                                          # odak başka yerdeyse (panel vb.): belgenin görünür 3B görünümü
        name = FreeCAD.ActiveDocument.Name if FreeCAD.ActiveDocument else ""
        cands = [s for s in mdi.subWindowList() if s.widget() is not None and s.isVisible()]
        by_name = [s for s in cands if name and name in s.windowTitle()]
        sub = (by_name or cands or [None])[0]
    return sub.widget() if sub is not None else None


def close_overlay():
    import FreeCAD
    ov = getattr(FreeCAD, _KEY, None)
    if ov is not None:
        try:
            ov.close_all()
        except Exception:
            pass
        setattr(FreeCAD, _KEY, None)


def _fit_rect(W, H, aspect):
    """W x H alanına `aspect` oranlı en büyük dikdörtgen, ortalı: (x, y, w, h)."""
    if W / float(H) > aspect:
        h = H
        w = int(round(H * aspect))
    else:
        w = W
        h = int(round(W / aspect))
    return (W - w) // 2, (H - h) // 2, max(w, 16), max(h, 16)


class _Overlay(object):
    """3B görünümün üzerinde: görüntü, durum çubuğu, Kaydet ve ✕ düğmeleri."""

    def __init__(self, host, rect, on_close, on_save):
        QtCore, QtGui = _qt()
        self.QtCore, self.QtGui = QtCore, QtGui
        x, y, w, h = rect
        self.host = host
        self.alive = True
        self.on_close = on_close
        self.on_save = on_save
        self.on_double = None                                    # çift tıklama: (u, v, ctrl) -> tıklanan yüzeyin malzemesini seç
        self.img = QtGui.QLabel(host)
        self.img.setGeometry(x, y, w, h)
        self.img.setScaledContents(True)
        self.img.setStyleSheet("background-color: #1e1e22; border: 2px solid #ff9a2e;")
        self.img.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.bar = QtGui.QLabel(host)
        self.bar.setStyleSheet("background-color: rgba(20,20,24,200); color: #f0f0f0; padding: 3px 8px; border-radius: 3px;")
        self.btn_save = QtGui.QPushButton(T("Kaydet"), host)
        self.btn_close = QtGui.QPushButton("✕", host)
        for b in (self.btn_save, self.btn_close):
            b.setStyleSheet("QPushButton { background-color: rgba(20,20,24,220); color: #f0f0f0; border: 1px solid #55555a; border-radius: 3px; "
                            "padding: 3px 10px; min-width: 0px; } QPushButton:hover { background-color: #ff9a2e; color: #111; }")
        self.btn_save.setToolTip(T("Görüntüyü PNG olarak kaydeder"))
        self.btn_close.setToolTip(T("Kapat (Esc). Render sürüyorsa iptal eder"))
        self.btn_save.setEnabled(False)
        self.btn_close.clicked.connect(self._close_clicked)
        self.btn_save.clicked.connect(lambda *_a: self.on_save())
        self._place()
        for wd in (self.img, self.bar, self.btn_save, self.btn_close):
            wd.show()
            wd.raise_()
        # Esc ile kapat
        self._filter = _EscFilter(self, QtCore)
        self.img.installEventFilter(self._filter)
        self.img.setFocus()

    def _place(self):
        g = self.img.geometry()
        self.btn_close.adjustSize()
        self.btn_save.adjustSize()
        self.btn_close.move(g.right() - self.btn_close.width() - 8, g.top() + 8)
        self.btn_save.move(self.btn_close.x() - self.btn_save.width() - 6, g.top() + 8)
        self.bar.adjustSize()
        self.bar.move(g.left() + 8, g.top() + 8)

    def set_status(self, text):
        self.bar.setText(text)
        self.bar.adjustSize()
        self.bar.raise_()

    def set_array(self, arr, w, h):
        QtCore, QtGui = self.QtCore, self.QtGui
        a = np.ascontiguousarray(arr)
        qi = QtGui.QImage(a.data, w, h, 3 * w, QtGui.QImage.Format_RGB888).copy()
        self.img.setPixmap(QtGui.QPixmap.fromImage(qi))
        for wd in (self.bar, self.btn_save, self.btn_close):
            wd.raise_()

    def _close_clicked(self, *_a):
        self.on_close()

    def close_all(self):
        self.alive = False
        for wd in (self.img, self.bar, self.btn_save, self.btn_close):
            try:
                wd.hide()
                wd.deleteLater()
            except Exception:
                pass


class _EscFilter(object):
    def __new__(cls, ov, QtCore):
        class F(QtCore.QObject):
            def eventFilter(self, obj, ev):
                if ev.type() == QtCore.QEvent.KeyPress and ev.key() == QtCore.Qt.Key_Escape:
                    ov.on_close()
                    return True
                if ev.type() == QtCore.QEvent.MouseButtonDblClick and ev.button() == QtCore.Qt.LeftButton and ov.on_double is not None:
                    p = ev.position() if hasattr(ev, "position") else ev.pos()
                    g = ov.img.size()
                    ctrl = bool(ev.modifiers() & QtCore.Qt.ControlModifier)
                    ov.on_double(p.x() / float(max(1, g.width())), p.y() / float(max(1, g.height())), ctrl)
                    return True
                return False
        return F(ov.img)


def _apply_settings(doc):
    """Render ayarlarını S'ye al: panel açıksa panelden, değilse belgede saklı ayarlardan."""
    from . import commands, docstore, lightobj
    dlg = commands._panel()
    api = getattr(dlg, "_raytrace_api", None) if dlg is not None else None
    if api and api.get("apply_all"):
        api["apply_all"]()
    else:
        docstore.load_settings(doc)
    if str(S.LIGHT_MODE) != "legacy":
        lightobj.apply_to_settings(doc)
    else:
        S._OBJ_LIGHTS = None


def run():
    """Hızlı Render'ı çalıştırır (araç çubuğu komutu)."""
    import FreeCAD
    import FreeCADGui as Gui
    from . import cameraobj, docstore
    from .freecad_scene import collect_scene, read_camera
    from .parallel import _Cancelled
    from .render import render
    from .output import pick_out_path, write_png
    QtCore, QtGui = _qt()
    if _running["on"]:
        return
    doc = FreeCAD.ActiveDocument
    if doc is None or Gui.ActiveDocument is None or getattr(Gui.ActiveDocument, "ActiveView", None) is None:
        return
    host = _view_widget()
    if host is None:
        FreeCAD.Console.PrintWarning(T("Hızlı Render: 3B görünüm bulunamadı.\n"))
        return
    close_overlay()
    _running["on"] = True
    state = {"alive": True, "out": None}
    ov = None
    saved = {}
    try:
        co = cameraobj.active_camera(doc)
        if co is not None:
            cameraobj.look_through(co)                              # kadraj görünümün içine oturur
            for _ in range(3):
                QtCore.QCoreApplication.processEvents()
            cam, aspect = cameraobj.render_camera(co)
            rect = _fit_rect(host.width(), host.height(), aspect)
        else:
            cam, aspect = read_camera(Gui.ActiveDocument.ActiveView)
            rect = (0, 0, host.width(), host.height())
            aspect = rect[2] / float(rect[3])

        def on_close():
            state["alive"] = False
            close_overlay()

        def on_save():
            if state["out"] is None:
                return
            try:
                path = pick_out_path(doc.FileName)
                write_png(path, state["out"])
                ov.set_status(T("kaydedildi: %s") % path)
                FreeCAD.Console.PrintMessage(T("Hızlı Render: kaydedildi: %s\n") % path)
            except Exception as ex:
                ov.set_status(T("KAYDEDİLEMEDİ (%s)") % ex)

        def on_double(u, v, ctrl):
            """Çift tıklanan yüzeyi bul; Malzeme penceresini açıp o nesneyi seçer (boya kovası açıksa malzemeyi atar)."""
            sc = state.get("scene")
            if sc is None:
                return
            from .pick import pick as _pick
            from . import commands
            try:
                w_, h_ = state["size"]
                hit = _pick(sc, cam, w_, h_, u * w_, v * h_)
            except Exception:
                import traceback
                FreeCAD.Console.PrintError(T("RayTrace hatası:\n") + traceback.format_exc())
                return
            if hit is None:
                ov.set_status(T("Tıklanan yerde nesne yok (arka plan ya da zemin)."))
                return
            sd = getattr(FreeCAD, "_ybt_surface_dlg", None)
            try:
                alive_ = sd is not None and sd.isVisible()
            except Exception:
                alive_ = False
            if not alive_:
                commands.open_materials()
                sd = getattr(FreeCAD, "_ybt_surface_dlg", None)
            if sd is None:
                return
            sd._ybt_api["pick"](hit[0], ctrl)
            o = doc.getObject(hit[0])
            ov.set_status(T("Seçildi: %s") % (o.Label if o is not None else hit[0]))
            try:
                sd.raise_()
                sd.activateWindow()
            except Exception:
                pass

        ov = _Overlay(host, rect, on_close, on_save)
        ov.on_double = on_double
        FreeCAD._ybt_quick_overlay = ov
        ov.set_status(T("hazırlanıyor..."))
        QtCore.QCoreApplication.processEvents()
        _apply_settings(doc)
        saved.update({k: getattr(S, k) for k in ("WIDTH", "AA", "SOFT_SAMPLES")})      # iki geçiş bunları geçici değiştirir
        t0 = time.time()
        last = [0.0]

        def alive():
            return state["alive"] and ov.alive

        def status(msg, force=False, frac=None):
            now = time.time()
            if force or now - last[0] > 0.15:
                last[0] = now
                ov.set_status(msg)
                QtCore.QCoreApplication.processEvents()
            if not alive():
                raise _Cancelled()

        def tick():
            QtCore.QCoreApplication.processEvents()
            return alive()

        scene, nobj = collect_scene(doc, status, camera=cam, aspect=aspect)
        if not alive():
            raise _Cancelled()
        state["scene"] = scene
        state["size"] = (max(64, int(S.WIDTH)), max(1, int(round(max(64, int(S.WIDTH)) / aspect))))
        final_w = max(64, int(S.WIDTH))
        passes = []
        w1 = max(120, int(rect[2] * 0.35))
        if w1 * 1.4 < final_w:
            passes.append((w1, 0, T("hızlı önizleme")))               # kaba, kenar yumuşatmasız
        passes.append((final_w, int(S.AA), T("ışınlar izleniyor")))
        out = None
        for (w, aa, label) in passes:
            h = max(1, int(round(w / aspect)))
            S.WIDTH = w
            S.AA = aa
            rough = (w, aa, label) != passes[-1]
            S.SOFT_SAMPLES = min(int(saved["SOFT_SAMPLES"]), 8) if rough else saved["SOFT_SAMPLES"]   # kaba önizlemede az gölge örneği
            S.QUICK_PASS = rough                                  # ışık başına örnek sayısı da en çok 8 olur

            def show(img, rows, frac=None, label=label, w=w, h=h):
                if not alive():
                    return False
                ov.set_array(np.clip(img * 255.0, 0, 255).astype(np.uint8), w, h)
                ov.set_status("%s  %d%%" % (label, int(100 * (rows / float(h) if frac is None else frac))))
                QtCore.QCoreApplication.processEvents()
                return alive()

            t1 = time.time()
            out = render(scene, cam, w, h, shadows=S.SHADOWS, progress=show, tile=S.TILE, tick=tick,
                         stage=lambda s: status(s, True, None))
            if out is None:
                raise _Cancelled()
            ov.set_array(out, w, h)
            if (w, aa, label) != passes[-1]:
                ov.set_status("%s %.1f sn" % (label, time.time() - t1))
        state["out"] = out
        ov.btn_save.setEnabled(True)
        ov.set_status(T("bitti: %dx%d | %.1f sn | Esc: kapat") % (out.shape[1], out.shape[0], time.time() - t0))
        FreeCAD.Console.PrintMessage(T("Hızlı Render: %dx%d, %.1f sn\n") % (out.shape[1], out.shape[0], time.time() - t0))
    except _Cancelled:
        FreeCAD.Console.PrintMessage(T("Hızlı Render: iptal edildi.\n"))
        close_overlay()
    except Exception:
        import traceback
        FreeCAD.Console.PrintError(T("RayTrace hatası:\n") + traceback.format_exc())
        close_overlay()
    finally:
        for k, v in saved.items():
            setattr(S, k, v)
        S.QUICK_PASS = False
        _running["on"] = False
