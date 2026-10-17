# -*- coding: utf-8 -*-
"""
Hazır aydınlatma düzenleri (stüdyo / ürün fotoğrafçılığı kalıpları).

Açılar KAMERAYA göredir: h = yatay (0 = kameradan, eksi = sol, artı = sağ, 180 = arkadan), v = dikey (artı = yukarıdan).
Her düzen: en çok 3 ışık (ana, dolgu, arka) + ortam ışığı. Güçler birbirine göre oranlıdır (dolgu < ana: yumuşak gölge oranı).
Sıcak ışık ~3200-4000 K (turuncumsu), soğuk ışık ~7000-9000 K (mavimsi) olarak yaklaşık RGB'ye çevrilmiştir.
"""

W = (1.0, 1.0, 1.0)            # nötr beyaz (5600 K civarı)
WARM = (1.0, 0.86, 0.70)       # tungsten / gün batımı
HOT = (1.0, 0.62, 0.30)        # güçlü turuncu (jel)
COOL = (0.75, 0.86, 1.0)       # gökyüzü / gölge mavisi
ICE = (0.55, 0.72, 1.0)        # buz mavisi (jel)
CYAN = (0.25, 0.85, 1.0)
MAGENTA = (1.0, 0.25, 0.75)
LIME = (0.65, 1.0, 0.35)


def _l(on, h, v, color, power, shadow):
    return dict(on=on, h=float(h), v=float(v), color=color, power=float(power), shadow=shadow)


_OFF = _l(False, 0, 0, W, 0.2, False)

# (anahtar, ad, ışıklar, ortam gücü, ortam rengi, açıklama)
PRESETS = [
    ("default", "Varsayılan",
     [_l(True, -39, 44, W, 0.70, True), _l(True, 45, -6, W, 0.22, False), _l(False, 180, 25, W, 0.40, False)],
     0.28, W, "Ana ışık + hafif dolgu; her sahnede güvenli başlangıç."),
    ("three_point", "Stüdyo: 3 ışık (klasik)",
     [_l(True, -45, 35, W, 0.75, True), _l(True, 40, 10, W, 0.30, False), _l(True, 180, 40, W, 0.45, False)],
     0.20, W, "Ana + dolgu + arka (kontur) ışığı. Dolgu ana ışığın yaklaşık 2/5'i: yumuşak gölge, parça arka plandan ayrılır."),
    ("three_point_color", "Stüdyo: 3 ışık, sıcak-soğuk",
     [_l(True, -45, 35, WARM, 0.80, True), _l(True, 40, 5, COOL, 0.30, False), _l(True, 180, 40, ICE, 0.50, False)],
     0.18, COOL, "Sıcak ana ışık, soğuk dolgu ve mavi kontur: ürün çekimlerinde sık kullanılan renk karşıtlığı."),
    ("two_key_fill", "İki ışık: ana + dolgu",
     [_l(True, -40, 35, W, 0.75, True), _l(True, 45, 0, W, 0.28, False), _OFF],
     0.22, W, "En yalın düzen. Dolgu kısıldıkça kontrast ve derinlik artar."),
    ("two_key_rim", "İki ışık: ana + kontur",
     [_l(True, -30, 40, W, 0.70, True), _OFF, _l(True, 160, 35, W, 0.55, False)],
     0.22, W, "Ön ışık ve arkadan kenar ışığı; metal ve cam kenarlarını parlatır."),
    ("two_color", "İki ışık: sıcak + soğuk",
     [_l(True, -50, 30, WARM, 0.75, True), _l(True, 55, 15, ICE, 0.55, False), _OFF],
     0.18, COOL, "Soldan sıcak, sağdan soğuk ışık; iki taraf farklı renkte boyanır."),
    ("softbox", "Ürün: yumuşak kutu (softbox)",
     [_l(True, -30, 50, W, 0.55, False), _l(True, 35, 25, W, 0.40, False), _l(True, 160, 45, W, 0.25, False)],
     0.38, W, "Gölgesiz, geniş ve yumuşak ışık; katalog / beyaz fon görünümü. En hızlı düzenlerden biri."),
    ("rembrandt", "Rembrandt (45° / 45°)",
     [_l(True, -45, 45, WARM, 0.85, True), _l(True, 50, 0, W, 0.12, False), _OFF],
     0.12, W, "Ana ışık 45° yandan ve 45° yukarıdan; gölgede küçük bir ışık üçgeni kalır. Tek ışık, düşük dolgu."),
    ("butterfly", "Kelebek (üstten)",
     [_l(True, 0, 65, W, 0.80, True), _l(True, 0, -25, W, 0.22, False), _OFF],
     0.15, W, "Işık kameranın hemen üstünde; altta hafif yansıtıcı (dolgu). Burun altı gölgesi 'kelebek' biçimi."),
    ("split", "Yarım (split)",
     [_l(True, -90, 5, W, 0.85, True), _OFF, _OFF],
     0.08, W, "Işık tam yandan: nesnenin yarısı aydınlık, yarısı karanlık. Dramatik, yüksek kontrast."),
    ("lowkey", "Dramatik (low-key)",
     [_l(True, -60, 25, W, 0.85, True), _OFF, _l(True, 150, 30, COOL, 0.35, False)],
     0.06, W, "Karanlık gölgeler, tek güçlü ışık ve ince kontur. Düşük ortam ışığı AO etkisini de görünür yapar."),
    ("gel_cm", "Renkli jel: camgöbeği + eflatun",
     [_l(True, -60, 25, CYAN, 0.80, True), _l(True, 60, 20, MAGENTA, 0.80, False), _l(True, 180, 40, W, 0.30, False)],
     0.10, W, "Yan ışıklarda zıt renkli jeller; teknolojik / 'neon' görünüm."),
    ("gel_ob", "Renkli jel: turuncu + mavi",
     [_l(True, -55, 30, HOT, 0.80, True), _l(True, 55, 15, ICE, 0.60, False), _l(True, 180, 35, LIME, 0.30, False)],
     0.10, W, "Tamamlayıcı renkler (turuncu / mavi) ve hafif yeşil kontur."),
    ("daylight", "Gün ışığı",
     [_l(True, -35, 55, (1.0, 0.96, 0.88), 0.90, True), _l(True, 50, 5, COOL, 0.25, False), _OFF],
     0.35, COOL, "Güneş (sıcak, yüksek) + gökyüzünden mavimsi dolgu ve ortam ışığı."),
    ("sunset", "Gün batımı",
     [_l(True, -70, 8, HOT, 0.95, True), _l(True, 60, 20, ICE, 0.25, False), _l(True, 170, 20, WARM, 0.30, False)],
     0.14, (0.75, 0.80, 1.0), "Alçak, turuncu güneş ve mavi gölgeler; uzun gölgeler."),
]

CUSTOM_KEY = "custom"


def names():
    return [p[1] for p in PRESETS]


def get(i):
    return PRESETS[i]


def index_of(key):
    for i, p in enumerate(PRESETS):
        if p[0] == key:
            return i
    return -1
