# Geliştirme notları / Development handoff (v1.5.0)

Yeni bir oturumda devam etmek için bu dosyayı oku. / Read this first when continuing in a new session.

## Proje
FreeCAD için bağımlılıksız (yalnız numpy) yerleşik ışın izleyici makro. Repo: https://github.com/sedatkrn/FC_YBTRayTracer (main).
Kullanıcı: Sedat (Türkçe konuşur; Manjaro/KDE Wayland; FreeCAD 1.1.4; YouTube FreeCAD kanalı; GitHub: sedatkrn). Öncelik: daha hızlı + daha kaliteli render.

## Kod yapısı (`ybt_raytracer/`)
- `settings.py` genel ayarlar (S.NAME); UI `vars(S)` üzerinden yazar.
- `core.py` Scene (üçgenler, renk, alpha, `mid`/`mtable` = malzeme), ışın-üçgen, smooth_normals.
- `accel.py` ekran karoları, ışık-uzayı ızgarası, Morton küme hızlandırıcı (`_closest_general`).
- `render.py` ana izleyici (Whitted: gölge, yansıma, Snell kırılma, zemin, doku, malzeme tabloları), fork tabanlı çok süreç.
- `theme.py`: koyu palet QSS (apply(dlg)); ok/onay ikonları `icons/*.png`. NOT: QGroupBox::title bu Qt'de QSS ile güvenilir çizilmiyor; başlıklar `ui.py` içindeki `collapsible()` başlık düğmesiyle verilir. Sol panelin kaydırma alanında sıkışmaması için `fix_left_height()`.
- Önizleme ekranı `_Preview` (ui.py): kendi paintEvent'i, ölçek/ofset durumu (`scale, ox, oy, fitted`), tekerlek zoom, sürükle-kaydır (5 px eşik; altı = tıklama), `on_click(u, v, ctrl)` görüntü içi 0..1.
- `pick.py`: tıkla-seç. `Scene.oid` (üçgen başına nesne indeksi) + `Scene.onames` (o.Name) `collect_scene`'de doldurulur; `pick(scene, cam, w, h, fx, fy)` tek ışını tüm üçgenlerle sınar. ui.py: `_Preview.mousePressEvent` -> `on_preview_click` -> Malzemeler penceresinin `_ybt_api["pick"]` (boya kovası modu `btn_paint`). `state["pick"]` = (sahne, kamera, w, h) son render'a aittir, sahne sıfırlansa da kalır.
- Benzer nesneler (surface_ui.py): `_signature(shp)` (şekil türü, yüz/kenar sayısı [countElement], yerel sınır kutusu; ÜST YERLEŞİM SIFIRLANIR; Area/Volume KULLANMA: 877 parçada ~22 sn; mesh için üçgen sayısı) -> `sim_info()` gruplar. Seçim genişletme `expand_similar`, `sellock` bayrağı seçim sinyalinin yeniden girmesini önler.
- `freecad_scene.py` `_gather` (görünür nesneleri toplar: Link/Assembly/Part/Body/Mesh), `collect_scene` (tessellate + malzeme; `tess_cache`, `camera/aspect` ile kadraj dışı atma, "dahil et" süzgeci).
  Mesh: `_is_mesh`, `_MeshGeom` (Part şekli gibi davranan sarmalayıcı), `_mesh_geom` (dünya = G·P⁻¹·Topology; Link'te LinkTransform açıksa yalnız G).
- `materials.py` malzeme sözlüğü, 15 hazır malzeme, kullanıcı JSON kütüphanesi (`<UserAppData>/YBTRayTracer/materials.json`), atama = nesnenin `YBTMaterial` özelliği;
  "render'a dahil et" = nesnenin `YBTInclude` (bool) özelliği, yalnız hariç tutulunca eklenir; `included/set_included` YALNIZ nesnenin kendi özelliğine bakar (`PropertiesList`; App::Link bağlı nesnenin özelliğini yansıtır, hasattr/getattr yanıltır).
- `surface_ui.py` Malzeme/Surface penceresi (nesne listesi = `_gather` ile aynı kaynak, kütüphane, parametreler, canlı önizleme küresi).
- `api.py` arayüzsüz API: `render_document/render_scene/prepare_scene`, `make_camera/fit_camera/orbit_cameras/camera_from_view`, `turntable`; ayarlar kw ile `_Override` (çağrı sonunda geri yazılır). Örnek: `examples/FC_ybt_turntable.FCMacro`.
- `ui.py` ana panel; `i18n.py` TR/EN (`T("Türkçe metin")`, kaynak metin Türkçe, EN sözlüğü `EN`); `textures.py` zemin dokuları.
- Başlatıcı: `FC_ybt_raytracer.FCMacro` (paketi bulur, `ybt_raytracer.ui.main()` çağırır).
- İçerik klasörü: `paths.py` (FreeCAD param `Mod/FCYBTRayTracer/ContentDir`; alt klasörler `materials textures hdri settings renders`; `content_dir`, `set_content_dir`, `sub_dir`, `texture_dir`, `hdri_dir`, `out_dir`, `migrate_to_content`, `list_files`, `resolve`). Yol ayar dosyalarında tutulamaz (onlar klasörün içinde), bu yüzden FreeCAD parametresinde. `materials.user_lib_path` ve `userdefaults.path` ayarlıysa içerik klasöründen okur, değilse eski yerden (`legacy_*`). Çıktı yolu `output.pick_out_path` içinde (`settings.OUT_TO` = renders/document; makineye özgü, `docstore._SKIP`); eksik doku/HDRI yolu `textures.load` ve `envmap.get_env` içinde `resolve` ile çözülür. Arayüz: ui.py `open_options` (sekmeler Genel + Varsayılanlar), `refresh_content()`; surface_ui.py doku listesine klasör girdileri. Test: `_raytrace_api["widgets"]["hdri_list"/"floor_tex"]`, `_raytrace_api["open_options"]`.
- Eklenti (v1.5.0 hazırlığı): `Init.py` (yalnız sys.path), `InitGui.py` (komutları kaydeder; "YBT Raytracer" tezgâhı varsayılan açık, parametreyle kapatılır), `ybt_raytracer/commands.py` (YBT_Render / YBT_Materials / YBT_Options). Her tezgâhta görünme: `Gui.addWorkbenchManipulator` ile standart "Macro" araç çubuğu + `Std_DlgMacroExecute`'un menüsüne ekleme (manipulator yeni araç çubuğu/menü YARATAMAZ, yalnız var olanlara ekler). Seçenekler/Malzemeler komutları açık panelin `_raytrace_api["open_options"/"open_mats"]` işlevlerini kullanır. Parametreler: `Mod/FCYBTRayTracer/SeparateWorkbench` (varsayılan true), `ShowInAllWorkbenches` (varsayılan true). KURALLAR: `package.xml` `<workbench>` girdisinde `<subdirectory>./</subdirectory>` ŞART (yoksa FreeCAD InitGui.py'yi `Mod/<klasör>/<tezgâh adı>/` içinde arar ve eklenti hiç yüklenmez). Gerçek FreeCAD 1.1.4'te `Mod/` kurulumuyla denendi (komutlar, menü, panel, render). İkon: `ybt_raytracer/icon.png` ve `FC_ybt_raytracer.png` (256 px). TUZAK: FreeCAD `InitGui.py`'yi ayrı globals/locals sözlükleriyle çalıştırır; dosya düzeyindeki adlar sınıf gövdesinden ve yöntemlerden görünmez (NameError). Sınıfta yalnız yerleşik adlar ve yerel `import` kullan; sahte testte `exec(kod, g, loc)` ile ayrı sözlük kullan.

