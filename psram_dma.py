import rp2
from machine import Pin, SoftSPI
import time
import uos

class PsramDevice:
    sm_init_flag = False
    
    def __init__(self):
        FREQ = 2_000_000
        FREQ_HI = 10_000_000
        FREQ_HI_RD = 10_000_000
        CS_PIN=20
        CLK_PIN=21
        SIDESET_PINS = 21  # cs:GP20, sck:GP21
        BASE_PINS = 2   # TX,DIO0:GP2, RX,DIO1:GP3, DIO2:GP4, DIO3:GP5
        SPI_OUT_BASE_PIN = 2
        SPI_IN_BASE_PIN = 3

        self.tx = Pin(SPI_OUT_BASE_PIN)
        self.rx = Pin(SPI_IN_BASE_PIN)
        self.clk = Pin(CLK_PIN, mode=Pin.OUT, pull=Pin.PULL_UP, value=0)
        self.cs = Pin(CS_PIN, mode = Pin.OUT, value=1)
        self.dio0 = Pin(BASE_PINS)
        self.dio1 = Pin(BASE_PINS+1)
        self.dio2 = Pin(BASE_PINS+2)
        self.dio3 = Pin(BASE_PINS+3)

        self.sectors = 4096 * 1024 // 512

        self.tx.init(self.tx.OPEN_DRAIN, self.tx.PULL_UP)
        self.rx.init(self.rx.IN, self.rx.PULL_UP)

        self.psram_reset()
        PsramDevice.sm_start(FREQ, FREQ_HI, FREQ_HI_RD)

    @classmethod
    def sm_start(cls, FREQ = 2_000_000, FREQ_HI = 25_000_000, FREQ_HI_RD = 30_000_000):
        CS_PIN=20
        CLK_PIN=21
        SIDESET_PINS = 21  # cs:GP20, sck:GP21
        BASE_PINS = 2   # TX,DIO0:GP2, RX,DIO1:GP3, DIO2:GP4, DIO3:GP5
        SPI_OUT_BASE_PIN = 2
        SPI_IN_BASE_PIN = 3

        # PIO definition
        @rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW, out_init=rp2.PIO.OUT_HIGH)
        def spiwrite_one():
            wrap_target()       
            pull()  .side(0)    #1
            set(x, 7)           #2  8bit (byte)
            label("BYTE")
            out(pins, 1).side(0)#3
            jmp(x_dec, "BYTE").side(1)       #4: CLK = HI  (tSA = 1clk, tHD = 1clk)
            push()              #5
            wrap()

        @rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW, out_init=(rp2.PIO.OUT_HIGH,rp2.PIO.OUT_HIGH,rp2.PIO.OUT_HIGH,rp2.PIO.OUT_HIGH))
        def spiwrite_quad():
            wrap_target()
            pull()  .side(0)    #1  length - 1(in byte)
            mov(y, osr)         #2
            label("LOOP")
            pull()  .side(0)    #3 data(byte (MSB))
            set(x, 1)           #4 2cycle (8bit)
            label("WORD")
            out(pins, 4).side(0)   #5
            jmp(x_dec, "WORD").side(1)#6
            jmp(y_dec, "LOOP").side(0)#7
            push(noblock)                  #8
            wrap()
            
        @rp2.asm_pio(push_thresh=8, autopull=False, autopush=False,sideset_init=rp2.PIO.OUT_LOW, set_init=(rp2.PIO.OUT_HIGH, rp2.PIO.OUT_HIGH, rp2.PIO.OUT_HIGH, rp2.PIO.OUT_HIGH))
        def spiread_quad():
            wrap_target()
            pull()              #1 length - 1(in byte)
            set(pindirs, 0)     #2
            mov(y, osr).side(0) #3
            label("ALL_LOOP")
            set(x, 1)           #4 2cycle x 4bit
            label("WORD")  
            in_(pins, 4)	.side(1)    #5
            jmp(x_dec, "WORD").side(0)  #6
            push()                      #7
            jmp(y_dec, "ALL_LOOP").side(0)  #8
            set(pindirs, 0xf)           #9
            wrap()

        if not cls.sm_init_flag:
            cls.sm_init_flag = True
            cls.sm_spi_wr_num = 0
            cls.sm_qspi_wr_num = 1
            cls.sm_qspi_rd_num = 2
            cls.sm_qspi_rd2_num = 3
            cls.sm_spi_wr = rp2.StateMachine(0, spiwrite_one, freq=FREQ, sideset_base=Pin(CLK_PIN), out_base=Pin(SPI_OUT_BASE_PIN))
            cls.sm_qspi_wr = rp2.StateMachine(1, spiwrite_quad, freq=FREQ_HI, sideset_base=Pin(CLK_PIN), out_base=Pin(BASE_PINS))
            cls.sm_qspi_rd = rp2.StateMachine(2, spiread_quad, freq=FREQ_HI_RD, sideset_base=Pin(CLK_PIN), in_base=Pin(BASE_PINS),set_base=Pin(BASE_PINS))
            cls.sm_qspi_rd2 = rp2.StateMachine(3, spiread_quad, freq=FREQ_HI_RD, sideset_base=Pin(CLK_PIN), in_base=Pin(BASE_PINS),set_base=Pin(BASE_PINS))

            cls.sm_spi_wr.active(1)
            cls.sm_qspi_wr.active(1)
            cls.sm_qspi_rd.active(1)
            cls.sm_qspi_rd2.active(1)
        time.sleep_ms(1)

    def send8(self, val):
        self.set_pins_spi()
        self.clk.value(0)
        for i in range(8):
            if (val & 0x80 ) != 0:
                self.tx.value(1)
            else:
                self.tx.value(0)
            val = val << 1
            self.clk.value(1)
            time.sleep_us(1)
            self.clk.value(0)
            time.sleep_us(1)
                    
    def psram_reset(self):
        self.cs.value(0)
        self.send8(0x66)
        self.cs.value(1)
        time.sleep_us(1)
        self.cs.value(0)
        self.send8(0x99)
        self.cs.value(1)
        time.sleep_us(150)

    def set_pins_spi(self):
        self.tx.init(self.tx.OPEN_DRAIN, self.tx.PULL_UP)
        self.rx.init(self.rx.IN, self.rx.PULL_UP)

    @micropython.viper
    def pio_push(self, byte:int, shift:int, sm_num:int):
            PIO0_BASE = 0x50200000
            TXF0 = 0x010
            FSTAT= 0x004
            dst = ptr32(uint(PIO0_BASE) + uint(TXF0) + 4 * sm_num)
            stat= ptr32(uint(PIO0_BASE) + uint(FSTAT))
            mask = 0x010000 << sm_num		# TXFULL
            while stat[0] & mask != 0:	# is FULL
                pass
            dst[0] = byte << shift

    @micropython.viper
    def pio_stat(self, sm_num:int) -> int:
            PIO0_BASE = 0x50200000
            FSTAT= 0x004
            stat= ptr32(uint(PIO0_BASE) + uint(FSTAT))
            return stat[0]

    @micropython.viper
    def pio_pull(self, sm_num:int) -> int:
            PIO0_BASE = 0x50200000
            RXF0 = 0x020
            FSTAT= 0x004
            src = ptr32(uint(PIO0_BASE) + uint(RXF0) + 4 * sm_num)
            stat= ptr32(uint(PIO0_BASE) + uint(FSTAT))
            mask = 0x0100 << sm_num		# RXEMPTY
            while stat[0] & mask != 0:	# is empty
                pass
            return src[0]
    
    @micropython.native    
    def spi_write(self, data):
        for b in data:
            self.pio_push(int(b),24, self.sm_spi_wr_num)
            self.pio_pull(self.sm_spi_wr_num)
            #self.sm_spi_wr.put(int(b), 24)
            #self.sm_spi_wr.get()
    
    @micropython.native    
    def qspi_write(self, data):
        self.sm_qspi_wr.put(len(data) - 1)
        for i in range(len(data)):
            val = data[i]
            self.pio_push(val, 24, self.sm_qspi_wr_num)
            #self.sm_qspi_wr.put(val,24)
        self.pio_pull(self.sm_qspi_wr_num)
        #self.sm_qspi_wr.get()
    
    @micropython.native    
    def qspi_read(self, length):
        data = bytearray(length)
        self.sm_qspi_rd.put(len(data) - 1)
        for i in range(len(data)):
            data[i] = self.sm_qspi_rd.get() & 0xff
        return data

    
    def qspi_readinto(self, data):
        self.sm_qspi_rd.put(len(data) - 1)
        for i in range(len(data)):
            data[i] = self.sm_qspi_rd.get() & 0xff
        return len(data)

    def psram_write_spi(self, addr, data):
        cmd = bytearray([0x02]) + addr.to_bytes(3, 'big') + data
        self.cs.value(0)
        self.spi_write(cmd)
        self.cs.value(1)
        
    def psram_write_quad(self, addr, data):
        cmd = bytearray([0x38])
        cmd2 = addr.to_bytes(3, 'big')
        self.cs.value(0)
        self.spi_write(cmd)     # command must be spi
        self.qspi_write(cmd2)
        self.qspi_write(data)
        self.cs.value(1)

    @micropython.native
    def psram_write_quad_dma(self, addr, data): #fast read cmd
        cmd = bytearray([0x38])
        cmd2 = addr.to_bytes(3, 'big')
        self.cs.value(0)
        self.spi_write(cmd)
        self.qspi_write(cmd2)
        time.sleep_us(1)

        length = len(data)
        self.sm_qspi_wr.put(length - 1)
        DmaPio.write_start(data, self.sm_qspi_wr_num) #SM=1
        DmaPio.write_wait()
        self.cs.value(1)
        while self.sm_qspi_wr.rx_fifo() > 0:
            rc1 = self.sm_qspi_wr.get()
            pass
        return 
                
    def psram_readinto_quad(self, addr, buff):
        cmd = bytearray([0xEB])
        cmd2 = addr.to_bytes(3, 'big')
        self.cs.value(0)
        self.spi_write(cmd)
        self.qspi_write(cmd2)
        self.qspi_readinto(buff[0:3])    # dummy read
        self.qspi_readinto(buff)
        self.cs.value(1)
        while self.sm_qspi_rd.rx_fifo() > 0:
            rc1 = self.sm_qspi_rd.get()
        return 
      
    @micropython.native
    def psram_readinto_quad_dma(self, addr, buff): #fast read cmd
        cmd = bytearray([0xEB])
        cmd2 = addr.to_bytes(3, 'big')
        self.cs.value(0)
        self.spi_write(cmd)
        self.qspi_write(cmd2)
        time.sleep_us(1)
        self.qspi_read(buff[0:3])    # dummy read
        length = len(buff)
        DmaPio.read_start(buff, self.sm_qspi_rd_num)  #SM = 2
        self.sm_qspi_rd.put(length - 1)
        DmaPio.read_wait()
        self.cs.value(1)
        while self.sm_qspi_rd.rx_fifo() > 0:
            rc1 = self.sm_qspi_rd.get()
            pass
        return 

    @micropython.native
    def readblocks(self, block_num, buf):
        nblocks = len(buf) // 512
        mv = memoryview(buf)
        #print(f"readblocks num={block_num},n={nblocks}")
        for i in range(nblocks):
            offset = i * 512
            #self.psram_readinto_quad(block_num * 512 + offset, mv[offset + 0:offset + 512])
            self.psram_readinto_quad_dma(block_num * 512 + offset, mv[offset + 0:offset + 512])

    @micropython.native
    def writeblocks(self, block_num, buf):
        nblocks = len(buf) // 512
        mv = memoryview(buf)
        for i in range(nblocks):
            offset = i * 512
            #self.psram_write_quad(block_num * 512 + offset, mv[offset + 0:offset + 512])
            self.psram_write_quad_dma(block_num * 512 + offset, mv[offset + 0:offset + 512])

    def ioctl(self, op, arg):
        if op == 4:  # get number of blocks
            return self.sectors
        if op == 5:  # get block size in bytes
            return 512
        return 0


