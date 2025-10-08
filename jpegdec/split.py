# test jpeg draw functions
# split draw

import io
import time
import picocalc
import jpegdec
import gc
import os

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
    def getOption(cls, scale):
        JPEG_SCALE_HALF = 2
        JPEG_SCALE_QUARTER = 4
        JPEG_SCALE_EIGHTH = 8

        ioption = 0
        if scale == 1:
            pass
        elif scale >= 0.5:
            ioption = JPEG_SCALE_HALF
        elif scale >= 0.25:
            ioption = JPEG_SCALE_QUARTER
        elif scale >= 0.125:
            ioption = JPEG_SCALE_EIGHTH
        return ioption

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
    def calcscale(cls, buf):
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
        for fact in (4,2,1):
            if w > wmax * fact or h > hmax * fact:
                fact = fact * 2
                w = w // fact
                h = h // fact
                scale = 1 / fact
                print(f"change w={w}, h={h}, scale={scale}")
                break
        """    
        if w > wmax:
            off_x = 0
            clp_x = int((w - wmax) / scale) // 2
            clp_w = int( wmax / scale)
        else:
            off_x = (wmax - w) // 2
            clp_x = 0
            clp_w = w0

        if h > hmax:
            off_y = 0
            clp_y = int((h - hmax) / scale) //2
            clp_h = int( hmax / scale)
        else:
            off_y = (hmax - h) //2
            clp_y = 0
            clp_h = h0
        """
        clp_x = 0
        clp_y = 0
        clp_w = int(w0 * scale )
        clp_h = int(h0)
        return (scale, (off_x, off_y), (clp_x, clp_y, clp_w, clp_h))

    @classmethod
    def show_split(cls, fsize, buf):
        (scale, offset, clip) = cls.calcscale(buf)
        ioption = cls.getOption(scale)
        print(scale, offset, clip, ioption)
        clip=None
        offset=None
        jpginfo = jpegdec.decode_split(fsize, buf, offset, clip, ioption)
        return jpginfo[0]

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
    def splitplay(cls, outfn, fi):
        if not outfn.endswith((".jpg",".jpeg")):
            print("Bad ext", outfn)
            return 0
        jpegdec.clear()
        rc = 0
        last = time.ticks_ms()
        fs = os.stat(outfn)
        fsize = fs[6]
        if fsize < 8192 :
            bufsize = fsize
        else:
            bufsize = 4096
        jpginfo = None
        t_read = 0
        t_decode = 0
        lap0 = time.ticks_ms()
        buf = fi.read(bufsize)
        t_read += lap0 - time.ticks_ms()
        cls.buf_save = buf  # To exclude gc while docoder running
        cls.decoder_running = True
        rc = cls.show_split(fsize, buf)
        
        newpos = -1
        lap0 = time.ticks_ms()
        while True:
            retc = jpegdec.decode_split_wait()
            if retc[0] == 0: # running
                if retc[1] < 0:  # fpos is not set
                    continue
                newpos = retc[1]
                newsize = retc[2]
            else:               # Done
                break
            t_decode += lap0 - time.ticks_ms()
            lap0 = time.ticks_ms()
            fi.seek(newpos)
            buf = fi.read(bufsize)
            if len(buf) < bufsize:
                buf = buf + bytes(bufsize - len(buf))
            #print(f"seek to {newpos},{newsize}, size={len(buf)}")
            t_read += lap0 - time.ticks_ms()
            lap0 = time.ticks_ms()
            jpginfo = jpegdec.decode_split_buffer(0, newpos, buf)
            #print(jpginfo)

        n_time = time.ticks_ms()
        dif = n_time - last
        print(f"time: read={t_read}, decode={t_decode}, total={dif}")
        cls.decoder_running = False
        return rc

    @classmethod
    def splitview(cls, outfn):
        print(outfn)
        try:
            fi = io.open(outfn, mode='rb')
        except :
            print("file open error")
            return -1
        rc = cls.splitplay(outfn, fi)
        fi.close()
        return rc
        
    @classmethod
    def start(cls):
        jpegdec.start(0)

    @classmethod
    def end(cls):
        if cls.decoder_running:
            jpegdec.decode_core_wait(1)
            jpegdec.decode_core_wait(1)
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
        fdir = "/sd/"
        flist = os.listdir(fdir)
        for fn in flist:
            rc = jpegfunc.splitview(fdir+fn)
            if rc == 1:
                time.sleep(5)
            
        rc = jpegfunc.splitview("/gun320.jpg")
        time.sleep(5)
        rc = jpegfunc.splitview("/rezero-l.jpg")
        time.sleep(5)
        rc = jpegfunc.splitview("/rezero.jpg")
        time.sleep(5)
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

