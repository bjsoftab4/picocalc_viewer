# test jpeg draw functions

import io
import time
import gc
import os
import picocalc
from picojpeg import PicoJpeg
from jpegfunc import JpegFunc
from mp3 import Pcm
import utils

wmax=320
hmax=320


class MyException(Exception):
    pass
import gc


def play_movie(fname):
    return JpegFunc.play_movie3(fname, fname)
    
screen = picocalc.display
def run(fdir = "/sd"):
    global screen
    utils.waitKeyOff()
    print("Enter main")
    screen.stopRefresh()
    print("\x1b[35;9H")
    try:
        JpegFunc.start()
        Pcm.init()
        utils.scan_dir(fdir, play_movie, (".tar"))
        #for fname in ("/sd/eva01.tar","/sd/GQXOP.tar"):
        #    rc = JpegFunc.play_movie3(fname, fname)
        #    waitKeyOff()
    finally:
        print("Leave main")
        JpegFunc.end()
        Pcm.deinit()
        screen.recoverRefresh()

if __name__ == "__main__":
    run()

