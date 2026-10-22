#include <string.h>
#include "pico/stdlib.h"
#include "pico/bootrom.h"
#include "capture_journal.h"
#if !PICO_NO_FLASH
#include "pico/flash.h"
#include "hardware/flash.h"
#include "hardware/structs/watchdog.h"
#include "tusb.h"
#endif
enum { HEADER_BYTES=128,EVENT_BYTES=24,CRC_OFFSET=CAPTURE_SLOT_SIZE-4,
       CAPACITY=(CRC_OFFSET-HEADER_BYTES)/EVENT_BYTES };
static uint8_t image[CAPTURE_SLOT_SIZE] __attribute__((aligned(256)));
static uint32_t total,first_dropped;
static uint64_t started_ms,started_us;
static bool mounted,preview_valid;
static void put16(uint8_t *p,uint16_t n){p[0]=(uint8_t)n;p[1]=(uint8_t)(n>>8);}
static void put32(uint8_t *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(8*i));}
#if !PICO_NO_FLASH
static uint32_t get32(uint8_t const *p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
#endif
static uint32_t crc32(uint8_t const *p,size_t n){
    uint32_t crc=0xffffffffu;
    for(size_t i=0;i<n;i++){
        crc^=p[i];for(unsigned j=0;j<8;j++)crc=(crc>>1)^((0u-(crc&1u))&0xedb88320u);
    }
    return ~crc;
}
void capture_init(uint64_t now){
    started_ms=now;started_us=time_us_64();total=0;first_dropped=UINT32_MAX;
    mounted=false;preview_valid=false;memset(image,0xff,sizeof(image));
}
void capture_mounted(void){mounted=true;}
void capture_record(uint64_t now,uint8_t id,uint8_t const *p,uint16_t size){
    (void)now;if(size>63)return;
    uint32_t timestamp=(uint32_t)(time_us_64()-started_us);
    if(total<CAPACITY){
        uint8_t *r=image+HEADER_BYTES+total*EVENT_BYTES;memset(r,0,EVENT_BYTES);
        put32(r,timestamp);put32(r+4,total);r[8]=id;r[9]=(uint8_t)(size+1);
        if(id==1 && size>=10){r[10]=p[9];if(size>=11)r[11]=p[10];}
        else if(id==0x80 && size)r[10]=p[0];
        if((id==1 || id==0x10) && size>=9){memcpy(r+12,p+1,8);r[20]|=1;r[21]=p[0];}
        // Only command and first phase byte are retained; never credentials.
        if(id==1 && size>=10 && p[9]==1)r[20]|=2;
    }else if(first_dropped==UINT32_MAX)first_dropped=timestamp;
    total++;
}
static void serialize(uint8_t const *diagnostics,uint64_t now,uint32_t reason,uint32_t generation,uint32_t target){
    (void)now;memset(image,0,HEADER_BYTES);memcpy(image,"BPROLOG5",8);
    uint32_t count=total<CAPACITY?total:CAPACITY;
    put32(image+8,5);put32(image+12,generation);put32(image+16,reason);
    put32(image+20,(uint32_t)((time_us_64()-started_us+999)/1000));put32(image+24,total);
    put16(image+28,(uint16_t)count);put16(image+30,EVENT_BYTES);
    put32(image+32,(mounted?1u:0u)|(total>CAPACITY?2u:0u)|(PICO_NO_FLASH?4u:0u));
    put32(image+36,count*EVENT_BYTES);put32(image+40,target);put32(image+44,CAPACITY);
    put32(image+48,first_dropped);put32(image+52,1000000);
    memcpy(image+64,diagnostics,64);put32(image+CRC_OFFSET,crc32(image,CRC_OFFSET));preview_valid=true;
}
bool capture_due(uint64_t now){
#if PICO_NO_FLASH
    (void)now;return false;
#else
    return now-started_ms>=20000;
#endif
}
void capture_preview(uint8_t const *diagnostics,uint64_t now){serialize(diagnostics,now,2,0,0);}
uint8_t capture_preview_byte(uint32_t offset){return preview_valid && offset<sizeof(image)?image[offset]:0xff;}
#if !PICO_NO_FLASH
static bool valid(uint8_t const *p){return !memcmp(p,"BPROLOG5",8) && get32(p+8)==5 && get32(p+CRC_OFFSET)==crc32(p,CRC_OFFSET);}
static uint32_t target_offset;
static void __not_in_flash_func(write_slot)(void *unused){
    (void)unused;flash_range_erase(target_offset,CAPTURE_SLOT_SIZE);
    flash_range_program(target_offset,image,CAPTURE_SLOT_SIZE);
}
#endif
void capture_finish(uint8_t const *diagnostics,uint64_t now){
#if PICO_NO_FLASH
    capture_preview(diagnostics,now);
#else
    uint8_t const *a=(uint8_t const *)(XIP_BASE+CAPTURE_SLOT0_OFFSET);
    uint8_t const *b=(uint8_t const *)(XIP_BASE+CAPTURE_SLOT1_OFFSET);
    bool va=valid(a),vb=valid(b);uint32_t generation=0;
    if(va && (!vb || (int32_t)(get32(a+12)-get32(b+12))>0)){generation=get32(a+12);target_offset=CAPTURE_SLOT1_OFFSET;}
    else if(vb){generation=get32(b+12);target_offset=CAPTURE_SLOT0_OFFSET;}
    else target_offset=CAPTURE_SLOT0_OFFSET;
    tud_disconnect();sleep_ms(100);serialize(diagnostics,now,1,generation+1,target_offset);
    int result=flash_safe_execute(write_slot,NULL,3000);
    bool checked=result==PICO_OK && valid((uint8_t const *)(XIP_BASE+target_offset)) &&
        !memcmp((void const *)(XIP_BASE+target_offset),image,sizeof(image));
    watchdog_hw->scratch[0]=checked?0x4341504fu:0x43415046u;
    reset_usb_boot(0,0);while(true)tight_loop_contents();
#endif
}
