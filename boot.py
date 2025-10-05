import picocalc
from picocalc import PicoDisplay, PicoKeyboard, PicoSD, PicoSpeaker
#from picocalc import PicoDisplay, PicoKeyboard, PicoSpeaker
#from picosd2 import PicoSD2
import os
import vt
import sys
# Separated imports because Micropython is super finnicky
from picocalc_system import run, files, memory, disk

from pye import pye_edit
import framebuf
try:
    #pc_display = PicoDisplay(320, 320,framebuf.RGB565)
    pc_display = PicoDisplay(320, 320)
    #pc_display = PicoDisplay(320, 320,4) # BW
    #pc_display = PicoDisplay(320, 320,5) # 2bit
    #pc_display = PicoDisplay(320, 320,6) # 8bit
    pc_keyboard = PicoKeyboard()
    # Mount SD card to /sd on boot
    #pc_sd = PicoSD()
    pc_sd = PicoSD(baudrate=5_000_000)
    pc_sd.mount()
    pcs_L = PicoSpeaker(26)
    pcs_R = PicoSpeaker(27)
    pc_terminal = vt.vt(pc_display, pc_keyboard, sd=pc_sd())

    _usb = sys.stdout  #

    def usb_debug(msg):
        if isinstance(msg, str):
            _usb.write(msg)
        else:
            _usb.write(str(msg))
        _usb.write('\r\n')
    picocalc.usb_debug = usb_debug

    picocalc.display = pc_display
    picocalc.keyboard = pc_keyboard
    picocalc.terminal = pc_terminal
    picocalc.sd = pc_sd

    def edit(*args, tab_size=2, undo=50):
        #dry the key buffer before editing
        pc_terminal.dryBuffer()
        return pye_edit(args, tab_size=tab_size, undo=undo, io_device=pc_terminal)
    picocalc.edit = edit

    os.dupterm(pc_terminal)
    pc_sd.check_mount()
    #usb_debug("boot.py done.")

except Exception as e:
    import sys
    sys.print_exception(e)
    try:
        os.dupterm(None).write(b"[boot.py error]\n")
    except:
        pass

