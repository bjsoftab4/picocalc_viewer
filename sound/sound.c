#include "py/obj.h"
#include "py/objstr.h"
#include "py/objmodule.h"
#include "py/runtime.h"
#include "py/builtin.h"

#include "pico/stdlib.h"
#include "hardware/pwm.h"
#include "hardware/timer.h"
#include "hardware/clocks.h"
#include "hardware/dma.h"

#define PCM_BUFF_MAX (4)
int16_t *pcm_buff[PCM_BUFF_MAX];
int pcm_size[PCM_BUFF_MAX];
volatile uint8_t  pcm_ridx, pcm_widx;
volatile uint8_t  pcm_ch ;
int pcm_rpos;
//=============================================
// PWM DMA
volatile int8_t PWM_DMA_channel = -1;
volatile int8_t PWM_DMA_channel2 = -1;
volatile int8_t PWM_DMA_timer = -1;
static uint ch_dma, ch2_dma, tm_dma;
volatile int16_t *p_pwm_buffer;
volatile int pwm_buffer_byte;

void pwm_dma_start(int16_t *addr, int size){
    p_pwm_buffer = addr;
    pwm_buffer_byte = size;
    dma_channel_set_read_addr (ch_dma, p_pwm_buffer, false);
    dma_channel_set_trans_count (ch_dma, pwm_buffer_byte / 4, true);
}

uint32_t pwm_dma_get_count(){
    return dma_channel_hw_addr(ch_dma)->transfer_count;
}

void pwm_dma_stop(){
    dma_channel_cleanup (ch_dma);
    dma_channel_cleanup (ch2_dma);
}

void pwm_dma_init(int target_hz){
    //DMA init
    if (PWM_DMA_channel != -1) {
        dma_channel_unclaim((uint)PWM_DMA_channel);
    }
    ch_dma = dma_claim_unused_channel(true);
    PWM_DMA_channel = (int8_t)ch_dma;
    
    if (PWM_DMA_channel2 != -1) {
        dma_channel_unclaim((uint)PWM_DMA_channel2);
    }
    ch2_dma = dma_claim_unused_channel(true);
    PWM_DMA_channel2 = (int8_t)ch2_dma;

    if (PWM_DMA_timer != -1) {
        dma_timer_unclaim((uint)PWM_DMA_timer);
    }
    tm_dma = dma_claim_unused_timer (true);
    PWM_DMA_timer = (int8_t)tm_dma;
    
    // set dma timer
    uint sysclk_hz = clock_get_hz(clk_sys);
    uint base_hz = sysclk_hz >> 16;
    uint numer = target_hz / base_hz;
    uint denom = numer * sysclk_hz / target_hz;
    dma_timer_set_fraction (tm_dma, (uint16_t)numer, (uint16_t)denom);
    
    dma_channel_config config = dma_channel_get_default_config(ch_dma);
    channel_config_set_transfer_data_size(&config, DMA_SIZE_32);
    channel_config_set_read_increment(&config, true);
    channel_config_set_write_increment(&config, false);
    channel_config_set_chain_to(&config, ch2_dma);
    channel_config_set_bswap(&config, false);
    channel_config_set_dreq(&config, dma_get_timer_dreq (tm_dma));
    uint slice_num = pwm_gpio_to_slice_num(26);
    dma_channel_configure(ch_dma, &config, &(pwm_hw->slice[slice_num].cc), p_pwm_buffer, pwm_buffer_byte / 4, false);

    dma_channel_config config2 = dma_channel_get_default_config(ch2_dma);
    channel_config_set_transfer_data_size(&config2, DMA_SIZE_32);
    channel_config_set_read_increment(&config2, false);
    channel_config_set_write_increment(&config2, false);
    channel_config_set_bswap(&config2, false);
    dma_channel_configure(ch2_dma, &config2, &(dma_hw->ch[ch_dma].al3_read_addr_trig), &p_pwm_buffer, 1, false);

}

//=============================================

void clearPcmbuff() {
    for( int i = 0; i < PCM_BUFF_MAX; i++) {
        pcm_buff[i] = NULL;
        pcm_size[i] = 0;
    }
    pcm_widx = 0;
    pcm_ridx = 0;
    pcm_rpos = 0;
}

