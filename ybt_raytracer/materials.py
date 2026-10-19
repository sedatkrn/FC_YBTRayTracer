# -*- coding: utf-8 -*-
"""Malzeme (yüzey) kütüphanesi: hazır malzemeler + kullanıcı malzemeleri (JSON), nesne bazında atama.

Bir malzeme sözlüğü:
  color   (r,g,b) 0..1 ya da None  -> None: nesnenin FreeCAD rengi kullanılır
  diffuse 0..1   yayılı (mat) ışık çarpanı
  spec    0..1   parlak vurgu (specular) şiddeti
  gloss   0..1   parlaklık (vurgunun keskinliği)
  metal   0..1   metal: vurguyu yüzey rengine boyar, yayılı ışığı azaltır
  refl    0..1   yansıma
  transp  0..1   saydamlık (0 = opak, 1 = tam saydam)
  ior     1..3   kırılma indisi (yalnız saydam malzemede etkili; 1 = düz geçiş)
  lum     0..1   kendi ışığı (parlama, ışıktan bağımsız)
  tex     ""/anahtar  doku (textures.PRESETS anahtarı; "" = düz renk). Nesneye UV gerekmez: dünya koordinatından üç düzlemli izdüşüm.
  tex_scale  >=0 doku tekrarının belge birimiyle (mm) genişliği; 0 = otomatik (sahne boyutuna göre)
  tex_mix 0..1   doku ile malzeme/nesne renginin karışımı (1 = yalnız doku)
  tex_proj  "cubic" (3 yönlü, varsayılan) | "planar" | "cylindrical" | "spherical": doku izdüşümü
  tex_axis  0/1/2  düzlemsel: bakış ekseni (X/Y/Z); silindirik/küresel: kutup ekseni
  tex_sx/sy/sz     eksen başına doku ölçeği çarpanı (1 = tex_scale genişliği)
  tex_px/py/pz     doku konumu (mm; koordinat orijinine göre kayma)
  tex_rx/ry/rz     doku dönmesi (derece, X sonra Y sonra Z)
  tex_world        False: nesne koordinatı (doku nesnenin sınır kutusu merkezine bağlı, nesneyle birlikte gider); True: dünya koordinatı
Atama nesnenin 'YBTMaterial' (metin) özelliğinde saklanır; belgeyle birlikte kaydolur.
"Render'a dahil et" işareti nesnenin 'YBTInclude' (mantıksal) özelliğinde saklanır; özellik yoksa nesne dahildir.
"""
import json
import os

PROP = "YBTMaterial"
INC_PROP = "YBTInclude"

DEFAULT = dict(color=None, diffuse=1.0, spec=0.30, gloss=0.28, metal=0.0, refl=0.0, transp=0.0, ior=1.0, lum=0.0,
               tex="", tex_scale=0.0, tex_mix=1.0,
               tex_proj="cubic", tex_axis=2, tex_sx=1.0, tex_sy=1.0, tex_sz=1.0,
               tex_px=0.0, tex_py=0.0, tex_pz=0.0, tex_rx=0.0, tex_ry=0.0, tex_rz=0.0, tex_world=False)
KEYS = tuple(DEFAULT.keys())


def shininess(gloss):
    """gloss 0..1 -> Blinn-Phong üssü (0.28 ~ eski varsayılan 48)."""
    g = min(max(float(gloss), 0.0), 1.0)
    return 2.0 + 600.0 * g * g


def _m(**kw):
    d = dict(DEFAULT)
    d.update(kw)
    return d


