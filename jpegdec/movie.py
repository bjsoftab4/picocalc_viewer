# test jpeg draw functions

# import io
# import time
import gc

import picocalc

# from picojpeg import PicoJpeg
from jpegfunc import JpegFunc

wmax = 320
hmax = 320


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
    buf = bytearray(kc + 1)
    keyb.readinto(buf)
    st = buf.rstrip(b"\0").decode()
    return st


class MyException(Exception):
    pass


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
            for fname, fps in (
                ("/sd/countdown.tar", 8),
                ("/sd/sig320x8-1.tar", 8),
                ("/sd/sig320x8-2.tar", 8),
                ("/sd/sig240x12-1.tar", 12),
                ("/sd/sig240x12-2.tar", 12),
            ):
                rc = JpegFunc.play_movie(fname, fps)
                if rc < 0:
                    break
                st = getKeystring()
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


if __name__ == "__main__":
    run()
