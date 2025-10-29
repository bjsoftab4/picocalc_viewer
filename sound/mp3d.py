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

class DecodeMP3:
    audiodata1 = bytearray(MAX_BUFFER_LEN * 2 )
    audiodata2 = bytearray(MAX_BUFFER_LEN * 2 )
    audiodata = memoryview(audiodata1)
    audioflag = 1
    audiopos = 0
    pcmbuf = memoryview(bytearray(MAX_BUFFER_LEN * 2 * 20))
    pcmdata1 = memoryview(pcmbuf[0:len(pcmbuf)//2])
    pcmdata2 = memoryview(pcmbuf[len(pcmbuf)//2:len(pcmbuf)])
    pcmdata = memoryview(pcmdata1)
    pcmflag = 1
    pcmpos = 0
    pcmlen = len(pcmbuf)//4
    
    filedata1 = bytearray(4096)
    filedata2 = bytearray(4096)

    stream = memoryview(filedata1)
    stream_ptr = 0
    stream_end = 0
    stream_flag = 1

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
            return

        data = cls.stream[cls.READ_PTR():]
        if not ( data[0] == 'I' and
            data[1] == 'D' and
            data[2] == '3' and
            data[3] != 0xff and
            data[4] != 0xff and
            (data[5] & 0x1f) == 0 and
            (data[6] & 0x80) == 0 and
            (data[7] & 0x80) == 0 and
            (data[8] & 0x80) == 0 and
            (data[9] & 0x80) == 0):
                return
        
        size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | (data[9])
        size += 10 # size excludes the "header" (but not the "extended header")
        cls.CONSUME(size + 10)

    @classmethod
    def mp3file_find_sync_word(cls):
        offset = sound.mp3findsyncword(cls.stream[cls.READ_PTR():], cls.BYTES_LEFT())
        if offset >= 0:
            cls.CONSUME(offset)
            return True
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
        print(rc)
        bitrate, nchans, samprate, bitspersample, outputsamps, layer, version = rc
        
        #bitrate, nchans, samprate, bitspersample, outputsamps, layer, version = unpack_from("<i", frameinfo)
        print(f"bitrate={bitrate}, nchans={nchans},samprate={samprate},bitspersample={bitspersample},outputsamps={outputsamps},layer={layer},version={version}")

    @classmethod
    def push_audio(cls, audiobuf):
        
        if cls.audiopos + len(audiobuf) <= len(cls.audiodata):
            cls.audiodata[cls.audiopos:cls.audiopos+len(audiobuf)] = audiobuf[0:len(audiobuf)]
            cls.audiopos += len(audiobuf)
            if cls.audiopos < len(cls.audiodata):
                return
        while sound.testbuff() < 3:
                pass
        sound.addbuff(cls.audiodata)
        #print(len(cls.audiodata))
 
        cls.audiopos = 0
        if cls.audioflag == 1:
            cls.audiodata = memoryview(cls.audiodata2)
            cls.audioflag = 2
        else:
            cls.audiodata = memoryview(cls.audiodata1)
            cls.audioflag = 1

        if False: #debug
            if audiodata[0] != 0:
                for i in range(len(audiodata)):
                    print('{:02x}'.format(audiodata[i]), end="")
                    if i % 2 != 0:
                        print(' ',end="")
                    if i % 32 == 31:
                        print("")
                break
            
    @classmethod
    def push_pcm(cls, inbuf):
        left = 0
        if cls.pcmpos + len(inbuf) <= len(cls.pcmdata):	#copy normally
            cls.pcmdata[cls.pcmpos:cls.pcmpos+len(inbuf)] = inbuf[0:len(inbuf)]
            cls.pcmpos += len(inbuf)
            if cls.pcmpos < len(cls.pcmdata):
                return
        else:	# exceed buffer
            rest = len(cls.pcmdata) - cls.pcmpos
            cls.pcmdata[cls.pcmpos:len(cls.pcmdata)] = inbuf[0:rest]
            left = len(inbuf) - rest
            
        #print(cls.pcmflag, sound.dma_getcount())
        #cls.hexdump(memoryview(cls.pcmdata), "cls.pcmdata")
        if cls.pcmflag == 1:	# wrote first half (playing 2nd half)
            while sound.dma_getcount() < cls.pcmlen / 2:
                pass
        else:
            while sound.dma_getcount() >= cls.pcmlen / 2:
                pass
        #print("leav",cls.pcmflag, sound.dma_getcount())
        cls.pcmpos = 0
        if cls.pcmflag == 1:
            cls.pcmdata = memoryview(cls.pcmdata2)
            cls.pcmflag = 2
        else:
            cls.pcmdata = memoryview(cls.pcmdata1)
            cls.pcmflag = 1
        if left != 0:
            cls.pcmdata[0:left] = inbuf[rest:len(inbuf)]
            cls.pcmpos = left
            
        if False: #debug
            if pcmdata[0] != 0:
                for i in range(len(pcmdata)):
                    print('{:02x}'.format(pcmdata[i]), end="")
                    if i % 2 != 0:
                        print(' ',end="")
                    if i % 32 == 31:
                        print("")
                break
    @classmethod
    def hexdump(cls, buf, title=""):
        print(title)
        for i in range(32):
            print(buf[i],end=" ")
        print("")
        
    @classmethod
    def main(cls, infile):
        cls.audiodata = memoryview(cls.audiodata1)
        cls.audioflag = 1
        print(infile)
        fs = 44000
        delay = int(1_000_000 / fs)

        decoder = sound.mp3initdecoder()
        print(decoder)
        fi = open(infile, "rb")
        fsize = fi.seek(0, 2)  # os.SEEK_END
        fi.seek(0, 0)  # os.SEEK_SET
        fleft = fsize

        cls.stream_end = len(cls.stream) #fsize
        cls.stream_ptr = 0

        fi.readinto(cls.stream)
        fleft -= len(cls.stream)
        print(f"fleft={fleft}")
        frame=0
        frameinfo = bytearray(32)
        audiobuf0 = bytearray(MAX_BUFFER_LEN * 2)
        audiobuf = memoryview(audiobuf0)
        sound.dma_play(memoryview(cls.pcmbuf), 44100)
        pcmbufx = memoryview(bytearray(MAX_BUFFER_LEN * 2 * 2))
        while cls.mp3file_find_sync_word():
            if checkKey():
                break
            cls.skip_id3v2()
            #print(fi)
            err = sound.mp3getnextframeinfo(decoder, frameinfo, cls.stream[cls.READ_PTR():]);
            if err != ERR_MP3_NONE:
                print("It may be VBR  MP3GetNextFrameInfo rc=", err)
                return
            rc = unpack("<LLLLLLL", frameinfo)
            bitrate, nchans, samprate, bitspersample, outputsamps, layer, version = rc
            if fs != samprate / 1:
                fs = samprate / 1
                delay = int(1_000_000 / fs)
                #sound.reopen(delay, nchans)
                cls.print_frameinfo(frameinfo)
                print(f"fs={fs}, delay={delay}")
                sound.dma_end()
                sound.dma_play(memoryview(cls.pcmbuf), int(fs))


            #cls.print_frameinfo(frameinfo)
            #print(fi)
            bytes_left = cls.BYTES_LEFT()
            inbuf = cls.stream[cls.READ_PTR():]
            #print("stream len", len(cls.stream), bytes_left)
            #print("inbuf len", len(inbuf))
            #print("audiodata len", len(audiodata))
            #break
            rc = sound.mp3decode(decoder, inbuf, bytes_left, audiobuf, 0)
            if rc <= 0:
                cls.stream[0:bytes_left] = inbuf[0:bytes_left]
                rc = fi.readinto(cls.stream[bytes_left:])
                fleft -= len(cls.stream)
                #print(f"fleft={fleft}")
                if rc <=0:
                    print("EOF")
                    break
                cls.stream_ptr = 0
                cls.stream_end = len(cls.stream)
                bytes_left = cls.BYTES_LEFT()
                inbuf = cls.stream[cls.READ_PTR():]
                rc = sound.mp3decode(decoder, inbuf, bytes_left, audiobuf, 0)
                if rc < 0:
                    print("give up")
                    break
            #print(cls.pcmflag, sound.dma_getcount(), outputsamps)
            sound.mp3pcm2dma(audiobuf[0:outputsamps * 2], pcmbufx,0)
            #cls.hexdump(memoryview(cls.pcmbuf), "cls.pcmbuf")
                    
            cls.push_pcm(pcmbufx[0:outputsamps * 2])
            #rc = sound.mp3decode(decoder, inbuf, bytes_left, audiodata, 0);
            #print(rc)
            cls.CONSUME(cls.BYTES_LEFT() - rc) 
fs = 11000
#delay = 1_000_000 / 44100
delay = int(1_000_000 / fs)
keyb = picocalc.keyboard
#sound.open(delay)


fdir = "/sd"
flist = os.listdir(fdir)
flist.sort()
try:
    for fn in flist:
        if fn.endswith(".mp3"):
           DecodeMP3.main(fdir +"/" + fn)
        if checkKey():
            st = getKeystring()
            if 'q' in st:
                rc = -1
                break
        time.sleep_ms(500)
        while checkKey():
            st = getKeystring()
finally:
    print("close")
    sound.dma_end()
    