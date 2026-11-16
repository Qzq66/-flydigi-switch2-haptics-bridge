/* Discovery only. No connection, pairing, SDP/GATT request or HID output. */
#include <stdio.h>
#include <string.h>
#include "pico/stdlib.h"
#include "pico/stdio_usb.h"
#include "pico/bootrom.h"
#include "pico/cyw43_arch.h"
#include "btstack.h"
#include "ram_bank.h"
#define MAX_OBSERVATIONS 96
static btstack_packet_callback_registration_t registration;
static uint8_t phase; /* 0 waiting, 1 init, 2 classic, 3 BLE, 4 done */
static uint64_t boot_us,phase_us;
static bool radio_ready,radio_initialized;
static unsigned classic_count,ble_count,dropped;
static uint8_t classic_seen[MAX_OBSERVATIONS][71],ble_seen[MAX_OBSERVATIONS][39];
static void hex(const uint8_t *data,unsigned length) {
    if(!length){printf("-");return;}
    for(unsigned i=0;i<length;i++)printf("%02x",data[i]);
}
static bool new_peer(uint8_t *seen,unsigned width,unsigned *count,const uint8_t *key) {
    for(unsigned i=0;i<*count;i++)if(!memcmp(seen+i*width,key,width))return false;
    if(*count==MAX_OBSERVATIONS){dropped++;return false;}
    memcpy(seen+(*count)*width,key,width);(*count)++;return true;
}
static void finish(const char *reason) {
    if(phase==4)return;
    if(radio_ready){if(phase==2)gap_inquiry_stop();if(phase==3)gap_stop_scan();hci_power_control(HCI_POWER_OFF);}
    phase=4;
    printf("BTD1 DONE reason=%s classic=%u ble=%u dropped=%u ram_errors=%lu ram_writes=%lu ram_erases=%lu\n",
        reason,classic_count,ble_count,dropped,(unsigned long)probe_ram_bank_errors(),
        (unsigned long)probe_ram_bank_writes(),(unsigned long)probe_ram_bank_erases());
}
static void begin_ble(void) {
    if(phase!=2)return;
    phase=3;phase_us=time_us_64();
    gap_set_scan_parameters(1,0x30,0x30); /* active LE scan: request scan responses for names */
    gap_start_scan();printf("BTD1 PHASE BLE\n");
}
static void event(uint8_t type,uint16_t channel,uint8_t *packet,uint16_t length) {
    (void)channel;
    if(type!=HCI_EVENT_PACKET || length<2 || (unsigned)packet[1]+2>length)return;
    switch(hci_event_packet_get_type(packet)) {
    case BTSTACK_EVENT_STATE:
        if(length>=3 && btstack_event_state_get_state(packet)==HCI_STATE_WORKING && phase==1){
            radio_ready=true;gap_connectable_control(0);gap_discoverable_control(0);gap_set_bondable_mode(0);
            hci_set_inquiry_mode(INQUIRY_MODE_RSSI_AND_EIR);
            phase=2;phase_us=time_us_64();printf("BTD1 PHASE CLASSIC\n");
            if(gap_inquiry_start(8))finish("inquiry_error");
        }
        break;
    case GAP_EVENT_INQUIRY_RESULT:
        if(phase==2 && length>=27){
            bd_addr_t addr;gap_event_inquiry_result_get_bd_addr(packet,addr);
            unsigned n=gap_event_inquiry_result_get_name_len(packet);
            if(n>length-27u)return;
            if(n>64)n=64;
            uint8_t key[71]={0};memcpy(key,addr,6);key[6]=(uint8_t)n;memcpy(key+7,gap_event_inquiry_result_get_name(packet),n);
            if(new_peer(&classic_seen[0][0],71,&classic_count,key)){
                printf("BTD1 CLASSIC addr=");hex(addr,6);
                printf(" cod=%06lx name=",(unsigned long)gap_event_inquiry_result_get_class_of_device(packet));
                hex(gap_event_inquiry_result_get_name(packet),n);printf("\n");
            }
        }
        break;
    case GAP_EVENT_INQUIRY_COMPLETE:
        if(phase==2){if(length>=3 && packet[2]!=0)finish("inquiry_failed");else begin_ble();}
        break;
    case GAP_EVENT_ADVERTISING_REPORT:
        if(phase==3 && length>=12){
            uint8_t key[39]={0};key[0]=gap_event_advertising_report_get_address_type(packet);
            gap_event_advertising_report_get_address(packet,key+1);
            unsigned n=gap_event_advertising_report_get_data_length(packet);
            if(n>31 || n>length-12u)return;
            key[7]=(uint8_t)n;memcpy(key+8,gap_event_advertising_report_get_data(packet),n);
            if(new_peer(&ble_seen[0][0],39,&ble_count,key)){
                printf("BTD1 BLE addr=");hex(key+1,6);
                printf(" type=%u rssi=%d data=",key[0],gap_event_advertising_report_get_rssi(packet));
                hex(gap_event_advertising_report_get_data(packet),n);printf("\n");
            }
        }
        break;
    default:break;
    }
}
int main(void) {
    boot_us=time_us_64();stdio_init_all();
    char command[12];unsigned used=0;bool banner=false;
    while(phase!=4){
        if(stdio_usb_connected() && !banner){printf("BTD1 READY v=1 no_pair=1 storage=ram command=SCAN\n");banner=true;}
        int ch=getchar_timeout_us(0);
        if(ch>=0){
            if(ch=='\r' || ch=='\n'){
                command[used]=0;
                if(!strcmp(command,"CANCEL"))finish("cancelled");
                if(!strcmp(command,"SCAN") && phase==0){
                    phase=1;phase_us=time_us_64();
                    if(cyw43_arch_init())finish("radio_init_failed");
                    else {radio_initialized=true;registration.callback=event;hci_add_event_handler(&registration);hci_power_control(HCI_POWER_ON);}
                }
                used=0;
            }else if(used<sizeof command-1)command[used++]=(char)ch;
            else used=0;
        }
        if(phase && phase!=4)cyw43_arch_poll();
        uint64_t now=time_us_64();
        if(phase==1 && now-phase_us>10000000)finish("radio_init_timeout");
        if(phase==2 && now-phase_us>14000000)finish("inquiry_timeout");
        if(phase==3 && now-phase_us>25000000)finish("complete");
        if(now-boot_us>90000000)finish("boot_limit");
        if(probe_ram_bank_errors())finish("ram_bank_error");
        sleep_ms(1);
    }
    if(radio_initialized){
        uint64_t until=time_us_64()+500000;
        while(hci_get_state()!=HCI_STATE_OFF && time_us_64()<until){cyw43_arch_poll();sleep_ms(1);}
        cyw43_arch_deinit();
    }
    sleep_ms(300);reset_usb_boot(0,0);return 0;
}
