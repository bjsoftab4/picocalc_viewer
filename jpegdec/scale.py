"""test jpeg draw functions"""

# split draw

import io
import time
import gc
import os

import picocalc
from picojpeg import PicoJpeg

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


class JpegFunc:
    JPEG_SCALE_HALF = const(2)
    JPEG_SCALE_QUARTER = const(4)
    JPEG_SCALE_EIGHTH = const(8)
    drawpage = 1
    buf_save = None
    decoder_running = False

    BUFFERSIZE = const(8192)
    BUFFERNUM = const(2)
    filebuffer = None
    buffers = [None] * BUFFERNUM

    @classmethod
    def get_option(cls, scale):

        ioption = 0
        if scale == 1:
            pass
        elif scale >= 0.5:
            ioption = cls.JPEG_SCALE_HALF
        elif scale >= 0.25:
            ioption = cls.JPEG_SCALE_QUARTER
        elif scale >= 0.125:
            ioption = cls.JPEG_SCALE_EIGHTH
        return ioption

    @classmethod
    def decode(cls, buf, offset=None, clip=None, scale=1):

        if offset is None:
            offset = (0, 0)
        if clip is None:
            ox = offset[0]
            oy = offset[1]
            clip = (ox, oy, WMAX - ox, HMAX - oy)
        ioption = cls.get_option(scale)

        jpginfo = PicoJpeg.decode_opt(buf, offset, clip, ioption)
        return jpginfo
        
        
    @classmethod
    def fix_crop(cls, scale, crop, jpegsize):
        """
          in:  crop, jpegsize (in jpeg pixel)
          out: fixed crop value for JPEGDEC
        """
        jw, jh = jpegsize
        x, y, w, h = crop
        x1 = x + w
        y1 = y + h
        if x & 0xf != 0:
            x = (x & 0xfff0) + 16
        if y & 0xf != 0:
            y = (y & 0xfff0) + 16
        x1 = x1 & 0xfff0
        y1 = y1 & 0xfff0
        if y1 > jh - 32:        # to avoid buffer overrun
            y1 = jh - 32
        #if x1 > jw - 16:        # to avoid buffer overrun
        #   x1 = jw - 16
        w = x1 - x
        h = y1 - y
        cx = int(x * scale)     # cx,cw is in display pixel
        cw = int(w * scale)
        cy = int(y * scale)     # cy is in display pixel
        ch = int( y1 - cy )     # ch is ???
        return (cx, cy, cw, ch)
 
    @classmethod
    def calcscale(cls, buf):

        off_x = off_y = 0
        clp_x = clp_y = 0

        jpginfo = PicoJpeg.getinfo(buf)
        w = jpginfo[1]
        h = jpginfo[2]
        print(f"w={w}, h={h}")
        w0 = w
        h0 = h
        scale = 1.0
        if crop_mode < 0:
            if( w > 320):
                clp_x = int((w - 320)//2)
                clp_w = 320
            else:
                clp_x = 0
                clp_w = w
            if( h > 320):
                clp_y = int((h - 320)//2)
                clp_h = 320
            else:
                clp_y = 0
                clp_h = h
            return (scale, (off_x, off_y), (clp_x, clp_y, clp_w, clp_h)) 
           
        for fact in (4, 2, 1):
            if w > WMAX * fact or h > HMAX * fact:
                fact = fact * 2
                w = w // fact
                h = h // fact
                scale = 1 / fact
                print(f"change w={w}, h={h}, scale={scale}")
                break
        clp_x = 0
        clp_y = 0
        clp_w = w0
        clp_h = h0


        divider = 3
        if crop_mode != 0:
            if crop_mode < 10:
                clp_x = w0 / divider * (crop_mode - 1)
                clp_w = w0 / divider
            else:
                clp_y = h0 / divider * (crop_mode//10 - 1)
                clp_h = h0 / divider
            clp_x = int(clp_x)
            clp_y = int(clp_y)
            clp_w = int(clp_w)
            clp_h = int(clp_h)
        print((clp_x, clp_y, clp_w, clp_h))
        clp_x, clp_y, clp_w, clp_h = cls.fix_crop(scale, (clp_x, clp_y, clp_w, clp_h), (w0, h0))
        off_x = clp_x
        off_y = clp_y
        print((clp_x, clp_y, clp_w, clp_h))
        return (scale, (off_x, off_y), (clp_x, clp_y, clp_w, clp_h))

        eps = 32
        if scale <= 0.125 :
            eps = 32
        if crop_mode == 1:
            off_x = 0
            clp_x = 0
#            clp_w = w0 / 4 - eps
            clp_w = w / 4 - eps
            print("width 1/4")

        if crop_mode == 2:
            off_x = w / 4
#            clp_x = w0 / 4
#            clp_w = w0 / 4 - eps
            clp_x = w / 4
            clp_w = w / 4 - eps
            print("width 2/4")
            
        if crop_mode == 3:
            off_x = w / 4 * 2
#            clp_x = w0 / 4 * 2
#            clp_w = w0 / 4 - eps
            clp_x = w / 4 * 2
            clp_w = w / 4 - eps
            print("width 3/4")

        if crop_mode == 4:
            off_x = w / 4 * 3
#            clp_x = w0 / 4 * 3
#            clp_w = w0 / 4 - eps
            clp_x = w / 4 * 3
            clp_w = w / 4 - eps
            print("width 4/4")
            

        if False : #scale == 0.25:
            if crop_mode == 10:
                off_y = 0
                clp_y = 0
                clp_h = h0 /4 - eps
                print("height 1/4")
            if crop_mode == 20:
                off_y = h / 4
                clp_y = h / 4
                clp_h = h0 / 2 - clp_y - eps #h + h / 2 - eps
                print("height 2/4")

            if crop_mode == 30:
                off_y = h / 4 * 2
                clp_y = h / 4 * 2
                clp_h = 3 * h0 / 4 - clp_y - eps # clp_y * 4 + h / 2 - eps
                
                print("height 3/4")

            if crop_mode == 40:
                off_y = h / 4 * 3
                clp_y = h / 4 * 3
                clp_h = h0 - clp_y -eps #clp_y * 4 + h / 2 - eps
                print("height 4/4")

            
        else:
            divider = 3

            if crop_mode == 10:
                off_y = 0
                clp_y = 0
                clp_h = h0 / divider - eps
                print(f"height 1/{divider}")
            if crop_mode == 20:
                off_y = h / divider
                clp_y = h / divider
                clp_h = 2 * h0 / divider - clp_y - eps #h + h / 2 - eps
                print("height 2/3")

            if crop_mode == 30:
                off_y = 2 * h / divider
                clp_y = 2 * h / divider
                clp_h = 3 * h0 / divider - clp_y - eps #h + h / 2 - eps
                print("height 3/3")

        off_x = int(off_x)
        off_y = int(off_y)
        clp_x = int(clp_x)
        clp_y = int(clp_y)
        clp_w = int(clp_w)
        clp_h = int(clp_h)
        
        return (scale, (off_x, off_y), (clp_x, clp_y, clp_w, clp_h))


    @classmethod
    def start_split(cls, fsize, buf):
        (scale, offset, clip) = cls.calcscale(buf)
        ioption = cls.get_option(scale)
        print(scale, offset, clip, ioption)
        # clip = None
        #offset = None
        jpginfo = PicoJpeg.decode_split(fsize, buf, offset, clip, ioption)
        return jpginfo[0]

    @classmethod
    def decode_split(cls, outfn, fi, fsize):
        rc = 0
        last = time.ticks_ms()
        t_read = 0
        t_decode = 0
        lap0 = time.ticks_ms()

        buf_idx = 0
        buf = cls.buffers[buf_idx]
        fi.readinto(buf)
        t_read += lap0 - time.ticks_ms()
        cls.decoder_running = True
        rc = cls.start_split(fsize, buf)

        newpos = -1
        lap0 = time.ticks_ms()
        while True:
            # Todo ここで先読みしておきたいが、必要になるまで通知が来ないので、先読みできない
            retc = PicoJpeg.decode_split_wait()
            if retc[0] == 0:  # running
                if retc[1] < 0:  # fpos is not set
                    continue
                newpos = retc[1]
                newsize = retc[2]
            else:  # Done
                break
            t_decode += lap0 - time.ticks_ms()
            lap0 = time.ticks_ms()
            buf = cls.buffers[buf_idx]
            fi.seek(newpos)
            fi.readinto(buf)
            #print(f"seek to {newpos},{newsize}, size={len(buf)}")
            t_read += lap0 - time.ticks_ms()
            lap0 = time.ticks_ms()
            jpginfo = PicoJpeg.decode_split_buffer(buf_idx, newpos, buf)
            # print(jpginfo)

        n_time = time.ticks_ms()
        dif = n_time - last
        print(f"time: read={t_read}, decode={t_decode}, total={dif}")
        cls.decoder_running = False
        return rc

    @classmethod
    def single_view(cls, outfn):
        print(outfn)
        if not outfn.endswith((".jpg", ".jpeg")):
            print("Bad file", outfn)
            return 0
        rc = 0
        try:
            with io.open(outfn, mode="rb") as fi:
                PicoJpeg.clear()

                fsize = fi.seek(0, 2)  # os.SEEK_END
                fi.seek(0, 0)  # os.SEEK_SET

                if fsize < cls.BUFFERSIZE * cls.BUFFERNUM:
                    rc = cls.decode_normal(outfn, fi)
                else:
                    rc = cls.decode_split(outfn, fi, fsize)
        except OSError as e:
            print(e, "file open error")
            return -1
        return rc

    @classmethod
    def start(cls):
        PicoJpeg.start(0)
        if cls.filebuffer is None:
            cls.filebuffer = bytearray(cls.BUFFERSIZE * cls.BUFFERNUM)
            mv = memoryview(cls.filebuffer)
            for i in range(cls.BUFFERNUM):
                cls.buffers[i] = mv[i * cls.BUFFERSIZE : (i + 1) * cls.BUFFERSIZE]

    @classmethod
    def end(cls):
        if cls.decoder_running:
            PicoJpeg.decode_core_wait(1)
            PicoJpeg.decode_core_wait(1)
            cls.decoder_running = False
        PicoJpeg.end()


class MyException(Exception):
    pass



def run():
    print("Enter main")
    screen.stopRefresh()

    global crop_mode
    
    JpegFunc.start() 
    for crop_mode in (-1,0): 
        #rc = JpegFunc.single_view("/sd/2560x2560.jpg")
        #rc = JpegFunc.single_view("/1280x1280.jpg")
        rc = JpegFunc.single_view("/640x640.jpg")
        #rc = JpegFunc.single_view("/gun320.jpg")
        get_keystring()
        while check_key() is False:
            time.sleep(1)
            
    JpegFunc.end()
    screen.recoverRefresh()


if __name__ == "__main__":
    run()
