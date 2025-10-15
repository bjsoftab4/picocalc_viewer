# test jpeg draw functions

import io
import time
import picocalc
import jpegdec
import gc

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

class jpegfunc():
    drawpage = 1
    buf_save = None
    decoder_running = False

    @classmethod
    def decode(cls, buf, offset=None, clip=None, scale=1):
        JPEG_SCALE_HALF = 2
        JPEG_SCALE_QUARTER = 4
        JPEG_SCALE_EIGHTH = 8
        global wmax, hmax
        
        if offset is None:
            offset = (0,0)
        if clip is None:
            ox = offset[0]
            oy = offset[1]
            clip = (ox, oy, wmax - ox, hmax - oy)
        ioption = 0
        if scale == 1:
            pass
        elif scale >= 0.5:
            ioption = JPEG_SCALE_HALF
        elif scale >= 0.25:
            ioption = JPEG_SCALE_QUARTER
        elif scale >= 0.125:
            ioption = JPEG_SCALE_EIGHTH
        
        jpginfo = jpegdec.decode_opt(buf, offset, clip, ioption)
        return jpginfo

    @classmethod
    def showcenter(cls, buf):
        global hmax, wmax
        
        off_x = off_y = 0
        clp_x = clp_y = 0

        jpginfo = jpegdec.getinfo(buf)
        w = jpginfo[1]
        h = jpginfo[2]
        print(f"w={w}, h={h}")
        w0 = w
        h0 = h
        scale = 1.0
        if w >= wmax * 2 or h >= hmax * 2:
            w = w // 2
            h = h // 2
            scale = 0.5
            print(f"change w={w}, h={h}, scale={scale}")
            
        if w > wmax:
            off_x = 0
            clp_x = (w - wmax) // 2
            clp_w = wmax
        else:
            off_x = (wmax - w) // 2
            clp_x = 0
            clp_w = w

        if h > hmax:
            off_y = 0
            clp_y = (h - hmax) // 2
            clp_h = hmax
        else:
            off_y = (hmax - h) // 2
            clp_y = 0
            clp_h = h

        jpginfo = cls.decode(buf
                              , offset=(off_x,off_y)
                              #, clip=(clp_x, clp_y + off_y, clp_w + off_x, clp_h + off_y)
                              , clip=(0,0,w0,h0)
                              , scale=scale)
        rc = 0
        if jpginfo[0] == 0:
            rc = -1
        return rc

    @classmethod
    def flipdrawpage(cls):
        if cls.drawpage == 1:
            cls.drawpage = 2
        else:
            cls.drawpage = 1
            
    @classmethod
    def showjpeg(cls, buf):
        if cls.decoder_running :
            jpginfo = jpegdec.decode_core_wait()
            if jpginfo[0] == 0 and jpginfo[1] != 0:
                print(f"decode error {jpginfo}")
        cls.buf_save = buf  # To exclude gc while docoder running
        cls.decoder_running = True
        
        jpginfo = jpegdec.getinfo(buf)
        w = jpginfo[1]
        h = jpginfo[2]

        if h > 240:
            jpginfo = jpegdec.decode_core(cls.buf_save, 0, 1)          #single page
        else:
            jpginfo = jpegdec.decode_core(cls.buf_save, cls.drawpage, 1)   #flip page

        cls.flipdrawpage()
        return 0

    @classmethod
    def play(cls, outfn, fi, fps):
        global keyb
        jpegdec.clear()
        waitms=int(1000/fps)
        rc = 0
        for i in range(3600):
            last = time.ticks_ms()
            if outfn.endswith('.tar'):
                headbuf = fi.read(512)              # read tar header
                if len(headbuf) != 512:
                    rc = 0
                    break
                fn=headbuf[0:100].rstrip(b"\0").decode()
                if len(fn) == 0:
                    rc = 0
                    break  # EOF
                sz = int(headbuf[0x7c:0x87].decode(),8)
                if (sz % 512) != 0:
                  sz += 512 - sz % 512
                buf = fi.read(sz)
                if len(buf) != sz:
                    rc = 0
                    break  # EOF or bad data
                if fn.endswith((".jpg",".jpeg")) is False:
                    continue
            elif outfn.endswith((".jpg",".jpeg")):
                buf = fi.read()
                if len(buf) == 0:
                    rc = 0
                    break  # EOF or bad data
            else:
                rc = 0
                break
            
            if checkKey(): 
                break
            lap1 = time.ticks_ms()
            rc = cls.showjpeg(buf)
            # rc = cls.showcenter(buf)
            
            n_time = time.ticks_ms()
            dif = n_time - last
            #print(f"time: read={lap1-last}, decode={n_time - lap1}, total={dif}")
            if( dif < waitms):
                    time.sleep_ms(waitms - dif)
            if rc < 0:
                break
        time.sleep_ms(500)
        if cls.decoder_running:
            jpginfo = jpegdec.decode_core_wait()
            cls.decoder_running = False
        return rc

    @classmethod
    def pictview(cls, outfn, fps):
        print(outfn)
        try:
            fi = io.open(outfn, mode='rb')
        except :
            return -1
        rc = cls.play(outfn, fi, fps)
        fi.close()
        return rc
        
    @classmethod
    def start(cls):
        jpegdec.start(0)

    @classmethod
    def end(cls):
        if cls.decoder_running:
            jpegdec.decode_core_wait()
            cls.decoder_running = False
        jpegdec.end()

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
        jpegfunc.start()

        while True:
            rc = 0
            for (fname,fps) in (
                ("/sd/countdown.tar", 8)
                , ("/sd/sig320x8-1.tar", 8)
                , ("/sd/sig320x8-2.tar", 8)
                , ("/sd/sig240x12-1.tar", 12)
                , ("/sd/sig240x12-2.tar", 12)

                ):
                rc = jpegfunc.pictview(fname, fps)
                if rc < 0:
                    break
                st = getKeystring()
                if 'q' in st:
                    rc = -1
                    break
            if rc < 0:
                break
            gc.collect()
    finally:
        print("Leave main")
        jpegfunc.end()
        screen.recoverRefresh()

if __name__ == "__main__":
    run()

