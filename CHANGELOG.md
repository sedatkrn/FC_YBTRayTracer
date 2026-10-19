# Değişiklik geçmişi / Changelog

```
v1.5.0 (hazırlanıyor):

- **Ortam / HDRI (küresel ortam ışığı)**: Işıklandırma bölümünde "Ortam" seçimi: hazır gökyüzü ya da .hdr (Radiance) / PNG / JPG equirectangular harita. Harita arka planda görünür, yansımalarda kullanılır, sahneyi aydınlatır (piksel başına gökyüzü görünürlük ışınları + bilateral süzgeç; pencereden içeri giren gökyüzü ışığı dahil) ve haritadaki güneş otomatik ayrılıp gölgeli yönlü ışık olur (yumuşak gölge ayarları geçerli). Şiddet, dönüş, ışın sayısı, "Aydınlat / Yansıt / Arka planda göster / Güneşi ayır / Sahne ışıkları kalsın" seçenekleri. Doğrudan ışık + gökyüzü; sekmeli (bounce) iç aydınlatma henüz yok.
- **LightWave tarzı Doku Düzenleyici**: her T düğmesi bir pencere açar. Sol: katman listesi (aç/kapa, opaklık, blend harfi), "Katman ekle ▾" → **Görüntü dokusu** / **Prosedürel doku**, kaldır, kopyala/yapıştır (kanallar ve malzemeler arası), yukarı/aşağı taşı. Sağ: Katman türü, Blend modu (Normal, Toplamsal, Çıkarmalı, Çarpma, Bölme, Fark, Ekran, Açık olan, Koyu olan), Katman opaklığı, Ters çevir, Doku ekseni X/Y/Z, Dünya koordinatları, Otomatik boyutlandır, Ölçek/Konum/Dönme sekmeleri. Görüntü dokusu hazır listeden ya da dosyadan (PNG/JPG/BMP) seçilir.
- **Doku düzenleyici**: "Otomatik boyutlandır" artık görüntüyü nesnenin yüzüne tam oturtur (tek kez, nesne boyutuna gerilir; düzlemsel/küp/silindirik/küresel), yüklenen dosyalarda varsayılan açık; sekmeler koyu tema; doku yükleme Qt ile hızlandırıldı (açılış çok daha hızlı); katman önizlemesi (ayarlar değişince güncellenir), "Görüntü yükle..." düğmesiyle bilgisayardan PNG/JPG/BMP yükleme, açılır listeler koyu tema (Fusion/KDE popup düzeltmesi).
- **Malzemeler penceresi**: nesne listesinde sağ tık → Malzemeyi kopyala / Yapıştır / Atamayı kaldır; "Yeni surface" düğmesi gri varsayılan yüzey oluşturur.
- **Prosedürel dokular** (görüntüsüz 3B desenler, saf numpy): Türbülans, Fraktal gürültü, Damarlar, Mermer, Ahşap halkaları, Dama, Izgara, Noktalar, Tuğla örgüsü, Dalgalar; Doku değeri, Frekanslar, Kontrast, Küçük güç, Desen sıklığı, Tohum; Renk kanalında iki renk arası karışım. Uzakta ince oktavlar sönümlenir.
- **Kanal başına doku (T düğmesi)**: Surface penceresinde Renk, Diffuse, Specular, Glossiness, Reflection, Transparency ve Luminosity değerlerinin yanında "T"; dokusu olan kanalın düğmesi vurgulu. Gri tonlu kanallarda doku parlaklığı değer olur ("Doku payı", "Ters çevir"). Her kanalın kendi projeksiyonu / yerleşimi vardır (aşağıdaki madde).
- **Bump haritası**: gri tonlu doku yükseklik haritası olarak yüzey normalini eğer (geometri değişmez; UV gerekmez; küp / düzlemsel / silindirik / küresel); "Bump yüksekliği" %.
- Not: saydamlık dokusu gölgeyi etkilemez (gölge malzemenin sabit saydamlığına göre).
- Surface'ta yapılan değişiklikler seçili nesnelere otomatik uygulanır (kutu ile kapatılabilir).
- **Doku yönü ve yerleşimi** (Surface penceresi, "Doku yönü ve yerleşimi" grubu): projeksiyon (Küp 3 yönlü / Düzlemsel / Silindirik / Küresel), eksen (X/Y/Z), eksen başına ölçek, konum (mm), dönme, "Dünya koordinatları" kutusu. Varsayılan nesne koordinatı: doku nesnenin sınır kutusu merkezine bağlıdır, nesneyle birlikte gider. UV gerekmez.

v1.4.0:

- **Varsayılanlar menüsü**: panelin en üstünde "⚙ Varsayılanlar…" düğmesi. Mevcut ayarlar düzenlenebilir tabloda görünür; varsayılan olarak kaydedilir (FreeCAD açılışında yüklenir), son 10 kayıtlık geçmişten geri dönülür, fabrika ayarları panele yüklenebilir (ybt_raytracer/userdefaults.py, `ybt_raytracer_defaults.json`).
- **Hızlı yumuşak gölge düzeltmeleri**: hesaplanan gölge tamponu artık gölgelendirmede gerçekten kullanılıyor; üst üste binen yumuşak gölgeler bloklu/çizgili değil düzgün karışıyor (iki geçişli, kesirli yarıçaplı süzgeç, yarıçap alanı yumuşatma).
- **Parlama (specular) ışık görünürlüğüyle ölçeklenir**: gölge kenarında basamak / "patlama" giderildi; AO olmadan da yumuşak gölgeli sonuç alınır.
- **Kenar yumuşatma**: düşük kontrastlı siluetler (nesne/arka plan sınırı) artık yakalanıyor; alt örneklerde gölge tamponu doğrulanıyor.
- **Ortam tıkanıklığı (AO)**: köşelerde ve nesne–zemin temasında yumuşak temas gölgesi; "Işık Ayarları"nda şiddet, erişim ve ışın sayısı. Bilateral süzgeçle gürültü giderilir.
- Yansıma / cam / AO ışınları ~2-3x hızlandı: daha ince küme ağacı (8 üçgenlik kümeler, 4'lü ağaç), küme düzeyinde yakından uzağa tur sıralı budama. Çıktı piksel piksel aynı.
- **Yumuşak gölge** (alan ışığı; ışık yarıçapı derece cinsinden), **ton eşleme** (Reinhard / ACES + pozlama) ve opak parlak malzemelerde **Fresnel** yansıması. Varsayılan ayarlarda çıktı öncekiyle piksel piksel aynı (Fresnel kapalıyken).
- Yumuşak gölge **genişlik çarpanı** (`SOFT_SCALE`, arayüzde % olarak) ve çözünürlükle orantılı azami yarı gölge yarıçapı.
- **Hızlı yumuşak gölge** (varsayılan, `SOFT_METHOD="fast"`): piksel başına tek gölge ışını + engel mesafesinden yarı gölge genişliği, nesne bazlı toplam-alan tablosuyla süzgeç. Eski çok örnekli yöntem `"sampled"` olarak duruyor; demo sahnede süre ~27 sn → ~14 sn.
- **Hazır aydınlatma düzenleri**: 14 stüdyo/ürün düzeni (3 ışık, sıcak-soğuk, softbox, Rembrandt, kelebek, split, renkli jel, gün ışığı ...); ayrıntılar "Özel ayarlar" altında.
- Performans: kümelerde 8'li ağaç ve `tmax` ile kısa menzilli ışınlar, `einsum` tabanlı nokta çarpımı, daha hızlı bant seçimi.
        * Malzeme kütüphanesi: 60 hazır malzeme, kategorili liste (Plastik, Boya, Metal, Cam/sıvı, Doğal/yapı, Deri/karbon, Işık); kullanıcı
          malzemeleri "Benim malzemelerim" altında.
        * Doku malzemeleri: malzemeye doku atanabilir (tex / tex_scale / tex_mix); nesnede UV gerekmez, doku dünya koordinatından üç düzlemli
          izdüşümle uygulanır; mip düzeyli süzme. Yeni dokular: beton, karbon fiber, tuğla, deri, fırçalı metal (tools/make_textures.py).
        * Önizleme şekli: küre ya da küp (seçim hatırlanır).
v1.3.0: * Mesh nesneleri (Mesh::Feature): üçgenler üçgenleme gerekmeden doğrudan sahneye alınır; App::Part / Link (LinkTransform dahil) içinde doğru konumlanır;
          malzeme atanabilir, Malzemeler penceresindeki listede görünür.
        * Arayüzsüz API (ybt_raytracer.api): render_document, render_scene, prepare_scene; kamera yardımcıları (make_camera, fit_camera, orbit_cameras);
          turntable(); ayarlar anahtar sözcükle (yalnız o çağrı için). Hareketli parça animasyonu için tess_cache (şekil bir kez üçgenlenir, her karede yalnız yerleşim).
          Örnek makro: examples/FC_ybt_turntable.FCMacro (kamera turntable'ı / dönen parça).
        * "Render'a dahil et": Malzemeler penceresinde nesne başına onay kutusu + Seçilileri dahil et / hariç tut düğmeleri (nesnenin YBTInclude özelliği).
        * "Kadraj dışındaki nesneleri atla" seçeneği (CULL_OFFSCREEN): kadraj dışı nesneler üçgenlenmez, sahne boyutuna/gölgeye/zemine katılmaz.
        * Malzemesiz Part sahnesinde v1.2.2 ile piksel piksel aynı çıktı (regresyon testi).
        * Önizlemede tıkla-seç: render önizlemesinde bir parçaya tıklayınca Malzemeler penceresinde o nesne seçilir (Ctrl: seçime ekle) ve 3B
          görünümde vurgulanır (ybt_raytracer/pick.py; sahne artık üçgen başına nesne kimliği taşır). "Boya kovası" modunda tıklanan parçaya
          düzenlenen malzeme doğrudan atanır.
        * Benzer nesneler: şekil imzası (yüz/kenar sayısı, alan, hacim; konum/dönmeden bağımsız) aynı olan nesneler (kopyalar, Link'ler)
          listede "Benzer ×N" olarak gösterilir; "Benzerleri birlikte seç", "Benzerleri yan yana diz" ve "Benzerlerini seç" ile toplu işlem.
        * api.pick_object(scene, camera, w, h, x, y).
        * HIZ (2,79 M üçgenli motor sahnesi, 960x540: önceki sürümde >10 dk -> ~41 sn; 1920x1080 ~83 sn): (1) birincil ışınlar görünürlük
          tamponuyla (accel.raster_rows; her üçgen yalnız ekran kutusundaki piksellere uygulanır, piksel başına tüm üçgenler taranmaz; sonuç eskiyle
          piksel piksel aynı), kenar yumuşatma örnekleri de aynı tampondan; (2) gölge ızgarası çok seviyeli (üçgen boyutuna göre ince/kaba seviye)
          + "kesin aydınlık" erken çıkışı + vektörel çift testi (_LightGrid); (3) cam/yansıma yolundaki ön ışınlar için ön-arka sıralı erken çıkış
          (core._closest_sorted). Ekran karoları yalnız cam/yansıma sahnelerinde hesaplanır.
        * Yeni görünüm: koyu gri renk paleti (theme.py + icons/; iki pencerede de); "Önizleme ve Seçim Ekranı": çerçeveli, fare tekerleğiyle
          yakınlaştırma/uzaklaştırma (imleç altında sabit), sürükleyerek kaydırma, "Otomatik ortala" ve "1:1" düğmeleri, çift tıklama = sığdır,
          yakınlaşınca pikseller yumuşatılmadan gösterilir. Kalite / Sanal Zemin / Işık bölümleri başlığa tıklayınca açılır-kapanır
          (Sanal Zemin ve Işık varsayılan kapalı).
        * Malzemeler penceresi: render penceresinin soluna açılır; "Her zaman üstte" kutusu (varsayılan açık, ayar kaydedilir) önizlemeye
          tıklayınca arkaya kaçmasını önler; konsol tarzı işlem günlüğü (her işlem zaman damgalı); sürgü/sayı değişiminde önizleme
          1 sn sessizlik beklenince yenilenir (PREVIEW_DELAY_MS). Render penceresi başlığında sürüm gösterilir.
        * Malzemeler penceresi hızlı açılır: pencere hemen görünür, nesne taraması arkasından yapılır ve belge değişmedikçe önbellekten gelir
          ("Yenile" önbelleği atlar); benzer nesne imzası ucuzlatıldı (Area/Volume yerine yüz/kenar sayısı + yerel sınır kutusu; 877 parçada
          25 sn -> 2,5 sn). Pencere açıkken düğmeye basmak onu öne getirir; basılınca düğme "Açılıyor..." gösterir, imleç bekleme imleci olur;
          düğmelerde basma efekti.
        * Düzeltme: yumuşak yüzeylerde köşe eşleştirme çakışması giderildi (karmaşık gövdelerde, ör. jant lastiği, harf/benek biçimli bozulma;
          eski xor-özet farklı köşeleri aynı sayıp normallerini karıştırıyordu, artık çakışmasız tam anahtar).
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
