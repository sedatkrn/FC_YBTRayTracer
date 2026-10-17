# -*- coding: utf-8 -*-
"""
Arayüzsüz (panelsiz) API: ayar penceresini açmadan render alma ve animasyon karesi üretme.

Temel kullanım (FreeCAD içinde: makro, Python konsolu ya da `freecadcmd`):

    from ybt_raytracer import api
    api.render_document(App.ActiveDocument, "/tmp/sahne.png", width=1280, floor=True, aa=3)

Turntable (kamera çevresinde dönüş; sahne bir kez hazırlanır, her karede yalnız kamera değişir):

    doc = App.ActiveDocument
    scene = api.prepare_scene(doc)
    for i, cam in enumerate(api.orbit_cameras(scene, frames=72, elevation=20)):
        api.render_document(doc, "/tmp/kare_%04d.png" % i, width=960, camera=cam, scene=scene)

Hareketli parçalar (nesnelerin yerleşimi her karede değişir, şekilleri değişmez):

    cache = {}                                   # üçgenleme önbelleği: şekiller bir kez üçgenlenir
    for i in range(72):
        doc.getObject("Krank").Placement = ...    # kareyi hazırla
        doc.recompute()
        api.render_document(doc, "/tmp/kare_%04d.png" % i, width=960, camera=cam, tess_cache=cache)
    # Şekil parametreleri (Length, Radius ...) değiştiyse önbelleği yeni bir sözlükle (cache = {}) sıfırlayın.

Ayarlar: `settings.py` içindeki her ad küçük harfle anahtar sözcük olarak verilebilir (floor=True, shadows=False,
aa=4, tess_factor=0.002, bounces=3 ...). Değerler yalnız o çağrı için geçerlidir; çağrıdan sonra eski haline döner.
"""
import os
import numpy as np

from . import settings as S
from .output import write_png


# ------------------------------------------------------------------ ayarlar
class _Override(object):
    """Ayarları (settings.py) geçici olarak değiştirir; çıkışta (hata olsa da) eski değerleri geri yazar."""

    def __init__(self, values):
        self.values = {}
        for k, v in (values or {}).items():
            K = str(k).upper()
            if K.startswith("_") or not hasattr(S, K):
                names = sorted(n for n in dir(S) if n.isupper() and not n.startswith("_"))
                raise TypeError("bilinmeyen ayar: %r (geçerli ayarlar: %s)" % (k, ", ".join(n.lower() for n in names)))
            self.values[K] = v
        self.saved = {}

    def __enter__(self):
        for K, v in self.values.items():
            old = getattr(S, K)
            self.saved[K] = list(old) if isinstance(old, list) else old
            setattr(S, K, v)
        return self

    def __exit__(self, *_exc):
        for K, v in self.saved.items():
            setattr(S, K, v)
        return False


# ------------------------------------------------------------------ kamera
def make_camera(pos, target=None, up=(0.0, 0.0, 1.0), fov=40.0, ortho_height=None, fwd=None):
    """Kamera sözlüğü. pos: göz noktası (mm). Bakış: target (nokta) ya da fwd (yön vektörü).
    fov: perspektifte DİKEY bakış açısı (derece); ortho_height verilirse ortografik kamera (görünür yükseklik, mm)."""
    pos = np.asarray(pos, dtype=np.float64)
    if fwd is None:
        if target is None:
            raise ValueError("target ya da fwd verilmeli")
        fwd = np.asarray(target, dtype=np.float64) - pos
    fwd = np.asarray(fwd, dtype=np.float64)
    if np.linalg.norm(fwd) < 1e-12:
        raise ValueError("kamera hedefle aynı noktada")
    cam = dict(pos=pos, fwd=fwd, up=np.asarray(up, dtype=np.float64))
    if ortho_height is not None:
        cam["persp"], cam["size"] = False, float(ortho_height)
    else:
        cam["persp"], cam["size"] = True, float(np.radians(fov))
    return cam


def _as_camera(cam):
    """Kullanıcı sözlüğünü render'ın beklediği biçime çevirir (target/fov kısayolları kabul edilir)."""
    if "fwd" in cam and "persp" in cam and "size" in cam and "up" in cam:
        return cam
    c = dict(cam)
    if "fwd" not in c:
        c["fwd"] = np.asarray(c["target"], dtype=np.float64) - np.asarray(c["pos"], dtype=np.float64)
    c.setdefault("up", (0.0, 0.0, 1.0))
    if "ortho_height" in c:
        c["persp"], c["size"] = False, float(c["ortho_height"])
    else:
        c.setdefault("persp", True)
        if "size" not in c:
            c["size"] = float(np.radians(c.get("fov", 40.0)))
    for k in ("pos", "fwd", "up"):
        c[k] = np.asarray(c[k], dtype=np.float64)
    return c