# Ad'lar Türkçe (kaynak); arayüzde i18n.T ile çevrilir. CATEGORIES: kütüphane listesindeki gruplar (sırayla).
BUILTIN = {
    # --- Plastik / kauçuk
    "Mat plastik":      _m(color=(0.80, 0.80, 0.82), spec=0.12, gloss=0.18),
    "Parlak plastik":   _m(color=(0.75, 0.10, 0.10), spec=0.60, gloss=0.55, refl=0.06),
    "Beyaz plastik":    _m(color=(0.93, 0.93, 0.92), spec=0.30, gloss=0.35, refl=0.03),
    "Siyah plastik":    _m(color=(0.03, 0.03, 0.035), spec=0.45, gloss=0.50, refl=0.05),
    "Mavi plastik":     _m(color=(0.08, 0.22, 0.65), spec=0.50, gloss=0.50, refl=0.05),
    "Yeşil plastik":    _m(color=(0.10, 0.50, 0.18), spec=0.50, gloss=0.50, refl=0.05),
    "Sarı plastik":     _m(color=(0.95, 0.78, 0.08), spec=0.50, gloss=0.50, refl=0.05),
    "Kauçuk":           _m(color=(0.06, 0.06, 0.06), spec=0.05, gloss=0.12),
    "Silikon":          _m(color=(0.85, 0.85, 0.82), spec=0.25, gloss=0.25, refl=0.02),
    "Naylon (mat)":     _m(color=(0.92, 0.91, 0.86), spec=0.10, gloss=0.15),
    # --- Boya
    "Boya (araba)":     _m(color=(0.70, 0.05, 0.05), spec=0.70, gloss=0.70, refl=0.15),
    "Boya (mavi metalik)": _m(color=(0.10, 0.25, 0.60), spec=0.80, gloss=0.75, metal=0.35, refl=0.18),
    "Boya (siyah piyano)": _m(color=(0.02, 0.02, 0.025), spec=0.90, gloss=0.85, refl=0.25),
    "Boya (beyaz mat)": _m(color=(0.90, 0.90, 0.88), spec=0.08, gloss=0.15),
    "Boya (gri mat)":   _m(color=(0.45, 0.46, 0.48), spec=0.08, gloss=0.15),
    "Toz boya (kum)":   _m(color=(0.42, 0.40, 0.36), spec=0.15, gloss=0.20),
    # --- Metal
    "Krom":             _m(color=(0.92, 0.92, 0.95), diffuse=0.20, spec=1.00, gloss=0.90, metal=1.0, refl=0.85),
    "Çelik (fırçalı)":  _m(color=(0.62, 0.63, 0.66), diffuse=0.55, spec=0.55, gloss=0.40, metal=1.0, refl=0.15),
    "Çelik (cilalı)":   _m(color=(0.70, 0.71, 0.74), diffuse=0.30, spec=0.90, gloss=0.80, metal=1.0, refl=0.55),
    "Paslanmaz çelik":  _m(color=(0.75, 0.76, 0.78), diffuse=0.45, spec=0.70, gloss=0.55, metal=1.0, refl=0.25),
    "Dökme demir":      _m(color=(0.22, 0.22, 0.24), diffuse=0.70, spec=0.25, gloss=0.25, metal=0.8, refl=0.04),
    "Fırçalı çelik (dokulu)": _m(color=(0.70, 0.72, 0.76), diffuse=0.50, spec=0.60, gloss=0.45, metal=1.0, refl=0.12,
                                 tex="celik_firca", tex_mix=0.85),
    "Alüminyum":        _m(color=(0.80, 0.81, 0.83), diffuse=0.50, spec=0.70, gloss=0.55, metal=1.0, refl=0.30),
    "Eloksal (siyah)":  _m(color=(0.06, 0.06, 0.07), diffuse=0.55, spec=0.50, gloss=0.45, metal=0.9, refl=0.10),
    "Eloksal (mavi)":   _m(color=(0.10, 0.25, 0.70), diffuse=0.55, spec=0.60, gloss=0.50, metal=0.9, refl=0.12),
    "Eloksal (kırmızı)": _m(color=(0.70, 0.08, 0.08), diffuse=0.55, spec=0.60, gloss=0.50, metal=0.9, refl=0.12),
    "Altın":            _m(color=(1.00, 0.77, 0.34), diffuse=0.40, spec=0.90, gloss=0.75, metal=1.0, refl=0.35),
    "Gümüş":            _m(color=(0.96, 0.95, 0.92), diffuse=0.30, spec=0.95, gloss=0.85, metal=1.0, refl=0.60),
    "Bakır":            _m(color=(0.95, 0.52, 0.38), diffuse=0.45, spec=0.80, gloss=0.65, metal=1.0, refl=0.30),
    "Pirinç":           _m(color=(0.86, 0.66, 0.28), diffuse=0.45, spec=0.80, gloss=0.65, metal=1.0, refl=0.28),
    "Bronz":            _m(color=(0.68, 0.45, 0.22), diffuse=0.50, spec=0.65, gloss=0.50, metal=1.0, refl=0.18),
    "Titanyum":         _m(color=(0.58, 0.56, 0.54), diffuse=0.50, spec=0.60, gloss=0.50, metal=1.0, refl=0.20),
    "Kurşun":           _m(color=(0.38, 0.39, 0.42), diffuse=0.65, spec=0.30, gloss=0.30, metal=1.0, refl=0.08),
    "Pas":              _m(color=(0.45, 0.22, 0.10), diffuse=1.0, spec=0.08, gloss=0.15),
    # --- Cam / sıvı
    "Cam":              _m(color=(0.85, 0.95, 0.95), spec=1.00, gloss=0.90, refl=1.0, transp=0.90, ior=1.5),
    "Cam (yeşilimsi)":  _m(color=(0.60, 0.85, 0.72), spec=1.00, gloss=0.90, refl=1.0, transp=0.85, ior=1.5),
    "Cam (füme)":       _m(color=(0.25, 0.27, 0.30), spec=1.00, gloss=0.90, refl=1.0, transp=0.75, ior=1.5),
    "Cam (mavi)":       _m(color=(0.45, 0.70, 0.95), spec=1.00, gloss=0.90, refl=1.0, transp=0.82, ior=1.5),
    "Buzlu cam":        _m(color=(0.90, 0.95, 0.95), spec=0.40, gloss=0.30, refl=0.40, transp=0.75, ior=1.0),
    "Akrilik (şeffaf)": _m(color=(0.92, 0.96, 0.96), spec=0.90, gloss=0.85, refl=0.7, transp=0.88, ior=1.49),
    "Su":               _m(color=(0.70, 0.88, 0.95), spec=1.00, gloss=0.90, refl=1.0, transp=0.92, ior=1.33),
    "Elmas":            _m(color=(0.95, 0.98, 1.00), spec=1.00, gloss=0.95, refl=1.0, transp=0.92, ior=2.4),
    # --- Doğal / yapı (dokulu)
    "Ahşap (cilalı)":   _m(color=(0.55, 0.33, 0.16), spec=0.25, gloss=0.35, refl=0.03),
    "Ahşap (dokulu)":   _m(color=(0.70, 0.55, 0.38), spec=0.20, gloss=0.30, refl=0.02, tex="ahsap", tex_scale=0.0),
    "Mermer (dokulu)":  _m(color=(0.90, 0.90, 0.90), spec=0.55, gloss=0.65, refl=0.08, tex="mermer"),
    "Travertin":        _m(color=(0.85, 0.80, 0.70), spec=0.15, gloss=0.25, tex="travertin"),
    "Beton":            _m(color=(0.70, 0.70, 0.68), spec=0.05, gloss=0.12, tex="beton"),
    "Tuğla":            _m(color=(0.70, 0.35, 0.28), spec=0.05, gloss=0.12, tex="tugla"),
    "Taş kaplama":      _m(color=(0.60, 0.58, 0.54), spec=0.08, gloss=0.15, tex="tas_duvar"),
    "Terrakota":        _m(color=(0.75, 0.45, 0.32), spec=0.08, gloss=0.18, tex="terrakota"),
    "Sıva":             _m(color=(0.90, 0.88, 0.82), spec=0.04, gloss=0.10, tex="siva"),
    "Çakıl":            _m(color=(0.60, 0.58, 0.55), spec=0.06, gloss=0.12, tex="cakil"),
    "Seramik":          _m(color=(0.93, 0.93, 0.90), spec=0.70, gloss=0.65, refl=0.08),
    "Porselen":         _m(color=(0.97, 0.97, 0.95), spec=0.85, gloss=0.80, refl=0.10),
    # --- Kumaş / deri / karbon
    "Deri (dokulu)":    _m(color=(0.80, 0.70, 0.65), spec=0.30, gloss=0.30, refl=0.02, tex="deri"),
    "Karbon fiber":     _m(color=(0.90, 0.92, 0.96), spec=0.60, gloss=0.65, refl=0.10, tex="karbon"),
    # --- Işık
    "Parlayan (ışık)":  _m(color=(1.00, 0.95, 0.80), spec=0.0, lum=1.0),
    "LED (beyaz)":      _m(color=(1.00, 1.00, 1.00), spec=0.0, lum=1.0),
    "LED (kırmızı)":    _m(color=(1.00, 0.15, 0.10), spec=0.0, lum=1.0),
    "LED (yeşil)":      _m(color=(0.20, 1.00, 0.30), spec=0.0, lum=1.0),
    # --- Mimari (dokulu)
    "Granit (gri)": _m(color=(0.88, 0.88, 0.88), spec=0.30, gloss=0.40, metal=0.00, refl=0.04, tex="mimari_granit1"),
    "Granit (bej)": _m(color=(0.88, 0.88, 0.88), spec=0.30, gloss=0.40, metal=0.00, refl=0.04, tex="mimari_granit2"),
    "Granit (mavi inci)": _m(color=(0.88, 0.88, 0.88), spec=0.45, gloss=0.55, metal=0.00, refl=0.06, tex="mimari_granit_mavi"),
    "Granit (siyah)": _m(color=(0.88, 0.88, 0.88), spec=0.50, gloss=0.60, metal=0.00, refl=0.07, tex="mimari_granit_siyah"),
    "Granit (kırmızı)": _m(color=(0.88, 0.88, 0.88), spec=0.45, gloss=0.55, metal=0.00, refl=0.06, tex="mimari_granit_kirmizi"),
    "Granit (yeşil)": _m(color=(0.88, 0.88, 0.88), spec=0.45, gloss=0.55, metal=0.00, refl=0.06, tex="mimari_granit_yesil"),
    "Mermer (Carrara)": _m(color=(0.88, 0.88, 0.88), spec=0.45, gloss=0.55, metal=0.00, refl=0.06, tex="mimari_mermer_carrara"),
    "Mermer (Botticino)": _m(color=(0.88, 0.88, 0.88), spec=0.40, gloss=0.50, metal=0.00, refl=0.05, tex="mimari_mermer_botticino"),
    "Mermer (krem)": _m(color=(0.88, 0.88, 0.88), spec=0.40, gloss=0.50, metal=0.00, refl=0.05, tex="mimari_mermer_krem"),
    "Mermer (gri)": _m(color=(0.88, 0.88, 0.88), spec=0.40, gloss=0.50, metal=0.00, refl=0.05, tex="mimari_mermer_gri"),
    "Mermer (rosso)": _m(color=(0.88, 0.88, 0.88), spec=0.45, gloss=0.55, metal=0.00, refl=0.06, tex="mimari_mermer_kirmizi"),
    "Mermer (yeşil)": _m(color=(0.88, 0.88, 0.88), spec=0.45, gloss=0.55, metal=0.00, refl=0.06, tex="mimari_mermer_yesil"),
    "Kalker": _m(color=(0.88, 0.88, 0.88), spec=0.06, gloss=0.12, metal=0.00, refl=0.00, tex="mimari_kalker"),
    "Kumtaşı": _m(color=(0.88, 0.88, 0.88), spec=0.05, gloss=0.10, metal=0.00, refl=0.00, tex="mimari_kumtasi"),
    "Travertin (gümüş)": _m(color=(0.88, 0.88, 0.88), spec=0.18, gloss=0.30, metal=0.00, refl=0.02, tex="mimari_travertin_gri"),
    "Kaba taş (kale)": _m(color=(0.88, 0.88, 0.88), spec=0.05, gloss=0.10, metal=0.00, refl=0.00, tex="mimari_kale_tasi"),
    "Kesme taş": _m(color=(0.88, 0.88, 0.88), spec=0.06, gloss=0.12, metal=0.00, refl=0.00, tex="mimari_kesme_tas"),
    "Dere taşı": _m(color=(0.88, 0.88, 0.88), spec=0.10, gloss=0.18, metal=0.00, refl=0.00, tex="mimari_dere_tasi"),
    "Taş (düz)": _m(color=(0.88, 0.88, 0.88), spec=0.06, gloss=0.12, metal=0.00, refl=0.00, tex="mimari_tas4"),
    "Tuğla (eski)": _m(color=(0.88, 0.88, 0.88), spec=0.04, gloss=0.08, metal=0.00, refl=0.00, tex="mimari_tugla_eski"),
    "Tuğla (yeni)": _m(color=(0.88, 0.88, 0.88), spec=0.05, gloss=0.10, metal=0.00, refl=0.00, tex="mimari_tugla_yeni"),
    "Tuğla (beyaz)": _m(color=(0.88, 0.88, 0.88), spec=0.05, gloss=0.10, metal=0.00, refl=0.00, tex="mimari_tugla_beyaz"),
    "Beton (düz)": _m(color=(0.88, 0.88, 0.88), spec=0.05, gloss=0.12, metal=0.00, refl=0.00, tex="mimari_beton_duz"),
    "Beton (dökme)": _m(color=(0.88, 0.88, 0.88), spec=0.05, gloss=0.12, metal=0.00, refl=0.00, tex="mimari_beton_dokme"),
    "Beton (açık gri)": _m(color=(0.88, 0.88, 0.88), spec=0.05, gloss=0.12, metal=0.00, refl=0.00, tex="mimari_beton_dokme2"),
    "Sıva (kırmızı)": _m(color=(0.88, 0.88, 0.88), spec=0.03, gloss=0.08, metal=0.00, refl=0.00, tex="mimari_siva_kirmizi"),
    "Sıva (sarı)": _m(color=(0.88, 0.88, 0.88), spec=0.03, gloss=0.08, metal=0.00, refl=0.00, tex="mimari_siva_sari"),
    "Sıva (güneybatı)": _m(color=(0.88, 0.88, 0.88), spec=0.03, gloss=0.08, metal=0.00, refl=0.00, tex="mimari_siva_guney"),
    "Stuko": _m(color=(0.88, 0.88, 0.88), spec=0.03, gloss=0.08, metal=0.00, refl=0.00, tex="mimari_stuko"),
    "Sıva (dokulu beyaz)": _m(color=(0.88, 0.88, 0.88), spec=0.03, gloss=0.08, metal=0.00, refl=0.00, tex="mimari_siva_beyaz"),
    "Cephe kaplama (sedir)": _m(color=(0.88, 0.88, 0.88), spec=0.10, gloss=0.20, metal=0.00, refl=0.00, tex="mimari_kaplama_sedir"),
    "Cephe kaplama (koyu)": _m(color=(0.88, 0.88, 0.88), spec=0.10, gloss=0.20, metal=0.00, refl=0.00, tex="mimari_kaplama_koyu"),
    "Cephe kaplama (açık)": _m(color=(0.88, 0.88, 0.88), spec=0.10, gloss=0.20, metal=0.00, refl=0.00, tex="mimari_kaplama_acik"),
    "Kütük duvar": _m(color=(0.88, 0.88, 0.88), spec=0.08, gloss=0.15, metal=0.00, refl=0.00, tex="mimari_kutuk_duvar"),
    "Ahşap (dişbudak)": _m(color=(0.88, 0.88, 0.88), spec=0.15, gloss=0.30, metal=0.00, refl=0.01, tex="mimari_ahsap_dis"),
    "Ahşap (maun)": _m(color=(0.88, 0.88, 0.88), spec=0.20, gloss=0.35, metal=0.00, refl=0.02, tex="mimari_ahsap_maun"),
    "Ahşap (akçaağaç)": _m(color=(0.88, 0.88, 0.88), spec=0.15, gloss=0.30, metal=0.00, refl=0.01, tex="mimari_ahsap_akcaagac"),
    "Ahşap (meşe, koyu)": _m(color=(0.88, 0.88, 0.88), spec=0.15, gloss=0.30, metal=0.00, refl=0.01, tex="mimari_ahsap_mese_koyu"),
    "Ahşap (meşe, açık)": _m(color=(0.88, 0.88, 0.88), spec=0.15, gloss=0.30, metal=0.00, refl=0.01, tex="mimari_ahsap_mese_acik"),
    "Ahşap (çam)": _m(color=(0.88, 0.88, 0.88), spec=0.12, gloss=0.25, metal=0.00, refl=0.00, tex="mimari_ahsap_cam"),
    "Ahşap (ceviz)": _m(color=(0.88, 0.88, 0.88), spec=0.20, gloss=0.35, metal=0.00, refl=0.02, tex="mimari_ahsap_ceviz"),
    "Ahşap (karaağaç)": _m(color=(0.88, 0.88, 0.88), spec=0.20, gloss=0.35, metal=0.00, refl=0.02, tex="mimari_ahsap_karaagac"),
    "Parke (1)": _m(color=(0.88, 0.88, 0.88), spec=0.18, gloss=0.30, metal=0.00, refl=0.02, tex="mimari_parke4"),
    "Parke (2)": _m(color=(0.88, 0.88, 0.88), spec=0.18, gloss=0.30, metal=0.00, refl=0.02, tex="mimari_parke5"),
    "Tahta döşeme": _m(color=(0.88, 0.88, 0.88), spec=0.12, gloss=0.25, metal=0.00, refl=0.00, tex="mimari_tahta_doseme"),
    "Seramik karo": _m(color=(0.88, 0.88, 0.88), spec=0.40, gloss=0.55, metal=0.00, refl=0.08, tex="mimari_seramik3"),
    "Karo (gri)": _m(color=(0.88, 0.88, 0.88), spec=0.35, gloss=0.50, metal=0.00, refl=0.06, tex="mimari_karo_gri"),
    "Karo (açık kahve)": _m(color=(0.88, 0.88, 0.88), spec=0.35, gloss=0.50, metal=0.00, refl=0.06, tex="mimari_karo_kahve"),
    "Karo (kırmızı)": _m(color=(0.88, 0.88, 0.88), spec=0.35, gloss=0.50, metal=0.00, refl=0.06, tex="mimari_karo_kirmizi"),
    "Mozaik": _m(color=(0.88, 0.88, 0.88), spec=0.40, gloss=0.55, metal=0.00, refl=0.06, tex="mimari_mozaik"),
    "Karo (beyaz)": _m(color=(0.88, 0.88, 0.88), spec=0.45, gloss=0.60, metal=0.00, refl=0.08, tex="mimari_karo_beyaz"),
    "Karo (mavi)": _m(color=(0.88, 0.88, 0.88), spec=0.45, gloss=0.60, metal=0.00, refl=0.08, tex="mimari_karo_mavi"),
    "Kiremit": _m(color=(0.88, 0.88, 0.88), spec=0.08, gloss=0.15, metal=0.00, refl=0.00, tex="mimari_kiremit"),
    "Çatı kaplama (kiremit 2)": _m(color=(0.88, 0.88, 0.88), spec=0.08, gloss=0.15, metal=0.00, refl=0.00, tex="mimari_cati1"),
    "Çatı kaplama (gri)": _m(color=(0.88, 0.88, 0.88), spec=0.08, gloss=0.15, metal=0.00, refl=0.00, tex="mimari_cati_gri"),
    "Çatı (sedir tahta)": _m(color=(0.88, 0.88, 0.88), spec=0.08, gloss=0.15, metal=0.00, refl=0.00, tex="mimari_cati_sedir"),
    "Çatı (terrakota)": _m(color=(0.88, 0.88, 0.88), spec=0.10, gloss=0.18, metal=0.00, refl=0.00, tex="mimari_cati_terrakota"),
    "Bakır sac (eskimiş)": _m(color=(0.88, 0.88, 0.88), spec=0.50, gloss=0.50, metal=0.70, refl=0.12, tex="mimari_bakir_eski"),
    "Çinko sac": _m(color=(0.88, 0.88, 0.88), spec=0.55, gloss=0.50, metal=0.80, refl=0.15, tex="mimari_cinko"),
    "Oluklu sac": _m(color=(0.88, 0.88, 0.88), spec=0.55, gloss=0.45, metal=0.80, refl=0.12, tex="mimari_oluklu_sac"),
    "Asfalt": _m(color=(0.88, 0.88, 0.88), spec=0.04, gloss=0.08, metal=0.00, refl=0.00, tex="mimari_asfalt"),
    "Toprak": _m(color=(0.88, 0.88, 0.88), spec=0.02, gloss=0.05, metal=0.00, refl=0.00, tex="mimari_toprak"),
    "Kesme taş kaldırım": _m(color=(0.88, 0.88, 0.88), spec=0.06, gloss=0.12, metal=0.00, refl=0.00, tex="mimari_kaldirim"),
    "Tuğla yaya yolu": _m(color=(0.88, 0.88, 0.88), spec=0.05, gloss=0.10, metal=0.00, refl=0.00, tex="mimari_tugla_yol"),
    "Halı (gri)": _m(color=(0.88, 0.88, 0.88), spec=0.02, gloss=0.05, metal=0.00, refl=0.00, tex="mimari_hali_gri"),
    "Deri (kahverengi)": _m(color=(0.88, 0.88, 0.88), spec=0.30, gloss=0.35, metal=0.00, refl=0.02, tex="mimari_deri3"),
    "Kumaş": _m(color=(0.88, 0.88, 0.88), spec=0.03, gloss=0.06, metal=0.00, refl=0.00, tex="mimari_kumas1"),
    "Çim": _m(color=(0.88, 0.88, 0.88), spec=0.02, gloss=0.05, metal=0.00, refl=0.00, tex="mimari_cim"),
}

