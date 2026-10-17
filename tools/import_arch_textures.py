# -*- coding: utf-8 -*-
"""Yerel doku arşivinden (örn. '[TImg] Textures 15') seçili görüntüleri 'ybt_raytracer/textures/' içine PNG olarak aktarır
(en uzun kenar <= 384 px, RGB) ve textures.py / materials.py için hazır satırları basar.
Kullanım: python tools/import_arch_textures.py <arşiv-kökü> [çıkış-klasörü]"""
import os, sys
from PIL import Image

# (kaynak yol, anahtar, ad, mod, otomatik genişlik, malzeme: spec, gloss, metal, refl)
S = "Stone 15/"; W = "Wall Finishes 15/"; WD = "Wood 15/"; FL = "Flooring 15/"; RF = "Roof 15/"
ITEMS = [
    (S + "Granite 1.jpg", "granit1", "Granit (gri)", .35, .30, .40, 0, .04),
    (S + "Granite 2.jpg", "granit2", "Granit (bej)", .35, .30, .40, 0, .04),
    (S + "Granite Blue Pearl.jpg", "granit_mavi", "Granit (mavi inci)", .35, .45, .55, 0, .06),
    (S + "Granite Pinot Noir.jpg", "granit_siyah", "Granit (siyah)", .35, .50, .60, 0, .07),
    (S + "Granite Ruby Red.jpg", "granit_kirmizi", "Granit (kırmızı)", .35, .45, .55, 0, .06),
    (S + "Graniet Verde Meragozza.jpg", "granit_yesil", "Granit (yeşil)", .35, .45, .55, 0, .06),
    (S + "Marble Carrara.jpg", "mermer_carrara", "Mermer (Carrara)", .45, .45, .55, 0, .06),
    (S + "Marble Botticino.jpg", "mermer_botticino", "Mermer (Botticino)", .45, .40, .50, 0, .05),
    (S + "Marble Cremo Delicato.jpg", "mermer_krem", "Mermer (krem)", .45, .40, .50, 0, .05),
    (S + "Marble Gray.jpg", "mermer_gri", "Mermer (gri)", .45, .40, .50, 0, .05),
    (S + "Marble Rosso Silicia.jpg", "mermer_kirmizi", "Mermer (rosso)", .45, .45, .55, 0, .06),
    (S + "Marble Vermont Verde.jpg", "mermer_yesil", "Mermer (yeşil)", .45, .45, .55, 0, .06),
    (S + "Limestone.jpg", "kalker", "Kalker", .35, .06, .12, 0, 0),
    (S + "Sandstone.JPG", "kumtasi", "Kumtaşı", .35, .05, .10, 0, 0),
    (S + "Travertin Silver.jpg", "travertin_gri", "Travertin (gümüş)", .45, .18, .30, 0, .02),
    (S + "Castle Rock.jpg", "kale_tasi", "Kaba taş (kale)", .35, .05, .10, 0, 0),
    (S + "Cut Stone 1.jpg", "kesme_tas", "Kesme taş", .35, .06, .12, 0, 0),
    (S + "RiverRock 1.JPG", "dere_tasi", "Dere taşı", .30, .10, .18, 0, 0),
    (S + "Stone 4.jpg", "tas4", "Taş (düz)", .35, .06, .12, 0, 0),
    (W + "Bricks 15/Brick Aged4.jpg", "tugla_eski", "Tuğla (eski)", .35, .04, .08, 0, 0),
    (W + "Bricks 15/Brick New 3.jpg", "tugla_yeni", "Tuğla (yeni)", .35, .05, .10, 0, 0),
    (W + "Bricks 15/Brick White.JPG", "tugla_beyaz", "Tuğla (beyaz)", .35, .05, .10, 0, 0),
    (W + "Concrete 15/Concrete.JPG", "beton_duz", "Beton (düz)", .40, .05, .12, 0, 0),
    (W + "Concrete 15/Poured concrete.jpg", "beton_dokme", "Beton (dökme)", .40, .05, .12, 0, 0),
    (W + "Concrete 15/Poured concrete 2.jpg", "beton_dokme2", "Beton (açık gri)", .40, .05, .12, 0, 0),
    (W + "Render 15/Render red.jpg", "siva_kirmizi", "Sıva (kırmızı)", .30, .03, .08, 0, 0),
    (W + "Render 15/Render yellow.jpg", "siva_sari", "Sıva (sarı)", .30, .03, .08, 0, 0),
    (W + "Render 15/Southwestern.jpg", "siva_guney", "Sıva (güneybatı)", .30, .03, .08, 0, 0),
    (W + "Render 15/Stucco.png", "stuko", "Stuko", .30, .03, .08, 0, 0),
    (W + "Render 15/Textured render white.png", "siva_beyaz", "Sıva (dokulu beyaz)", .30, .03, .08, 0, 0),
    (W + "Siding 15/Cedar Siding.jpg", "kaplama_sedir", "Cephe kaplama (sedir)", .40, .10, .20, 0, 0),
    (W + "Siding 15/Dark siding.jpg", "kaplama_koyu", "Cephe kaplama (koyu)", .40, .10, .20, 0, 0),
    (W + "Siding 15/Light siding.jpg", "kaplama_acik", "Cephe kaplama (açık)", .40, .10, .20, 0, 0),
    (W + "Siding 15/Log Wall.jpg", "kutuk_duvar", "Kütük duvar", .40, .08, .15, 0, 0),
    (WD + "Ash.jpg", "ahsap_dis", "Ahşap (dişbudak)", .40, .15, .30, 0, .01),
    (WD + "Mahogany.jpg", "ahsap_maun", "Ahşap (maun)", .40, .20, .35, 0, .02),
    (WD + "Maple.jpg", "ahsap_akcaagac", "Ahşap (akçaağaç)", .40, .15, .30, 0, .01),
    (WD + "Oak dark.jpg", "ahsap_mese_koyu", "Ahşap (meşe, koyu)", .40, .15, .30, 0, .01),
    (WD + "Oak light.jpg", "ahsap_mese_acik", "Ahşap (meşe, açık)", .40, .15, .30, 0, .01),
    (WD + "Pine.jpg", "ahsap_cam", "Ahşap (çam)", .40, .12, .25, 0, 0),
    (WD + "Walnut.jpg", "ahsap_ceviz", "Ahşap (ceviz)", .40, .20, .35, 0, .02),
    (WD + "Burled Elm.jpg", "ahsap_karaagac", "Ahşap (karaağaç)", .40, .20, .35, 0, .02),
    (FL + "Parquet 15/Parquet 4.jpg", "parke4", "Parke (1)", .40, .18, .30, 0, .02),
    (FL + "Parquet 15/Parquet 5.jpg", "parke5", "Parke (2)", .40, .18, .30, 0, .02),
    (FL + "Parquet 15/Floorboards 2.jpg", "tahta_doseme", "Tahta döşeme", .40, .12, .25, 0, 0),
    (FL + "Tiled Surfaces 15/Ceramics 3.jpg", "seramik3", "Seramik karo", .30, .40, .55, 0, .08),
    (FL + "Tiled Surfaces 15/Gray Tiles.jpg", "karo_gri", "Karo (gri)", .30, .35, .50, 0, .06),
    (FL + "Tiled Surfaces 15/Light Brown Tiles.jpg", "karo_kahve", "Karo (açık kahve)", .30, .35, .50, 0, .06),
    (FL + "Tiled Surfaces 15/Red Tiles.jpg", "karo_kirmizi", "Karo (kırmızı)", .30, .35, .50, 0, .06),
    (FL + "Tiled Surfaces 15/Mosaic.jpg", "mozaik", "Mozaik", .30, .40, .55, 0, .06),
    (FL + "Tiled Surfaces 15/White Tiles 1.jpg", "karo_beyaz", "Karo (beyaz)", .30, .45, .60, 0, .08),
    (FL + "Tiled Surfaces 15/Blue Tiles.jpg", "karo_mavi", "Karo (mavi)", .30, .45, .60, 0, .08),
    (RF + "Roof Tiles 15/Roof Tile.jpg", "kiremit", "Kiremit", .30, .08, .15, 0, 0),
    (RF + "Roof Tiles 15/Roof 1.jpg", "cati1", "Çatı kaplama (kiremit 2)", .30, .08, .15, 0, 0),
    (RF + "Roof Tiles 15/Gray Roof.jpg", "cati_gri", "Çatı kaplama (gri)", .30, .08, .15, 0, 0),
    (RF + "Roof Tiles 15/Cedar Shingle.jpg", "cati_sedir", "Çatı (sedir tahta)", .30, .08, .15, 0, 0),
    (RF + "Roof Tiles 15/Terracotta roof tile optimal.png", "cati_terrakota", "Çatı (terrakota)", .30, .10, .18, 0, 0),
    (RF + "Metal Sheets 15/Aged Copper2.jpg", "bakir_eski", "Bakır sac (eskimiş)", .40, .50, .50, .7, .12),
    (RF + "Metal Sheets 15/Zinc.jpg", "cinko", "Çinko sac", .40, .55, .50, .8, .15),
    (RF + "Metal Sheets 15/Corrugated Sheet1.png", "oluklu_sac", "Oluklu sac", .30, .55, .45, .8, .12),
    (FL + "Hard Surfaces 15/Asphalt.JPG", "asfalt", "Asfalt", .40, .04, .08, 0, 0),
    (FL + "Hard Surfaces 15/Earth2.JPG", "toprak", "Toprak", .40, .02, .05, 0, 0),
    (FL + "Paving 15/Cut Stone Paving.jpg", "kaldirim", "Kesme taş kaldırım", .40, .06, .12, 0, 0),
    (FL + "Paving 15/Brick Walk 1.jpg", "tugla_yol", "Tuğla yaya yolu", .40, .05, .10, 0, 0),
    (FL + "Carpet 15/Gray Carpet.jpg", "hali_gri", "Halı (gri)", .20, .02, .05, 0, 0),
    ("Fabrics 15/Leather 15/Leather3.jpg", "deri3", "Deri (kahverengi)", .20, .30, .35, 0, .02),
    ("Fabrics 15/Textile 15/Fabric1.jpg", "kumas1", "Kumaş", .20, .03, .06, 0, 0),
    ("Landscape 15/Grass 15/Grass1.jpg", "cim", "Çim", .40, .02, .05, 0, 0),
]


def main():
    root = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), "..", "ybt_raytracer", "textures")
    pres, mats, names = [], [], []
    for src, key, name, rel, spec, gloss, metal, refl in ITEMS:
        p = os.path.join(root, src)
        im = Image.open(p).convert("RGB")
        w, h = im.size
        sc = min(1.0, 384.0 / max(w, h))
        if sc < 1.0:
            im = im.resize((max(1, int(round(w * sc))), max(1, int(round(h * sc)))), Image.LANCZOS)
        fn = "mimari_%s.png" % key
        im.save(os.path.join(out, fn), optimize=True)
        pres.append('    ("%s", "%s", "%s", "mirror", %.2f),' % ("mimari_" + key, name, fn, rel))
        mats.append('    "%s": _m(color=(0.88, 0.88, 0.88), spec=%.2f, gloss=%.2f, metal=%.2f, refl=%.2f, tex="mimari_%s"),' % (name, spec, gloss, metal, refl, key))
        names.append(name)
    print("PRESETS:\n" + "\n".join(pres))
    print("MATS:\n" + "\n".join(mats))
    print("NAMES:" + repr(names))


if __name__ == "__main__":
    main()