def fit_camera(scene, direction=(1.0, -1.0, 0.8), up=(0.0, 0.0, 1.0), fov=35.0, margin=1.15, persp=True):
    """Sahneyi (sınır küresiyle) kadraja sığdıran kamera. direction: sahne merkezinden kameraya doğru yön.
    Varsayılan: FreeCAD'in izometrik bakışına yakın. margin: kenar boşluğu çarpanı."""
    d = np.asarray(direction, dtype=np.float64)
    d = d / np.linalg.norm(d)
    r = scene.diag / 2.0 * float(margin)
    ctr = np.asarray(scene.center, dtype=np.float64)
    if persp:
        dist = r / np.sin(np.radians(fov) / 2.0)            # küçük kenara göre (render da küçük kenara uygular)
        return make_camera(ctr + d * dist, ctr, up, fov=fov)
    return make_camera(ctr + d * (scene.diag * 2.0), ctr, up, ortho_height=2.0 * r)


def orbit_cameras(scene, frames=72, elevation=20.0, start_azimuth=0.0, fov=35.0, margin=1.15, center=None,
                  radius=None, up=(0.0, 0.0, 1.0), persp=True, endpoint=False):
    """Sahne çevresinde dönen kameralar (turntable). Liste döner (len = frames).
    azimut 0 = önden bakış (kamera -Y tarafında); artan açı kamerayı yukarıdan bakınca saat yönünün tersine döndürür.
    elevation: yükseklik açısı (derece). radius: kamera uzaklığı (mm); verilmezse sahneyi sığdıracak kadar.
    center: dönüş merkezi (mm); verilmezse sahnenin sınır kutusu merkezi. endpoint=True: son kare 360° (ilk kareyle aynı)."""
    ctr = np.asarray(scene.center if center is None else center, dtype=np.float64)
    el = np.radians(float(elevation))
    r = scene.diag / 2.0 * float(margin)
    if radius is None:
        radius = r / np.sin(np.radians(fov) / 2.0) if persp else scene.diag * 2.0
    n = max(1, int(frames))
    steps = np.linspace(0.0, 360.0, n) if (endpoint and n > 1) else np.arange(n) * (360.0 / n)
    cams = []
    for a in steps:
        az = np.radians(float(start_azimuth) + float(a))
        d = np.array([np.sin(az) * np.cos(el), -np.cos(az) * np.cos(el), np.sin(el)])
        if persp:
            cams.append(make_camera(ctr + d * radius, ctr, up, fov=fov))
        else:
            cams.append(make_camera(ctr + d * radius, ctr, up, ortho_height=2.0 * r))
    return cams


def camera_from_view(view=None):
    """Aktif 3B görünümün kamerası (yalnız arayüzlü FreeCAD'de). Döner (kamera, en/boy oranı)."""
    import FreeCADGui as Gui
    from .freecad_scene import read_camera
    if view is None:
        view = Gui.ActiveDocument.ActiveView
    return read_camera(view)


# ------------------------------------------------------------------ sahne
_PREP_KEYS = ("tess_factor", "cull_offscreen", "cull_margin", "invisible_alpha")    # sahne hazırlığını etkileyen ayarlar


def prepare_scene(doc=None, tess_cache=None, status=None, camera=None, aspect=None, **settings):
    """Belgenin görünür nesnelerini Scene'e çevirir (üçgenleme + ön hesaplar). Aynı sahneyle birçok kare
    alınacaksa (yalnız kamera/ışık/kalite değişiyor) bir kez hazırlayıp `scene=` ile geri verin.
    "Render'a dahil et" işareti kaldırılmış nesneler (Surface penceresi) sahneye girmez.
    tess_cache: boş sözlük -> hareketli parça animasyonu için üçgenleme önbelleği (modül açıklamasına bakın).
    camera/aspect + cull_offscreen=True: kadraj dışındaki nesneler sahneye alınmaz (sahne yalnız bu kamera için geçerlidir).
    settings: tess_factor, cull_offscreen, cull_margin gibi hazırlığı etkileyen ayarlar."""
    from .freecad_scene import collect_scene
    doc = _doc(doc)
    cam = _as_camera(camera) if camera is not None else None
    with _Override(settings):
        scene, nobj = collect_scene(doc, status or (lambda *a, **k: None), tess_cache=tess_cache,
                                    camera=cam, aspect=aspect or 16.0 / 9.0)
    scene.nobj = nobj
    return scene


def _doc(doc):
    if doc is None:
        import FreeCAD
        doc = FreeCAD.ActiveDocument
    if doc is None:
        raise RuntimeError("açık belge yok")
    return doc


# ------------------------------------------------------------------ render
def render_scene(scene, camera, width=None, height=None, aspect=None, out_path=None, settings=None,
                 fc_lights=False, progress=None, tick=None, stage=None, **kw):
    """Hazır Scene'den tek kare. Döner: (h, w, 3) uint8 dizi (out_path verilirse PNG de yazılır).
    camera: make_camera/fit_camera/orbit_cameras çıktısı (ya da pos+target(+fov) sözlüğü).
    width/height: piksel; yalnız biri verilirse diğeri aspect'ten (varsayılan 16:9) hesaplanır.
    settings: ayar sözlüğü; kw: ayarlar (floor=True ...) -- ikisi birleştirilir."""
    from .render import render
    values = dict(settings or {})
    values.update(kw)
    if fc_lights:                                           # kullanıcı ışıkları kendisi verdiyse onlar geçerli
        given = {str(k).upper() for k in values}
        from .freecad_scene import read_freecad_lights
        lights, amb, amb_col, _info = read_freecad_lights()
        for K, v in (("LIGHTS", lights), ("AMBIENT", amb), ("AMBIENT_COLOR", amb_col)):
            if K not in given:
                values[K] = v
    cam = _as_camera(camera)
    with _Override(values):
        asp = aspect or 16.0 / 9.0
        w = int(width if width else (round(height * asp) if height else S.WIDTH))
        h = int(height if height else max(1, round(w / asp)))
        out = render(scene, cam, w, h, shadows=S.SHADOWS, progress=progress, tile=S.TILE, tick=tick, stage=stage)
    if out is None:
        return None
    if out_path:
        _write(out_path, out)
    return out


