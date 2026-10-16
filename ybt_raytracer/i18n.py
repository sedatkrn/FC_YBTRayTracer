# -*- coding: utf-8 -*-
"""Arayüz dili: Türkçe (kaynak metinler) / English. T("Türkçe metin") -> seçili dilde metin.
Seçim FreeCAD kullanıcı parametrelerine kaydedilir; kayıt yoksa FreeCAD arayüz diline göre belirlenir."""

LANG = "tr"
_PARAM = "User parameter:BaseApp/Preferences/Mod/FCYBTRayTracer"


def T(s):
    if LANG == "en":
        return EN.get(s, s)
    return s


def set_lang(lang, save=True):
    global LANG
    LANG = "en" if lang == "en" else "tr"
    if save:
        try:
            import FreeCAD
            FreeCAD.ParamGet(_PARAM).SetString("Lang", LANG)
        except Exception:
            pass


def init_lang():
    """Kayıtlı dil; yoksa FreeCAD'in arayüz dili Türkçe ise 'tr', değilse 'en'."""
    global LANG
    try:
        import FreeCAD
        v = FreeCAD.ParamGet(_PARAM).GetString("Lang", "")
        if v in ("tr", "en"):
            LANG = v
            return LANG
    except Exception:
        pass
    loc = ""
    try:
        import FreeCADGui
        loc = str(FreeCADGui.getLocale())
    except Exception:
        pass
    LANG = "tr" if loc.lower().startswith(("tür", "tur", "tr")) else "en"
    return LANG


