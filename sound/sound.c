#include "py/obj.h"
#include "py/objstr.h"
#include "py/objmodule.h"
#include "py/runtime.h"
#include "py/builtin.h"

#include "pico/stdlib.h"
#include "hardware/pwm.h"
#include "hardware/timer.h"

#define PCM_BUFF_MAX (4)
int16_t *pcm_buff[PCM_BUFF_MAX];
int pcm_size[PCM_BUFF_MAX];
volatile uint8_t  pcm_ridx, pcm_widx;
int pcm_rpos;

void clearPcmbuff() {
    for( int i = 0; i < PCM_BUFF_MAX; i++) {
        pcm_buff[i] = NULL;
        pcm_size[i] = 0;
    }
    pcm_widx = 0;
    pcm_ridx = 0;
    pcm_rpos = 0;
}

static repeating_timer_t sound_timer;
bool cb_writePcm(repeating_timer_t *rt) {
    if( pcm_widx == pcm_ridx) {
        return true;
    }
    uint slice_num = pwm_gpio_to_slice_num(26);
    int val = pcm_buff[pcm_ridx][pcm_rpos];
    val = val + 32768;  // int16 to uint16
    uint16_t level = val >> 5;  // 0 - 2047
    pwm_set_both_levels (slice_num, level, level);
    
    pcm_rpos ++;
    if( pcm_rpos >= pcm_size[pcm_ridx]) {
        pcm_rpos = 0;
        pcm_ridx ++;
        if( pcm_ridx >= PCM_BUFF_MAX) {
            pcm_ridx = 0;
        }
    }
    return true;
}

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

static void sound_pwm_start(int delay_us) {
 // Tell GPIO 0 and 1 they are allocated to the PWM
    gpio_set_function(26, GPIO_FUNC_PWM);
    // gpio_set_function(27, GPIO_FUNC_PWM);

    // Find out which PWM slice is connected to GPIO 0 (it's slice 0)
    uint slice_num = pwm_gpio_to_slice_num(26);
    pwm_set_clkdiv_int_frac4(slice_num, 1, 0);
    pwm_set_wrap(slice_num, 2047);
    // Set the PWM running
    pwm_set_enabled(slice_num, true);
    
    clearPcmbuff();
    add_repeating_timer_us(delay_us, cb_writePcm, NULL, &sound_timer);    

}

static void sound_pwm_stop() {
    uint slice_num = pwm_gpio_to_slice_num(26);
    pwm_set_enabled(slice_num, false);
    cancel_repeating_timer(&sound_timer);   
}

#define WAIT_US (23)    // 44KHz
//#define WAIT_US (1000)    // 1KHz

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
    if (n_args >= 1) {
        if (args[0] != mp_const_none) {
            delay_us = mp_obj_get_int(args[0]);
        }
    }

    sound_pwm_start(delay_us);

	return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(sound_open_obj, 0, 1, sound_open);

static mp_obj_t sound_close(size_t n_args, const mp_obj_t *args) {

    sound_pwm_stop();
    
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
    mp_obj_t res[4];
        res[0]= mp_obj_new_int(res0);
        res[1]= mp_obj_new_int(res1);
        res[2]= mp_obj_new_int(res2);
        res[3]= mp_obj_new_int(res3);
    
	return mp_obj_new_tuple(4, res);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(infobuff_obj, 0, 0, infobuff);

#include "mp3common.h"
static mp_obj_t mp3decode(size_t n_args, const mp_obj_t *args) {
    MP3InitDecoder();
	return mp_obj_new_int(0);
}

static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(mp3decode_obj, 1, 2, mp3decode);

static const mp_rom_map_elem_t sound_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_sound) },
    {MP_ROM_QSTR(MP_QSTR_open), MP_ROM_PTR(&sound_open_obj)},
    {MP_ROM_QSTR(MP_QSTR_close), MP_ROM_PTR(&sound_close_obj)},
    {MP_ROM_QSTR(MP_QSTR_play), MP_ROM_PTR(&play_obj)},
    {MP_ROM_QSTR(MP_QSTR_addbuff), MP_ROM_PTR(&addbuff_obj)},
    {MP_ROM_QSTR(MP_QSTR_testbuff), MP_ROM_PTR(&testbuff_obj)},
    {MP_ROM_QSTR(MP_QSTR_infobuff), MP_ROM_PTR(&infobuff_obj)},
    {MP_ROM_QSTR(MP_QSTR_mp3decode), MP_ROM_PTR(&mp3decode_obj)},
};
static MP_DEFINE_CONST_DICT(sound_globals, sound_globals_table);
/* methods end */

const mp_obj_module_t sound_cmodule = {
    .base = {&mp_type_module},
    .globals = (mp_obj_dict_t *)&sound_globals,
};

MP_REGISTER_MODULE(MP_QSTR_sound, sound_cmodule);
