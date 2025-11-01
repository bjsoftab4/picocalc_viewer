from struct import *
import os
import time

import sound
import picocalc
from picojpeg import PicoJpeg
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

MAX_NGRAN = 2
MAX_NCHAN = 2
MAX_NSAMP = 576
MAX_BUFFER_LEN=(MAX_NSAMP * MAX_NGRAN * MAX_NCHAN)
ERR_MP3_NONE = 0
class Pcm:
    @classmethod
    def init(cls):
        sound.pcm_init()
    
    @classmethod
    def deinit(cls):
        sound.pcm_deinit()
    
    @classmethod
    def setbuffer(cls,addr):
        sound.pcm_setbuffer(addr)
    
    @classmethod
    def setfreq(cls,f):
        sound.pcm_setfreq(f)
    
    @classmethod
    def start(cls):
        sound.pcm_start()
    
    @classmethod
    def stop(cls):
        sound.pcm_stop()
        
    @classmethod
    def get_freebuf(cls):
        return sound.pcm_get_freebuf()
    
    @classmethod
    def push(cls,addr,mode):
        return sound.pcm_push(addr,mode)   
    
    
class DecodeMP3:
    MIN_FILE_BUF_SIZE = 1044
    pcmbuf = memoryview(bytearray(MAX_BUFFER_LEN * 2 * 10))
    pcmlen = len(pcmbuf)//4
    
    filedata1 = bytearray(2048)
    filedata2 = bytearray(2048)

    stream = memoryview(filedata1)
    stream2 = memoryview(filedata2)
    stream_ptr = 0
    stream_end = 0
    fill_flag = False
    fileremain = 0

    @classmethod
    def BYTES_LEFT(cls):
        return cls.stream_end - cls.stream_ptr
        
    @classmethod
    def READ_PTR(cls):
        return cls.stream_ptr

    @classmethod
    def CONSUME(cls, n):
        cls.stream_ptr += n

    @classmethod
    def skip_id3v2(cls, fi=None):
        if cls.BYTES_LEFT() < 10:
            return 0

        data = cls.stream[cls.READ_PTR():]
        if not ( data[0] == 0x49 and
            data[1] == 0x44 and
            data[2] == 0x33 and
            data[3] != 0xff and
            data[4] != 0xff and
            (data[5] & 0x1f) == 0 and
            (data[6] & 0x80) == 0 and
            (data[7] & 0x80) == 0 and
            (data[8] & 0x80) == 0 and
            (data[9] & 0x80) == 0):
                #print(f"NO id3v2")
                return 0
        
        size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | (data[9])
        size += 10 # size excludes the "header" (but not the "extended header")
        cls.CONSUME(size)
        print(f"skip_id3v2:{size}bytes")

        if fi is not None:
            if cls.BYTES_LEFT() < 0:
                left = -cls.BYTES_LEFT()
                print("skip_id3v2 overrun", left)
                left -= len(cls.stream)
                rc = fi.seek(left, 1)
                cls.fileremain -= left
                rc = cls.fillfilebuffer(fi, True)
                if rc < 0:
                    print("skip id EOF")
                    return -1
        return 0
    
    @classmethod
    def swapstream(cls):
        cls.fill_flag = True
        wk = cls.stream
        cls.stream = cls.stream2
        cls.stream2 = wk
        cls.stream_ptr = 0
        cls.stream_end = len(cls.stream)
        
    @classmethod
    def mp3file_find_sync_word(cls):
        inbuf = cls.stream[cls.READ_PTR():]
        inbuf2 = cls.stream2
        for i in range(len(inbuf)):
            if inbuf[i] == 0xff:
                if i + 1 < len(inbuf):
                    if inbuf[i+1] & 0xe0 == 0xe0:
                        cls.CONSUME(i)
                        #print("findsyncword1:",i)
                        return True
                else:
                    if inbuf2[0] & 0xe0 == 0xe0:
                        cls.CONSUME(i)
                        #print("findsyncword2:",i)
                        return True
        cls.swapstream()
        inbuf = cls.stream
        for i in range(len(inbuf) - 1):
            if inbuf[i] == 0xff:
                if i + 1 < len(inbuf):
                    if inbuf[i+1] & 0xe0 == 0xe0:
                        cls.CONSUME(i)
                        #print("findsyncword3:",i)
                        return True
        return False
                
        offset = sound.mp3findsyncword(cls.stream[cls.READ_PTR():], cls.BYTES_LEFT())
        if offset >= 0:
            cls.CONSUME(offset)
            return True
        print(offset)
        cls.hexdump(cls.stream[cls.READ_PTR():], title="mp3file_find_sync_word")
        return False
    """
    typedef struct _MP3FrameInfo {
        int bitrate;
        int nChans;
        int samprate;
        int bitsPerSample;
        int outputSamps;
        int layer;
        int version;
    } MP3FrameInfo;
    """
    @classmethod
    def print_frameinfo(cls, frameinfo):
        #print(frameinfo)
        rc = unpack("<LLLLLLL", frameinfo)
        #print(rc)
        bitrate, nchans, samprate, bitspersample, outputsamps, layer, version = rc
        
        #bitrate, nchans, samprate, bitspersample, outputsamps, layer, version = unpack_from("<i", frameinfo)
        print(f"bitrate={bitrate}, nchans={nchans},samprate={samprate},bitspersample={bitspersample},outputsamps={outputsamps},layer={layer},version={version}")

    @classmethod
    def hexdump(cls, buf, title=""):
        print(title)
        for i in range(32):
            print(buf[i],end=" ")
        print("")
        
    @classmethod
    def fillfilebuffer(cls, fi, fillall = False):
        rc = 0
        if fillall:
            rc = fi.readinto(cls.stream)
            if rc <= 0:		# EOF
                return -1
            cls.fileremain -= rc
            cls.stream_ptr = 0
            cls.stream_end = len(cls.stream)
            cls.fill_flag = True
            
        if cls.fill_flag:
            rc = fi.readinto(cls.stream2)
            if rc <= 0:		# EOF
                return -1
            cls.fileremain -= rc
            cls.fill_flag = False
        return rc


    @classmethod
    def mp3decode(cls, decoder, audiobuf):
        inbuf = cls.stream[cls.READ_PTR():]
        bytes_left = cls.BYTES_LEFT()
        bytes_add = cls.MIN_FILE_BUF_SIZE - bytes_left
       # print("Enter decode bytes_left=", bytes_left, end="")
        
        if bytes_add > 0:
            #print(" add data", bytes_add, end="")
            cls.stream[0:bytes_left] = cls.stream[cls.stream_ptr:cls.stream_end]
            cls.stream[bytes_left:bytes_left+bytes_add] = cls.stream2[0:bytes_add]
            inbuf = cls.stream[0:cls.MIN_FILE_BUF_SIZE]
            rc = sound.mp3decode(decoder, inbuf, len(inbuf), audiobuf, 0)
            if rc <= bytes_left:
                cls.CONSUME(rc)
            else:
                cls.swapstream()
                cls.CONSUME(rc - bytes_left)
                
        else:
            rc = sound.mp3decode(decoder, inbuf, len(inbuf), audiobuf, 0)
            cls.CONSUME(rc)
        #print(" - Leave decode result=", rc)
        return rc


    @classmethod
    def getframeinfo(cls, decoder, frameinfo):
        inbuf = cls.stream[cls.READ_PTR():]
        bytes_left = cls.BYTES_LEFT()
        bytes_add = 6 - bytes_left
        #print("Enter getframeinfo", end="")
        if bytes_add > 0:
            #print("getframeinfo add data", bytes_add) #, end="")
            cls.stream[0:bytes_left] = cls.stream[cls.stream_ptr:cls.stream_end]
            cls.stream[bytes_left:bytes_left+bytes_add] = cls.stream2[0:bytes_add]
            inbuf = cls.stream[0:6]
            err = sound.mp3getnextframeinfo(decoder, frameinfo, inbuf)
        else:
            err = sound.mp3getnextframeinfo(decoder, frameinfo, inbuf)
        if err < 0:
            print(" - Leave  err=", err)
        return err


    @classmethod
    def main(cls, infile):
        sr0 = 0
        br0 = 0
        cls.MIN_FILE_BUF_SIZE = int(144 * 320_000 / 44_100) + 6

        decoder = sound.mp3initdecoder()
        fi = open(infile, "rb")
        fsize = fi.seek(0, 2)  # os.SEEK_END
        fi.seek(0, 0)  # os.SEEK_SET
        cls.fileremain = fsize

        cls.stream_end = 0
        cls.stream_ptr = 0

        rc = cls.fillfilebuffer(fi, True)

        frameinfo = memoryview(bytearray(32))
        audiobuf = memoryview(bytearray(MAX_BUFFER_LEN * 2))

        Pcm.setbuffer(memoryview(cls.pcmbuf))
        Pcm.setfreq(44100)
        Pcm.start()
        pcmbufx = memoryview(bytearray(MAX_BUFFER_LEN * 2 * 2))
        wait_us = 0
        t_start = time.ticks_ms()
        progress = int(50 * cls.fileremain / fsize)
        bar = "|"
        bar += " " * 48
        bar += "|"
        
        rc = cls.skip_id3v2(fi)
        if rc < 0:
            print("EOF")
            return
        while cls.mp3file_find_sync_word():
            if checkKey():
                Pcm.stop()
                break
            rc = cls.skip_id3v2(fi)
            if rc < 0:
                print("EOF")
                break
            #err = sound.mp3getnextframeinfo(decoder, frameinfo, cls.stream[cls.READ_PTR():]);
            err = cls.getframeinfo(decoder, frameinfo)
            if err != ERR_MP3_NONE:  #バッファが4バイト未満の時もエラーになる
                cls.hexdump(cls.stream[cls.READ_PTR():], "frameinfo")
                print("MP3GetNextFrameInfo rc=", err)
                break
            if err == ERR_MP3_NONE:
                rc = unpack("<LLLLLLL", frameinfo)
                bitrate, nchans, samprate, bitspersample, outputsamps, layer, version = rc
                if br0 != bitrate:
                    br0 = bitrate
                    cls.MIN_FILE_BUF_SIZE = int(144 * bitrate / samprate) + 6
                if sr0 != samprate:
                    sr0 = samprate
                    cls.MIN_FILE_BUF_SIZE = int(144 * bitrate / samprate) + 6
                    #print(cls.MIN_FILE_BUF_SIZE)
                    cls.print_frameinfo(frameinfo)
                    Pcm.stop()
                    Pcm.setfreq(samprate)
                    Pcm.start()
                    print(bar,end="\r")
                    
            bytes_left = cls.BYTES_LEFT()
            inbuf = cls.stream[cls.READ_PTR():]
                
            #rc = sound.mp3decode(decoder, inbuf, bytes_left, audiobuf, 0)
            rc = cls.mp3decode(decoder, audiobuf)
            if rc < 0:
                print("mp3decode rc=",rc)
                break
            #print(cls.pcmflag, sound.dma_getcount(), outputsamps)
            lap0 = time.ticks_us()
            while Pcm.get_freebuf() <= outputsamps * 4:
                # print(Pcm.get_freebuf())
                pass
            wait_us += time.ticks_diff(time.ticks_us(), lap0)

            left = Pcm.push(audiobuf[0:outputsamps * 2], nchans)
            if( left != 0):
                print("left=",left)

            rc = cls.fillfilebuffer(fi)
            if rc < 0:
               print("EOF")
               break
    
            #rc = sound.mp3decode(decoder, inbuf, bytes_left, audiodata, 0);
            #print(rc)
            p1 = int(50 * cls.fileremain / fsize)
            if p1 != progress:
                progress = p1
                print("x",end="")
        print("")
        total_ms = time.ticks_ms() - t_start
        print(f"wait_ms={int(wait_us/1000)}, total_ms={total_ms}, CPU LOAD={int(wait_us/10/total_ms)}%")
        
sr0 = 11000
keyb = picocalc.keyboard
while checkKey():
    st = getKeystring()
    time.sleep_ms(100)
Pcm.init()
fdir = "/sd/mp3-0"
#fdir = "/"
flist = os.listdir(fdir)
flist.sort()
print(flist)
try:
    i = 0
    while i < len(flist):
        fn = flist[i]
        if fn.endswith((".mp3",".MP3")):
           print(fdir +"/" + fn)
           DecodeMP3.main(fdir +"/" + fn)
        if checkKey():
            st = getKeystring()
            if 'q' in st:
                rc = -1
                break
            if 'p' in st:
                i = i - 1
                if( i < 0):
                    i = 0
                continue
        time.sleep_ms(100)
        while checkKey():
            st = getKeystring()
        i+=1
finally:
    print("close")
    Pcm.deinit()
    os.listdir("/")
    