class DmaPio:
    txdma = None
    txsrc = 0
    rxdma = None
    rxdst = 0
    
    @classmethod
    def read_start(cls, data, rx_sm):
        @micropython.viper
        def getaddr(buf) -> int:
            addr = ptr(buf)
            return int(addr)

        dst = memoryview(data)
        if cls.rxdma is None:
        PIO0_BASE = 0x50200000
        TXF0 = 0x010
        RXF0 = 0x020
        DREQ_PIO0_TX0 = 0
        DREQ_PIO0_RX0 = 4

            src = PIO0_BASE + RXF0 + 4 * rx_sm  
        cls.rxdma = rp2.DMA()
        dmactrl = cls.rxdma.pack_ctrl(inc_read = False, treq_sel = DREQ_PIO0_RX0 + rx_sm, size = 0)
            cls.rxdma.config(read=src, write=dst, count=len(dst), ctrl=dmactrl, trigger=False)
        else:
            cls.rxdma.registers[6] = getaddr(dst)	#CH0_AL1_WRITE_ADDR
        cls.rxdma.registers[7] = len(dst)	#CH0_AL1_TRANS_COUNT_TRIG

    @classmethod
    def read_wait(cls):
        while cls.rxdma.active():
            pass
            
    @classmethod
    def read_close(cls):
        cls.rxdma.close()
        cls.rxdma = None
    
    @classmethod
    def write_start(cls, data, tx_sm):
        @micropython.viper
        def getaddr(buf) -> int:
            addr = ptr(buf)
            return int(addr)

        src = memoryview(data)
        if cls.txdma is None:
        PIO0_BASE = 0x50200000
        #PIO1_BASE = 0x50300000
        TXF0 = 0x010
        RXF0 = 0x020
        DREQ_PIO0_TX0 = 0
        DREQ_PIO0_RX0 = 4

        dst = PIO0_BASE + TXF0 + 4 * tx_sm # LSB byte
        src = memoryview(data)
        cls.txdma = rp2.DMA()
        dmactrl = cls.txdma.pack_ctrl(inc_write = False, treq_sel = DREQ_PIO0_TX0 + tx_sm, size = 0)
            cls.txdma.config(read=src, write=dst, count=len(src), ctrl=dmactrl, trigger=False)
        else:
            cls.txdma.registers[5] = getaddr(src)	#CH0_AL1_READ_ADDR
        cls.txdma.registers[7] = len(src)	#CH0_AL1_TRANS_COUNT_TRIG

    @classmethod
    def write_wait(cls):
        while cls.txdma.active():
            pass
            
    @classmethod
    def write_close(cls):
        cls.txdma.close()
        cls.txdma = None
    
def mount(point="/psram"):
        psramdisk=PsramDevice()
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
            buf=bytearray(512)
            psramdisk.writeblocks(0,buf)    #erase 1st sector
            uos.VfsFat.mkfs(psramdisk)
            uos.mount(psramdisk, point)
            print("Mount new filesystem:"+point)

mount()
