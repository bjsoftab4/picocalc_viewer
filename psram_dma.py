"""
Picocalc
PSRAM block device driver using PIO0 or 1
"""

import time
import rp2
from machine import Pin, Timer
import uos

CS_PIN = const(20)  # cs:GP20
CLK_PIN = const(21)  # sck:GP21
SIDESET_PINS = CLK_PIN  # sck:GP21
BASE_PINS = const(2)  # for QSPI : TX,DIO0:GP2, RX,DIO1:GP3, DIO2:GP4, DIO3:GP5
SPI_OUT_PIN = const(2)  # for SPI:   TX:GP2, RX:GP3
SPI_IN_PIN = const(3)

FREQ = const(40_000_000) #max freq is 60Mhz but unstable

# PIO registers
SM_PIO0_NUM = const(0)
SM_PIO1_NUM = const(4)
PIO0_BASE = const(0x50200000)
PIO1_BASE = const(0x50300000)
TXF0 = const(0x010)
RXF0 = const(0x020)
FSTAT = const(0x004)
DREQ_PIO0_TX0 = const(0)
DREQ_PIO0_RX0 = const(4)
DREQ_PIO1_TX0 = const(8)
DREQ_PIO1_RX0 = const(12)

if True:    # use PIO0
    GPIO_ALT = 6
    PIO_BASE_ADDR = PIO0_BASE
    SM_BASE_NUM = SM_PIO0_NUM
    DREQ_PIO_TX = DREQ_PIO0_TX0
    DREQ_PIO_RX = DREQ_PIO0_RX0
else:       # use PIO1
    GPIO_ALT = 7
    PIO_BASE_ADDR = PIO1_BASE
    SM_BASE_NUM = SM_PIO1_NUM
    DREQ_PIO_TX = DREQ_PIO1_TX0
    DREQ_PIO_RX = DREQ_PIO1_RX0