CATEGORIES = [
    ("Plastik / kauçuk", ["Mat plastik", "Parlak plastik", "Beyaz plastik", "Siyah plastik", "Mavi plastik", "Yeşil plastik",
                          "Sarı plastik", "Kauçuk", "Silikon", "Naylon (mat)"]),
    ("Boya", ["Boya (araba)", "Boya (mavi metalik)", "Boya (siyah piyano)", "Boya (beyaz mat)", "Boya (gri mat)", "Toz boya (kum)"]),
    ("Metal", ["Krom", "Çelik (fırçalı)", "Çelik (cilalı)", "Paslanmaz çelik", "Dökme demir", "Fırçalı çelik (dokulu)", "Alüminyum",
               "Eloksal (siyah)", "Eloksal (mavi)", "Eloksal (kırmızı)", "Altın", "Gümüş", "Bakır", "Pirinç", "Bronz", "Titanyum",
               "Kurşun", "Pas"]),
    ("Cam / sıvı", ["Cam", "Cam (yeşilimsi)", "Cam (füme)", "Cam (mavi)", "Buzlu cam", "Akrilik (şeffaf)", "Su", "Elmas"]),
    ("Doğal / yapı", ["Ahşap (cilalı)", "Ahşap (dokulu)", "Mermer (dokulu)", "Travertin", "Beton", "Tuğla", "Taş kaplama",
                      "Terrakota", "Sıva", "Çakıl", "Seramik", "Porselen"]),
    ("Mimari", ['Granit (gri)', 'Granit (bej)', 'Granit (mavi inci)', 'Granit (siyah)', 'Granit (kırmızı)', 'Granit (yeşil)', 'Mermer (Carrara)', 'Mermer (Botticino)', 'Mermer (krem)', 'Mermer (gri)', 'Mermer (rosso)', 'Mermer (yeşil)', 'Kalker', 'Kumtaşı', 'Travertin (gümüş)', 'Kaba taş (kale)', 'Kesme taş', 'Dere taşı', 'Taş (düz)', 'Tuğla (eski)', 'Tuğla (yeni)', 'Tuğla (beyaz)', 'Beton (düz)', 'Beton (dökme)', 'Beton (açık gri)', 'Sıva (kırmızı)', 'Sıva (sarı)', 'Sıva (güneybatı)', 'Stuko', 'Sıva (dokulu beyaz)', 'Cephe kaplama (sedir)', 'Cephe kaplama (koyu)', 'Cephe kaplama (açık)', 'Kütük duvar', 'Ahşap (dişbudak)', 'Ahşap (maun)', 'Ahşap (akçaağaç)', 'Ahşap (meşe, koyu)', 'Ahşap (meşe, açık)', 'Ahşap (çam)', 'Ahşap (ceviz)', 'Ahşap (karaağaç)', 'Parke (1)', 'Parke (2)', 'Tahta döşeme', 'Seramik karo', 'Karo (gri)', 'Karo (açık kahve)', 'Karo (kırmızı)', 'Mozaik', 'Karo (beyaz)', 'Karo (mavi)', 'Kiremit', 'Çatı kaplama (kiremit 2)', 'Çatı kaplama (gri)', 'Çatı (sedir tahta)', 'Çatı (terrakota)', 'Bakır sac (eskimiş)', 'Çinko sac', 'Oluklu sac', 'Asfalt', 'Toprak', 'Kesme taş kaldırım', 'Tuğla yaya yolu', 'Halı (gri)', 'Deri (kahverengi)', 'Kumaş', 'Çim']),
    ("Deri / karbon", ["Deri (dokulu)", "Karbon fiber"]),
    ("Işık", ["Parlayan (ışık)", "LED (beyaz)", "LED (kırmızı)", "LED (yeşil)"]),
]


