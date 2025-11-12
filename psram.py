import rp2
from machine import Pin, SoftSPI
import time
import uos

class PSRAMBlockDevice:
    def __init__(self):

        spi = SoftSPI(baudrate=10_000_000, polarity=0, phase=0,
                  sck=Pin(21), mosi=Pin(2), miso=Pin(3))
        cs = Pin(20, Pin.OUT)
        cs.value(1)
        spi.init(baudrate=200_000)
        self.sectors = 4096 * 1024 // 512
        self.spi = spi
        self.cs = cs
        self.psram_reset()

    def psram_reset(self):
        self.cs.value(0)
        self.spi.write(b'\x66')  # Reset Enable
        self.cs.value(1)
        time.sleep_us(1)
        self.cs.value(0)
        self.spi.write(b'\x99')  # Reset
        self.cs.value(1)
        time.sleep_us(150)

    def psram_read_id(self):
        self.cs.value(0)
        self.spi.write(b'\x9F')  # Read ID command
        self.spi.write(b'\x00\x00\x00')  # 24bit addr(dummy)
        data = spi.read(8)	# 2バイト目　0x55 fail, 0x5d pass
        self.cs.value(1)
        return data

    def psram_write(self,addr, data):
        cmd = bytearray([0x02]) + addr.to_bytes(3, 'big') + data
        self.cs.value(0)
        self.spi.write(cmd)
        self.cs.value(1)

    def psram_read(self,addr, length):
        cmd = bytearray([0x03]) + addr.to_bytes(3, 'big')
        self.cs.value(0)
        self.spi.write(cmd)
        result = self.spi.read(length)
        self.cs.value(1)
        return result
        
    def psram_readinto(self,addr, buff):
        cmd = bytearray([0x03]) + addr.to_bytes(3, 'big')
        self.cs.value(0)
        self.spi.write(cmd)
        self.spi.readinto(buff)
        self.cs.value(1)
        return 

    def psram_fastread(self,addr, length):
        cmd = bytearray([0x0B]) + addr.to_bytes(3, 'big')
        self.cs.value(0)
        self.spi.write(cmd)
        result = self.spi.read(length)
        self.cs.value(1)
        return result


    def readblocks(self, block_num, buf):
        nblocks = len(buf) // 512
        mv = memoryview(buf)
        for i in range(nblocks):
            offset = i * 512
            self.psram_readinto(block_num * 512 + offset, mv[offset + 0:offset + 512])

    def writeblocks(self, block_num, buf):
        nblocks = len(buf) // 512
        mv = memoryview(buf)
        for i in range(nblocks):
            offset = i * 512
            self.psram_write(block_num * 512 + offset, mv[offset + 0:offset + 512])

    def ioctl(self, op, arg):
        if op == 4:  # get number of blocks
            return self.sectors
        if op == 5:  # get block size in bytes
            return 512
        return 0

def mount(point="/psram"):
        psramdisk=PSRAMBlockDevice()
        try:
            uos.mount(psramdisk, point)
        except:
            pass
        found = False
        for mt in uos.mount():
            if mt[1] == point:
                found = True
                print("Mount existed filesystem:"+point)
        if not found:
            print("Creating filesystem")
            uos.VfsFat.mkfs(psramdisk)
            uos.mount(psramdisk, point)
            print("Mount new filesystem:"+point)

mount()