PSRAM_BLOCKS = const(8192 * 1024 // 512)  # maxsize = 8MiB


class PsramDevice:
    sm_init_flag = False
    cs = Pin(CS_PIN, mode=Pin.OUT, value=1)
    
    def __init__(self, blocknum=PSRAM_BLOCKS):
        if PsramDevice.sm_init_flag:
            return

        PsramDevice.stop_pio()
        PsramDevice.sm_start(FREQ)

        for _ in range(3):
            time.sleep_ms(1)
            self.psram_reset()
            time.sleep_ms(1)
            readid = self.psram_read_id()  # 2nd byte: 0x55 fail, 0x5d pass
            if readid & 0x00ff0000 == 0x5D0000:
                break
            time.sleep_ms(100)
        
        if readid & 0x00ff0000 != 0x5D0000:
            print(f"PSRAM READID fail:{readid:08x}")
            PsramDevice.sectors = 0
            PsramDevice.sm_activate(0)
            return
        PsramDevice.dma_config(PsramDevice.sm_qspi_rd_num, PsramDevice.sm_qspi_wr_num)
        PsramDevice.sectors = blocknum

    @micropython.viper
    @staticmethod
    def stat_pio()->int:
       pio = ptr32(uint(PIO_BASE_ADDR))
       return pio[51]

    @micropython.viper
    @staticmethod
    def stop_pio(): # PIO registers to RESET value
       pio = ptr32(uint(PIO_BASE_ADDR))
       pio[0] = 0   # SM_ENABLE = 0
       for i in range(32):
         pio[0x12 + i] = 0  # INSTR_MEM  jmp 0
       for i in range(4):
         pio[0x32 + i * 6] = 0x0001_0000  # CLKDIV (0xc8)
         pio[0x33 + i * 6] = 0x0001_F000  # EXECCTRL
         pio[0x34 + i * 6] = 0x000C_0000  # SHIFTCTRL
         pio[0x37 + i * 6] = 0x1400_0000  # PINCTRL

    @classmethod
    def sm_activate(cls, flag):
        cls.sm_spi_wr.active(flag)
        cls.sm_qspi_wr.active(flag)
        cls.sm_qspi_rd.active(flag)
        cls.sm_qspi_wr2.active(flag)

    @classmethod
    def sm_restart(cls):
        cls.sm_spi_wr.restart()
        cls.sm_qspi_wr.restart()
        cls.sm_qspi_rd.restart()
        cls.sm_qspi_wr2.restart()
        
    @classmethod
    def sm_start(cls, FREQ=2_000_000, force_init = False):
        # PIO definition

        @rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW, out_init=rp2.PIO.OUT_HIGH)
        def spiwrite_one():
            wrap_target()
            pull()  # 1
            set(x, 7)  # 2  8bit (byte)
            label("BYTE")
            out(pins, 1).side(0)[1]  # 3
            jmp(x_dec, "BYTE").side(1)[1]  # 4: CLK = HI  (tSA = 1clk, tHD = 1clk)
            push().side(0)  # 5
            wrap()

        @rp2.asm_pio(
            sideset_init=rp2.PIO.OUT_LOW,
            out_init=(
                rp2.PIO.OUT_HIGH,
                rp2.PIO.OUT_HIGH,
                rp2.PIO.OUT_HIGH,
                rp2.PIO.OUT_HIGH,
            )
        )
        def spiwrite_quad1():
            wrap_target()
            pull()  # 1
            set(x, 1)  # 2  2 cyle 8bit (byte)
            label("BYTE")
            out(pins, 4).side(0)[1]  # 3
            jmp(x_dec, "BYTE").side(1)[1]  # 4: CLK = HI  (tSA = 1clk, tHD = 1clk)
            push().side(0)  # 5
            wrap()

        @rp2.asm_pio(
            sideset_init=rp2.PIO.OUT_LOW,
            out_init=(
                rp2.PIO.OUT_HIGH,
                rp2.PIO.OUT_HIGH,
                rp2.PIO.OUT_HIGH,
                rp2.PIO.OUT_HIGH,
            )
        )
        def spiwrite_quad4():
            wrap_target()
            pull()  # 1  length - 1(in byte)
            mov(y, osr)  # 2
            label("LOOP")
            pull().side(0)  # 3 data(byte (MSB))
            set(x, 7)  # 4 8cycle (32bit)
            label("WORD")
            out(pins, 4).side(0)[1]  # 5
            jmp(x_dec, "WORD").side(1)[1]  # 6
            jmp(y_dec, "LOOP").side(0)  # 7
            push(noblock)  # 8
            wrap()

        @rp2.asm_pio(
            push_thresh=8,
            autopull=False,
            autopush=False,
            sideset_init=rp2.PIO.OUT_LOW,
            set_init=(
                rp2.PIO.OUT_HIGH,
                rp2.PIO.OUT_HIGH,
                rp2.PIO.OUT_HIGH,
                rp2.PIO.OUT_HIGH,
            )
        )
        def spiread_quad4():
            wrap_target()
            pull()  # 1 length - 1(in byte)
            set(pindirs, 0)  # 2
            mov(y, osr).side(0)  # 3
            set(x, 5)  #4 6cycle
            label("preload")
            in_(pins, 4).side(1)[1]  # 5
            jmp(x_dec, "preload").side(0)[1]  # 6
            label("ALL_LOOP")
            set(x, 7)  # 7 8cycle x 4bit
            label("WORD")
            in_(pins, 4).side(1)[1]  # 8
            jmp(x_dec, "WORD").side(0)[1]  # 9
            push()  # 10
            jmp(y_dec, "ALL_LOOP").side(0)  # 11
            set(pindirs, 0xF)  # 12
            wrap()

        if not cls.sm_init_flag or force_init or PsramDevice.stat_pio() == 0x0001f000:
            cls.sm_init_flag = True
            cls.sm_spi_wr_num = SM_BASE_NUM + 0
            cls.sm_qspi_wr_num = SM_BASE_NUM + 1
            cls.sm_qspi_rd_num = SM_BASE_NUM + 2
            cls.sm_qspi_wr2_num = SM_BASE_NUM + 3
            cls.sm_spi_wr = rp2.StateMachine(cls.sm_spi_wr_num)
            cls.sm_qspi_wr = rp2.StateMachine(cls.sm_qspi_wr_num)
            cls.sm_qspi_rd = rp2.StateMachine(cls.sm_qspi_rd_num)
            cls.sm_qspi_wr2 = rp2.StateMachine(cls.sm_qspi_wr2_num)

            cls.sm_spi_wr.init(
                spiwrite_one,
                freq=FREQ,
                sideset_base=Pin(CLK_PIN),
                out_base=Pin(SPI_OUT_PIN),
            )
            cls.sm_qspi_wr.init(
                spiwrite_quad4,
                freq=FREQ,
                sideset_base=Pin(CLK_PIN),
                out_base=Pin(BASE_PINS),
            )
            cls.sm_qspi_wr2.init(
                spiwrite_quad1,
                freq=FREQ,
                sideset_base=Pin(CLK_PIN),
                out_base=Pin(BASE_PINS),
            )
            cls.sm_qspi_rd.init(
                spiread_quad4,
                freq=FREQ,
                sideset_base=Pin(CLK_PIN),
                in_base=Pin(BASE_PINS),
                set_base=Pin(BASE_PINS),
            )
            cls.sm_spi_wr.active(1)
            cls.sm_qspi_wr.active(1)
            cls.sm_qspi_rd.active(1)
            cls.sm_qspi_wr2.active(1)

    def psram_reset(self):
        cs = PsramDevice.cs
        pio_push_cmd = PsramDevice.pio_push_cmd
        num_cmd = PsramDevice.sm_spi_wr_num

        cs.value(0)
        pio_push_cmd(0x66, num_cmd)  # Reset Enable
        cs.value(1)
        time.sleep_us(10)
        cs.value(0)
        pio_push_cmd(0x99, num_cmd)  # Reset
        cs.value(1)
        time.sleep_us(200)

    def psram_read_id(self):
        cs = PsramDevice.cs
        pio_push = PsramDevice.pio_push
        pio_pull = PsramDevice.pio_pull
        num_rdat = PsramDevice.sm_qspi_rd_num
        num_cmd = PsramDevice.sm_spi_wr_num
        buf=bytearray(64)

        cs.value(0)
        PsramDevice.pio_push_cmd(0x9F, num_cmd)  # Read ID
        PsramDevice.pio_push(len(buf)//4 - 1, 0, num_rdat)
        for i in range(len(buf)//4):
            dat = PsramDevice.pio_pull(num_rdat)
            buf[i*4] = dat >> 24
            buf[i*4+1] = dat >> 16
            buf[i*4+2] = dat >> 8
            buf[i*4+3] = dat 
        cs.value(1)
        data = 0
        for i in range(9,9+16):
            data = data << 1
            if buf[i] & 0x20 != 0:
                data |= 1
            data = data << 1
            if buf[i] & 0x2 != 0:
                data |= 1
        return data

    @staticmethod
    @micropython.viper
    def pio_push(byte: uint, shift: int, sm_num: int):
        sm_num = sm_num & 0x03
        dst = ptr32(uint(PIO_BASE_ADDR) + uint(TXF0) + 4 * sm_num)
        stat = ptr32(uint(PIO_BASE_ADDR) + uint(FSTAT))
        mask = 0x010000 << sm_num  # TXFULL
        while stat[0] & mask != 0:  # is FULL
            pass
        dst[0] = byte << shift

    @staticmethod
    @micropython.viper
    def pio_pull(sm_num: int) -> uint:
        sm_num = sm_num & 0x03

        src = ptr32(uint(PIO_BASE_ADDR) + uint(RXF0) + 4 * sm_num)
        stat = ptr32(uint(PIO_BASE_ADDR) + uint(FSTAT))
        mask = 0x0100 << sm_num  # RXEMPTY
        while stat[0] & mask != 0:  # is empty
            pass
        return uint(src[0])
        
    @staticmethod
    @micropython.viper
    def pio_push_cmd(byte: int, sm_num: int) -> int:
        sm_num = sm_num & 0x03
        dst = ptr32(uint(PIO_BASE_ADDR) + uint(TXF0) + 4 * sm_num)
        src = ptr32(uint(PIO_BASE_ADDR) + uint(RXF0) + 4 * sm_num)
        stat = ptr32(uint(PIO_BASE_ADDR) + uint(FSTAT))

        mask = 0x010000 << sm_num  # TXFULL
        while stat[0] & mask != 0:  # is FULL
            pass
        dst[0] = byte << 24
        
        mask = 0x0100 << sm_num  # RXEMPTY
        while stat[0] & mask != 0:  # is empty
            pass
        return src[0]
        
    @staticmethod
    @micropython.viper
    def pio_push_addr(addr: int, sm_num: int) -> int:
        sm_num = sm_num & 0x03
        dst = ptr32(uint(PIO_BASE_ADDR) + uint(TXF0) + 4 * sm_num)
        src = ptr32(uint(PIO_BASE_ADDR) + uint(RXF0) + 4 * sm_num)
        stat = ptr32(uint(PIO_BASE_ADDR) + uint(FSTAT))

        mask = 0x0100_0000 << sm_num  # TXEMPTY
        while stat[0] & mask == 0:  # is not EMPTY
            pass
        dst[0] = addr << 8
        dst[0] = addr << 16
        dst[0] = addr << 24
        
        mask = 0x0100 << sm_num  # RXEMPTY
        for _ in range(3):
            while stat[0] & mask != 0:  # is empty
                pass
            dmy = src[0]

    @classmethod
    @micropython.native
    def readblocks(cls, block_num, buf):
        reg = PsramDevice.rxdma.registers
        nblocks = len(buf) // 512
        dma_addr = PsramDevice.getaddr(buf)
        psramaddr = block_num * 512
        num_cmd = PsramDevice.sm_spi_wr_num
        num_rdat = PsramDevice.sm_qspi_rd_num
        num_adr = PsramDevice.sm_qspi_wr2_num
        pio_push = PsramDevice.pio_push
        pio_pull = PsramDevice.pio_pull
        pio_push_addr = PsramDevice.pio_push_addr
        pio_push_cmd = PsramDevice.pio_push_cmd
        
        cs = PsramDevice.cs
        for _ in range(nblocks):
            cs.value(0)
            pio_push_cmd(0xEB, num_cmd)  # fast read cmd

            pio_push_addr(psramaddr, num_adr)
            time.sleep_us(1)

            reg[6] = dma_addr  # CH0_AL1_WRITE_ADDR
            reg[7] = 512 // 4  # CH0_AL1_TRANS_COUNT_TRIG

            pio_push(512 // 4 - 1, 0, num_rdat)

            psramaddr += 512  # add addr while DMA is running
            dma_addr += 512

            while (
                reg[3] & 0x0400_0000
            ) != 0:  # wait for DMA end ( CTRL_REG & BUSYflag )
                pass
            cs.value(1)

    @staticmethod
    @micropython.viper
    def getaddr(buf) -> int:
        addr = ptr(buf)
        return int(addr)

    @classmethod
    @micropython.native
    def writeblocks(cls, block_num, buf):
        reg = PsramDevice.txdma.registers
        nblocks = len(buf) // 512
        dma_addr = PsramDevice.getaddr(buf)
        psramaddr = block_num * 512
        num_cmd = PsramDevice.sm_spi_wr_num
        num_wdat = PsramDevice.sm_qspi_wr_num
        num_adr = PsramDevice.sm_qspi_wr2_num
        pio_push = PsramDevice.pio_push
        pio_pull = PsramDevice.pio_pull
        pio_push_addr = PsramDevice.pio_push_addr
        pio_push_cmd = PsramDevice.pio_push_cmd
        cs = PsramDevice.cs

        for _ in range(nblocks):
            cs.value(0)
            pio_push_cmd(0x38, num_cmd)  # quad write cmd
            pio_push_addr(psramaddr, num_adr)
            time.sleep_us(1)

            pio_push(512 // 4 - 1, 0, num_wdat)
            reg[5] = dma_addr  # CH0_AL1_READ_ADDR
            reg[7] = 512 // 4  # CH0_AL1_TRANS_COUNT_TRIG   (Start DMA)

            psramaddr += 512  # add addr while DMA is running
            dma_addr += 512

            while (
                reg[3] & 0x0400_0000
            ) != 0:  # wait for DMA end ( CTRL_REG & BUSYflag )
                pass
            pio_pull(num_wdat)
            cs.value(1)

    def ioctl(self, op, _):
        if op == 4:  # get number of blocks
            return PsramDevice.sectors
        if op == 5:  # get block size in bytes
            return 512
        return 0

    # for DMA
    txdma = None
    rxdma = None

    @classmethod
    def dma_close(cls):
        cls.rxdma.close()
        cls.rxdma = None
        cls.txdma.close()
        cls.txdma = None

    @classmethod
    @micropython.native
    def dma_config(cls, rx_sm, tx_sm):
        rx_sm = rx_sm & 3
        tx_sm = tx_sm & 3
        if cls.rxdma is None:
            src = PIO_BASE_ADDR + RXF0 + 4 * rx_sm
            cls.rxdma = rp2.DMA()
            dmactrl = cls.rxdma.pack_ctrl(
                inc_read=False, treq_sel=DREQ_PIO_RX + rx_sm, size=2, bswap=True
            )
            cls.rxdma.config(read=src, write=0, count=0, ctrl=dmactrl, trigger=False)
        if cls.txdma is None:
            dst = PIO_BASE_ADDR + TXF0 + 4 * tx_sm
            cls.txdma = rp2.DMA()
            dmactrl = cls.txdma.pack_ctrl(
                inc_write=False, treq_sel=DREQ_PIO_TX + tx_sm, size=2, bswap=True
            )
            cls.txdma.config(read=0, write=dst, count=0, ctrl=dmactrl, trigger=False)


def mount(point="/psram"):
    psramdisk = PsramDevice()
    if psramdisk.sectors == 0:
        print("No PSRAM device")
        print("Try soft-reset")
        return
    try:
        uos.mount(psramdisk, point)
    except:
        pass
    found = False
    for mt in uos.mount():
        if mt[1] == point:
            found = True
            print("Mount existed filesystem:" + point)
            if rwtest() == 0:
                print("R/W test OK")
            else:
                print("Failed. Error on R/W test")
                print("Try soft-reset")
                PsramDevice.sm_activate(0)
                uos.umount("/psram")
                return

    if not found:
        print("Creating filesystem")
        bufz = bytearray([0] * 512)
        psramdisk.writeblocks(0, bufz)  # Erase 1st sector
        uos.VfsFat.mkfs(psramdisk)
        try:
            uos.mount(psramdisk, point)
            print("Mount new filesystem:" + point)
        except:
            print("Failed. Error on mount filesystem:" + point)
            print("Try soft-reset")
            PsramDevice.sm_activate(0)
            return
        if rwtest() == 0:
            print("R/W test OK")
        else:
            print("Failed. Error on R/W test")
            print("Try soft-reset")
            PsramDevice.sm_activate(0)

def format():
    psramdisk = PsramDevice() 
    buf = bytearray([0] * 512)
    psramdisk.readblocks(0, buf)
    
def rwtest(fn="/psram/work.txt"):
    try:
        buff = memoryview(bytearray(512))
        for i in range(len(buff)):
            buff[i] = i % 64 + 32

        st = time.ticks_ms()
        with open(fn, "wb") as f:
            for i in range(200):
                f.write(buff)
        ed = time.ticks_diff(time.ticks_ms(), st)
        print(f"write time:{ed}ms, {100_000 / ed}kByte/s")
        
        st = time.ticks_ms()
        with open(fn, "rb") as f:
            for i in range(200):
                f.readinto(buff)
        ed = time.ticks_diff(time.ticks_ms(), st)
        print(f"read time:{ed}ms, {100_000 / ed}kByte/s")
        return 0
    except:
        PsramDevice.sm_activate(0)
        return -1
  
mount()

