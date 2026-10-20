# -*- coding: utf-8 -*-
import os
import struct
import zlib
from . import settings as S
from . import paths as _paths


def write_png(path, arr):
    """Bağımlılıksız PNG yazıcı. arr: (h, w, 3) uint8."""
    h, w, _ = arr.shape
    raw = b"".join(b"\x00" + arr[y].tobytes() for y in range(h))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


def pick_out_path(doc_filename):
    """Yazılabilir bir klasör seç: ayarlı çıktı klasörü (DIR_OUT) -> belge klasörü -> ~/Pictures -> ev dizini -> geçici klasör."""
    if S.OUT_NAME:
        return S.OUT_NAME
    name = (os.path.splitext(os.path.basename(doc_filename))[0] + "_render.png"
            if doc_filename else "FreeCAD_render.png")
    od = _paths.out_dir(doc_filename)                        # ayarlı çıktı klasörü (yoksa oluşturulur) en başta denenir
    if od:
        try:
            os.makedirs(od, exist_ok=True)
        except OSError:
            od = ""
        if od and os.access(od, os.W_OK):
            return os.path.join(od, name)
    dirs = []
    if doc_filename:
        dirs.append(os.path.dirname(doc_filename))
    home = os.path.expanduser("~")
    dirs += [os.path.join(home, "Pictures"), os.path.join(home, "Resimler"), home]
    import tempfile
    dirs.append(tempfile.gettempdir())
    for d in dirs:
        if d and os.path.isdir(d) and os.access(d, os.W_OK):
            return os.path.join(d, name)
    return os.path.join(home, name)
