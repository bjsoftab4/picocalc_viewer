
#include "../../JPEGDEC/src/JPEGDEC.h"
#include "../../JPEGDEC/src/jpeg.inl"

volatile uint8_t core1_running = 0;     // 0: stop, 1: run, 2: done
void *JPEGdummy = {readFLASH};          // to avoid compiler error
static uint16_t disp_height, disp_width;
static int docode_result;
static JPEGIMAGE _jpeg;
static uint8_t Coremode = 0;

#define CORE1_STACK_SIZE 1024
extern uint32_t core1_stack[];

/* defined in picocalcdisplay.c */
void JPEGUpdate(uint16_t *pBuf, uint16_t x,  uint16_t y,  uint16_t w,  uint16_t h);
uint8_t JPEGGetMode();
void JPEGSetDrawPage(uint8_t page);
uint8_t JPEGGetDrawPage();
void JPEGSetViewPage(uint8_t page);
uint8_t JPEGGetViewPage();
void JPEGModeStart(uint8_t mode);
void JPEGModeChange(uint8_t mode);
void JPEGModeEnd();
void JPEGWaitDma();
uint8_t *JPEGGetFramebuffer();
void JPEGGetDisp(uint16_t *w, uint16_t *h);
void JPEGClearScreen(uint8_t mode);


int core1_decode_is_busy();

/* callback funtion from JPEGDEC */
static int JPEGDraw(JPEGDRAW *pDraw) {
    uint16_t *pBuf1 = pDraw->pPixels;
    mp_int_t x = pDraw->x;
    mp_int_t y = pDraw->y;
    mp_int_t w = pDraw->iWidth;
    mp_int_t h = pDraw->iHeight;
    JPEGUpdate(pBuf1, x, y, w, h);
    return 1;
}


static int JPEGDrawx2(JPEGDRAW *pDraw) {
    #if 0 // under construction
    uint16_t *pBuf1 = pDraw->pPixels;
    mp_int_t x = pDraw->x;
    mp_int_t y = pDraw->y;
    mp_int_t w = pDraw->iWidth;
    mp_int_t h = pDraw->iHeight;
    uint16_t *pBuf2 = m_malloc(sizeof(uint16_t) * disp_width);

    mp_int_t x2, y2;
    x2 = MIN(disp_width, x * 2 + w * 2);
    y2 = MIN(disp_height, y * 2 + h * 2);

    int hmax = disp_height / 2;
    int wmax = disp_width / 2;
    hmax = MIN(hmax,  h);
    wmax = MIN(wmax,  w);
    uint16_t *src, *dst;
    for (int ln = 0; ln < hmax; ln++) {
        src = (uint16_t *)pBuf1 + w * ln;
        dst = (uint16_t *)pBuf2;
        for (int ro = 0; ro < wmax; ro++) {
            *dst++ = *src;
            *dst++ = *src++;
        }
        const int buf_size = 4096;
        int limit = wmax * 2 * 2;               // width * 2(pixel) * 2(uint16)
        int chunks = limit / buf_size;
        int rest = limit % buf_size;
        for (int j = 0; j < 2; j++) {
            int i = 0;
            const uint8_t *ptr = (const uint8_t *)pBuf2;
            for (; i < chunks; i++) {
//		        write_spi(self->spi_obj, ptr + i * buf_size, buf_size);
            }
            if (rest) {
//		        write_spi(self->spi_obj, ptr + i * buf_size, rest);
            }
        }
    }
    m_free(pBuf2);
    #endif
    return 1;
}

static void jpeg_param_init(JPEGIMAGE *pJpeg, int iDataSize, uint8_t *pData, JPEG_DRAW_CALLBACK func) {
    JPEGGetDisp(&disp_width, &disp_height);
    memset((void *)pJpeg, 0, sizeof(JPEGIMAGE));
    pJpeg->ucMemType = JPEG_MEM_RAM;
    pJpeg->pfnRead = readRAM;
    pJpeg->pfnSeek = seekMem;
    pJpeg->pfnDraw = func;
    pJpeg->pfnOpen = NULL;
    pJpeg->pfnClose = NULL;
    pJpeg->pUser = NULL;
    pJpeg->iError = 1111;
    pJpeg->JPEGFile.iSize = iDataSize;
    pJpeg->JPEGFile.pData = pData;
    pJpeg->ucPixelType = RGB565_BIG_ENDIAN;
    pJpeg->iMaxMCUs = 1000; // set to an unnaturally high value to start
}

