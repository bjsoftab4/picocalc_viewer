from struct import *
import os
import time

import sound
import picocalc
from picojpeg import PicoJpeg

keyb = picocalc.keyboard
def waitKeyOff():
    time.sleep_ms(100)
    while checkKey():
        st = getKeystring()
        time.sleep_ms(200)

def checkKey():
    kc = keyb.keyCount()
    if kc == 0:
        return False
    return True

def getKeystring():
    kc = keyb.keyCount()
    if kc == 0:
        return ""
    buf = bytearray(kc+1)
    keyb.readinto(buf)
    st = buf.rstrip(b"\0").decode()
    return st

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
    MAX_SAMPLE_SIZE=(576 * 2 * 2)    # max dataset of mp3frame
    ERR_MP3_NONE = 0
    MIN_FILE_BUF_SIZE = 1044
    frameinfo = memoryview(bytearray(32))
    decodedbuf = memoryview(bytearray(MAX_SAMPLE_SIZE * 2))

    pcmbuf = memoryview(bytearray(MAX_SAMPLE_SIZE * 2 * 10)) 
    
    filedata1 = bytearray(2048)
    filedata2 = bytearray(2048)

    stream = memoryview(filedata1)
    stream2 = memoryview(filedata2)
    stream_ptr = 0
    stream_end = 0
    fill_flag = False
    fileremain = 0
    sr0 = 0
    br0 = 0
    
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
    def skip_id3v2(cls):
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
        #print(f"skip_id3v2:{size}bytes")

        if cls.fi is not None:
            if cls.BYTES_LEFT() < 0:
                left = -cls.BYTES_LEFT()
                #print("skip_id3v2 overrun", left)
                left -= len(cls.stream)
                rc = cls.fi.seek(left, 1)
                cls.fileremain -= left
                rc = cls.fillfilebuffer(True)
                if rc < 0:
                    #print("skip id EOF")
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
    @staticmethod
    def print_frameinfo(frameinfo):
        #print(frameinfo)
        rc = unpack("<LLLLLLL", frameinfo)
        #print(rc)
        bitrate, nchans, samprate, bitspersample, outputsamps, layer, version = rc
        
        #bitrate, nchans, samprate, bitspersample, outputsamps, layer, version = unpack_from("<i", frameinfo)
        print(f"bitrate={bitrate}, nchans={nchans},samprate={samprate},bitspersample={bitspersample},outputsamps={outputsamps},layer={layer},version={version}")

    @staticmethod
    def hexdump(buf, title=""):
        print(title)
        for i in range(32):
            print(buf[i],end=" ")
        print("")
        
    @classmethod
    def fillfilebuffer(cls, fillall = False):
        rc = 0
        if fillall:
            rc = cls.fi.readinto(cls.stream)
            if rc <= 0:		# EOF
                return -1
            cls.fileremain -= rc
            cls.stream_ptr = 0
            cls.stream_end = len(cls.stream)
            cls.fill_flag = True
            
        if cls.fill_flag:
            rc = cls.fi.readinto(cls.stream2)
            if rc <= 0:		# EOF
                return -1
            cls.fileremain -= rc
            cls.fill_flag = False
        return rc


    @classmethod
    def mp3decode(cls, decoder, decodedbuf):
        inbuf = cls.stream[cls.READ_PTR():]
        bytes_left = cls.BYTES_LEFT()
        bytes_add = cls.MIN_FILE_BUF_SIZE - bytes_left
       # print("Enter decode bytes_left=", bytes_left, end="")
        
        if bytes_add > 0:
            #print(" add data", bytes_add, end="")
            cls.stream[0:bytes_left] = cls.stream[cls.stream_ptr:cls.stream_end]
            cls.stream[bytes_left:bytes_left+bytes_add] = cls.stream2[0:bytes_add]
            inbuf = cls.stream[0:cls.MIN_FILE_BUF_SIZE]
            rc = sound.mp3decode(decoder, inbuf, len(inbuf), decodedbuf, 0)
            if rc <= bytes_left:
                cls.CONSUME(rc)
            else:
                cls.swapstream()
                cls.CONSUME(rc - bytes_left)
                
        else:
            rc = sound.mp3decode(decoder, inbuf, len(inbuf), decodedbuf, 0)
            cls.CONSUME(rc)
        #print(" - Leave decode result=", rc)
        return rc


    @classmethod
    def getframeinfo(cls, decoder, frameinfo):
        inbuf = cls.stream[cls.READ_PTR():]
        bytes_left = cls.BYTES_LEFT()
        bytes_add = 6 - bytes_left  # mpeg frame info is 4 or 6 byte (with CRC)
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
    def set_minfilebufsize(cls, bitrate, samprate):
        cls.MIN_FILE_BUF_SIZE = int(144 * bitrate / samprate) + 6   # 6 for next header
        return
        
    @classmethod
    def part_decode(cls):
        rc = cls.skip_id3v2()
        if rc < 0:
            print("EOF")
            return -1
        rc = cls.getframeinfo(cls.decoder, cls.frameinfo)
        if rc < 0:
            cls.hexdump(cls.stream[cls.READ_PTR():], "frameinfo")
            print("MP3GetNextFrameInfo rc=", err)
            return -1
        rc = unpack("<LLLLLLL", cls.frameinfo)
        bitrate, nchans, samprate, bitspersample, outputsamps, layer, version = rc
        if cls.br0 != bitrate:
            cls.br0 = bitrate
            cls.set_minfilebufsize(bitrate, samprate)
        if cls.sr0 != samprate:
            cls.sr0 = samprate
            cls.set_minfilebufsize(bitrate, samprate)
            #print(cls.MIN_FILE_BUF_SIZE)
            cls.print_frameinfo(cls.frameinfo)
            Pcm.stop()
            Pcm.setfreq(samprate)
            Pcm.start()
            return 1
            
        rc = cls.mp3decode(cls.decoder, cls.decodedbuf)
        if rc < 0:
            print("mp3decode rc=",rc)
            return -1
        left = Pcm.push(cls.decodedbuf[0:outputsamps * 2], nchans)
        return 0

    @classmethod
    def part_fileread():
        rc = cls.fillfilebuffer()
        if rc < 0:
           print("EOF")
           return -1
        return 0
    


    @classmethod
    def mainloop(cls, infile):
        cls.sr0 = 0
        cls.br0 = 0
        cls.set_minfilebufsize(320_000, 44_100)
        cls.decoder = sound.mp3initdecoder()
        cls.fi = open(infile, "rb")
        fsize = cls.fi.seek(0, 2)  # os.SEEK_END
        cls.fileremain = fsize
        cls.fi.seek(0, 0)  # os.SEEK_SET
        rc = cls.fillfilebuffer(True)

        Pcm.setbuffer(memoryview(cls.pcmbuf))
        Pcm.setfreq(44100)
        Pcm.start()

        wait_us = 0
        t_start = time.ticks_ms()
        progress = int(50 * cls.fileremain / fsize)
        bar = "-" * 50
        
        rc = cls.skip_id3v2()
        if rc < 0:
            return
        
        while cls.mp3file_find_sync_word():
            if checkKey():
                break

            lap0 = time.ticks_us()
            while Pcm.get_freebuf() <= len(cls.pcmbuf) // 4 // 2:	# get_freebuf returns sample counts
                #print(Pcm.get_freebuf())
                pass
            wait_us += time.ticks_diff(time.ticks_us(), lap0)

            rc = cls.part_decode()
            if rc == 1:
                print(bar,end="\r")
                continue
            if rc < 0:
                break

            rc = cls.fillfilebuffer()
            if rc < 0:
               break

            p1 = int(50 * cls.fileremain / fsize)
            if p1 != progress:
                progress = p1
                print("+",end="")
        Pcm.stop()
        print("")
        total_ms = time.ticks_ms() - t_start
        #print(f"wait_ms={int(wait_us/1000)}, total_ms={total_ms}, CPU LOAD={100-int(wait_us/10/total_ms)}%")

def isdir(dname):
    st = os.stat(dname)
    if st[6] == 0:
        return True
    return False

def dirplay(dname):
    flist = os.listdir(dname)
    flist.sort()
    print("Scan directory:"+dname)
    dirlist = [
        f for f in flist if isdir(dname+"/"+f)
    ]
    for d in dirlist:
        rc = dirplay(dname + "/" + d)
        if rc < 0 :
            return -1
    filelist = [
        f for f in flist if not isdir(dname+"/"+f) and f.endswith((".mp3",".MP3"))
    ]
    print("File list:", filelist)
    i = 0
    while i < len(filelist):
        waitKeyOff()

        fn = dname + "/" + filelist[i]
        
        if fn.endswith((".mp3",".MP3")):
           print(fn)
           DecodeMP3.mainloop(fn)
        if checkKey():
            st = getKeystring()
            if 'q' in st:
                rc = -1
                return -1
            if 'n' in st:
                break
            if 'p' in st:
                i = i - 1
                if( i < 0):
                    i = 0
                continue
        i+=1
    return 0
           
def run(fdir = "/sd"):
    Pcm.init()
    try:
        dirplay(fdir)
    finally:
        print("close")
        Pcm.deinit()
        os.listdir("/")

