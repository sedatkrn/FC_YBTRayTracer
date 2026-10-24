# -*- coding: utf-8 -*-
import threading
import time


def _limit_blas(n):
    """
    BLAS'ın (OpenBLAS/MKL) kendi iş parçacığı havuzunu n'e düşürür; kendi iş parçacıklarımızla çakışıp
    işlemciyi gereksiz yere meşgul etmesin (aşırı abonelik). Döner: eski ayarı geri yükleyen fonksiyon.
    threadpoolctl varsa onu, yoksa yüklü OpenBLAS/MKL kütüphanesini ctypes ile doğrudan kullanır.
    """
    try:
        from threadpoolctl import threadpool_limits
        lim = threadpool_limits(limits=n)
        return lim.restore_original_limits
    except Exception:
        pass
    restores = []
    try:
        import ctypes
        import os
        import sys
        paths = set()
        if sys.platform.startswith("win"):
            # Windows: süreçte yüklü BLAS DLL'i adıyla açılır (yüklüyse aynı tanıtıcı döner). FreeCAD: bin\openblas.dll;
            # pip numpy: numpy.libs\libscipy_openblas*.dll
            paths.update(("openblas.dll", "libopenblas.dll", "mkl_rt.dll"))
            try:
                import glob
                import numpy
                nd = os.path.dirname(os.path.dirname(numpy.__file__))
                for pat in ("numpy.libs/*openblas*.dll", "numpy/.libs/*openblas*.dll"):
                    paths.update(glob.glob(os.path.join(nd, pat)))
            except Exception:
                pass
        else:
            with open("/proc/self/maps") as f:
                for line in f:
                    low = line.lower()
                    if ("blas" in low or "mkl_rt" in low) and ".so" in low:
                        paths.add(line.split()[-1])
        for pth in paths:
            try:
                lib = ctypes.CDLL(pth)
            except OSError:
                continue
            done = False
            for pre in ("openblas", "scipy_openblas", "MKL"):
                for suf in ("", "64_", "_64_", "_"):
                    sname = "%s_set_num_threads%s" % (pre, suf)
                    gname = "%s_get_num_threads%s" % (pre, suf)
                    if pre == "MKL":
                        sname, gname = "MKL_Set_Num_Threads", "MKL_Get_Max_Threads"
                    st, gt = getattr(lib, sname, None), getattr(lib, gname, None)
                    if st is None:
                        continue
                    old = int(gt()) if gt is not None else 0
                    st(int(n))
                    if old > 0:
                        restores.append(lambda st=st, old=old: st(old))
                    done = True
                    break
                if done:
                    break
    except Exception:
        pass

    def restore():
        for r in restores:
            try:
                r()
            except Exception:
                pass
    return restore


class _Cancelled(BaseException):
    """Kullanıcı önizleme penceresini kapattı. BaseException: 'except Exception' bunu yutmasın."""


class _Ticker(object):
    """Uzun döngülerde en çok 0.15 sn'de bir geri çağrı yapar; geri çağrı False dönerse iptal."""

    def __init__(self, fn, every=0.15):
        self.fn, self.every, self.last = fn, every, 0.0
        self.owner = threading.current_thread()
        self.cancel = threading.Event()      # işçi iş parçacıklarına "dur" demek için

    def __call__(self):
        if threading.current_thread() is not self.owner:
            # işçi iş parçacığı: arayüze dokunmaz, yalnız iptal bayrağına bakar
            if self.cancel.is_set():
                raise _Cancelled()
            return
        if self.fn is None:
            return
        now = time.time()
        if now - self.last >= self.every:
            self.last = now
            if self.fn() is False:
                raise _Cancelled()
