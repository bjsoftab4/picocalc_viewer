
#include "../../JPEGDEC/src/JPEGDEC.h"
#include "../../JPEGDEC/src/jpeg.inl"

volatile uint8_t core1_running = 0;     // 0: stop, 1: run, 2: done
void *JPEGdummy = {readFLASH};          // to avoid compiler error
static uint16_t disp_height, disp_width;
static int core1_result;
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
    #if 0 //under construction
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
        _jpeg.iXOffset = 0;
        _jpeg.iYOffset = 0;
        _jpeg.iOptions = 0;
        _jpeg.iOptions = JPEG_USES_DMA;
        _jpeg.ucPixelType = RGB565_BIG_ENDIAN;
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

int core1_decode_is_busy() {
    if (core1_running == 1) {
        return 1;
    }
    return 0;
}

static int decode_core1_epilogue() {
//	int drawmode = (int)JPEGGetMode();
    while (core1_decode_is_busy()) {
        tight_loop_contents();
    }
//	if(drawmode == 0) {
//	} else if( drawmode == 1) {
//		uint8_t pageNum = JPEGGetDrawPage();
//		JPEGSetViewPage(pageNum);
//	}
    return core1_result;
}

static void decode_core1_prologue(int drawmode, JPEGIMAGE *pJpeg, int iDataSize, uint8_t *pData, JPEG_DRAW_CALLBACK func) {
    int result;
    jpeg_param_init(pJpeg, iDataSize, pData, func);
    result = JPEGInit(&_jpeg);
    if (result == 1) {
        _jpeg.iXOffset = 0;
        _jpeg.iYOffset = 0;
        _jpeg.iOptions = JPEG_USES_DMA;
        _jpeg.ucPixelType = RGB565_BIG_ENDIAN;
        JPEG_setCropArea(&_jpeg, 0, 0, disp_width, disp_height);
        if (drawmode == 0) {
            JPEGModeChange(0);
        } else if (drawmode == 1 || drawmode == 2) {
            JPEGModeChange(1);
            JPEGSetDrawPage(drawmode);
//			uint8_t pageNum = JPEGGetViewPage();
//			if( pageNum == 0 || pageNum == 2) {	// not initialized or page 2
//				JPEGSetDrawPage(1);
//			} else {
//				JPEGSetDrawPage(2);
//			}
        }
    }
}

void decode_core1_main() {
    multicore_lockout_victim_init();
    core1_running = 1;
    core1_result = DecodeJPEG(&_jpeg);
    JPEGWaitDma();
    uint8_t pageNum = JPEGGetDrawPage();
    JPEGSetViewPage(pageNum);

    core1_running = 2;
}
void decode_core0_main() {
    core1_running = 1;
    core1_result = DecodeJPEG(&_jpeg);
    JPEGWaitDma();
    uint8_t pageNum = JPEGGetDrawPage();
    JPEGSetViewPage(pageNum);

    core1_running = 2;
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

    // for core0 //core1_result = DecodeJPEG(&_jpeg);
}


static mp_obj_t jpegdec_decode_core(size_t n_args, const mp_obj_t *args) {
    int result;
    mp_buffer_info_t inbuf;

    mp_get_buffer_raise(args[0], &inbuf, MP_BUFFER_READ);
    int iDataSize = inbuf.len;
    uint8_t *pData = (uint8_t *)inbuf.buf;

    int drawmode = mp_obj_get_int(args[1]);     // mode 0:simple, 1:draw page1, 2:draw page2
    int run_core = 0;
    if (n_args == 3) {
        run_core = mp_obj_get_int(args[2]);             // mode 0:single core, 1:core1
    }
    Coremode = (uint8_t)(run_core);
    while (core1_decode_is_busy()) {
        tight_loop_contents();
    }
    if (core1_running == 2) {
        result = decode_core1_epilogue();
        core1_running = 0;
    }

    decode_core1_prologue(drawmode, &_jpeg, iDataSize, pData, JPEGDraw);
    decode_core1_body(&_jpeg, run_core);
    result = 1;
    if (run_core == 0) {
        result = 1;
//		result = decode_core1_epilogue();
    }
    if (run_core == 1) {
        result = 1;
        // result = decode_core1_epilogue();
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
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(jpegdec_decode_core_obj, 2, 3, jpegdec_decode_core);

static mp_obj_t jpegdec_decode_core_wait(size_t n_args, const mp_obj_t *args) {
    int result = 1;
    int res1 = (int)core1_running;
    int res2 = 0;
    if (n_args == 1) {          // force stop
        if (Coremode == 1) {
            multicore_reset_core1();
            result = decode_core1_epilogue();
            core1_running = 0;
        }
    } else {
        while (core1_decode_is_busy()) {
            tight_loop_contents();
        }
        res2 = (int)core1_running;
//		if (core1_running == 2){
        result = decode_core1_epilogue();
        core1_running = 0;
        // }
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

    jpeg_param_init(&_jpeg, iDataSize, pData, JPEGDraw);
    result = JPEGInit(&_jpeg);
    if (result == 1) {
        _jpeg.iXOffset = 0;
        _jpeg.iYOffset = 0;
        _jpeg.iOptions = JPEG_USES_DMA;
        _jpeg.ucPixelType = RGB565_BIG_ENDIAN;
        JPEG_setCropArea(&_jpeg, 0, 0, disp_width, disp_height);
        if (drawmode == 0) {
            JPEGModeChange(0);
            result = DecodeJPEG(&_jpeg);
//			JPEGModeEnd();
        } else if (drawmode == 1) {
            JPEGModeChange(1);
            uint8_t pageNum = JPEGGetViewPage();
            if (pageNum == 0 || pageNum == 2) {                 // not initialized or page 2
                JPEGSetDrawPage(1);
                result = DecodeJPEG(&_jpeg);
                JPEGSetViewPage(1);
            } else {
                JPEGSetDrawPage(2);
                result = DecodeJPEG(&_jpeg);
                JPEGSetViewPage(2);
            }
//			JPEGModeEnd();
        }
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
        _jpeg.ucPixelType = RGB565_BIG_ENDIAN;
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

static mp_obj_t jpegdec_start(size_t n_args, const mp_obj_t *args) {
    int drawmode = mp_obj_get_int(args[0]);     // mode 0:simple, 1:flip screen
    JPEGModeStart(drawmode);

    return mp_obj_new_int((int)&_jpeg);

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
    if ( n_args == 1) {
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
    {MP_ROM_QSTR(MP_QSTR_setview), MP_ROM_PTR(&jpegdec_setview_obj)},
};
static MP_DEFINE_CONST_DICT(jpegdec_globals, jpegdec_globals_table);
/* methods end */


const mp_obj_module_t jpegdec_cmodule = {
    .base = {&mp_type_module},
    .globals = (mp_obj_dict_t *)&jpegdec_globals,
};

MP_REGISTER_MODULE(MP_QSTR_jpegdec, jpegdec_cmodule);
