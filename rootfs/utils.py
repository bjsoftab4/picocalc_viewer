# utility functions

import io
import time
import gc
import os
import picocalc

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

def isdir(dname):
    st = os.stat(dname)
    if st[6] == 0:
        return True
    return False

def scan_dir(dname, func, ext=(".mp3",".MP3")):
    flist = os.listdir(dname)
    flist.sort()
    print("Scan directory:"+dname)
    dirlist = [
        f for f in flist if isdir(dname+"/"+f)
    ]
    i = 0
    while i < len(dirlist):
        d = dirlist[i]
        rc = scan_dir(dname + "/" + d, func, ext)
        if rc < 0 :
            return -1
        if rc == 4: # next folder
            pass
        if rc == 5: # prev folder
            i = i - 1
            if( i < 0):
                i = 0
            continue

        i += 1

    filelist = [
        f for f in flist if not isdir(dname+"/"+f) and f.endswith(ext)
    ]
    filelist.sort()
    print("File list:", filelist)
    i = 0
    while i < len(filelist):
        fn = dname + "/" + filelist[i]
        
        if fn.endswith(ext):
            waitKeyOff()
            rc = func(fn)
            if rc == 9: #quit
                break
            if rc == 2: # next file
                pass
            if rc == 3: # prev file
                i = i - 1
                if( i < 0):
                    i = 0
                continue
            if rc == 4 or rc == 5: # next/prev folder
                return rc
        i += 1
    return 0

def hexdump(buf, title=""):
    print(title)
    for i in range(32):
        print(f"{buf[i]:02x}",end=" ")
    print("")


def read_idx(fp_tar):
    global IDX_TIME
    IDX_TIME = 10   # 10sec
    fp_tar.seek(512)    #skip tar header of .idx
    line = fp_tar.readline().decode().strip()  # it must be mp3
    if not line.endswith(".mp3"):
        return None

    line = fp_tar.readline().decode().strip()  # it must be directory
    words = line.split()
    if words[0] == '0':
        fps=int(words[1][:-1])
    else:
        return None
    toc = []
    filecount = 0
    for line in fp_tar:
        words = line.decode().strip().split()
        filepos = int(words[0])
        if words[1] == "EOF":
            toc.append(filepos)
            break
        fname = words[1]
        
        # print(f"pos={filepos:04x}, count={filecount}, name={fname}, val={val}")
        if fname.endswith(".jpg"):
            if filecount % (60 // IDX_TIME) == 0: # for each one minite
                toc.append(filepos)
                #print("fname",fname,"filepos",filepos)
            filecount += 1
    return fps, toc
 
def read_tar_header(fi, headbuf):
    rd = fi.readinto(headbuf)  # read tar header
    if rd != 512:
        print("EOF")
        return None
    fn=headbuf[0:100].rstrip(b"\0").decode()
    if len(fn) == 0:
        print("EOF")
        return None
    sz = int(headbuf[0x7c:0x87].decode(),8)
    sz0 = sz
    if (sz % 512) != 0:
        sz += 512 - sz % 512
    return (fn, sz, sz0)

def analyze_tar(fp_tar):
    headbuf = bytearray(512)
    fps = None
    toc = None
    idxpos = 0     # pos is beginnig of idx
    mp3pos = 0
    jpgpos = 0
    
    fp_tar.seek(0)
    retc = read_tar_header(fp_tar, headbuf)
    if retc is None:
        return None
    fn, sz, sz0 = retc
    if fn.endswith(".idx"):
        retc = read_idx(fp_tar)
        if retc is None:
            return None
        fps, toc = retc
        mp3pos = idxpos + 512 + sz # pos is beginnig of mp3
    else:
        idxpos = None
    fp_tar.seek(mp3pos)
    retc = read_tar_header(fp_tar, headbuf)
    if retc is None:
        return None
    fn, sz, sz0 = retc
    if fn.endswith(".mp3"):
        jpgpos = mp3pos + 512 + sz # pos is beginnig of jpgs (start with directory)
    else:
        mp3pos = None
    
    return (fps, toc, idxpos, mp3pos, jpgpos)
