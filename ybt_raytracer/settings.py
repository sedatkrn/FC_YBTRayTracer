# -*- coding: utf-8 -*-


# ------------------------------- AYARLAR -------------------------------
WIDTH = 480            # çıktı genişliği (px); yükseklik 3B görünümün en-boy oranından gelir
SHADOWS = True         # gölge ışınları
TESS_FACTOR = 0.004    # tessellate toleransı = sahne köşegeni * bu değer (küçük = daha pürüzsüz, daha yavaş); 0.004 = 'Hızlı'
BG_TOP = (0.62, 0.72, 0.86)
BG_BOTTOM = (0.93, 0.94, 0.96)
AMBIENT = 0.28          # ortam ışığı şiddeti (0..1)
AMBIENT_COLOR = (1.0, 1.0, 1.0)
AO = False              # ortam tıkanıklığı (ambient occlusion): köşeler/girintiler/zemin dibi ortam ışığından daha az alır
ENV_MODE = "off"        # küresel ortam: off / sky (hazır gökyüzü) / hdri (dosya)
ENV_FILE = ""           # .hdr / .png / .jpg (equirectangular)
ENV_ROT = 0.0           # derece: ortam haritası dönüşü
ENV_INTENSITY = 1.0     # ortam ışığı ve güneş çarpanı
ENV_BACKGROUND = True   # arka planda göster
ENV_LIGHT = True        # sahneyi aydınlat (gökyüzü ışığı + görünürlük)
ENV_REFLECT = True      # yansımalarda kullan
ENV_SUN = True          # haritadaki güneşi ayrı gölgeli ışık yap
ENV_SUN_ELEV = 45.0     # hazır gökyüzü: güneş yüksekliği (derece)
ENV_SUN_AZ = 135.0      # hazır gökyüzü: güneş yönü (derece)
ENV_SAMPLES = 24        # piksel başına gökyüzü görünürlük ışını
ENV_KEEP_LIGHTS = False # ortam açıkken sahne ışıkları da kalsın
AO_SAMPLES = 26         # piksel başına AO ışını (az = gürültülü ama hızlı; gürültü bilateral süzgeçle azaltılır)
AO_RADIUS = 0.06        # AO erişimi (sahne köşegeninin oranı)
AO_STRENGTH = 0.3       # 0..1: ortam ışığının AO ile ne kadar kısılacağı
AO_STEP = 2             # AO ışınları her AO_STEP pikselde bir atılır (2 = dörtte biri), aradaki pikseller bilateral süzgeçle doldurulur
SOFT_SHADOW = 0.0       # yumuşak gölge: ışığın görünür yarıçapı (derece); 0 = keskin gölge (güneş ~0,27°, softbox ~5-15°)
SOFT_SCALE = 1.0         # yarı gölge genişlik çarpanı (ışık açısından bağımsız; 1 = açıya göre, 3 = 3 kat geniş)
SOFT_METHOD = "fast"    # "fast": piksel başına 1 gölge ışını + engel mesafesinden yarı gölge genişliği (ucuz); "sampled": ışık diskinde çok örnek (yavaş, her yüzeyde doğru)
SOFT_SAMPLES = 24       # yumuşak gölge için ışık başına örnek (her örnek ayrı bir gölge ızgarası = sahne büyüdükçe pahalı)
SOFT_MAX_TRIS = 1500000 # bu sayıdan çok üçgenli sahnede yumuşak gölge atlanır (ızgara kurma süresi)
TONEMAP = "none"        # ton eşleme: "none" (kırp), "soft" (Reinhard, beyaz noktalı), "aces" (filmik)
EXPOSURE = 1.0          # pozlama çarpanı (1 = değişiklik yok)
FRESNEL = True          # opak parlak malzemelerde yansıma açıyla artar (Schlick); kapalıysa sabit yansıma
# En çok 3 ışık. h = yatay açı (derece, 0 = kameradan; eksi = sol, artı = sağ),
# v = dikey açı (0 = göz hizası, artı = yukarıdan). Açılar KAMERAYA göredir.
LIGHTS = [
    dict(on=True,  h=-39.0, v=44.0, color=(1.0, 1.0, 1.0), power=0.70, shadow=True),    # ana ışık
    dict(on=True,  h=45.0,  v=-6.0, color=(1.0, 1.0, 1.0), power=0.22, shadow=False),   # dolgu
    dict(on=False, h=180.0, v=25.0, color=(1.0, 1.0, 1.0), power=0.40, shadow=False),   # arka ışık
]
SPEC = 0.30
SHININESS = 48.0
TILE = 8               # ekran karosu (px); aynı zamanda önizleme bant yüksekliği (ölçüm: 8, 16'dan %12-20 hızlı)
SHADOW_GRID = 0        # ışık-uzayı ızgarası (G x G hücre); 0 = otomatik (üçgen sayısına göre 64..256)
SMOOTH = True          # eğri yüzeylerde yumuşak (köşe normali) gölgeleme: facet/kırık görünüm yok
SMOOTH_ANGLE = 45.0    # derece; komşu yüzler arası açı bundan küçükse yumuşatılır, büyükse keskin kenar kalır
SMOOTH_MAX_TRIS = 1500000   # bu sayıdan çok üçgenli sahnede (hazırlık süresi) yumuşatma atlanır
IOR = 1.5              # malzemesi olmayan saydam nesnelerin kırılma indisi (cam); malzemeli nesneler kendi IOR değerini kullanır
REFRACTION = True      # kırılma (Snell yasası); kapalıysa ışık düz geçer
REFLECTIONS = True     # malzeme yansımaları (kapalı = yansıma yok, en hızlı)
GLASS = True           # saydam nesneler (Transparency) gerçekten saydam çizilsin
REFLECT_GLASS = 1.0    # cam yansıması çarpanı (0 = yok, 1 = normal, 2 = güçlü)
REFLECT_SURF = 0.0     # opak yüzeylerin sabit yansıması (0..0.6); 0 = kapalı
AA = 2                 # kenar yumuşatma: 0/1 = kapalı, 2 = 2x2, 3 = 3x3, 4 = 4x4 örnek (yalnız kenar piksellerinde)
AA_THRESH = 0.05       # komşu piksellerle renk farkı bu eşiği aşarsa kenar sayılır
BOUNCES = 2            # en çok yansıma sayısı
PARALLEL = "auto"        # "auto": Linux'ta ayrı süreçler (fork), diğerlerinde iş parçacığı; "thread": hep iş parçacığı
FLOOR = False           # sanal zemin: sahnenin en alt noktasına (+ ofset) yatay sonsuz düzlem
FLOOR_COLOR = (0.82, 0.82, 0.82)
FLOOR_OPACITY = 1.0    # 1 = opak, 0 = görünmez
FLOOR_REFLECT = 0.0    # 0..1; Fresnel'li yansıma (eğik bakışta güçlenir)
FLOOR_TEXTURE = ""      # "" = düz renk; hazır doku anahtarı (travertin, cakil, mermer, tas_duvar, terrakota, siva, ahsap) ya da dosya yolu
FLOOR_TEX_SCALE = 0.0  # mm; dokunun (orijinal görüntünün) zemindeki genişliği; 0 = otomatik (sahne köşegeninin %40'ı)
FLOOR_OFFSET = 0.0     # mm; sahnenin en alt z değerine eklenir (eksi = aşağı)
FLOOR_FADE = 0.7      # zeminden yansıyan nesnenin silikleşme uzunluğu (sahne köşegeni x bu sayı)
FLOOR_SKY_REFL = 0.35  # zeminin gökyüzü yansımasının gücü (1 = tam)
FLOOR_HAZE = 12.0       # ufka doğru sis uzunluğu (sahne köşegeni x bu sayı)
FLOOR_RADIUS = 25.0    # zemin yarıçapı = sahne köşegeni x bu sayı (ufuk çizgisine kadar)
THREADS = 0            # render iş parçacığı sayısı; 0 = otomatik (işlemci çekirdek sayısı, en çok 8)
CULL_OFFSCREEN = False  # True: kadraj dışında kalan nesneler sahneye hiç alınmaz (üçgenlenmez; sahne boyutuna, gölgeye,
                        # yansımaya ve sanal zemin yüksekliğine katılmaz). Kapalı = eski davranış (tüm görünür nesneler)