//#define REPEATING_TIMER
#define NON_REPEATING_TIMER
#ifdef NON_REPEATING_TIMER
static alarm_id_t sound_alarm_id;
static int16_t sound_delay_us;
int64_t cb_writePcm_alarm(alarm_id_t id, void *udata) {
    if( pcm_ch == 0) {
        return 0;
    }
    sound_alarm_id = add_alarm_in_us ((int64_t)sound_delay_us, cb_writePcm_alarm, NULL, false);
    if( pcm_widx == pcm_ridx) {
        return 0;
    }
    uint slice_num = pwm_gpio_to_slice_num(26);
    if ( pcm_ch == 1) {
        int val = pcm_buff[pcm_ridx][pcm_rpos++];
        val = val + 32768;  // int16 to uint16
        uint16_t level = val >> 5;  // 0 - 2047
        pwm_set_both_levels (slice_num, level, level);
    } else {
        int val1 = pcm_buff[pcm_ridx][pcm_rpos++] + 32768;
        int val2 = pcm_buff[pcm_ridx][pcm_rpos++] + 32768;
        uint16_t level1 = val1 >> 5;  // 0 - 2047
        uint16_t level2 = val2 >> 5;  // 0 - 2047
        if ( pcm_ch == 2) {
            pwm_set_both_levels (slice_num, level1, level2);
        } else {
            pwm_set_both_levels (slice_num, level2, level1);
        }
    }
    
    if( pcm_rpos >= pcm_size[pcm_ridx]) {
        pcm_rpos = 0;
        pcm_ridx ++;
        if( pcm_ridx >= PCM_BUFF_MAX) {
            pcm_ridx = 0;
        }
    }
    return 0;
}

#endif // NON_REPEATING_TIMER


#ifdef REPEATING_TIMER
static repeating_timer_t sound_timer;
bool cb_writePcm(repeating_timer_t *rt) {
    if( pcm_widx == pcm_ridx) {
        return true;
    }
    if( pcm_ch == 0) {
        return false;
    }
    uint slice_num = pwm_gpio_to_slice_num(26);
    if ( pcm_ch == 1) {
        int val = pcm_buff[pcm_ridx][pcm_rpos++];
        val = val + 32768;  // int16 to uint16
        uint16_t level = val >> 5;  // 0 - 2047
        pwm_set_both_levels (slice_num, level, level);
    } else {
        int val1 = pcm_buff[pcm_ridx][pcm_rpos++] + 32768;
        int val2 = pcm_buff[pcm_ridx][pcm_rpos++] + 32768;
        uint16_t level1 = val1 >> 5;  // 0 - 2047
        uint16_t level2 = val2 >> 5;  // 0 - 2047
        if ( pcm_ch == 2) {
            pwm_set_both_levels (slice_num, level1, level2);
        } else {
            pwm_set_both_levels (slice_num, level2, level1);
        }
    }
    
    if( pcm_rpos >= pcm_size[pcm_ridx]) {
        pcm_rpos = 0;
        pcm_ridx ++;
        if( pcm_ridx >= PCM_BUFF_MAX) {
            pcm_ridx = 0;
        }
    }
    return true;
}
#endif //REPEATING_TIMER
//r  w  -  - ok
//-  rw -  - ok
//-  w  r  - ng
//r  -  -  w ng

int testPcmbuff() {
    int wk;
    wk = (int)pcm_ridx - (int)pcm_widx - 1;
    if( wk < 0) {
        wk += PCM_BUFF_MAX;
    }
    return wk;
}

bool addPcmbuff(int16_t *buf, int siz) {
    if( testPcmbuff() == 0) {
        return false;
    }

    pcm_buff[pcm_widx] = buf;
    pcm_size[pcm_widx] = siz;
    int8_t wk8 = pcm_widx + 1;
    if( wk8 >= PCM_BUFF_MAX) {
        wk8 = 0;
    }
    pcm_widx = wk8;
    return true;
}

static void pwm_port_init() {
 // Tell GPIO 0 and 1 they are allocated to the PWM
    gpio_set_function(26, GPIO_FUNC_PWM);
    gpio_set_function(27, GPIO_FUNC_PWM);

    // Find out which PWM slice is connected to GPIO 0 (it's slice 0)
    uint slice_num = pwm_gpio_to_slice_num(26);
    pwm_set_clkdiv_int_frac4(slice_num, 1, 0);
    pwm_set_wrap(slice_num, 2047);
    // Set the PWM running
    pwm_set_enabled(slice_num, true);
}
static void pwm_port_deinit() {
    uint slice_num = pwm_gpio_to_slice_num(26);
    pwm_set_enabled(slice_num, false);
    gpio_set_function(26, GPIO_FUNC_NULL);
    gpio_set_function(27, GPIO_FUNC_NULL);
}    