static mp_obj_t jpegdec_decodex2(size_t n_args, const mp_obj_t *args) {
    int result;
    mp_buffer_info_t inbuf;

    mp_get_buffer_raise(args[0], &inbuf, MP_BUFFER_READ);
    int iDataSize = inbuf.len;
    uint8_t *pData = (uint8_t *)inbuf.buf;

//	int drawmode = mp_obj_get_int(args[1]);	// mode 0:simple, 1:flip screen

    jpeg_param_init(&_jpeg, iDataSize, pData, JPEGDrawx2);
    result = JPEGInit(&_jpeg);
    if (result == 1) {
        _jpeg.iOptions = JPEG_USES_DMA;
        JPEG_setCropArea(&_jpeg, 0, 0, disp_width / 2, disp_height / 2);
        result = DecodeJPEG(&_jpeg);
    }
    mp_obj_t res[3] = {
        mp_obj_new_int(result),
        mp_obj_new_int(_jpeg.iWidth),
        mp_obj_new_int(_jpeg.iHeight)
    };

    return mp_obj_new_tuple(3, res);
    // if( result == 0) result = _jpeg.iError;
    // return mp_obj_new_int(result);

}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(jpegdec_decodex2_obj, 2, 2, jpegdec_decodex2);
#define FIFO_CMD_DONE (0xffff0ff0)

uint32_t JPEG_msg_core1;

int core1_decode_is_busy() {
    uint32_t result;
    bool flag;
    if (core1_running == 1) {
        return 1;
    }
    result = 0;
    flag = multicore_fifo_pop_timeout_us(100, &result);    // wait 100us
    if (flag) {
        JPEG_msg_core1 = result;
    } else {
        // JPEG_msg_core1 = 0xff;
    }
    return 0;
}


static int decode_core1_prepare(int drawmode, JPEGIMAGE *pJpeg, int iDataSize, uint8_t *pData, JPEG_DRAW_CALLBACK func) {
    int result;
    jpeg_param_init(pJpeg, iDataSize, pData, func);
    result = JPEGInit(&_jpeg);
    if (result == 1) {
        _jpeg.iOptions = JPEG_USES_DMA;
        JPEG_setCropArea(&_jpeg, 0, 0, disp_width, disp_height);
        if (drawmode == 0) {
            JPEGModeChange(0);
        } else if (drawmode == 1 || drawmode == 2) {
            JPEGModeChange(1);
            JPEGSetDrawPage(drawmode);
        }
    }
    return result;
}

void decode_core1_main() {
    multicore_lockout_victim_init();
    core1_running = 1;
    docode_result = DecodeJPEG(&_jpeg);
    JPEGWaitDma();
    //uint8_t pageNum = JPEGGetDrawPage();
    //JPEGSetViewPage(pageNum);

    core1_running = 2;
    multicore_fifo_push_timeout_us(FIFO_CMD_DONE, 1000);    // wait 1000us
}
void decode_core0_main() {
    core1_running = 1;
    docode_result = DecodeJPEG(&_jpeg);
    JPEGWaitDma();
    uint8_t pageNum = JPEGGetDrawPage();
    JPEGSetViewPage(pageNum);

    core1_running = 2;
    multicore_fifo_push_timeout_us(FIFO_CMD_DONE, 1000);    // wait 1000us
}


static void decode_core1_body(JPEGIMAGE *pJpeg, int core) {
    while (core1_decode_is_busy()) {
        tight_loop_contents();
    }
    if (core == 0) {
        decode_core0_main();
    } else {
        multicore_reset_core1();
        multicore_launch_core1_with_stack(decode_core1_main, core1_stack, CORE1_STACK_SIZE);
    }

    // for core0 //docode_result = DecodeJPEG(&_jpeg);
}


