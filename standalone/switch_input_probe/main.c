/* Independent generic Switch-mode input observer. No HID output/config commands. */
#include <stdio.h>
#include <string.h>
#include <stdbool.h>
#include "pico/stdlib.h"
#include "pico/stdio_usb.h"
#include "pico/bootrom.h"
#include "pico/cyw43_arch.h"
#include "btstack.h"
#include "ram_bank.h"
#define PSM_CONTROL 0x11
#define PSM_INTERRUPT 0x13
static btstack_packet_callback_registration_t registration;
static bool radio,working,finished,locked,discovering,connecting,capturing,interrupt_open,inquiry_configured;
static bd_addr_t target;
static uint16_t control_cid,interrupt_cid;
static uint64_t boot_us,connect_us,capture_us,last_sample_us,discovery_us;
static unsigned discovered,reports,samples;
static void event(uint8_t type,uint16_t channel,uint8_t *packet,uint16_t length);
static void done(const char *why){
    if(finished)return;
    finished=true;
    printf("SWP1 DONE reason=%s reports=%u samples=%u ram_errors=%lu output_reports=0\n",
           why,reports,samples,(unsigned long)probe_ram_bank_errors());
}
static int nibble(char c){
    if(c>='0' && c<='9')return c-'0';
    if(c>='a' && c<='f')return c-'a'+10;
    if(c>='A' && c<='F')return c-'A'+10;
    return -1;
}
static bool set_target(const char *text){
    if(strlen(text)!=12)return false;
    bd_addr_t parsed;
    for(unsigned i=0;i<6;i++){
        int a=nibble(text[2*i]),b=nibble(text[2*i+1]);
        if(a<0 || b<0)return false;
        parsed[i]=(uint8_t)(a*16+b);
    }
    memcpy(target,parsed,6);return true;
}
static void print_hex(const uint8_t *p,unsigned n){for(unsigned i=0;i<n;i++)printf("%02x",p[i]);}
static void event(uint8_t type,uint16_t channel,uint8_t *p,uint16_t n){
    if(finished)return;
    if(type==L2CAP_DATA_PACKET){
        if(!interrupt_open || channel!=interrupt_cid || n<2 || n>128 || p[0]!=0xa1)return;
        reports++;
        if(reports==1)printf("SWP1 FIRST_INPUT id=0x%02x length=%u\n",p[1],n);
        uint64_t now=time_us_64();
        if(capturing && now-capture_us<15000000 && now-last_sample_us>=200000 && samples<80){
            last_sample_us=now;samples++;
            printf("SWP1 SAMPLE us=%llu data=",(unsigned long long)(now-capture_us));print_hex(p,n);printf("\n");
        }
        return;
    }
    if(type!=HCI_EVENT_PACKET || n<2 || (unsigned)p[1]+2>n)return;
    switch(p[0]){
    case HCI_EVENT_COMMAND_COMPLETE:
        if(n>=6 && little_endian_read_16(p,3)==HCI_OPCODE_HCI_WRITE_INQUIRY_MODE){
            inquiry_configured=(p[5]==0);
            printf("SWP1 INQUIRY_CONFIG status=0x%02x requested=eir\n",p[5]);
            if(p[5])done("inquiry_mode_failed");
        }
        break;
    case BTSTACK_EVENT_STATE:
        if(n>=3 && btstack_event_state_get_state(p)==HCI_STATE_WORKING){working=true;printf("SWP1 RADIO_READY\n");}
        break;
    case GAP_EVENT_INQUIRY_RESULT:
        if(!discovering || n<27 || p[26]>n-27u || discovered>=32)break;
        discovered++;
        {bd_addr_t addr;gap_event_inquiry_result_get_bd_addr(p,addr);
        printf("SWP1 DEVICE addr=");print_hex(addr,6);
        printf(" cod=%06lx name_hex=",(unsigned long)gap_event_inquiry_result_get_class_of_device(p));
        unsigned count=p[26];if(count>64)count=64;print_hex(p+27,count);printf("\n");}
        break;
    case GAP_EVENT_INQUIRY_COMPLETE:
        if(discovering)done(n>=3 && p[2]==0 ? "discovery_complete_no_connection" : "discovery_failed");
        break;
    case HCI_EVENT_CONNECTION_COMPLETE:
        if(n>=13 && connecting){
            bd_addr_t addr;hci_event_connection_complete_get_bd_addr(p,addr);
            if(memcmp(addr,target,6)){done("unexpected_peer");break;}
            unsigned status=hci_event_connection_complete_get_status(p);
            printf("SWP1 ACL status=0x%02x\n",status);
            if(status){done("acl_failed");break;}
            gap_request_security_level(hci_event_connection_complete_get_connection_handle(p),LEVEL_2);
        }
        break;
    case L2CAP_EVENT_INCOMING_CONNECTION:
        /* No unsolicited connections or automatic channel acceptance. */
        if(n>=16)l2cap_decline_connection(l2cap_event_incoming_connection_get_local_cid(p));
        break;
    case L2CAP_EVENT_CHANNEL_OPENED:
        if(n>=15 && connecting){
            bd_addr_t addr;l2cap_event_channel_opened_get_address(p,addr);
            if(memcmp(addr,target,6)){done("unexpected_channel_peer");break;}
            uint8_t status=l2cap_event_channel_opened_get_status(p);
            uint16_t psm=l2cap_event_channel_opened_get_psm(p),cid=l2cap_event_channel_opened_get_local_cid(p);
            printf("SWP1 CHANNEL psm=0x%04x status=0x%02x\n",psm,status);
            if(status){done("channel_failed");break;}
            if(psm==PSM_CONTROL){
                control_cid=cid;
                if(l2cap_create_channel(event,target,PSM_INTERRUPT,128,&interrupt_cid))done("interrupt_start_failed");
            }else if(psm==PSM_INTERRUPT){interrupt_cid=cid;interrupt_open=true;printf("SWP1 INPUT_READY command=CAPTURE output=disabled\n");}
        }
        break;
    case L2CAP_EVENT_CHANNEL_CLOSED: done("channel_closed");break;
    case HCI_EVENT_AUTHENTICATION_COMPLETE:
        if(n>=5)printf("SWP1 AUTH status=0x%02x\n",p[2]);
        break;
    case HCI_EVENT_USER_CONFIRMATION_REQUEST:
        printf("SWP1 CONFIRM_REQUEST action=none\n");break;
    case HCI_EVENT_IO_CAPABILITY_RESPONSE:
        if(n>=11)printf("SWP1 REMOTE_IO io=%u oob=%u authreq=%u\n",p[8],p[9],p[10]);
        break;
    default:break;
    }
}
int main(void){
    boot_us=time_us_64();stdio_init_all();
    bool banner=false;char line[32];unsigned used=0;bool overflow=false;
    while(!finished){
        if(stdio_usb_connected() && !banner){
            printf("SWP1 READY v=3 storage=ram output=disabled inquiry=eir_ack commands=RADIO,DISCOVER,TARGET,CONNECT,CAPTURE,CANCEL\n");banner=true;
        }
        int c=getchar_timeout_us(0);
        if(c>=0){
            if(c=='\r' || c=='\n'){
                line[used]=0;
                if(!overflow){
                    if(!strcmp(line,"CANCEL"))done("cancelled");
                    else if(!strcmp(line,"RADIO") && !radio){
                        if(cyw43_arch_init()){done("radio_init_failed");break;}
                        radio=true;l2cap_init();registration.callback=event;hci_add_event_handler(&registration);
                        gap_ssp_set_io_capability(SSP_IO_CAPABILITY_NO_INPUT_NO_OUTPUT);
                        gap_ssp_set_authentication_requirement(SSP_IO_AUTHREQ_MITM_PROTECTION_NOT_REQUIRED_GENERAL_BONDING);
                        gap_set_bondable_mode(1);gap_connectable_control(0);gap_discoverable_control(0);
                        hci_set_inquiry_mode(INQUIRY_MODE_RSSI_AND_EIR);
                        hci_power_control(HCI_POWER_ON);
                    }else if(!strcmp(line,"DISCOVER") && working && !connecting && !discovering){
                        if(!inquiry_configured){done("inquiry_mode_not_confirmed");break;}
                        discovering=true;discovery_us=time_us_64();if(gap_inquiry_start(8))done("discovery_start_failed");
                    }else if(!strncmp(line,"TARGET ",7) && !connecting && !discovering){
                        locked=set_target(line+7);printf("SWP1 TARGET_LOCKED ok=%u\n",locked);
                    }else if(!strcmp(line,"CONNECT") && working && locked && !connecting && !discovering){
                        connecting=true;connect_us=time_us_64();
                        if(l2cap_create_channel(event,target,PSM_CONTROL,128,&control_cid))done("control_start_failed");
                    }else if(!strcmp(line,"CAPTURE") && interrupt_open && connecting && !capturing){
                        capturing=true;capture_us=time_us_64();printf("SWP1 CAPTURE_BEGIN seconds=15\n");
                    }
                }
                used=0;overflow=false;
            }else if(used<sizeof(line)-1 && !overflow)line[used++]=(char)c;
            else overflow=true;
        }
        if(radio && !finished)cyw43_arch_poll();
        uint64_t now=time_us_64();
        if(capturing && now-capture_us>=15000000)done("capture_complete");
        if(connecting && !interrupt_open && now-connect_us>25000000)done("connect_timeout");
        if(discovering && now-discovery_us>14000000)done("discovery_timeout");
        if(now-boot_us>90000000)done("boot_limit");
        if(probe_ram_bank_errors())done("ram_bank_error");
        sleep_ms(1);
    }
    if(radio){
        if(interrupt_cid)l2cap_disconnect(interrupt_cid);
        if(control_cid)l2cap_disconnect(control_cid);
        hci_power_control(HCI_POWER_OFF);
        uint64_t until=time_us_64()+300000;while(time_us_64()<until){cyw43_arch_poll();sleep_ms(1);}
        cyw43_arch_deinit();
    }
    sleep_ms(200);reset_usb_boot(0,0);return 0;
}