## Tasarım kuralları
- Malzemesiz nesne = eski davranış (FreeCAD rengi); malzemesiz sahne eski sürümle piksel piksel aynı olmalı (regresyon testi).
- Malzeme tabloları indeks 0 = malzemesiz/zemin -> genel ayarlar. Yansıma/kırılma panelde yalnız açma-kapama (`REFLECTIONS`, `REFRACTION`); değerler malzemeden.
- Yeni arayüz metni: Türkçe yaz, `T()` ile sar, `i18n.EN`'e İngilizcesini ekle.
- GitHub: bu ortamda main'e push çalışır; etiket/release oluşturma 403 -> kullanıcı elle yapar (zip verilir).

## Yapılanlar
v1.0 ilk sürüm -> v1.1 TR/EN + ikon -> v1.2 malzeme sistemi/Surface penceresi -> v1.2.1 yansıma/kırılma kutuları -> v1.2.2 liste yalnız gerçek nesneler + arama/yenile -> v1.3.0 mesh nesneleri + arayüzsüz API/animasyon + "render'a dahil et" kutusu + kadraj dışı atma.

## Bekleyen işler, önerilen sıra
1. **Performans profili**: 300k üçgen, 1920 px, sanal zemin, varsayılanlar ≈ 2 dk (Reddit kullanıcısı). Pompa/buggy ölçümümüz: 634k üçgen 1080 px ≈ 20 sn. Sahne hazırlığı tek çekirdekte (Scene.__init__, smooth_normals); animasyonda kare başına tekrar ediyor.
2. Metal yansıma rengi (şu an yalnız specular boyanıyor), nesne dokuları (projeksiyon), kullanılan malzemeleri belgeye gömme. Mesh köşe renkleri (vertex colors) kullanılmıyor.
3. Addon Manager listesi (FreeCAD addon index PR, kullanıcının hesabından); klasör-makro kurulumu Addon Manager'da doğrulanmadı. package.xml'e `examples/` makrosu eklenmedi.
4. Animasyon: kare başına `_gather` taraması + `Scene` ön hesapları tekrarlanıyor; çok nesneli montajda sahne güncellemesi (yalnız yerleşimi değişenleri dönüştürme) yapılabilir. `tess_cache` sözleşmesi: şekil parametreleri değişirse çağıran yeni sözlük vermeli (geçerlilik denetimi yalnız yüz sayısı + sınır kutusu).
5. Kullanıcı "ekranda olmayan geometri de işleniyor" demişti; "kadraj dışı atla" (CULL_OFFSCREEN, varsayılan kapalı) ve "dahil et" kutusu ikisini de karşılıyor, gizli nesneler zaten taranmıyor. Kullanıcı neyi kastettiğini doğrulamadı.