static mp_obj_t jpegdec_decode_core(size_t n_args, const mp_obj_t *args) {
    int result;
    mp_buffer_info_t inbuf;

    mp_get_buffer_raise(args[0], &inbuf, MP_BUFFER_READ);
    int iDataSize = inbuf.len;
    uint8_t *pData = (uint8_t *)inbuf.buf;

    int drawmode = mp_obj_get_int(args[1]);     // mode 0:simple, 1:draw page1, 2:draw page2
    int run_core = 0;
    if (n_args >= 3) {
        run_core = mp_obj_get_int(args[2]);             // mode 0:single core, 1:core1
    }
    int ofst_x = 0, ofst_y = 0;
    mp_obj_t *tuple_data = NULL;
    size_t tuple_len = 0;
    if (n_args >= 4 ) {
        if (args[3] != mp_const_none)  {
            mp_obj_tuple_get(args[3], &tuple_len, &tuple_data);
            if (tuple_len >= 2) {
                ofst_x = mp_obj_get_int(tuple_data[0]);
                ofst_y = mp_obj_get_int(tuple_data[1]);
            }
        }
    }
    Coremode = (uint8_t)(run_core);
    while (core1_decode_is_busy()) {
        tight_loop_contents();
    }
    if (core1_running == 2) {
        result = docode_result;
        core1_running = 0;
    }

    result = decode_core1_prepare(drawmode, &_jpeg, iDataSize, pData, JPEGDraw);
    if(result == 1) {
        _jpeg.iXOffset = ofst_x;
        _jpeg.iYOffset = ofst_y;
        decode_core1_body(&_jpeg, run_core);
    }

    mp_obj_t res[3] = {
        mp_obj_new_int(result),
        mp_obj_new_int(_jpeg.iWidth),
        mp_obj_new_int(_jpeg.iHeight),
    };

    return mp_obj_new_tuple(3, res);
    // if( result == 0) result = _jpeg.iError;
    // return mp_obj_new_int(result);

}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(jpegdec_decode_core_obj, 2, 4, jpegdec_decode_core);


