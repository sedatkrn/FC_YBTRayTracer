# Değişiklik geçmişi / Changelog

```
v1.3.0: * Mesh nesneleri (Mesh::Feature): üçgenler üçgenleme gerekmeden doğrudan sahneye alınır; App::Part / Link (LinkTransform dahil) içinde doğru konumlanır;
          malzeme atanabilir, Malzemeler penceresindeki listede görünür.
        * Arayüzsüz API (ybt_raytracer.api): render_document, render_scene, prepare_scene; kamera yardımcıları (make_camera, fit_camera, orbit_cameras);
          turntable(); ayarlar anahtar sözcükle (yalnız o çağrı için). Hareketli parça animasyonu için tess_cache (şekil bir kez üçgenlenir, her karede yalnız yerleşim).
          Örnek makro: examples/FC_ybt_turntable.FCMacro (kamera turntable'ı / dönen parça).
        * "Render'a dahil et": Malzemeler penceresinde nesne başına onay kutusu + Seçilileri dahil et / hariç tut düğmeleri (nesnenin YBTInclude özelliği).
        * "Kadraj dışındaki nesneleri atla" seçeneği (CULL_OFFSCREEN): kadraj dışı nesneler üçgenlenmez, sahne boyutuna/gölgeye/zemine katılmaz.
        * Malzemesiz Part sahnesinde v1.2.2 ile piksel piksel aynı çıktı (regresyon testi).
v1.2.2: * Malzeme penceresinde nesne listesi artık yalnızca render edilen gerçek katı/yüzeyleri gösterir (düzlem, eksen, joint, kapsayıcı yok); arama kutusu ve Yenile düğmesi eklendi.
v1.2.1: * Kalite ayarlarında "Cam yansıması / Yüzey yansıması / Kırılma (IOR)" alanları kaldırıldı; yerine "Yansımalar" ve "Kırılma" açma-kapama kutuları
          (değerler artık malzemeden gelir). Malzemesiz saydam nesneler cam (IOR 1.5) sayılır.
v1.2:   * Malzeme sistemi: nesne bazında malzeme (renk, diffuse, specular, parlaklık, metal, yansıma, saydamlık, IOR, kendi ışığı).
          15 hazır malzeme + kullanıcı kütüphanesi (JSON); "Malzemeler (Surface)..." penceresi, canlı önizleme küresi. Atama belgeyle kaydolur.
v1.1:   * Arayüz dili: Türkçe / English (panelin üstünde "Dil / Language"); seçim kaydedilir, ilk açılışta FreeCAD diline göre belirlenir.
        * Makro ikonu ve pencere ikonu eklendi.
v1.0:   ilk yayın / first release (v0.10 ile aynı kod).
v0.10:  * Cam kırılması (ışık kırınımı): Snell yasası, girişte/çıkışta bükülme, tam iç yansıma. Panelde 'Kırılma (IOR)' (Kapalı = düz geçiş).
        * Kırılan/yansıyan ışınlarda çakışan yüzeylerde (cam kutu masaya değiyor vb.) benek giderildi: ikincil ışın hızlandırıcısı
          da eşit uzaklıkta en küçük indeksi seçer (birincil ışınlarla aynı kural).
v0.9:   * Yumuşak yüzeyler: köşe normalleriyle pürüzsüz gölgeleme (küre/simit/silindir artık kırık/facet görünmez),
          gölge terminatörü düzeltmesi; keskin kenarlar (45°'den büyük açılar) korunur. Panelde 'Yumuşak yüzeyler' kutusu.
v0.8.1: * Ayar paneli artık içeriğine göre geniş açılır, ara çubuğu sürüklenerek ayarlanır; değerler kırpılmaz.
        * Ortografik kamerada zemin sisi kaldırıldı (sahne sisli görünüyordu); perspektifte sis azaltıldı; zemin yansıması taban değeri düşürüldü.
v0.8:   * Zemin dokuları: 7 hazır doku (travertin, çakıl, mermer, taş kaplama, terrakota, sıva, ahşap) + kendi görüntü dosyanız;
          doku boyu ayarlanır, uzak zeminde mip süzme (benek/moire yok). Eğik ortografik kamerada zeminin köşede kaybolması giderildi.

FC_ybt_raytracer.FCMacro  --  v0.6
FreeCAD içinde yerleşik, basit numpy ışın izleyici (harici program gerekmez).

Ne yapar:
  * Görünür tüm nesneleri üçgenlere çevirir (tessellate)
  * Aktif 3D görünümün kamerasından render alır
  * Doğrudan ışık + gölge + parlama (Whitted tarzı, gürültüsüz)
  * Görüntü satır satır önizleme penceresinde belirir, sonunda PNG kaydedilir

v0.6:   * Sanal zemin: sahnenin en alt z değerine (+ ofset) yatay düzlem; renk, opaklık, yansıma, yükseklik ofseti
          panelden ayarlanır. Zemin gölge alır ama gölge düşürmez; hızlandırıcı yapılara girmez (analitik düzlem).
v0.5:   * %98-100 saydam nesneler (FreeCAD'de görünmez; ör. Grid) artık sahneye alınmaz; önceden camlaşıp zeminde
          ayna gibi yansıma yapıyordu. Atlananlar Report View'a yazılır.
        * Linux'ta paralel render ayrı süreçlerle (fork + ortak bellek): iş parçacıkları Python'un GIL kilidi
          yüzünden çekirdekleri doyurmuyordu. Diğer sistemlerde iş parçacığı kullanılır (PARALLEL = "thread" ile zorlanabilir).
        * Çakışan yüzeylerde benek (z-fighting) giderildi: eşit uzaklıkta en küçük üçgen indeksi seçilir.
        * Assembly gibi kapsayıcıların kendi birleşik şekli (çocukların kopyası) artık sahneye eklenmiyor;
          önceden her parça iki kez (opak kopya + gerçek) çiziliyor, saydam parçalar opak görünüyordu.
        * İkincil ışınlarda kutular yakından uzağa gezilir, daha yakın isabet varsa uzaktakiler atlanır.
        * Ekran karosu 16 -> 8 px.
        * Gölge ızgarası artık sahne büyüklüğüne göre otomatik (64..256): 2,5 milyon üçgenli sahnede gölge
          hesabı ~7 kat hızlandı (149 sn -> 20 sn, görüntü birebir aynı).
        * Tek renkli nesneler tüm şekil tek çağrıyla üçgenlenir (yüz yüz çağırmaya göre ~%40 daha hızlı);
          Report View'a 'hazırlık: tarama / üçgenleme / ön hesap' süreleri yazılır.
        * BLAS'ın kendi iş parçacığı havuzu render sırasında 1'e indirilir (12 çekirdekli makinede
          iş parçacıkları birbirini yavaşlatıyordu).
        * Çok çekirdekli render: bantlar ve kenar yumuşatma parçaları iş parçacığı havuzunda paralel çizilir
          (ayar panelinde Çekirdek: Otomatik/1/2/4). Sonuç tek çekirdekle birebir aynıdır.
v0.4:   * Işıklar: ortam (renk/şiddet) + en çok 3 ışık (yatay/dikey açı, renk, güç, ışık başına gölge).
        * Kenar yumuşatma (AA): yalnız kenar piksellerinde 2x2/3x3/4x4 örnekleme (ayar panelinde).
        * Render penceresi ayar paneliyle açılır; render 'Render' düğmesiyle başlar. Pencere açıkken 3B
          görünümü çevirip tekrar Render alınabilir (sahne önbelleğe alınır).
        * Saydamlık: nesnenin Transparency değeri (ViewObject ve ShapeAppearance) okunur, cam gerçekten
          saydam çizilir; camdan geçen ışık yarı gölge verir.
        * Yansıma: camda Fresnel yansıması, opak yüzeyler için isteğe bağlı sabit yansıma (en çok 3 sekme).
        * BIM (Arch BuildingPart/Site/Floor) kapsayıcılarında tarama takılması giderildi.
v0.3:   büyük sahnelerde donma giderildi: perspektif kamerada kameranın arkasındaki üçgenler elenir,
        yakın düzlemi kesenler kırpılır, hücre-üçgen çifti sayısı sınırlı (bellek); hazırlık
        aşamaları pencerede görünür ve işlem pencere kapatılarak iptal edilebilir.
v0.2.3: renkler FreeCAD 1.x'in ShapeAppearance özelliğinden okunur (DiffuseColor/ShapeColor yedek).
v0.2.2: ortografik kamerada kameranın "arkasında" kalan nesneler artık çizilir; origin düzlemleri
        (sonsuz boyutlu şekil) atlanır -> tessellate toleransı normale döndü; Link renkleri hedef
        nesneden okunur ve Report View'a yazılır.
v0.2.1: App::Link / Assembly / App::Part / Body desteği.

v0.2 değişiklikleri:
  * float64 + sahne merkeze taşınarak hesap (ince üçgenlerde delik/pürüz sorunu giderildi)
  * Ekran karoları (birincil ışınlar) ve ışık-uzayı ızgarası (gölgeler) ile üçgen eleme: çok daha hızlı
  * PNG yazılamazsa (salt-okunur klasör) ~/Pictures veya ev dizinine kaydeder

Kullanım: Macro > Macros... > bu dosyayı çalıştır.
```
