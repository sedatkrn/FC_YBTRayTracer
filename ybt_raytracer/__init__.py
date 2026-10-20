# -*- coding: utf-8 -*-
"""FC YBT Raytracer -- FreeCAD için bağımlılıksız numpy ışın izleyici.

Modüller:
  settings       kullanıcı ayarları (render bu modülden okur: settings.AA, settings.FLOOR ...)
  core           Scene (üçgen verisi) + temel kesişim fonksiyonları
  parallel       BLAS iş parçacığı sınırı, iptal / ilerleme (Ticker)
  accel          ekran karoları, ışık-uzayı ızgarası, küme (BVH benzeri) hızlandırıcılar
  render         ışın izleme döngüsü (gölge, cam, yansıma, zemin, AA, paralel)
  output         PNG yazıcı, çıktı yolu
  freecad_scene  FreeCAD nesnelerini üçgenlere çevirme, kamera, ışık tercihleri
  ui             ayar paneli ve önizleme penceresi
  api            arayüzsüz API: render_document, prepare_scene, orbit_cameras, turntable (animasyon), pick_object
  pick           tıkla-seç: görüntüdeki piksel -> nesne (önizleme tıklaması, boya kovası)
"""
__version__ = "1.5.1"