CULL_MARGIN = 0.1      # kadraj her kenarda bu oranda genişletilir; yalnız bunun da dışındaki nesneler atılır
DEBUG = False          # Report View'a nesne başına üçgen sayısı / sınır kutusu yaz
OUT_NAME = None        # None = belgenin yanına <belge>_render.png (yazılamazsa ~/Pictures, sonra ~)
DIR_OUT = ""           # çıktı klasörü: boş = belgenin yanı; mutlak yol = sabit klasör; göreli ad (ör. render) = belgenin yanında alt klasör
DIR_TEX = ""           # doku klasörü (dosya seçiciler buradan açılır, görüntüler listede görünür; belgedeki eksik doku yolu burada aranır)
DIR_HDRI = ""          # HDRI klasörü (aynı mantık)
# -----------------------------------------------------------------------

_EPS = 1e-12
REFL_MIN_W = 0.02      # bu ağırlığın altındaki yansımalar hiç izlenmez (büyütmek camlı sahneyi hızlandırır)
INVISIBLE_ALPHA = 0.02  # opaklığı bu değerin altındaki (FreeCAD'de %98-100 saydam) yüzeyler görünmezdir: sahneye alınmaz
TIE_TOL = 2e-6         # çakışan yüzeylerde 'eşit uzaklık' toleransı (sahne köşegeni oranı)
TIE_LAST = False       # eşitlikte False: ids içinde ilk (küçük indeks), True: son
_MAXPAIR = 2_000_000   # bir seferde işlenen (ışın x üçgen) çifti üst sınırı (bellek)
USE_FC_LIGHTS = False   # arayüz: "FreeCAD ışık ayarlarını kullan" işareti (dil değişiminde korunur)