EN = {
    # --- ui: kalite ---
    "RayTrace: açık belge yok.\n": "RayTrace: no open document.\n",
    "Kalite Ayarları": "Quality Settings",
    "Kapalı": "Off",
    "Otomatik": "Auto",
    "Hızlı": "Fast",
    "İnce": "Fine",
    "Gölgeler": "Shadows",
    "Saydamlık (cam)": "Transparency (glass)",
    "Yumuşak yüzeyler": "Smooth surfaces",
    "Bitince otomatik kaydet": "Save automatically when done",
    "Genişlik": "Width",
    "Kalite": "Quality",
    "Kenar yumuşatma": "Anti-aliasing",
    "Yansıma sayısı": "Reflection bounces",
    "Cam yansıması": "Glass reflection",
    "Yüzey yansıması": "Surface reflection",
    "Kırılma (IOR)": "Refraction (IOR)",
    "Çekirdek": "Cores",
    "Render için kullanılacak çekirdek (iş parçacığı) sayısı; Otomatik = işlemci çekirdek sayısı":
        "Number of cores (workers) used for rendering; Auto = number of CPU cores",
    "Cam kırılma indisi (Snell yasası): cam 1.5, su 1.33, elmas 2.4. Kapalı = ışık düz geçer (en hızlı). Kırılma için nesne saydam olmalı; küre/silindir gibi kapalı gövdelerde en iyi sonuç.":
        "Glass index of refraction (Snell's law): glass 1.5, water 1.33, diamond 2.4. Off = light passes straight through (fastest). "
        "The object must be transparent; works best on closed bodies such as spheres and cylinders.",
    "Eğri yüzeyleri (küre, simit, silindir) pürüzsüz gölgeler; keskin kenarlar (küp, plaka) korunur. Kapalıysa üçgenler görünür.":
        "Shades curved surfaces (sphere, torus, cylinder) smoothly; sharp edges (cube, plate) are kept. When off, triangles are visible.",
    "Çıktı genişliği; yükseklik 3B görünümün oranından gelir": "Output width; height follows the 3D view's aspect ratio",
    "Yüzey pürüzsüzlüğü (üçgenleme inceliği). Değişince sahne yeniden okunur":
        "Surface smoothness (tessellation fineness). The scene is re-read when changed",
    "Kenar yumuşatma: yalnız kenar piksellerinde çoklu örnekleme yapar": "Anti-aliasing: multi-samples only the edge pixels",
    "Nesnenin Transparency (saydamlık) özelliğine göre arkası görünür": "Objects show what is behind them according to their Transparency property",
    "Cam yüzeylerin yansıması (Fresnel: eğik bakışta daha çok)": "Reflection of glass surfaces (Fresnel: stronger at grazing angles)",
    "Opak yüzeylerin sabit yansıması; 0 = kapalı (en hızlı)": "Constant reflection of opaque surfaces; 0 = off (fastest)",
    "Bir ışının en çok kaç kez yansıyacağı": "Maximum number of times a ray can bounce",
    # --- ui: ışık ---
    "Işık Ayarları": "Light Settings",
    "Işık rengi": "Light colour",
    "FreeCAD ışık ayarlarını kullan": "Use FreeCAD light settings",
    "İşaretliyse Tercihler > Display > Light Sources ayarları kullanılır; aşağıdaki ayarlar devre dışı kalır":
        "When checked, Preferences > Display > Light Sources is used and the settings below are disabled",
    "Ana ışık": "Key light",
    "Dolgu ışığı": "Fill light",
    "Arka ışık": "Back light",
    "Işık gücü": "Light power",
    "Yatay açı (kameraya göre; eksi = sol, artı = sağ, 180 = arkadan)": "Horizontal angle (relative to the camera; negative = left, positive = right, 180 = from behind)",
    "Dikey açı (artı = yukarıdan)": "Vertical angle (positive = from above)",
    "Gölge": "Shadow",
    "Bu ışık gölge düşürsün (her gölgeli ışık süreyi artırır)": "This light casts shadows (each shadow-casting light increases render time)",
    "Yatay": "Horizontal",
    "Dikey": "Vertical",
    "Ortam ışığı": "Ambient light",
    # --- ui: zemin ---
    "Sanal Zemin": "Virtual Floor",
    "Sanal zemin ekle": "Add virtual floor",
    "Sahnenin en alt noktasına (+ ofset) yatay, sonsuz bir zemin koyar. FreeCAD'de Z yukarı kabul edilir.":
        "Places a horizontal, infinite floor at the scene's lowest point (+ offset). Z is up in FreeCAD.",
    "Zemin rengi": "Floor colour",
    "Zemin opaklığı; 100 = opak, düşünce zemin saydamlaşır": "Floor opacity; 100 = opaque, lower values make the floor transparent",
    "Zemin yansıması (eğik bakışta güçlenir); 0 = yansımasız, en hızlı": "Floor reflection (stronger at grazing angles); 0 = none, fastest",
    "Zemin yüksekliği: sahnenin en alt z değerine göre ofset (eksi = aşağı, artı = yukarı)":
        "Floor height: offset from the scene's lowest z (negative = down, positive = up)",
    "Renk": "Colour",
    "Opaklık": "Opacity",
    "Yansıma": "Reflection",
    "Ofset": "Offset",
    "Düz renk": "Solid colour",
    "Dosyadan…": "From file…",
    "Zemin dokusu. 'Dosyadan…' ile kendi PNG/JPG görüntünüzü seçebilirsiniz.": "Floor texture. Use 'From file…' to pick your own PNG/JPG image.",
    "Dokunun zemindeki genişliği (mm). Otomatik = doku türüne göre sahne büyüklüğüyle orantılı":
        "Width of the texture on the floor (mm). Auto = proportional to scene size, depending on the texture",
    "Doku": "Texture",
    "Doku boyu": "Texture size",
    "Zemin dokusu seç": "Choose floor texture",
    "Görüntü (*.png *.jpg *.jpeg *.bmp)": "Image (*.png *.jpg *.jpeg *.bmp)",
    "Dosya: ": "File: ",
    "Travertin karo": "Travertine tile",
    "Çakıl": "Gravel",
    "Beyaz mermer": "White marble",
    "Taş kaplama": "Stone cladding",
    "Terrakota karo": "Terracotta tile",
    "Sıva (kaba)": "Plaster (rough)",
    "Ahşap": "Wood",
    # --- ui: düğmeler / durum ---
    "Durdur": "Stop",
    "Farklı kaydet...": "Save as...",
    "Sahneyi yenile": "Refresh scene",
    "Model değiştiyse sahneyi bir sonraki Render'da yeniden okur": "If the model changed, the scene is re-read on the next Render",
    "Ön izleme ekranı": "Preview",
    "Hazır. Ayarları seç, 3B görünümü çevir ve Render'a bas.": "Ready. Choose settings, rotate the 3D view and press Render.",
    "ışınlar izleniyor": "tracing rays",
    "Açık belge yok.": "No open document.",
    "RayTrace: FreeCAD ışık ayarları okunamadı (%s); kendi ayarlar kullanılıyor.\n":
        "RayTrace: could not read FreeCAD light settings (%s); using own settings.\n",
    "RayTrace: %d nesne, %d üçgen (hazırlık %.1f sn)\n": "RayTrace: %d objects, %d triangles (preparation %.1f s)\n",
    " | kaydedildi: %s": " | saved: %s",
    " | KAYDEDİLEMEDİ (%s)": " | COULD NOT SAVE (%s)",
    "bitti: %dx%d | %d üçgen | render %.1f sn | toplam %.1f sn": "done: %dx%d | %d triangles | render %.1f s | total %.1f s",
    "kaydedildi: %s": "saved: %s",
    "RayTrace: render %.1f sn, toplam %.1f sn%s\n": "RayTrace: render %.1f s, total %.1f s%s\n",
    "iptal edildi.": "cancelled.",
    "RayTrace: iptal edildi.\n": "RayTrace: cancelled.\n",
    "RayTrace hatası:\n": "RayTrace error:\n",
    "HATA: Report View'a bak.": "ERROR: see Report View.",
    "Render'ı kaydet": "Save render",
    "KAYDEDİLEMEDİ (%s)": "COULD NOT SAVE (%s)",
    "Sahne bir sonraki Render'da yeniden okunacak.": "The scene will be re-read on the next Render.",
    "Dil / Language": "Language",
    # --- render: aşamalar ---
    "yüzey normalleri yumuşatılıyor...": "smoothing surface normals...",
    "üçgenler ekran karolarına dağıtılıyor (%d üçgen)...": "binning triangles into screen tiles (%d triangles)...",
    "gölge ızgaraları hazırlanıyor...": "building shadow grids...",
    "yansıma/saydamlık hızlandırıcısı hazırlanıyor...": "building reflection/transparency accelerator...",
    "ışınlar izleniyor...": "tracing rays...",
    "RayTrace işçi süreç hatası:\n": "RayTrace worker process error:\n",
    "işçi süreç hata ile bitti (Report View'a / terminale bak)": "worker process failed (see Report View / terminal)",
    "işçi süreçler işi bitirmeden çıktı": "worker processes exited before finishing",
    "kenarlar aranıyor...": "finding edges...",
    "kenar yumuşatma: %d piksel x %d örnek...": "anti-aliasing: %d pixels x %d samples...",
    "kenar yumuşatma": "anti-aliasing",
    # --- freecad_scene ---
    "sahne taranıyor... %d nesne": "scanning scene... %d objects",
    "sahne taranıyor...": "scanning scene...",
    "yedek tarama... %d nesne": "fallback scan... %d objects",
    "Görünür, yüzeyi olan nesne bulunamadı.": "No visible object with a surface was found.",
    "RayTrace: %d nesne bulundu (%.1f sn), sahne köşegeni %.1f mm, tessellate toleransı %.3f mm\n":
        "RayTrace: found %d objects (%.1f s), scene diagonal %.1f mm, tessellation tolerance %.3f mm\n",
    "üçgenleniyor %d/%d: %s (%d üçgen)": "tessellating %d/%d: %s (%d triangles)",
    "RayTrace: %d tamamen saydam (görünmez) nesne atlandı: %s\n": "RayTrace: skipped %d fully transparent (invisible) objects: %s\n",
    "Tessellation üçgen üretmedi.": "Tessellation produced no triangles.",
    "ışın izleme ön hesapları (%d üçgen)...": "ray-tracing precomputation (%d triangles)...",
    "RayTrace: hazırlık: tarama %.1f sn, üçgenleme %.1f sn, ön hesap %.1f sn\n":
        "RayTrace: preparation: scan %.1f s, tessellation %.1f s, precompute %.1f s\n",
    "ayarlar: %s (%d anahtar)": "settings: %s (%d keys)",
    "FreeCAD ışık parametreleri bulunamadı, varsayılan değerler kullanıldı": "FreeCAD light parameters not found; using defaults",
    " | ışıklar: ": " | lights: ",
    "açık": "on",
    "kapalı": "off",
    ", ortam %d%%": ", ambient %d%%",
}
