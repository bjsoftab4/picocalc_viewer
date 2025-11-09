# Jpeg support functions

import io
import time

import picocalc
from picojpeg import PicoJpeg
from mp3 import DecodeMP3, Pcm
import sound
import utils

WMAX = 320
HMAX = 320

IDX_TIME = 1

class JpegFunc:
    debug = const(False)
    debug_time = const(False)
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
    buffers_pos = [-1] * BUFFERNUM
    buffers_len = [BUFFERSIZE] * BUFFERNUM
    
    @classmethod
    def test_buffer(cls, ipos, ilen):  # retc = buffer idx
        idx = -1
        freeidx = 0
        for i in range(cls.BUFFERNUM):
            bufpos = cls.buffers_pos[i]
            buflen = cls.buffers_len[i]
            if bufpos < 0:
                freeidx = freeidx | (1 << i)
                continue
            if bufpos <= ipos and ipos + ilen <= bufpos + buflen:
                idx = i
            if bufpos + buflen <= ipos:
                freeidx = freeidx | (1 << i)
        return idx, freeidx

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
    def fix_crop(cls, scale, crop, jpegsize):
        """
        in:  crop, jpegsize (in jpeg pixel)
        out: fixed crop value for JPEGDEC
        """
        jw, jh = jpegsize
        x, y, w, h = crop
        x1 = x + w
        y1 = y + h
        if x & 0xF != 0:
            x = (x & 0xFFF0) + 16
        if y & 0xF != 0:
            y = (y & 0xFFF0) + 16
        x1 = x1 & 0xFFF0
        y1 = y1 & 0xFFF0
        if y1 > jh - 32:  # to avoid buffer overrun
            y1 = jh - 32
        # if x1 > jw - 16:        # to avoid buffer overrun
        #   x1 = jw - 16
        w = x1 - x
        h = y1 - y
        cx = int(x * scale)  # cx,cw is in display pixel
        cw = int(w * scale)
        cy = int(y * scale)  # cy is in display pixel
        ch = int(y1 - cy)  # ch is ???
        return (cx, cy, cw, ch)

    @classmethod
    def get_scale(cls, w, h):
        """
        return scale, offset value for centering picture
        """
        scale = 1.0
        for fact in (4, 2, 1):
            if w > WMAX * fact or h > HMAX * fact:
                fact = fact * 2
                scale = 1 / fact
                break
        w = int(w * scale)
        h = int(h * scale)
        off_x = (WMAX - w) // 2
        off_y = (HMAX - h) // 2
        return (scale, (off_x, off_y))

    @classmethod
    def start_split(cls, fsize, buf):
        jpginfo = PicoJpeg.getinfo(buf)
        w = jpginfo[1]
        h = jpginfo[2]
        scale, offset = cls.get_scale(w, h)
        ioption = cls.get_option(scale)
        # print(scale, offset, crop, ioption)
        crop = None
        # offset = None
        jpginfo = PicoJpeg.decode_split(fsize, buf, offset, crop, ioption)
        return jpginfo[0]

    @classmethod
    def read_into_buf(cls, fi, buf):
        lap = time.ticks_ms()
        fi.readinto(buf)
        cls.time_read += time.ticks_ms() - lap

    @classmethod
    def decode_split(cls, outfn, fi, fsize):
        rc = 0
        last = time.ticks_ms()
        cls.time_read = 0
        t_decode = 0

        buf_idx = 0
        buf = cls.buffers[buf_idx]
        cls.buffers_pos[buf_idx] = 0
        cls.read_into_buf(fi, buf)
        cls.decoder_running = True
        rc = cls.start_split(fsize, buf)

        buf2 = cls.buffers[1]
        pos2 = cls.BUFFERSIZE
        cls.buffers_pos[1] = pos2
        fi.seek(pos2)
        cls.read_into_buf(fi, buf2)
        if cls.debug:
            print(f"preload seek to {pos2}, write buf{1}")
        jpginfo = PicoJpeg.decode_split_buffer(1, pos2, buf2)

        newpos = -1
        while True:
            lap0 = time.ticks_ms()
            while True:
                retc = PicoJpeg.decode_split_wait()
                if retc[0] == 0:  # running
                    if retc[1] < 0:  # fpos is not set
                        continue
                    newpos = retc[1]
                    newsize = retc[2]
                    idxinfo = retc[3]
                    break
                else:  # Done
                    print("retc:", retc)
                    break
            if retc[0] != 0:  # Done
                break
            if cls.debug:
                print(f"split_wait {newpos},{newsize} idxinfo={idxinfo}")
            t_decode += time.ticks_ms() - lap0

            idx, freeidx = cls.test_buffer(newpos, newsize)
            if cls.debug:
                print(f"readRAM {newpos},{newsize}  idx={idx},freebufbit={freeidx}")
            if freeidx != 0:
                for i in range(cls.BUFFERNUM):
                    if freeidx & (1 << i) != 0:
                        # print(f"fill buffer[{i}]")
                        buf2 = cls.buffers[i]
                        for j in range(cls.BUFFERNUM):  # scan all buffer
                            if newpos < cls.buffers_pos[j] + cls.BUFFERSIZE:
                                newpos = (
                                    cls.buffers_pos[j] + cls.BUFFERSIZE
                                )  # newpos is largest addr
                        pos2 = newpos
                        cls.buffers_pos[i] = pos2
                        fi.seek(pos2)
                        cls.read_into_buf(fi, buf2)
                        if cls.debug:
                            print(f"preload seek to {pos2}")
                        jpginfo = PicoJpeg.decode_split_buffer(i, pos2, buf2)
                continue

            if idx != -1:  # requested buffer is not empty
                # print("using buf", idx)
                continue
            else:  # all buffers are empty
                buf_idx = 0
            buf = cls.buffers[buf_idx]
            cls.buffers_pos[buf_idx] = newpos
            fi.seek(newpos)
            cls.read_into_buf(fi, buf)
            if cls.debug:
                print(f"seek to {newpos},{newsize}, size={len(buf)}")
            jpginfo = PicoJpeg.decode_split_buffer(buf_idx, newpos, buf)
            if cls.debug:
                print(jpginfo)

            buf_idx += 1
            if buf_idx >= cls.BUFFERNUM:
                buf_idx = 0
            buf = cls.buffers[buf_idx]
            newpos += cls.BUFFERSIZE
            cls.buffers_pos[buf_idx] = newpos
            fi.seek(newpos)
            cls.read_into_buf(fi, buf)
            if cls.debug:
                print(f"preload seek to {newpos},{newsize}, size={len(buf)}")
            jpginfo = PicoJpeg.decode_split_buffer(buf_idx, newpos, buf)

        n_time = time.ticks_ms()
        dif = n_time - last
        if cls.debug:
            print(f"time: read={cls.time_read}, decode={t_decode}, total={dif}")
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
                cls.buffers[i] = mv[i * cls.BUFFERSIZE:(i + 1) * cls.BUFFERSIZE]

    @classmethod
    def end(cls):
        if cls.decoder_running:
            PicoJpeg.decode_core_wait(1)
            PicoJpeg.decode_core_wait(1)
            cls.decoder_running = False
        PicoJpeg.end()

    @classmethod
    def decode(cls, buf, offset=None, crop=None, scale=1):
        if offset is None:
            offset = (0, 0)
        if crop is None:
            ox = offset[0]
            oy = offset[1]
            crop = (ox, oy, WMAX - ox, HMAX - oy)
        ioption = cls.get_option(scale)

        jpginfo = PicoJpeg.decode_opt(buf, offset, crop, ioption)
        return jpginfo

    @classmethod
    def flipdrawpage(cls):
        if cls.drawpage == 1:
            cls.drawpage = 2
        else:
            cls.drawpage = 1

    @classmethod
    def showjpeg(cls, buf, center=False):
        if cls.decoder_running:
            jpginfo = PicoJpeg.decode_core_wait()
            if jpginfo[0] == 0 and jpginfo[1] != 0:
                print(f"decode error {jpginfo}")
        cls.buf_save = buf  # To exclude gc while docoder running
        cls.decoder_running = True

        jpginfo = PicoJpeg.getinfo(buf)
        w = jpginfo[1]
        h = jpginfo[2]
        offset = None
        if h > 240:
            if center:
                offset = ((WMAX - w) // 2, (HMAX - h) // 2)
            jpginfo = PicoJpeg.decode_core(cls.buf_save, 0, 1, offset)  # single page
        else:
            if center:
                offset = ((WMAX - w) // 2, (240 - h) // 2)
            jpginfo = PicoJpeg.decode_core(
                cls.buf_save, cls.drawpage, 1, offset
            )  # flip page

        cls.flipdrawpage()
        return jpginfo

    @classmethod
    def play_movie2(cls, outfn, fps):
        print(outfn)
        if not outfn.endswith(".tar"):
            if outfn.endswith((".jpg", ".jpeg")):
                rc = cls.play_picture(outfn, fps)
                return rc
            return -1

        try:
            fi = io.open(outfn, mode="rb")
        except (FileNotFoundError, PermissionError, IOError, ValueError):
            return -1
        rc = cls.play_tar(fi, None, fps)
        fi.close()
        return rc
    @classmethod
    def play_movie(cls, outfn, fps):
        print(outfn)
        if not outfn.endswith(".tar"):
            if outfn.endswith((".jpg", ".jpeg")):
                rc = cls.play_picture(outfn, fps)
                return rc
            return -1

        try:
            fi = io.open(outfn, mode="rb")
        except (FileNotFoundError, PermissionError, IOError, ValueError):
            return -1
        rc = cls.extract_tar(fi, fps)
        fi.close()
        return rc


    @classmethod
    def play_movie3(cls, outfn, mp3fn = None):
        print(outfn)
        if not outfn.endswith('.tar'):
            return -1
        
        try:
            fi = io.open(outfn, mode='rb')
        except :
            return -1
        
        if mp3fn != None:
            try:
                mp3fi = io.open(mp3fn, mode='rb')
            except :
                return -1
        else:
            mp3fi = None
        rc = cls.play_tar(fi, mp3fi)
        fi.close()
        return rc
    

    @classmethod
    def fillPcmbuff(cls):
        rc = 0
        if not DecodeMP3.mp3file_find_sync_word():
            rc = -1
        if Pcm.get_freebuf() > len(DecodeMP3.pcmbuf) // 4 // 2:
            rc = DecodeMP3.part_decode()
            if rc == 1: # new mp3 file
                return 2
            if rc < 0:
                return -1
            rc = DecodeMP3.fillfilebuffer()
            if rc < 0:
                return -1
            return 1
        return 0

    @classmethod
    def extract_tar(cls, fi, fps):
        global keyb
        PicoJpeg.clear()
        waitms = int(1000 / fps)
        rc = 0
        headbuf = bytearray(512)
        for i in range(3600):
            last = time.ticks_ms()
            rd = fi.readinto(headbuf)  # read tar header
            if rd != 512:
                rc = 0
                break
            fn = headbuf[0:100].rstrip(b"\0").decode()
            if len(fn) == 0:
                rc = 0
                break  # EOF
            sz = int(headbuf[0x7C:0x87].decode(), 8)
            if (sz % 512) != 0:
                sz += 512 - sz % 512

            if fn.endswith((".jpg", ".jpeg")) is False:
                fi.seek(sz, 1)  # Do not read, skip
                continue
            buf = fi.read(sz)
            if len(buf) != sz:
                rc = 0
                break  # EOF or bad data

            if utils.checkKey():
                break
            lap1 = time.ticks_ms()
            rc = cls.showjpeg(buf, True)
            rc = rc[0]

            n_time = time.ticks_ms()
            dif = n_time - last
            if cls.debug_time:
                print(f"time: read={lap1-last}, decode={n_time - lap1}, total={dif}")
            if dif < waitms:
                time.sleep_ms(waitms - dif)
            if rc < 0:
                break
        time.sleep_ms(500)
        if cls.decoder_running:
            jpginfo = PicoJpeg.decode_core_wait()
            cls.decoder_running = False
        return rc

    @classmethod
    def play_tar(cls, fp_tar, fp_mp3 = None, argfps = 12):
        sec = 0
        ret = utils.analyze_tar(fp_tar)
        if ret is None:
            fps = argfps
            jpgtoc = None
            idxpos = None
            mp3pos = 0
            jpgpos = 0
        else:
            fps, jpgtoc, idxpos, mp3pos, jpgpos = ret
            if fps is None:
                fps = argfps
            #print(ret)
        tar_info = (fps, jpgtoc, idxpos, mp3pos, jpgpos)
        PicoJpeg.clear()
        if fp_mp3 is not None:
            if mp3pos != None:
                DecodeMP3.prolog(fp_mp3, mp3pos + 512, jpgpos - mp3pos - 512)     #tar
                rc = DecodeMP3.skip_id3v2()
                if rc < 0:
                    return None
                if not DecodeMP3.mp3file_find_sync_word():
                    return None
                rc = DecodeMP3.fillfilebuffer()
                if rc < 0:
                    return None
                rc = DecodeMP3.look_for_1stframe()
                rc = DecodeMP3.getframeinfo(DecodeMP3.decoder, DecodeMP3.frameinfo)
                if rc < 0:
                    return None
                # utils.hexdump(DecodeMP3.frameinfo, "frameinfo")
            else:
                fp_mp3 = None

        rc = 0
        while True:
            retc = cls.play_tar_from(fp_tar, fp_mp3, sec, tar_info)
            if retc is None:
                break
            print(retc)
            rc, sec = retc
            if rc == 1: # seek forward
                continue
            if rc == 2: # next movie
                break
            if rc == 3: # previous movie
                break
            if rc == 9: # quit
                break
        if fp_mp3 is not None:            
            DecodeMP3.epilogue()
            print("MP3 epilogue")
        if cls.decoder_running:
            jpginfo = PicoJpeg.decode_core_wait()
            cls.decoder_running = False
        return rc


    @classmethod
    def play_tar_from(cls, fp_tar, fp_mp3, startsec, tar_info):
        print("Start play tar from", startsec, "sec")
        fps, jpgtoc, idxpos, mp3pos, jpgpos = tar_info

        def mainloop(startmin):
            startsec = startmin * 60
            rc = 0
            headbuf = bytearray(512)
            
            sleeptotal = 0
            skipcount=0
            readtime_us = 0
            mp3time_us = 0
            
            # preload
            jpgload_req = True
            frame_number = startmin * 60 * fps
            mp3play_req = False
            frame_start = frame_number
            t_start = time.ticks_ms()
            while True:
                last = time.ticks_ms()
                start_us = time.ticks_us()
                
                if utils.checkKey():  # 早送りなどの検出
                    rc = 0
                    sec = int(frame_number / fps)
                    st = utils.getKeystring()
                    if ' ' in st:
                        if jpgtoc != None:
                            sec += 60  
                            DecodeMP3.pause()
                            return (1,sec)
                    if 'N' in st:
                        DecodeMP3.pause()
                        retc = 4
                        break
                    if 'P' in st:
                        DecodeMP3.pause()
                        retc = 5
                        break
                    if 'n' in st:
                        DecodeMP3.pause()
                        return (2,0)
                    if 'p' in st:
                        DecodeMP3.pause()
                        return (3,0)
                    if 'q' in st:
                        DecodeMP3.pause()
                        return (9,0)
                    utils.waitKeyOff()
                    continue

                if jpgload_req:
                    if startmin >= 0:
                        if jpgtoc != None:
                            if startmin >= len(jpgtoc) - 1:
                                break
                            fp_tar.seek(jpgpos + jpgtoc[startmin], 0)
                        else:
                            fp_tar.seek(0, 0)
                        #print("fptar seek jpgpos", jpgpos, "startmin", startmin, "jpgtoc[startmin]", jpgtoc[startmin])
                        startmin = -1
                    retc = utils.read_tar_header(fp_tar, headbuf)
                    if retc is None:
                        utils.hexdump(headbuf, "headbuf")
                        return None
                    fn, sz, sz0 = retc
                    if fn.endswith((".jpg",".jpeg")) is False:
                        fp_tar.seek(sz, 1)  # Do not read, skip
                        continue
                    buf = fp_tar.read(sz)

                    rd = len(buf)
                    if rd != sz:
                        rc = 0
                        print("bad file size, or EOF")
                        break  # EOF or bad data
                    lap = time.ticks_diff(time.ticks_us(), start_us)
                    if lap > 100_000:
                        print("Too slow to read")
                    readtime_us += lap
                    jpgload_req = False

                
                #初回JPEGデコード
                if not mp3play_req:
                    # show 1st frame
                    rc = cls.showjpeg(buf, True)
                    #print (rc)
                    mp3play_req = True
                    jpgload_req = True
                    frame_number += 1
                    continue
                    
                #PCM再生
                rc = 0
                mp3start_us = time.ticks_us()
                if fp_mp3 is not None:
                    while mp3play_req:
                        rc = cls.fillPcmbuff()
                        if rc == 2:     # start PCM
                            continue
                        if rc == 1:     # add PCM data
                            continue
                        break           # error or PCM buffer full
                mp3time_us += time.ticks_diff(time.ticks_us(), mp3start_us)
                if rc < 0:
                    break

                #タイミング調整
                if fp_mp3 is not None:
                    targettime_ms = int(DecodeMP3.getplaytime()  * 1000) - 80
                else:
                    targettime_ms = time.ticks_diff(time.ticks_ms(), t_start)
                margin = time.ticks_diff(1000 * (frame_number - frame_start) // fps, targettime_ms)
                if margin > 20:
                    time.sleep_ms(10)
                    sleeptotal += 10
                    continue

                if margin > 0:
                    time.sleep_ms(margin)
                    sleeptotal += margin
                else:
                    pass
                
                if fp_mp3 is not None:
                    mp3start_us = time.ticks_us()
                    if startsec >= 0:
                        if DecodeMP3.mp3seek(startsec, False) < 0:
                            break
                        startsec = -1
                    mp3time_us += time.ticks_diff(time.ticks_us(), mp3start_us)

                if margin > -50:
                    rc = cls.showjpeg(buf, True)
                    #print (rc)
                    mp3play_req = True
                else:
                    skipcount += 1
                    if skipcount < 10:
                        print("skip", skipcount)
                jpgload_req = True
                frame_number += 1
        retc = mainloop(startsec // 60)
        return retc
        #print(f"frames={framecount}, skip={skipcount}, sleep={sleeptotal}, total={i * waitms}, busy={100-int(100*sleeptotal/(i * waitms))}")
        #print(f"readtime={readtime_us / 1000_000}sec, mp3time={mp3time_us / 1000_000}sec")
        #time.sleep_ms(500)


    @classmethod
    def pictview(cls, outfn, fps):
        rc = cls.play_movie(outfn, fps)
        return rc
 