import rp2
from machine import Pin, SoftSPI
import time
import uos

class PsramDevice:
    sm_init_flag = False
    
    def __init__(self):
        FREQ = 2_000_000        #our frequency to generate (SCLK)
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
        PsramDevice.sm_start()

    @classmethod
    def sm_start(cls):
        FREQ = 2_000_000        #our frequency to generate (SCLK)
        FREQ_HI = 20_000_000
        FREQ_HI_RD = 20_000_000
        CS_PIN=20
        CLK_PIN=21
        SIDESET_PINS = 21  # cs:GP20, sck:GP21
        BASE_PINS = 2   # TX,DIO0:GP2, RX,DIO1:GP3, DIO2:GP4, DIO3:GP5
        SPI_OUT_BASE_PIN = 2
        SPI_IN_BASE_PIN = 3

        # PIO definition
        @rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW, out_init=rp2.PIO.OUT_HIGH)
        def spiwrite_one():
            wrap_target()       #2
            pull()  .side(0)    #3  data
            set(x, 7)           #4  8bit (byte)
            label("BYTE")
            out(pins, 1).side(0)#5
            jmp(x_dec, "BYTE").side(1)       #6: CLK = HI  (tSA = 1clk, tHD = 1clk)
            push().side(0)              #7
            wrap()

        @rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW, out_init=(rp2.PIO.OUT_HIGH,rp2.PIO.OUT_HIGH,rp2.PIO.OUT_HIGH,rp2.PIO.OUT_HIGH))
        def spiwrite_quad():
            wrap_target()
            pull()  .side(0)    #9  length - 1(in byte)
            mov(y, osr)         #10
            label("LOOP")
            pull()  .side(0)    #11 data(byte (MSB))
            set(x, 1)           #12 2cycle (8bit)
            label("WORD")
            out(pins, 4).side(0)   #13
            jmp(x_dec, "WORD").side(1)#14
            jmp(y_dec, "LOOP").side(0)#16
            push(noblock)                  #15
            wrap()
            
        @rp2.asm_pio(push_thresh=8, autopull=False, autopush=False,sideset_init=rp2.PIO.OUT_LOW, set_init=(rp2.PIO.OUT_HIGH, rp2.PIO.OUT_HIGH, rp2.PIO.OUT_HIGH, rp2.PIO.OUT_HIGH))
        def spiread_quad():
            wrap_target()
            pull()    #18 length - 1(in byte)
            set(pindirs, 0)     #17
            mov(y, osr).side(0)         #19
            label("ALL_LOOP")
            in_(pins, 4)	.side(1)#21
            mov(x,x) .side(0)
            in_(pins, 4)	.side(1)#21
            push()
            jmp(y_dec, "ALL_LOOP").side(0) #24
            set(pindirs, 0xf)     #8

            wrap()
        if not cls.sm_init_flag:
            cls.sm_init_flag = True
            cls.sm_spi_wr = rp2.StateMachine(0, spiwrite_one, freq=FREQ, sideset_base=Pin(CLK_PIN), out_base=Pin(SPI_OUT_BASE_PIN))
            cls.sm_qspi_wr = rp2.StateMachine(1, spiwrite_quad, freq=FREQ_HI, sideset_base=Pin(CLK_PIN), out_base=Pin(BASE_PINS))
            cls.sm_qspi_rd = rp2.StateMachine(2, spiread_quad, freq=FREQ_HI_RD, sideset_base=Pin(CLK_PIN), in_base=Pin(BASE_PINS),set_base=Pin(BASE_PINS))

            cls.sm_spi_wr.active(1)
            cls.sm_qspi_wr.active(1)
            cls.sm_qspi_rd.active(1)
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


    
    def spi_write(self, data):
        for b in data:
            self.sm_spi_wr.put(int(b), 24)
            self.sm_spi_wr.get()

    
    def qspi_write(self, data):
        self.sm_qspi_wr.put(len(data) - 1)
        for i in range(len(data)):
            val = data[i]
            self.sm_qspi_wr.put(val,24)
        self.sm_qspi_wr.get()

    
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


    def readblocks(self, block_num, buf):
        nblocks = len(buf) // 512
        mv = memoryview(buf)
        for i in range(nblocks):
            offset = i * 512
            self.psram_readinto_quad(block_num * 512 + offset, mv[offset + 0:offset + 512])

    def writeblocks(self, block_num, buf):
        nblocks = len(buf) // 512
        mv = memoryview(buf)
        for i in range(nblocks):
            offset = i * 512
            self.psram_write_quad(block_num * 512 + offset, mv[offset + 0:offset + 512])

    def ioctl(self, op, arg):
        if op == 4:  # get number of blocks
            return self.sectors
        if op == 5:  # get block size in bytes
            return 512
        return 0

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
            uos.VfsFat.mkfs(psramdisk)
            uos.mount(psramdisk, point)
            print("Mount new filesystem:"+point)

mount()
