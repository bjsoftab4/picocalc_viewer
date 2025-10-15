"""
test program for scaling

"""

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

crop_mode = 0

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

    global crop_mode
    
    JpegFunc.start()
    for fn in ("/sd/640x640.jpg", "/sd/1280x1280.jpg"):
        rc = JpegFunc.single_view(fn)
        try:
            get_keystring()
            while check_key() is False:
                time.sleep(1)
        except:
            break
    print("jpegfunc end")    
    JpegFunc.end()
    screen.recoverRefresh()


if __name__ == "__main__":
    run()
