"""test jpeg draw functions"""

# split draw

import io
import time
import gc
import os

import picocalc
from picojpeg import PicoJpeg
from jpegfunc import JpegFunc

WMAX = 320
HMAX = 320

screen = picocalc.display
keyb = picocalc.keyboard


def check_key():
    kc = keyb.keyCount()
    if kc == 0:
        return False
    return True


def get_keystring():
    kc = keyb.keyCount()
    if kc == 0:
        return ""
    buf = bytearray(kc + 1)
    keyb.readinto(buf)
    st = buf.rstrip(b"\0").decode()
    return st



class MyException(Exception):
    pass


def run0():
    print("Enter main")
    screen.stopRefresh()
    print("\x1b[35;9H")

    try:
        JpegFunc.start()
        fdir = "/sd/"
        flist = os.listdir(fdir)
        for fn in flist:
            rc = JpegFunc.single_view(fdir + fn)
            if rc == 1:
                time.sleep(5)

        rc = JpegFunc.single_view("/gun320.jpg")
        time.sleep(5)
        rc = JpegFunc.single_view("/rezero-l.jpg")
        time.sleep(5)
        rc = JpegFunc.single_view("/rezero.jpg")
        time.sleep(5)
        while True:
            rc = 0
            for fname, fps in (
                ("/sd/countdown.tar", 8),
                ("/sd/sig320x8-1.tar", 8),
                ("/sd/sig320x8-2.tar", 8),
                ("/sd/sig240x12-1.tar", 12),
                ("/sd/sig240x12-2.tar", 12),
            ):
                rc = JpegFunc.pictview(fname, fps)
                if rc < 0:
                    break
                st = get_keystring()
                if "q" in st:
                    rc = -1
                    break
            if rc < 0:
                break
            gc.collect()
    finally:
        print("Leave main")
        JpegFunc.end()
        screen.recoverRefresh()


def run():
    print("Enter main")
    screen.stopRefresh()

    JpegFunc.start()
    rc = JpegFunc.single_view("/rezero-l.jpg")
    time.sleep(5)

    JpegFunc.end()
    screen.recoverRefresh()


if __name__ == "__main__":
    run()
