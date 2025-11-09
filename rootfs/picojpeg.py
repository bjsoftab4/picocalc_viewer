"""wrapper for jpegdec"""

import jpegdec


class PicoJpeg:
    @classmethod
    def decode_opt(cls, buf, offset, crop, ioption):
        return jpegdec.decode_opt(buf, offset, crop, ioption)

    @classmethod
    def getinfo(cls, buf):
        return jpegdec.getinfo(buf)

    @classmethod
    def decode_split(cls, fsize, buf, offset, crop, ioption):
        return jpegdec.decode_split(fsize, buf, offset, crop, ioption)

    @classmethod
    def decode_core_wait(cls, force=None):
        if force is None:
            return jpegdec.decode_core_wait()
        else:
            return jpegdec.decode_core_wait(force)

    @classmethod
    def decode_core(cls, buf, mode, core, offset=None):
        if offset is None:
            return jpegdec.decode_core(buf, mode, core)
        else:
            return jpegdec.decode_core(buf, mode, core, offset)

    @classmethod
    def clear(cls):
        return jpegdec.clear()

    @classmethod
    def decode_split_wait(cls):
        return jpegdec.decode_split_wait()

    @classmethod
    def decode_split_buffer(cls, bufnum, newpos, buf):
        return jpegdec.decode_split_buffer(bufnum, newpos, buf)

    @classmethod
    def start(cls, mode=None):
        if mode is None:
            mode = 0
        return jpegdec.start(mode)

    @classmethod
    def end(cls):
        return jpegdec.end()