static mp_obj_t jpegdec_decode_core_stat(size_t n_args, const mp_obj_t *args) {
    int result =  (int)core1_running;
    mp_obj_t res[1] = {
        mp_obj_new_int(result),
    };
    return mp_obj_new_tuple(1, res);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(jpegdec_decode_core_stat_obj, 0, 0, jpegdec_decode_core_stat);

static mp_obj_t jpegdec_decode_core_wait(size_t n_args, const mp_obj_t *args) {
    int result = 1;
    int res1 = 0;
    int res2 = 0;
    int timeout;
    if (n_args == 1) {          // force stop
        timeout = mp_obj_get_int(args[0]);
    } else {
        timeout = 1000;
    }
    for ( ; timeout >= 0; timeout --) {
        if (core1_decode_is_busy() == 0) {
            break;
        }
        sleep_ms(1);
    }
    if (timeout < 0) {
        if (Coremode == 1) {
            multicore_reset_core1();
            core1_running = 0;
            result = 0;
        }
    } 
    if (core1_running == 2) {
        uint8_t pageNum = JPEGGetDrawPage();
        JPEGSetViewPage(pageNum);
        result = docode_result;
        core1_running = 0;
    }
    int res3 = (int)core1_running;
    mp_obj_t res[4] = {
        mp_obj_new_int(result),
        mp_obj_new_int(res1),
        mp_obj_new_int(res2),
        mp_obj_new_int(res3),
    };

    return mp_obj_new_tuple(4, res);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(jpegdec_decode_core_wait_obj, 0, 1, jpegdec_decode_core_wait);


static mp_obj_t jpegdec_decode(size_t n_args, const mp_obj_t *args) {
    int result;
    mp_buffer_info_t inbuf;

    mp_get_buffer_raise(args[0], &inbuf, MP_BUFFER_READ);
    int iDataSize = inbuf.len;
    uint8_t *pData = (uint8_t *)inbuf.buf;

    int drawmode = mp_obj_get_int(args[1]);     // mode 0:simple, 1:flip screen
    result = decode_core1_prepare(drawmode, &_jpeg, iDataSize, pData, JPEGDraw);
    if(result == 1) {
        result = DecodeJPEG(&_jpeg);
        JPEGWaitDma();
        uint8_t pageNum = JPEGGetDrawPage();
        JPEGSetViewPage(pageNum);
    }

    mp_obj_t res[3] = {
        mp_obj_new_int(result),
        mp_obj_new_int(_jpeg.iWidth),
        mp_obj_new_int(_jpeg.iHeight)
    };

    return mp_obj_new_tuple(3, res);
    // if( result == 0) result = _jpeg.iError;
    // return mp_obj_new_int(result);

}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(jpegdec_decode_obj, 2, 2, jpegdec_decode);

// decode_opt runs with multicore
static mp_obj_t jpegdec_decode_opt(size_t n_args, const mp_obj_t *args) {
    int result;
    mp_buffer_info_t inbuf;

    mp_get_buffer_raise(args[0], &inbuf, MP_BUFFER_READ);
    int iDataSize = inbuf.len;
    uint8_t *pData = (uint8_t *)inbuf.buf;

    int ofst_x = 0, ofst_y = 0, clip_x = 0, clip_y = 0, clip_w = disp_width, clip_h = disp_height;
    int ioption = 0;
    // get tuple
    mp_obj_t *tuple_data = NULL;
    size_t tuple_len = 0;
    if (n_args >= 2) {
        mp_obj_tuple_get(args[1], &tuple_len, &tuple_data);
        if (tuple_len >= 2) {
            ofst_x = mp_obj_get_int(tuple_data[0]);
            ofst_y = mp_obj_get_int(tuple_data[1]);
        }
    }
    if (n_args >= 3) {
        mp_obj_tuple_get(args[2], &tuple_len, &tuple_data);
        if (tuple_len >= 4) {
            clip_x = mp_obj_get_int(tuple_data[0]);
            clip_y = mp_obj_get_int(tuple_data[1]);
            clip_w = mp_obj_get_int(tuple_data[2]);
            clip_h = mp_obj_get_int(tuple_data[3]);
        }
    }
    if (n_args >= 4) {
        ioption = mp_obj_get_int(args[3]);
    }

    jpeg_param_init(&_jpeg, iDataSize, pData, JPEGDraw);
    result = JPEGInit(&_jpeg);
    if (result == 1) {
        _jpeg.iXOffset = ofst_x;
        _jpeg.iYOffset = ofst_y;
        _jpeg.iOptions = ioption | JPEG_USES_DMA;
        JPEG_setCropArea(&_jpeg, clip_x, clip_y, clip_w, clip_h);
        result = DecodeJPEG(&_jpeg);
        JPEGWaitDma();
    }

    mp_obj_t res[3] = {
        mp_obj_new_int(result),
        mp_obj_new_int(_jpeg.iWidth),
        mp_obj_new_int(_jpeg.iHeight)
    };

    return mp_obj_new_tuple(3, res);
    // if( result == 0) result = _jpeg.iError;
    // return mp_obj_new_int(result);

}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(jpegdec_decode_opt_obj, 1, 4, jpegdec_decode_opt);

// decode_split runs with multicore
#define FBUFFER_MAX (2)
#define INVALID_MESSAGE (0xffffffff)
volatile struct st_filebuffer {
    int32_t pos;
    int32_t size;               // if size == 0, this buffer is useless
    uint8_t *pbuf;
} JPEG_fbuffer[FBUFFER_MAX];

volatile uint32_t core_message_box;
volatile uint32_t core_message_box2;
volatile uint32_t core_message_box3;

uint32_t get_message_box() {
    return core_message_box;
}

void set_message_box(uint32_t msg) {
    core_message_box = msg;
}

uint32_t get_message_box2() {
    return core_message_box2;
}

void set_message_box2(uint32_t msg) {
    core_message_box2 = msg;
}

uint32_t get_message_box3() {
    return core_message_box3;
}

void set_message_box3(uint32_t msg) {
    core_message_box3 = msg;
}


void init_fbuffer() {
    int i;
    for ( i = 0; i < FBUFFER_MAX; i++) {
        JPEG_fbuffer[i].size = 0;
    }
    set_message_box(INVALID_MESSAGE);
}

void set_fbuffer(uint32_t bufnum, uint32_t pos, uint8_t *pbuf, uint32_t size) {
    if (bufnum < FBUFFER_MAX) {
        JPEG_fbuffer[bufnum].pos = pos;
        JPEG_fbuffer[bufnum].pbuf = pbuf;
        JPEG_fbuffer[bufnum].size = size;               // set size at last
    }
}
#if 0
// buffer     |bufpos         |+bufLen             |
// request        |iPos       |+iLen                    return i
// request        |iPos          |+iLen                 return 0x200 + i
#endif
static int testAndSetBuffer(int32_t *p_iPos, int32_t *p_iLen, uint8_t **p_dstBuf) {
    int i;
    int retc = -1;
    int32_t bufPos, bufLen;
    //int32_t bufPos2, bufLen2;

    int32_t iPos = *p_iPos, iLen = *p_iLen;
    uint8_t *dstBuf = *p_dstBuf;

    for ( i = 0; i < FBUFFER_MAX; i++) {
        if (JPEG_fbuffer[i].size == 0) {
            continue;
        }
        bufPos = JPEG_fbuffer[i].pos;
        bufLen = JPEG_fbuffer[i].size;
        if (bufPos <= iPos) {
            if (iPos + iLen <= bufPos + bufLen) {
                memcpy(dstBuf, JPEG_fbuffer[i].pbuf + (iPos - bufPos), iLen);
                *p_dstBuf += iLen;
                iPos += iLen;
                iLen = 0;
                *p_iPos = iPos;
                *p_iLen = iLen;
                retc = i;                // normal end
                return retc;
            }
            if (iPos < bufPos + bufLen) {   // found 1st part
                int32_t size_1st = bufPos + bufLen - iPos;
                memcpy(dstBuf, JPEG_fbuffer[i].pbuf + (iPos - bufPos), size_1st);
                dstBuf += size_1st;
                iPos += size_1st;
                iLen -= size_1st;
                JPEG_fbuffer[i].size = 0;       // buffer i is empty
                *p_dstBuf = dstBuf;
                *p_iPos = iPos;             // set new iPos, iLen
                *p_iLen = iLen;
                retc = 0x200 | i;           // i is empty and need reading
                return retc;
            }
        }
    }
    return retc;
}

static int32_t readRAM_split(JPEGFILE *pFile, uint8_t *pBuf, int32_t iLen) {
    int rc;
    int iBytesRead;
    int32_t iPos = pFile->iPos;
    int32_t iLen_sav = iLen;
    
    do {
        rc = testAndSetBuffer(&iPos, &iLen, &pBuf);
        if (rc < 0){
            set_message_box3(-1);
            set_message_box2(iLen);
            set_message_box(iPos);
            sleep_ms(0);
            continue;
        }
        if( (rc & 0x200) != 0) {          // copied only 1st part
            set_message_box3(rc);
            set_message_box2(iLen);     // request new buffer
            set_message_box(iPos);
            sleep_ms(0);
            rc = -1;
            continue;
        }
    } while (rc < 0);

    // return used buffer, or inform buffer empty
    set_message_box3(rc);
    set_message_box2(0);         // inform next iPos
    set_message_box(iPos);
    iBytesRead = iLen_sav;
    pFile->iPos += iLen_sav;
    return iBytesRead;
} /* readRAM_split() */

#if 0
static int32_t readRAM_split(JPEGFILE *pFile, uint8_t *pBuf, int32_t iLen) {
    uint8_t *pFilebuf;
    int rc;
    int offset, iBytesRead;

    set_message_box2(iLen);
    set_message_box(pFile->iPos);
    while ((rc = testBuffer(pFile->iPos, iLen)) < 0) {
        sleep_ms(0);
    }

    pFilebuf = JPEG_fbuffer[rc].pbuf;
    offset = pFile->iPos - JPEG_fbuffer[rc].pos;
    iBytesRead = iLen;
    memcpy(pBuf, &pFilebuf[offset], iBytesRead);
    pFile->iPos += iBytesRead;
    return iBytesRead;
} /* readRAM_split() */
#endif

static int32_t seekMem_split(JPEGFILE *pFile, int32_t iPosition) {
    if (iPosition < 0) {
        iPosition = 0;
    } else if (iPosition >= pFile->iSize) {
        iPosition = pFile->iSize - 1;
    }
    pFile->iPos = iPosition;
    return iPosition;
} /* seekMem_split() */

static void jpeg_param_init_split(JPEGIMAGE *pJpeg, int iDataSize, uint8_t *pData, JPEG_DRAW_CALLBACK func) {
    jpeg_param_init(pJpeg, iDataSize, pData, func);
    pJpeg->pfnRead = readRAM_split;
    pJpeg->pfnSeek = seekMem_split;
}

void decode_core1_split() {
    multicore_lockout_victim_init();
    core1_running = 1;
    docode_result = DecodeJPEG(&_jpeg);
    JPEGWaitDma();
    core1_running = 2;
}

static mp_obj_t jpegdec_decode_split_wait(size_t n_args, const mp_obj_t *args) {
    int result = 0;
    int res1 = INVALID_MESSAGE;
    int res2 = 0;
    int res3 = 0;
    if (core1_running == 1) {   // core1 is running
        res1 = get_message_box();
        res2 = get_message_box2();
        res3 = get_message_box3();
        if (res1 != INVALID_MESSAGE) {
            set_message_box(INVALID_MESSAGE);
        }
    } else if (core1_running == 2) {    // core1 done
        res2 = (int)JPEG_msg_core1;     // core1 result
        res1 = docode_result;
        core1_running = 0;
        result = 1;
    } else {                            // core1 does nothing
        result = 1;
    }
    mp_obj_t res[4] = {
        mp_obj_new_int(result), // 0: running, 1: done
        mp_obj_new_int(res1),   // if result==0 : message_box(required filepointer)
                                // if result==1 : core1 decode result
        mp_obj_new_int(res2),    // if result==0 : message_box(required datasize)
        mp_obj_new_int(res3),    // if result==0 : message_box(index information)
    };

    return mp_obj_new_tuple(4, res);

}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(jpegdec_decode_split_wait_obj, 0, 0, jpegdec_decode_split_wait);

static mp_obj_t jpegdec_decode_split_buffer(size_t n_args, const mp_obj_t *args) {
    // buffer num, filepointer, buffer
    mp_buffer_info_t inbuf;
    int result = 0;

    int bufnum = mp_obj_get_int(args[0]);
    int filepos = mp_obj_get_int(args[1]);
    if (bufnum < FBUFFER_MAX) {
        mp_get_buffer_raise(args[2], &inbuf, MP_BUFFER_READ);
        set_fbuffer(bufnum, filepos, (uint8_t *)inbuf.buf, inbuf.len);
        result = 1;
    }

    mp_obj_t res[1] = {
        mp_obj_new_int(result),
    };

    return mp_obj_new_tuple(1, res);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(jpegdec_decode_split_buffer_obj, 3, 3, jpegdec_decode_split_buffer);

static mp_obj_t jpegdec_decode_split(size_t n_args, const mp_obj_t *args) {
    // args[0] filesize, args[1] buf, [ args[2] ofset, args[3] clip, args[4] option ]
    int result = 0;
    int result0 = -1;
    mp_buffer_info_t inbuf;

    mp_obj_t *tuple_data = NULL;
    size_t tuple_len = 0;
    int fileSize;

    while (core1_decode_is_busy()) {
        tight_loop_contents();
    }
    if (core1_running == 2) {
        result0 = docode_result;
        core1_running = 0;
    }

    init_fbuffer();

    fileSize = mp_obj_get_int(args[0]);
    mp_get_buffer_raise(args[1], &inbuf, MP_BUFFER_READ);
    set_fbuffer(0, 0, (uint8_t *)inbuf.buf, inbuf.len);

    bool f_clip = false;
    int ofst_x = 0, ofst_y = 0, clip_x, clip_y, clip_w, clip_h;
    int ioption = 0;
    // get tuple
    if (n_args >= 3) {
        if (args[2] != mp_const_none) {
            mp_obj_tuple_get(args[2], &tuple_len, &tuple_data);
            if (tuple_len >= 2) {
                ofst_x = mp_obj_get_int(tuple_data[0]);
                ofst_y = mp_obj_get_int(tuple_data[1]);
            }
        }
    }
    if (n_args >= 4) {
        if (args[3] != mp_const_none) {
            mp_obj_tuple_get(args[3], &tuple_len, &tuple_data);
            if (tuple_len >= 4) {
                f_clip = true;
                clip_x = mp_obj_get_int(tuple_data[0]);
                clip_y = mp_obj_get_int(tuple_data[1]);
                clip_w = mp_obj_get_int(tuple_data[2]);
                clip_h = mp_obj_get_int(tuple_data[3]);
            }
        }
    }
    if (n_args >= 5) {
        ioption = mp_obj_get_int(args[4]);
    }


    jpeg_param_init_split(&_jpeg, fileSize, inbuf.buf, JPEGDraw);
    result = JPEGInit(&_jpeg);
    if (result == 1) {
        _jpeg.iXOffset = ofst_x;
        _jpeg.iYOffset = ofst_y;
        _jpeg.iOptions = ioption | JPEG_USES_DMA;
        if (f_clip) {
            JPEG_setCropArea(&_jpeg, clip_x, clip_y, clip_w, clip_h);
        }
        JPEGModeChange(0);

        multicore_reset_core1();
        multicore_launch_core1_with_stack(decode_core1_split, core1_stack, CORE1_STACK_SIZE);
    }

    mp_obj_t res[4] = {
        mp_obj_new_int(result),
        mp_obj_new_int(_jpeg.iWidth),
        mp_obj_new_int(_jpeg.iHeight),
        mp_obj_new_int(result0),
    };

    return mp_obj_new_tuple(4, res);
    // if( result == 0) result = _jpeg.iError;
    // return mp_obj_new_int(result);

}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(jpegdec_decode_split_obj, 2, 5, jpegdec_decode_split);

static mp_obj_t jpegdec_start(size_t n_args, const mp_obj_t *args) {
    int drawmode = mp_obj_get_int(args[0]);     // mode 0:simple, 1:flip screen
    uint8_t old_mode = JPEGGetMode();
    JPEGModeStart(drawmode);

    return mp_obj_new_int((int)old_mode);

    // if( result == 0) result = _jpeg.iError;
    // return mp_obj_new_int(result);

}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(jpegdec_start_obj, 1, 1, jpegdec_start);

static mp_obj_t jpegdec_end(size_t n_args, const mp_obj_t *args) {
    int result = 1;
    JPEGModeEnd();
    mp_obj_t res[1] = {
        mp_obj_new_int(result),
    };

    return mp_obj_new_tuple(1, res);
}

static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(jpegdec_end_obj, 0, 0, jpegdec_end);

static mp_obj_t jpegdec_clear(size_t n_args, const mp_obj_t *args) {
    int drawmode = (int)JPEGGetMode();
    if (n_args == 1) {
        drawmode = mp_obj_get_int(args[0]);     // mode 0:simple, 1:flip screen
    }
    JPEGClearScreen(drawmode);

    return mp_obj_new_int(1);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(jpegdec_clear_obj, 0, 1, jpegdec_clear);

static mp_obj_t jpegdec_setview(size_t n_args, const mp_obj_t *args) {
    int result = 1;
    int view = mp_obj_get_int(args[0]);         // mode 0:simple, 1:flip screen

    JPEGSetViewPage((uint8_t)view);
    mp_obj_t res[1] = {
        mp_obj_new_int(result),
    };

    return mp_obj_new_tuple(1, res);
}

static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(jpegdec_setview_obj, 1, 1, jpegdec_setview);


static mp_obj_t jpegdec_getinfo(size_t n_args, const mp_obj_t *args) {
    int result;

    mp_buffer_info_t inbuf;
    mp_get_buffer_raise(args[0], &inbuf, MP_BUFFER_READ);
    int iDataSize = inbuf.len;
    uint8_t *pData = (uint8_t *)inbuf.buf;
    // mt_lock = -1;
    while (core1_decode_is_busy()) {
        tight_loop_contents();
    }

    jpeg_param_init(&_jpeg, iDataSize, pData, JPEGDraw);
    result = JPEGInit(&_jpeg);
    mp_obj_t res[6] = {
        mp_obj_new_int(result),
        mp_obj_new_int(_jpeg.iWidth),
        mp_obj_new_int(_jpeg.iHeight),
        mp_obj_new_int((int)(&_jpeg)),
        mp_obj_new_int((int)(JPEGGetFramebuffer())),
        mp_obj_new_int((int)(JPEGGetDrawPage())),
    };
    return mp_obj_new_tuple(6, res);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(jpegdec_getinfo_obj, 1, 1, jpegdec_getinfo);
#if 0
static mp_obj_t jpegdec_getdebuginfo(size_t n_args, const mp_obj_t *args) {
    int result;
    mp_buffer_info_t inbuf;
    mp_get_buffer_raise(args[0], &inbuf, MP_BUFFER_READ);
    int iDataSize = inbuf.len;
    uint8_t *pData = (uint8_t *)inbuf.buf;
    {
        mp_obj_t res[5];
        res[0] = mp_obj_new_int(8);
        res[1] = mp_obj_new_int((int)(pData));
        res[2] = mp_obj_new_int((int)(&_jpeg));
        res[3] = mp_obj_new_int((int)(&jpegdec_getinfo));
        return mp_obj_new_tuple(4, res);
    }
    jpeg_param_init(&_jpeg, iDataSize, pData, JPEGDraw);
    if (pData[12] == 0) {
        mp_obj_t res[5];
        res[0] = mp_obj_new_int(9);
        res[1] = mp_obj_new_int((int)(pData));
        res[2] = mp_obj_new_int((int)(&_jpeg));
        return mp_obj_new_tuple(3, res);
    }
    result = JPEGInit(&_jpeg);
    mp_obj_t res[5];
    res[0] = mp_obj_new_int(result);
    res[1] = mp_obj_new_int(_jpeg.iWidth);
    res[2] = mp_obj_new_int(_jpeg.iHeight);
    res[3] = mp_obj_new_int(_jpeg.iError);
    res[4] = mp_obj_new_int((int)(_jpeg.pFramebuffer));
    return mp_obj_new_tuple(5, res);
}

static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(jpegdec_getinfo_obj, 1, 1, jpegdec_getinfo);
#endif
static const mp_rom_map_elem_t jpegdec_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_jpegdec) },
//    {MP_ROM_QSTR(MP_QSTR_init), MP_ROM_PTR(&jpegdec_init_obj)},
    {MP_ROM_QSTR(MP_QSTR_start), MP_ROM_PTR(&jpegdec_start_obj)},
    {MP_ROM_QSTR(MP_QSTR_end), MP_ROM_PTR(&jpegdec_end_obj)},
    {MP_ROM_QSTR(MP_QSTR_clear), MP_ROM_PTR(&jpegdec_clear_obj)},
    {MP_ROM_QSTR(MP_QSTR_getinfo), MP_ROM_PTR(&jpegdec_getinfo_obj)},
    {MP_ROM_QSTR(MP_QSTR_decode), MP_ROM_PTR(&jpegdec_decode_obj)},
    {MP_ROM_QSTR(MP_QSTR_decodex2), MP_ROM_PTR(&jpegdec_decodex2_obj)},
    {MP_ROM_QSTR(MP_QSTR_decode_core), MP_ROM_PTR(&jpegdec_decode_core_obj)},
    {MP_ROM_QSTR(MP_QSTR_decode_opt), MP_ROM_PTR(&jpegdec_decode_opt_obj)},
    {MP_ROM_QSTR(MP_QSTR_decode_core_wait), MP_ROM_PTR(&jpegdec_decode_core_wait_obj)},
    {MP_ROM_QSTR(MP_QSTR_decode_core_stat), MP_ROM_PTR(&jpegdec_decode_core_stat_obj)},
    {MP_ROM_QSTR(MP_QSTR_decode_split), MP_ROM_PTR(&jpegdec_decode_split_obj)},
    {MP_ROM_QSTR(MP_QSTR_decode_split_wait), MP_ROM_PTR(&jpegdec_decode_split_wait_obj)},
    {MP_ROM_QSTR(MP_QSTR_decode_split_buffer), MP_ROM_PTR(&jpegdec_decode_split_buffer_obj)},
    {MP_ROM_QSTR(MP_QSTR_setview), MP_ROM_PTR(&jpegdec_setview_obj)},
};
static MP_DEFINE_CONST_DICT(jpegdec_globals, jpegdec_globals_table);
/* methods end */

const mp_obj_module_t jpegdec_cmodule = {
    .base = {&mp_type_module},
    .globals = (mp_obj_dict_t *)&jpegdec_globals,
};

MP_REGISTER_MODULE(MP_QSTR_jpegdec, jpegdec_cmodule);