## Bilinen sınırlar
Işık kırınımında kaydırma açılarında nadir siyah noktalar (hapsolmuş tam iç yansıma); gölgeler camdan renksiz geçer, kostik yok; metal yansıması renklenmiyor.

## Test
- v1.3.0 geliştirmesi kullanıcının AÇIK FreeCAD'ine (FreeCAD MCP: `execute_code`) karşı yapıldı: kod `/home/sedat/claude-projeler/FC_ybt_raytracer/` klasörüne yazılıp `sys.path.insert(0, klasör)` ile içe aktarıldı (sys.modules'daki `ybt_raytracer*` silinerek yeniden yüklenir). Ekran görüntüsü için pencerede `grab().save(...)`.
- Regresyon (v1.3.0'da yapıldı): eski `freecad_scene.py` (git `fa98d55`) bir modül olarak yüklenip yeni `collect_scene` ile aynı belgede karşılaştırıldı: Scene dizileri birebir aynı, render farkı 0.
- FreeCAD 1.0.2 AppImage ile başsız GUI testi: `xvfb-run -a <AppRun/usr/bin/freecad> betik.py` (`HOME` ayrı bir klasör). Betik `FreeCAD._raytrace_dlg._raytrace_api` ile pencereyi sürer. (Önceki oturumda `/tmp/fcdl` altındaydı; yeni oturumda yeniden indirmek gerekebilir.)
- Regresyon: malzemesiz sahnede eski/yeni render farkı 0.0 olmalı.
- Büyük sahnede (300k+ üçgen) brute-force doğrulama çalıştırma (zaman aşımı).
- Dağıtım: değişen dosyalar main'e, ayrıca kullanıcının makro klasörüne (`FreeCAD.getUserMacroDir(True)`) ve `/home/sedat/claude-projeler/FC_ybt_raytracer/` altına kopyalanır; sürüm: `__init__.py`, `package.xml`, CHANGELOG.

- Sürüm kuralı: her sürümde `ybt_raytracer/__init__.py` `__version__`, `package.xml` `<version>`/`<date>` ve CHANGELOG birlikte güncellenir.
- Konumlu ışıklar (Point/Spot): `lightobj.py` TYPES + `collect` (kind, wpos, axis, falloff, ref, radius, cone, edge). `render.py`: `lpos`/`lsp` paralel listeleri; konumlu ışıkta yön ve sönme her noktada hesaplanır (shading döngüsünde `Ld` dizisi, `power` dizisi), gölge `lights_blocked` içinde `_closest_general` (kümeli hızlandırıcı, `tmax` = ışığa uzaklık) ile; yumuşaklık = ışık konumunun yarıçaplı küre içinde örneklenmesi (`sample_dirs[li]` konumlu ışıkta konum listesi). Yönlü ışık ızgaraları (`_LightGrid`) ve hızlı yumuşak gölge (`ss_*`) konumlu ışıkta atlanır. Panel: `light_ui.py` (`type_changed` → `lightobj.change_type`). Görünüm önizlemesi: `viewlight._sync_nodes` SoPointLight/SoSpotLight.
