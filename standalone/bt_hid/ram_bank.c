/* SDK TLV storage factory is link-wrapped to RAM, never hardware Flash. */
#include <stdbool.h>
#include <string.h>
#include "hal_flash_bank.h"
#include "ram_bank.h"
static uint8_t banks[2][4096];
static bool initialized;
static uint32_t errors,writes,erases;
static uint32_t size(void *ctx) {(void)ctx;return sizeof banks[0];}
static uint32_t alignment(void *ctx) {(void)ctx;return 1;}
static bool valid(int bank,uint32_t offset,uint32_t length) {
    bool ok=bank>=0 && bank<2 && offset<=sizeof banks[0] && length<=sizeof banks[0]-offset;
    if(!ok) errors++;
    return ok;
}
static void erase(void *ctx,int bank) {
    (void)ctx;if(valid(bank,0,0)){memset(banks[bank],0xff,sizeof banks[0]);erases++;}
}
static void read_bank(void *ctx,int bank,uint32_t offset,uint8_t *dest,uint32_t length) {
    (void)ctx;if(valid(bank,offset,length))memcpy(dest,banks[bank]+offset,length);
    else memset(dest,0xff,length);
}
static void write_bank(void *ctx,int bank,uint32_t offset,const uint8_t *data,uint32_t length) {
    (void)ctx;if(!valid(bank,offset,length))return;
    for(uint32_t i=0;i<length;i++)if((banks[bank][offset+i]&data[i])!=data[i]){errors++;return;}
    memcpy(banks[bank]+offset,data,length);writes++;
}
static const hal_flash_bank_t api={size,alignment,erase,read_bank,write_bank};
const hal_flash_bank_t *__wrap_pico_flash_bank_instance(void) {
    if(!initialized){memset(banks,0xff,sizeof banks);initialized=true;}
    return &api;
}
uint32_t probe_ram_bank_errors(void){return errors;}
uint32_t probe_ram_bank_writes(void){return writes;}
uint32_t probe_ram_bank_erases(void){return erases;}
