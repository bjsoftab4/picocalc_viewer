# test jpeg draw functions

import io
import time
import picocalc
import jpegdec
import gc
import os

import picocalc

wmax=320
hmax=320

def checkKey():
    global keyb
    kc = keyb.keyCount()
    if kc == 0:
        return False
    return True

def getKeystring():
    global keyb
    kc = keyb.keyCount()
    if kc == 0:
        return ""
    buf = bytearray(kc+1)
    keyb.readinto(buf)
    st = buf.rstrip(b"\0").decode()
    return st

class MyException(Exception):
    pass

from picojpeg import PicoJpeg
from jpegfunc import JpegFunc

screen = picocalc.display
keyb = picocalc.keyboard
def run():
    global screen
    print("Enter main")
    screen.stopRefresh()
    print("\x1b[35;9H")
    try:
        JpegFunc.start()

        while True:
            rc = 0

            for fdir in ("/sd/", "/"):
                flist = os.listdir(fdir)
                for fn in flist:
                    rc = JpegFunc.single_view(fdir + fn)
                    if rc == 1:
                        time.sleep(5)
                    st = getKeystring()
                    if 'q' in st:
                        rc = -1
                        break
                if rc < 0:
                    break
                gc.collect()
    finally:
        print("Leave main")
        JpegFunc.end()
        screen.recoverRefresh()

if __name__ == "__main__":
    run()

