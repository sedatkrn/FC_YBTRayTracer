# FC YBT Raytracer

**TR** | [EN](#english)

FreeCAD için, **harici program gerektirmeyen** (yalnızca FreeCAD'in kendi Python'u ve numpy) hızlı bir ışın izleyici makrosu.
Aktif 3B görünümün kamerasından sahneyi render eder, önizlemeyi pencerede gösterir ve PNG olarak kaydeder.

![Arayüz](docs/arayuz.png)

## Özellikler

- Doğrudan ışık, gölge, ortam ışığı ve parlama (Whitted tarzı: gürültüsüz, hızlı)
- En çok 3 ışık: yatay/dikey açı, renk, güç, ışık başına gölge; ortam rengi/şiddeti
- **"FreeCAD ışık ayarlarını kullan"** seçeneği (seçiliyken kendi ışık ayarları devre dışı)
- Saydamlık (cam), Fresnel yansıması ve **cam kırılması** (Snell yasası, kırılma indisi ayarlanır), isteğe bağlı yüzey yansıması
- **Yumuşak yüzeyler**: küre/simit/silindir pürüzsüz gölgelenir, keskin kenarlar korunur
- **Sanal zemin**: sahnenin en altına otomatik yerleşir; renk, opaklık, yansıma ve yükseklik ofseti ayarlanır; **7 hazır doku** (travertin, çakıl, mermer, taş, terrakota, sıva, ahşap) ya da kendi görüntünüz
- Kenar yumuşatma (yalnızca kenar piksellerinde 2x2 / 3x3 / 4x4)
- 4 kalite kademesi (Low, **Hızlı** varsayılan, ...); büyük montajlar için hızlı mod
- Büyük sahnelerde hızlandırma: ekran karoları, otomatik boyutlu ışık ızgarası, küme hiyerarşisi, sahne önbelleği
- Part, Body, App::Part, App::Link, Assembly, BIM (Arch) kapsayıcıları; renkler `ShapeAppearance`'tan
- **Çok çekirdekli render** (Çekirdek: Otomatik/1/2/4; Linux'ta ayrı süreçler, sonuç tek çekirdekle birebir aynı)
- Ayar paneli ile açılan pencere, alt kısımda ilerleme çubuğu, durdurma, farklı kaydet

![Sanal zemin ve ayar paneli](docs/sanal_zemin.png)
![Cam ve yansıma](docs/cam_yansima.png)
![Zemin dokuları](docs/floor_textures.png)
![Yumuşak yüzeyler: önce / sonra](docs/smooth_shading.png)
![Cam kırılması: IOR kapalı / 1.5](docs/refraction.png)
![Işıklar](docs/bim_isiklar.png)

## Dil / Language
Panelin sağ üstündeki "Dil / Language" kutusundan Türkçe veya English seçilir; seçim hatırlanır (ilk açılışta FreeCAD arayüz dili Türkçeyse Türkçe, değilse English).
The UI language (Türkçe / English) is chosen at the top-right of the panel; it is remembered (first run follows FreeCAD's locale).

## Kurulum

1. `FC_ybt_raytracer.FCMacro` dosyasını **ve** `ybt_raytracer/` klasörünü FreeCAD makro klasörüne birlikte kopyalayın
   (FreeCAD içinde *Macro > Macros...* penceresinde makro klasörü yolu görünür). Başlatıcı ile klasör yan yana durmalıdır.
2. Bir belgeyi açın, 3B görünümü istediğiniz açıya getirin.
3. *Macro > Macros...* ile makroyu çalıştırın, ayarları seçip **Render**'a basın.

Pencere açıkken 3B görünümü çevirip tekrar **Render** alabilirsiniz (sahne önbelleğe alınır).
Sonuç PNG olarak kaydedilir; klasör yazılamazsa `~/Pictures` veya ev dizini kullanılır.

## Gereksinimler

FreeCAD 1.0 veya üstü (1.1 / 26.x ile denendi), numpy (FreeCAD ile birlikte gelir). Başka bağımlılık yoktur.

## Sınırlar

- Kırılma yalnızca saydam yüzeylerde ve kapalı gövdelerde (küre, silindir, kutu) doğru çalışır; cam altında ışık odaklanması (kostik) yok, gölge camdan yarı saydam geçer.
- Zemin dokularının bir kısmı (çakıl, mermer, taş, ahşap) kenarlardan aynalanarak tekrarlanır; geniş zeminde simetri fark edilebilir.
- Sahne hazırlığı (üçgenleme, karo/ızgara/küme ağacı) tek çekirdekte; çok büyük sahnelerde cam/yansıma yavaştır (düşük kalite kademesi önerilir).
- Malzeme parlaklığı/yansıtıcılığı henüz nesneden okunmuyor.

## Yol haritası

Malzemeden parlaklık/yansıma, yumuşak gölge / gökyüzü ışığı, ayarların hatırlanması, ışık ön ayarları, turntable animasyonu, daha hızlı sahne hazırlığı.

## Lisans

MIT, bkz. [LICENSE](LICENSE).

---

## English

A fast, **dependency-free** ray-tracer macro for FreeCAD (just FreeCAD's own Python and numpy). It renders the active 3D view from its camera, shows a live preview and saves a PNG.

### Features

- Direct light, shadows, ambient light and specular highlights (Whitted style: noise-free and fast)
- Up to 3 lights: horizontal/vertical angle, colour, power, per-light shadows; ambient colour/intensity
- **"Use FreeCAD light settings"** option (disables the macro's own lights when checked)
- Transparency (glass) with Fresnel reflection and **refraction** (Snell's law, adjustable IOR), optional surface reflection
- **Smooth surfaces**: spheres/tori/cylinders shaded smoothly, sharp edges preserved
- **Virtual floor**: placed at the scene's lowest point automatically; colour, opacity, reflection and height offset adjustable; **7 built-in textures** (travertine, gravel, marble, stone, terracotta, plaster, wood) or your own image
- Edge-only anti-aliasing (2x2 / 3x3 / 4x4)
- 4 quality levels (Low, **Fast** default, ...), suited to large assemblies
- Large-scene acceleration: screen tiles, auto-sized light-space grid, cluster hierarchy, scene cache
- Part, Body, App::Part, App::Link, Assembly and BIM (Arch) containers; colours from `ShapeAppearance`
- **Multi-core rendering** (Cores: Auto/1/2/4; output identical to single-core)
- Settings panel opens first; progress bar, stop button, save-as

### Install

1. Copy `FC_ybt_raytracer.FCMacro` **and** the `ybt_raytracer/` folder together into your FreeCAD macro folder (shown in *Macro > Macros...*); the launcher and the folder must sit side by side.
2. Open a document and orient the 3D view.
3. Run the macro from *Macro > Macros...*, adjust settings, press **Render**.

You can rotate the 3D view while the window is open and press **Render** again; the scene is cached.

### Requirements

FreeCAD 1.0+ (tested with 1.1 / 26.x) and numpy (bundled with FreeCAD).

### Limitations

- Refraction works best on transparent closed bodies (sphere, cylinder, box); no caustics, shadows pass through glass as partial shade.
- Some floor textures (gravel, marble, stone, wood) tile by mirroring, so symmetry may show on a large floor.
- Scene preparation (tessellation, tile/grid/cluster build) is single-threaded; glass/reflections on very large scenes are slow (use a lower quality level).
- Material shininess/reflectivity is not yet read from objects.

### Roadmap

Material-based shininess/reflection, soft shadows / sky light, remembered settings, light presets, turntable animation, faster scene preparation.

### License

MIT, see [LICENSE](LICENSE).


## Zemin dokuları / Floor textures

Sanal zemin için hazır dokular: travertin, çakıl, beyaz mermer, taş kaplama, terrakota, sıva, ahşap; ayrıca *Dosyadan…* ile kendi PNG/JPG görüntünüz. *Doku boyu* ile ölçek ayarlanır.
Ready-made floor textures (7) or your own image via *Dosyadan…*; *Doku boyu* sets the scale.

## Kod yapısı / Code layout

```
FC_ybt_raytracer.FCMacro     ince başlatıcı / thin launcher
ybt_raytracer/
  settings.py        ayarlar / settings
  core.py            Scene + kesişim / intersection
  parallel.py        BLAS sınırı, iptal, ilerleme / BLAS limit, cancel, ticker
  accel.py           karo, ışık ızgarası, küme hızlandırıcılar / accelerators
  render.py          ışın izleme döngüsü / ray-tracing loop
  output.py          PNG yazıcı / PNG writer
  freecad_scene.py   FreeCAD -> üçgen, kamera, ışıklar / FreeCAD scene import
  ui.py              ayar paneli / settings panel
CHANGELOG.md
```