def render_document(doc=None, out_path=None, width=None, height=None, camera=None, aspect=None, scene=None,
                    tess_cache=None, settings=None, fc_lights=False, status=None, progress=None, tick=None,
                    stage=None, **kw):
    """Belgeyi panelsiz render eder. Döner: (h, w, 3) uint8 dizi (out_path verilirse PNG de yazılır).

    doc       FreeCAD belgesi (None = aktif belge)
    out_path  PNG yolu (klasör yoksa oluşturulur); None = yalnız diziyi döndür
    width     piksel (varsayılan: settings.WIDTH); height verilmezse en/boy oranından hesaplanır
    camera    make_camera/fit_camera/orbit_cameras çıktısı. None: arayüzlü FreeCAD'de aktif görünümün kamerası ve
              oranı; arayüzsüzde sahneyi sığdıran izometrik kamera, oran 16:9 (aspect ile değiştirilir)
    scene     prepare_scene çıktısı (verilirse belge yeniden taranmaz/üçgenlenmez)
    tess_cache  boş sözlük: hareketli parça animasyonunda üçgenleme önbelleği (modül açıklaması)
    fc_lights True: FreeCAD'in Tercihler > Display > Light Sources ışıklarını kullan
    **kw      ayarlar (floor=True, shadows=False, aa=3, tess_factor=0.002 ...)"""
    doc = _doc(doc)
    values = dict(settings or {})
    values.update(kw)
    if camera is None:                                      # arayüzlü FreeCAD: aktif görünümün kamerası
        try:
            import FreeCADGui as Gui
            gd = Gui.ActiveDocument
            if gd is not None and gd.Document.Name == doc.Name and gd.ActiveView is not None:
                camera, a0 = camera_from_view(gd.ActiveView)
                aspect = aspect or (float(width) / float(height) if (width and height) else a0)
        except Exception:
            camera = None
    if aspect is None and width and height:
        aspect = float(width) / float(height)
    if scene is None:
        # yalnız hazırlığı etkileyen ayarlar burada geçerli (kamera biliniyorsa kadraj dışı atma da); kalanı render_scene'de
        scene = prepare_scene(doc, tess_cache=tess_cache, status=status, camera=camera, aspect=aspect,
                              **{k: v for k, v in values.items() if str(k).lower() in _PREP_KEYS})
    if camera is None:                                      # arayüzsüz: sahneyi sığdıran izometrik kamera
        camera = fit_camera(scene)
    return render_scene(scene, camera, width=width, height=height, aspect=aspect, out_path=out_path,
                        settings=values, fc_lights=fc_lights, progress=progress, tick=tick, stage=stage)


def pick_object(scene, camera, width, height, x, y):
    """Görüntüde (x, y) pikselindeki nesne: (nesne_adı, üçgen_indeksi) ya da None (arka plan / zemin).
    scene: prepare_scene çıktısı; camera/width/height: o görüntünün render parametreleri."""
    from .pick import pick
    return pick(scene, _as_camera(camera), int(width), int(height), float(x), float(y))


def turntable(doc=None, out_dir=".", frames=72, width=960, elevation=20.0, name="kare", fov=35.0, aspect=None,
              tess_cache=None, on_frame=None, **kw):
    """Kamerayı sahne çevresinde döndürüp PNG kare dizisi yazar: <out_dir>/<name>_0001.png ...
    Döner: yazılan dosya yolları listesi. on_frame(i, n, yol) her kareden sonra çağrılır (False dönerse durur).
    Videoya çevirmek için (ffmpeg kuruluysa):
        ffmpeg -framerate 30 -i <out_dir>/<name>_%04d.png -pix_fmt yuv420p turntable.mp4"""
    doc = _doc(doc)
    scene = prepare_scene(doc, tess_cache=tess_cache, **{k: v for k, v in kw.items() if str(k).lower() == "tess_factor"})
    paths = []
    cams = orbit_cameras(scene, frames=frames, elevation=elevation, fov=fov)
    for i, cam in enumerate(cams):
        path = os.path.join(out_dir, "%s_%04d.png" % (name, i + 1))
        render_scene(scene, cam, width=width, aspect=aspect, out_path=path, **kw)
        paths.append(path)
        if on_frame is not None and on_frame(i + 1, len(cams), path) is False:
            break
    return paths


def _write(path, img):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    write_png(path, np.ascontiguousarray(img))
