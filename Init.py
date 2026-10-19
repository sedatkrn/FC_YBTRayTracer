# -*- coding: utf-8 -*-
# FC YBT Raytracer -- FreeCAD eklentisi, uygulama (GUI'siz) başlangıcı.
# Burada yalnız `ybt_raytracer` paketinin bulunabilmesi sağlanır; ağır hiçbir şey içe aktarılmaz.
# Komutlar / araç çubuğu / tezgâh InitGui.py içinde kaydedilir.
import os
import sys

try:
    _ybt_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:                                   # FreeCAD bazı sürümlerde __file__ vermez; Mod/ dizinleri zaten sys.path'e girer
    _ybt_dir = None
if _ybt_dir and os.path.isdir(os.path.join(_ybt_dir, "ybt_raytracer")) and _ybt_dir not in sys.path:
    sys.path.insert(0, _ybt_dir)
