#include <string.h>
#include "virtual_spi.h"
// Synthetic calibration in SRAM, not a dump of a real controller.
static uint8_t factory[256];
static void pack_pair(uint8_t *p,uint16_t x,uint16_t y){
    p[0]=(uint8_t)x;p[1]=(uint8_t)((x>>8)|((y&15)<<4));p[2]=(uint8_t)(y>>4);
}
void virtual_spi_init(void){
    memset(factory,0xff,sizeof(factory));
    memcpy(factory,"BPRO-RAM-0000002",16);
    factory[0x12]=3;factory[0x13]=0xa0;factory[0x1b]=2;
    memset(factory+0x20,0,24);
    for(unsigned i=0;i<3;i++){
        factory[0x26+2*i+1]=0x40; // Acc sensitivity 16384
        factory[0x32+2*i]=0x3b;factory[0x32+2*i+1]=0x34; // Gyro sensitivity 13371
    }
    pack_pair(factory+0x3d,1600,1600);pack_pair(factory+0x40,2048,2048);pack_pair(factory+0x43,1600,1600);
    pack_pair(factory+0x46,2048,2048);pack_pair(factory+0x49,1600,1600);pack_pair(factory+0x4c,1600,1600);
    uint8_t const colors[]={0x32,0x32,0x32,0xff,0xff,0xff,0x32,0x32,0x32,0x32,0x32,0x32};
    memcpy(factory+0x50,colors,sizeof(colors));factory[0x5c]=1;
    memset(factory+0x80,0,6);
    // Stick parameter bytes, reference layout from the MIT GP2040-CE driver.
    uint8_t const params[]={0x0f,0x30,0x61,0xae,0x90,0xd9,0xd4,0x14,0x54,0x41,0x15,0x54,0xc7,0x79,0x9c,0x33,0x36,0x63};
    memcpy(factory+0x86,params,sizeof(params));memcpy(factory+0x98,params,sizeof(params));
}
bool virtual_spi_read(uint32_t address,uint8_t *buffer,uint8_t size){
    if(size>29 || (size && address>UINT32_MAX-(size-1u)))return false;
    for(uint8_t i=0;i<size;i++){
        uint32_t at=address+i;
        buffer[i]=(at>=0x6000 && at<0x6100)?factory[at-0x6000]:0xff;
    }
    return true;
}
