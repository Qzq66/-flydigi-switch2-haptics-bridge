#include <string.h>
#include "pico.h"
#include "tusb.h"
#include "pro_report_descriptor.h"

static tusb_desc_device_t const device={
    .bLength=sizeof(tusb_desc_device_t),.bDescriptorType=TUSB_DESC_DEVICE,
    .bcdUSB=0x0200,.bMaxPacketSize0=64,
#if PICO_NO_FLASH
    .idVendor=0xcafe,.idProduct=0x4012,
#else
    .idVendor=0x057e,.idProduct=0x2009,
#endif
    .bcdDevice=0x0210,.iManufacturer=1,.iProduct=2,.iSerialNumber=3,
    .bNumConfigurations=1
};
enum { CONFIG_SIZE=TUD_CONFIG_DESC_LEN+TUD_HID_INOUT_DESC_LEN };
static uint8_t const configuration[]={
    TUD_CONFIG_DESCRIPTOR(1,1,0,CONFIG_SIZE,0,100),
    TUD_HID_INOUT_DESCRIPTOR(0,0,HID_ITF_PROTOCOL_NONE,sizeof(pro_report_descriptor),0x01,0x81,64,8)
};
uint8_t const *tud_descriptor_device_cb(void){return (uint8_t const*)&device;}
uint8_t const *tud_descriptor_configuration_cb(uint8_t index){(void)index;return configuration;}
uint8_t const *tud_hid_descriptor_report_cb(uint8_t instance){(void)instance;return pro_report_descriptor;}
uint16_t const *tud_descriptor_string_cb(uint8_t index,uint16_t langid){
    (void)langid;
    static uint16_t text[64];
    static char const *const strings[]={"","Bridge Lab","Bridge Pro Live 042","BPCAP-RP2350-LOCAL-042"};
    if(index==0){text[0]=0x0304;text[1]=0x0429;return text;}
    if(index>=sizeof(strings)/sizeof(strings[0]))return NULL;
    size_t n=strlen(strings[index]);if(n>63)n=63;
    text[0]=(uint16_t)(0x0300|((n+1)*2));
    for(size_t i=0;i<n;i++)text[i+1]=(uint8_t)strings[index][i];
    return text;
}
