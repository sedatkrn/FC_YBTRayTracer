# Geliştirme notları / Development handoff (v1.2.2)

Yeni bir oturumda devam etmek için bu dosyayı oku. / Read this first when continuing in a new session.

## Proje
FreeCAD için bağımlılıksız (yalnız numpy) yerleşik ışın izleyici makro. Repo: https://github.com/sedatkrn/FC_YBTRayTracer (main).
Kullanıcı: Sedat (Türkçe konuşur; Manjaro/KDE Wayland; FreeCAD 1.1.4; YouTube FreeCAD kanalı; GitHub: sedatkrn). Öncelik: daha hızlı + daha kaliteli render.

## Kod yapısı (`ybt_raytracer/`)
- `settings.py` genel ayarlar (S.NAME); UI `vars(S)` üzerinden yazar.
- `core.py` Scene (üçgenler, renk, alpha, `mid`/`mtable` = malzeme), ışın-üçgen, smooth_normals.
- `accel.py` ekran karoları, ışık-uzayı ızgarası, Morton küme hızlandırıcı (`_closest_general`).
- `render.py` ana izleyici (Whitted: gölge, yansıma, Snell kırılma, zemin, doku, malzeme tabloları), fork tabanlı çok süreç.
- `freecad_scene.py` `_gather` (görünür nesneleri toplar: Link/Assembly/Part/Body), `collect_scene` (tessellate + malzeme).
- `materials.py` malzeme sözlüğü, 15 hazır malzeme, kullanıcı JSON kütüphanesi (`<UserAppData>/YBTRayTracer/materials.json`), atama = nesnenin `YBTMaterial` özelliği.
- `surface_ui.py` Malzeme/Surface penceresi (nesne listesi = `_gather` ile aynı kaynak, kütüphane, parametreler, canlı önizleme küresi).
- `ui.py` ana panel; `i18n.py` TR/EN (`T("Türkçe metin")`, kaynak metin Türkçe, EN sözlüğü `EN`); `textures.py` zemin dokuları.
- Başlatıcı: `FC_ybt_raytracer.FCMacro` (paketi bulur, `ybt_raytracer.ui.main()` çağırır).

## Tasarım kuralları
- Malzemesiz nesne = eski davranış (FreeCAD rengi); malzemesiz sahne eski sürümle piksel piksel aynı olmalı (regresyon testi).
- Malzeme tabloları indeks 0 = malzemesiz/zemin -> genel ayarlar. Yansıma/kırılma panelde yalnız açma-kapama (`REFLECTIONS`, `REFRACTION`); değerler malzemeden.
- Yeni arayüz metni: Türkçe yaz, `T()` ile sar, `i18n.EN`'e İngilizcesini ekle.
- GitHub: bu ortamda main'e push çalışır; etiket/release oluşturma 403 -> kullanıcı elle yapar (zip verilir).

## Yapılanlar
v1.0 ilk sürüm -> v1.1 TR/EN + ikon -> v1.2 malzeme sistemi/Surface penceresi -> v1.2.1 yansıma/kırılma kutuları -> v1.2.2 liste yalnız gerçek nesneler + arama/yenile.

## Bekleyen işler (Reddit geri bildirimi + plan), önerilen sıra
1. **Mesh nesneleri** (`Mesh::Feature`): `_gather` yalnız Part şekilleri okuyor; mesh üçgenlerini doğrudan kullan (tessellate gerekmez), malzeme atanabilsin.
2. **Arayüzsüz API + animasyon**: `ybt_raytracer.api.render_document(doc, out_path, width=..., camera=..., **ayarlar)`; turntable/kare dizisi örnek makrosu. Sahne önbelleği (`_cache`) ve tessellation tekrar kullanımı.
3. **Nesne başına "Render'a dahil et"** kutusu (Surface listesinde) + "kadraj dışı nesneleri sahne boyutuna katma" seçeneği. Kullanıcı "ekranda olmayan geometri de işleniyor" dedi; neyi kastettiği belirsiz (kadraj dışı mı, gizli mi).
4. **Performans profili**: 300k üçgen, 1920 px, sanal zemin, varsayılanlar ≈ 2 dk (Reddit kullanıcısı). Pompa/buggy ölçümümüz: 634k üçgen 1080 px ≈ 20 sn.
5. Metal yansıma rengi (şu an yalnız specular boyanıyor), nesne dokuları (projeksiyon), kullanılan malzemeleri belgeye gömme.
6. Addon Manager listesi (FreeCAD addon index PR, kullanıcının hesabından); klasör-makro kurulumu Addon Manager'da doğrulanmadı.

## Bilinen sınırlar
Işık kırınımında kaydırma açılarında nadir siyah noktalar (hapsolmuş tam iç yansıma); gölgeler camdan renksiz geçer, kostik yok; metal yansıması renklenmiyor.

## Test
- FreeCAD 1.0.2 AppImage ile başsız GUI testi: `xvfb-run -a <AppRun/usr/bin/freecad> betik.py` (`HOME` ayrı bir klasör). Betik `FreeCAD._raytrace_dlg._raytrace_api` ile pencereyi sürer. (Önceki oturumda `/tmp/fcdl` altındaydı; yeni oturumda yeniden indirmek gerekebilir.)
- Regresyon: malzemesiz sahnede eski/yeni render farkı 0.0 olmalı.
- Büyük sahnede (300k+ üçgen) brute-force doğrulama çalıştırma (zaman aşımı).
- Dağıtım: değişen dosyalar main'e, ayrıca kullanıcının makro klasörüne (`FreeCAD.getUserMacroDir(True)`) ve `/home/sedat/claude-projeler/FC_ybt_raytracer/` altına kopyalanır; sürüm: `__init__.py`, `package.xml`, CHANGELOG.