static void sound_pwm_start(int delay_us, int channels) {
    pwm_port_init();
    pcm_ch = (uint8_t)channels;

    clearPcmbuff();
#ifdef REPEATING_TIMER    
    add_repeating_timer_us(delay_us, cb_writePcm, NULL, &sound_timer);    
#endif
#ifdef NON_REPEATING_TIMER    
    sound_delay_us = (uint16_t) delay_us;
    sound_alarm_id = add_alarm_in_us ((int64_t)sound_delay_us, cb_writePcm_alarm, NULL, false);
#endif
    

}

static void sound_pwm_stop() {
#ifdef REPEATING_TIMER    
    cancel_repeating_timer(&sound_timer);   
#endif
#ifdef NON_REPEATING_TIMER    
    cancel_alarm(sound_alarm_id);
#endif
    pwm_port_deinit();
}

#define WAIT_US (23)    // 44KHz

static void sound_pwm_send(uint slice_num, uint8_t *buf, int size, int delayus) {
    int i;
    uint16_t level;
    for( i = 0; i < size; i++){
        level = buf[i] << 3;
        pwm_set_both_levels (slice_num, level, level);
        sleep_us(delayus);
    }
}

static mp_obj_t sound_open(size_t n_args, const mp_obj_t *args) {
    int delay_us = WAIT_US;
    int channels = 2;
    if (n_args >= 1) {
        if (args[0] != mp_const_none) {
            delay_us = mp_obj_get_int(args[0]);
        }
    }
    if (n_args >= 2) {
        if (args[1] != mp_const_none) {
            channels = mp_obj_get_int(args[1]);
        }
    }
    pcm_ch = 0;
    sleep_us(200);

    sound_pwm_start(delay_us, channels);

	return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(sound_open_obj, 0, 2, sound_open);

static mp_obj_t sound_reopen(size_t n_args, const mp_obj_t *args) {
    int delay_us = WAIT_US;
    int channels = 2;
    if (n_args >= 1) {
        if (args[0] != mp_const_none) {
            delay_us = mp_obj_get_int(args[0]);
        }
    }
    if (n_args >= 2) {
        if (args[1] != mp_const_none) {
            channels = mp_obj_get_int(args[1]);
        }
    }
    pcm_ch = 0;
    sleep_us(200);
    sound_pwm_stop();
    sound_pwm_start(delay_us, channels);

	return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(sound_reopen_obj, 0, 2, sound_reopen);

static mp_obj_t sound_close(size_t n_args, const mp_obj_t *args) {

    sound_pwm_stop();
    pcm_ch = 0;
	return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(sound_close_obj, 0, 0, sound_close);

static mp_obj_t play(size_t n_args, const mp_obj_t *args) {

    int result = 0;
    mp_buffer_info_t inbuf;
    mp_get_buffer_raise(args[0], &inbuf, MP_BUFFER_READ);
    int iDataSize = inbuf.len;
    uint8_t *pData = (uint8_t *)inbuf.buf;
    uint slice_num = pwm_gpio_to_slice_num(26);
    int delayus = WAIT_US;
    
    if( n_args >= 2) {
        delayus = mp_obj_get_int(args[1]);     // delayus
    }
            
    sound_pwm_send(slice_num, pData, iDataSize, delayus);
    
    mp_obj_t res[3];
	res[0]= mp_obj_new_int(result);
    
	return mp_obj_new_tuple(3, res);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(play_obj, 1, 2, play);

static mp_obj_t dma_play(size_t n_args, const mp_obj_t *args) {

    int result = 0;
    mp_buffer_info_t inbuf;
    mp_get_buffer_raise(args[0], &inbuf, MP_BUFFER_READ);
    int iDataSize = inbuf.len;
    uint8_t *pData = (uint8_t *)inbuf.buf;
    int freq = 44100;
    
    if( n_args >= 2) {
        freq = mp_obj_get_int(args[1]);     // freq
    }
    pwm_port_init();
    pwm_dma_init(freq);
    pwm_dma_start((int16_t *)pData, iDataSize);
    
    mp_obj_t res[3];
	res[0]= mp_obj_new_int(result);
    
	return mp_obj_new_tuple(3, res);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(dma_play_obj, 1, 2, dma_play);

static mp_obj_t dma_end(size_t n_args, const mp_obj_t *args) {
    pwm_port_deinit();
    pwm_dma_stop();
    
	return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(dma_end_obj, 0, 0, dma_end);

static mp_obj_t dma_getcount(size_t n_args, const mp_obj_t *args) {
    
    return  mp_obj_new_int(pwm_dma_get_count());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(dma_getcount_obj, 0, 0, dma_getcount);

static mp_obj_t addbuff(size_t n_args, const mp_obj_t *args) {
    mp_buffer_info_t inbuf;
    mp_get_buffer_raise(args[0], &inbuf, MP_BUFFER_READ);
    int iDataSize = inbuf.len;
    int16_t *pData = (int16_t *)inbuf.buf;
    
    int result;
    bool bret = addPcmbuff(pData, iDataSize / 2);
    if( bret ) {
        result = 0;
    } else {
        result = -1;
    }
    return mp_obj_new_int(result);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(addbuff_obj, 1, 1, addbuff);

static mp_obj_t testbuff(size_t n_args, const mp_obj_t *args) {
    int result = testPcmbuff();
    return mp_obj_new_int(result);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(testbuff_obj, 0, 0, testbuff);

static mp_obj_t infobuff(size_t n_args, const mp_obj_t *args) {
    int res0 = testPcmbuff();
    int res1 = pcm_ridx;
    int res2 = pcm_rpos;
    int res3 = pcm_widx;
    int res4 = clock_get_hz(clk_sys);
    mp_obj_t res[5];
        res[0]= mp_obj_new_int(res0);
        res[1]= mp_obj_new_int(res1);
        res[2]= mp_obj_new_int(res2);
        res[3]= mp_obj_new_int(res3);
        res[4]= mp_obj_new_int(res4);
    
	return mp_obj_new_tuple(5, res);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(infobuff_obj, 0, 0, infobuff);

#include "mp3common.h"
static mp_obj_t mp3initdecoder(size_t n_args, const mp_obj_t *args) {
    HMP3Decoder decoder = MP3InitDecoder();
    return mp_obj_new_int((int)decoder);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(mp3initdecoder_obj, 0, 0, mp3initdecoder);

static mp_obj_t mp3getnextframeinfo(size_t n_args, const mp_obj_t *args) {
    HMP3Decoder hMP3Decoder;
    MP3FrameInfo *mp3FrameInfo;
    unsigned char *buf;
    mp_buffer_info_t fibuf, datbuf;

    hMP3Decoder = (HMP3Decoder)mp_obj_get_int(args[0]);
    mp_get_buffer_raise(args[1], &fibuf, MP_BUFFER_READ);
    mp3FrameInfo  = (MP3FrameInfo *)fibuf.buf;
    mp_get_buffer_raise(args[2], &datbuf, MP_BUFFER_READ);
    buf = (unsigned char *)datbuf.buf;
    int rc;
    rc = MP3GetNextFrameInfo(hMP3Decoder, mp3FrameInfo, buf);
    return mp_obj_new_int(rc);
}

static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(mp3getnextframeinfo_obj, 3, 3, mp3getnextframeinfo);

static mp_obj_t mp3decode(size_t n_args, const mp_obj_t *args) {
    HMP3Decoder hMP3Decoder;
    unsigned char *buf;
    int bytes_left;
    short *audiodata;
    mp_buffer_info_t datbuf, abuf;

    hMP3Decoder = (HMP3Decoder)mp_obj_get_int(args[0]);
    mp_get_buffer_raise(args[1], &datbuf, MP_BUFFER_READ);
    buf = (unsigned char *)datbuf.buf;
    bytes_left = (int)mp_obj_get_int(args[2]);
    mp_get_buffer_raise(args[3], &abuf, MP_BUFFER_READ);
    audiodata = (short *)abuf.buf;
    // args[4] is not used

    int rc, err;
    err = MP3Decode(hMP3Decoder, &buf, &bytes_left, audiodata, 0);
    if (err != ERR_MP3_NONE) {
        rc = err;
    } else {
        rc = bytes_left;
    }
	return mp_obj_new_int(rc);
}

static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(mp3decode_obj, 5, 5, mp3decode);

static mp_obj_t mp3pcm2dma(size_t n_args, const mp_obj_t *args) {
    int16_t *audioin;
    uint16_t *audioout;
    
    mp_buffer_info_t inbuf, outbuf;
    mp_get_buffer_raise(args[0], &inbuf, MP_BUFFER_READ);
    mp_get_buffer_raise(args[1], &outbuf, MP_BUFFER_READ);

    audioin = (int16_t*)inbuf.buf;
    audioout = (uint16_t*)outbuf.buf;
    
    int pcm_flag = 0;
    if( n_args >= 3) {
        if (args[2] != mp_const_none) {
            pcm_flag = (int)mp_obj_get_int(args[2]);
        }
    }

    int i;
    int val;
    uint16_t level;
    if( pcm_flag == 0) {    //normal
        for( i = 0; i < inbuf.len / 2; i++){
            val = audioin[i] + 32768;
            level = val >> 5;
            audioout[i] = level;
        }
    }
    if( pcm_flag == 1) {    //mono to stereo
        uint32_t *out32 = (uint32_t *)audioout;
        for( i = 0; i < inbuf.len / 2; i++){
            val = audioin[i] + 32768;
            level = val >> 5 ;
            out32[i] = level << 16 | level;
        }
    }
    return mp_const_none;
}
    
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(mp3pcm2dma_obj, 2, 3, mp3pcm2dma);
    
static mp_obj_t mp3findsyncword(size_t n_args, const mp_obj_t *args) {
    unsigned char *buf;
    int nBytes;
    mp_buffer_info_t datbuf;
    
    mp_get_buffer_raise(args[0], &datbuf, MP_BUFFER_READ);
    buf = datbuf.buf;
    nBytes = mp_obj_get_int(args[1]);

    int rc = MP3FindSyncWord(buf, nBytes);
    return mp_obj_new_int(rc);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(mp3findsyncword_obj, 2, 2, mp3findsyncword);

static const mp_rom_map_elem_t sound_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_sound) },
    {MP_ROM_QSTR(MP_QSTR_open), MP_ROM_PTR(&sound_open_obj)},
    {MP_ROM_QSTR(MP_QSTR_reopen), MP_ROM_PTR(&sound_reopen_obj)},
    {MP_ROM_QSTR(MP_QSTR_close), MP_ROM_PTR(&sound_close_obj)},
    {MP_ROM_QSTR(MP_QSTR_play), MP_ROM_PTR(&play_obj)},
    {MP_ROM_QSTR(MP_QSTR_dma_play), MP_ROM_PTR(&dma_play_obj)},
    {MP_ROM_QSTR(MP_QSTR_dma_getcount), MP_ROM_PTR(&dma_getcount_obj)},
    {MP_ROM_QSTR(MP_QSTR_dma_end), MP_ROM_PTR(&dma_end_obj)},
    {MP_ROM_QSTR(MP_QSTR_addbuff), MP_ROM_PTR(&addbuff_obj)},
    {MP_ROM_QSTR(MP_QSTR_testbuff), MP_ROM_PTR(&testbuff_obj)},
    {MP_ROM_QSTR(MP_QSTR_infobuff), MP_ROM_PTR(&infobuff_obj)},
    {MP_ROM_QSTR(MP_QSTR_mp3initdecoder), MP_ROM_PTR(&mp3initdecoder_obj)},
    {MP_ROM_QSTR(MP_QSTR_mp3getnextframeinfo), MP_ROM_PTR(&mp3getnextframeinfo_obj)},
    {MP_ROM_QSTR(MP_QSTR_mp3decode), MP_ROM_PTR(&mp3decode_obj)},
    {MP_ROM_QSTR(MP_QSTR_mp3findsyncword), MP_ROM_PTR(&mp3findsyncword_obj)},
    {MP_ROM_QSTR(MP_QSTR_mp3pcm2dma), MP_ROM_PTR(&mp3pcm2dma_obj)},
};
static MP_DEFINE_CONST_DICT(sound_globals, sound_globals_table);
/* methods end */

const mp_obj_module_t sound_cmodule = {
    .base = {&mp_type_module},
    .globals = (mp_obj_dict_t *)&sound_globals,
};

MP_REGISTER_MODULE(MP_QSTR_sound, sound_cmodule);
