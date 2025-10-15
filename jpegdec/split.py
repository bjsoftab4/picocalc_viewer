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