def _drop_missing_textures():
    """Dosyası bulunmayan 'mimari_*' dokulu hazır malzemeleri (ve boşalan kategorileri) listeden çıkarır."""
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "textures")
    gone = [n for n, m in BUILTIN.items()
            if str(m.get("tex", "")).startswith("mimari_") and not os.path.isfile(os.path.join(d, str(m["tex"]).replace("mimari_", "mimari_") + ".png"))]
    for n in gone:
        del BUILTIN[n]
    CATEGORIES[:] = [(c, [n for n in ns if n in BUILTIN]) for c, ns in CATEGORIES]
    CATEGORIES[:] = [(c, ns) for c, ns in CATEGORIES if ns]


_drop_missing_textures()


def category_of(name):
    for cat, names in CATEGORIES:
        if name in names:
            return cat
    return ""


def user_lib_path():
    try:
        import FreeCAD
        base = FreeCAD.getUserAppDataDir()
    except Exception:
        base = os.path.expanduser("~")
    return os.path.join(base, "YBTRayTracer", "materials.json")


def load_user():
    try:
        with open(user_lib_path(), "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {k: normalize(v) for k, v in raw.items()}
    except Exception:
        return {}


def save_user(lib):
    p = user_lib_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump({k: dict(v, color=list(v["color"]) if v.get("color") else None) for k, v in lib.items()},
                  f, ensure_ascii=False, indent=1)


def normalize(d):
    """Eksik/bozuk alanları varsayılanla tamamla, aralıklara sıkıştır."""
    out = dict(DEFAULT)
    for k in KEYS:
        if k in d and d[k] is not None:
            out[k] = d[k]
    c = out["color"]
    out["color"] = tuple(min(max(float(x), 0.0), 1.0) for x in c) if c else None
    lim = dict(diffuse=(0, 1), spec=(0, 1), gloss=(0, 1), metal=(0, 1), refl=(0, 1), transp=(0, 1), ior=(1, 3), lum=(0, 1),
               tex_scale=(0, 1e9), tex_mix=(0, 1))
    for k, (lo, hi) in lim.items():
        out[k] = min(max(float(out[k]), lo), hi)
    out["tex"] = str(out["tex"] or "")
    out["tex_proj"] = out["tex_proj"] if out["tex_proj"] in ("cubic", "planar", "cylindrical", "spherical") else "cubic"
    try:
        out["tex_axis"] = min(max(int(out["tex_axis"]), 0), 2)
    except Exception:
        out["tex_axis"] = 2
    for k in ("tex_sx", "tex_sy", "tex_sz"):
        out[k] = min(max(float(out[k]), 0.01), 1000.0)
    for k in ("tex_px", "tex_py", "tex_pz"):
        out[k] = min(max(float(out[k]), -1e9), 1e9)
    for k in ("tex_rx", "tex_ry", "tex_rz"):
        out[k] = min(max(float(out[k]), -360.0), 360.0)
    out["tex_world"] = bool(out["tex_world"])
    return out


def library():
    """Hazır + kullanıcı malzemeleri (kullanıcınınki aynı adı ezer)."""
    lib = dict(BUILTIN)
    lib.update(load_user())
    return lib


def get(name, lib=None):
    if not name:
        return None
    lib = library() if lib is None else lib
    m = lib.get(name)
    return normalize(m) if m is not None else None


def assigned(obj):
    """Nesneye atanmış malzeme adı ('' = yok). Link ise bağlı nesneye de bakılır."""
    for o in (obj, getattr(obj, "LinkedObject", None)):
        if o is None:
            continue
        try:
            v = getattr(o, PROP, "")
        except Exception:
            v = ""
        if v:
            return str(v)
    return ""


def _own(obj, prop):
    """Özellik nesnenin KENDİNDE mi? (App::Link, bağlı nesnenin özelliklerini de yansıtır; hasattr/getattr yanıltır.)"""
    try:
        return prop in obj.PropertiesList
    except Exception:
        return False


def included(obj):
    """Nesne render'a dahil mi? Özellik yoksa (hiç hariç tutulmamışsa) dahildir. Yalnız nesnenin kendi işareti geçerlidir:
    bir parça hariç tutulunca ona bağlı Link'ler (ve tersi) etkilenmez."""
    if not _own(obj, INC_PROP):
        return True
    try:
        return bool(getattr(obj, INC_PROP))
    except Exception:
        return True


def set_included(obj, flag):
    """Dahil et işaretini yaz. Özellik yalnızca ilk kez hariç tutulurken eklenir (belgeyle kaydolur)."""
    if not _own(obj, INC_PROP):
        if flag:
            return
        obj.addProperty("App::PropertyBool", INC_PROP, "YBT RayTracer", "Include this object in raytracer renders")
    if bool(getattr(obj, INC_PROP)) != bool(flag):
        setattr(obj, INC_PROP, bool(flag))


def assign(obj, name):
    """Nesneye malzeme ata ('' = kaldır). Özellik yoksa eklenir (belgeyle kaydolur)."""
    if not hasattr(obj, PROP):
        if not name:
            return
        obj.addProperty("App::PropertyString", PROP, "YBT RayTracer", "Raytracer material name")
    if getattr(obj, PROP) != (name or ""):
        setattr(obj, PROP, name or "")
