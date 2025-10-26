from struct import *
import sound

MAX_NGRAN = 2
MAX_NCHAN = 2
MAX_NSAMP = 576
MAX_BUFFER_LEN=(MAX_NSAMP * MAX_NGRAN * MAX_NCHAN)
ERR_MP3_NONE = 0
audiodata1 = bytearray(MAX_BUFFER_LEN * 2)
audiodata2 = bytearray(MAX_BUFFER_LEN * 2)

filedata1 = bytearray(4096)
filedata2 = bytearray(4096)

class DecodeMP3:
    global audiodata
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
        print(frameinfo)
        rc = unpack("<LLLLLLL", frameinfo)
        print(rc)
        bitrate, nchans, samprate, bitspersample, outputsamps, layer, version = rc
        
        #bitrate, nchans, samprate, bitspersample, outputsamps, layer, version = unpack_from("<i", frameinfo)
        print(f"bitrate={bitrate}, nchans={nchans},samprate={samprate},bitspersample={bitspersample},outputsamps={outputsamps},layer={layer},version={version}")

    @classmethod
    def main(cls, infile):
        audiodata = memoryview(audiodata1)
        audioflag = 1

        fs = 44000
        delay = int(1_000_000 / fs)
        sound.open(delay)

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
        frameinfo = bytearray(1024)
        tempbuf = bytearray(512) # mp3 bitrate / 8 ?
        while cls.mp3file_find_sync_word():
            cls.skip_id3v2()
            #print(fi)
            err = sound.mp3getnextframeinfo(decoder, frameinfo, cls.stream[cls.READ_PTR():]);
            if err != ERR_MP3_NONE:
                fatal("MP3GetNextFrameInfo")
            rc = unpack("<LLLLLLL", frameinfo)
            bitrate, nchans, samprate, bitspersample, outputsamps, layer, version = rc
            if fs != samprate / 2:
                fs = samprate / 2
                delay = int(1_000_000 / fs)
                sound.close()
                cls.print_frameinfo(frameinfo)
                print(f"fs={fs}, delay={delay}")
                sound.open(delay)

            #cls.print_frameinfo(frameinfo)
            #print(fi)
            bytes_left = cls.BYTES_LEFT()
            inbuf = cls.stream[cls.READ_PTR():]
            #print("stream len", len(cls.stream), bytes_left)
            #print("inbuf len", len(inbuf))
            #print("audiodata len", len(audiodata))
            #break
            rc = sound.mp3decode(decoder, inbuf, bytes_left, audiodata, 0)
            if rc <= 0:
                cls.stream[0:bytes_left] = inbuf[0:bytes_left]
                rc = fi.readinto(cls.stream[bytes_left:])
                fleft -= len(cls.stream)
                print(f"fleft={fleft}")
                if rc <=0:
                    print("EOF")
                    break
                cls.stream_ptr = 0
                cls.stream_end = len(cls.stream)
                bytes_left = cls.BYTES_LEFT()
                inbuf = cls.stream[cls.READ_PTR():]
                rc = sound.mp3decode(decoder, inbuf, bytes_left, audiodata, 0)
                if rc < 0:
                    print("give up")
                    break
            while sound.testbuff() < 3:
                pass
            audio2 = memoryview(audiodata[0:outputsamps * 2])
            sound.addbuff(audio2)
 
            #sound.play(audiodata, 23)
            if False:
                if audiodata[0] != 0:
                    for i in range(len(audiodata)):
                        print('{:02x}'.format(audiodata[i]), end="")
                        if i % 2 != 0:
                            print(' ',end="")
                        if i % 32 == 31:
                            print("")
                    break

            if audioflag == 1:
                audiodata = memoryview(audiodata2)
                audioflag = 2
            else:
                audiodata = memoryview(audiodata1)
                audioflag = 1

            #rc = sound.mp3decode(decoder, inbuf, bytes_left, audiodata, 0);
            #print(rc)
            cls.CONSUME(cls.BYTES_LEFT() - rc) 
fs = 11000
#delay = 1_000_000 / 44100
delay = int(1_000_000 / fs)

sound.open(delay)
DecodeMP3.main("/sd/07uikousen.mp3")
#DecodeMP3.main("/test.mp3")
sound.close()