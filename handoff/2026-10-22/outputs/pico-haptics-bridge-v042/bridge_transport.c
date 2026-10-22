#include <string.h>
#include "pico/stdlib.h"
#include "pico/cyw43_arch.h"
#include "pico/rand.h"
#include "hardware/watchdog.h"
#include "lwip/udp.h"
#include "bridge_transport.h"
#include "bridge_credentials.h"
enum { CAPACITY=256,BATCH=8 };
typedef struct {uint32_t at,sequence;uint8_t motors[8];} motor_event;
static motor_event events[CAPACITY];
static unsigned head,count;
static uint32_t produced,dropped,requests,boot_id,last_sent;
static bool initialized,active,enabled,sent_valid;
static bool draining,drain_confirmed;
static uint64_t confirmed_at;
static uint8_t input_state[9];
static uint64_t input_at;
static uint32_t input_sequence,input_updates;
static bool input_valid;
static uint64_t started,last_client;
static uint64_t last_join;
static unsigned join_attempts;
static struct udp_pcb *server;
static void put16(uint8_t *p,uint16_t v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);}
static void put32(uint8_t *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(i*8));}
static void put64(uint8_t *p,uint64_t v){for(unsigned i=0;i<8;i++)p[i]=(uint8_t)(v>>(i*8));}
static uint32_t get32(uint8_t const *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static uint64_t get64(uint8_t const *p){return (uint64_t)get32(p)|(uint64_t)get32(p+4)<<32;}
static uint32_t crc32(uint8_t const *p,size_t n){
    uint32_t c=~0u;for(size_t i=0;i<n;i++){c^=p[i];for(unsigned j=0;j<8;j++)c=(c>>1)^((0u-(c&1u))&0xedb88320u);}return ~c;
}
static uint32_t source_time(void){return (uint32_t)(time_us_64()-started);}
static void receive(void *arg,struct udp_pcb *pcb,struct pbuf *packet,ip_addr_t const *address,u16_t port){
    (void)arg;if(!packet)return;
    uint8_t request[36];
    unsigned request_size=packet->tot_len;
    if(request_size!=20 && request_size!=36){pbuf_free(packet);return;}
    pbuf_copy_partial(packet,request,request_size,0);pbuf_free(packet);
    bool final_ack=!memcmp(request,"BHE2",4);
    bool with_input=request_size==36 && !memcmp(request,"BHI2",4);
    if((!with_input && (request_size!=20 || (memcmp(request,"BHP2",4) && !final_ack)))||get64(request+8)!=BRIDGE_SESSION)return;
    // Only the task hotspot host may poll this bounded experimental stream.
    if(!IP_IS_V4(address)||ip4_addr_get_u32(ip_2_ip4(address))!=PP_HTONL(0xc0a88901u))return;
    if(with_input && !draining){
        uint8_t const *v=request+24;bool valid=(v[0]&~0xcfu)==0 && (v[1]&~0x0fu)==0 && (v[2]&~0xcfu)==0;
        for(unsigned i=3;i<9;i+=3){
            unsigned x=v[i]|(unsigned)(v[i+1]&15u)<<8;
            unsigned y=(v[i+1]>>4)|(unsigned)v[i+2]<<4;
            if(x<448 || x>3648 || y<448 || y>3648)valid=false;
        }
        uint32_t sequence=get32(request+20);
        if(valid && (!input_valid || (int32_t)(sequence-input_sequence)>0)){
            memcpy(input_state,v,9);input_sequence=sequence;input_at=time_us_64();input_valid=true;input_updates++;
        }
    }
    last_client=time_us_64();requests++;
    uint32_t ack=get32(request+16);
    if(sent_valid && (int32_t)(last_sent-ack)>=0){
        while(count && (int32_t)(ack-events[head].sequence)>=0){head=(head+1)%CAPACITY;count--;}
    }
    if(final_ack){
        if(!draining || count || ack!=produced-1u)return;
        if(!drain_confirmed)confirmed_at=time_us_64();
        drain_confirmed=true;
    }
    unsigned batch=count<BATCH?count:BATCH;unsigned size=36+16*batch;
    uint8_t response[36+16*BATCH]={0};
    memcpy(response,"BHR2",4);response[4]=2;
    response[5]=1|(active?2:0)|(enabled?4:0)|(draining?8:0)|((draining && !count)?16:0);
    put16(response+6,(uint16_t)size);put64(response+8,BRIDGE_SESSION);
    put32(response+16,get32(request+4));put32(response+20,boot_id);put32(response+24,source_time());
    put16(response+28,(uint16_t)batch);put16(response+30,(uint16_t)(dropped>65535?65535:dropped));
    for(unsigned i=0;i<batch;i++){
        motor_event const *event=events+(head+i)%CAPACITY;uint8_t *out=response+32+i*16;
        put32(out,event->at);put32(out+4,event->sequence);memcpy(out+8,event->motors,8);
    }
    put32(response+size-4,crc32(response,size-4));
    struct pbuf *reply=pbuf_alloc(PBUF_TRANSPORT,(u16_t)size,PBUF_RAM);
    if(reply){
        memcpy(reply->payload,response,size);
        if(udp_sendto(pcb,reply,address,port)==ERR_OK && batch){last_sent=events[(head+batch-1)%CAPACITY].sequence;sent_valid=true;}
        pbuf_free(reply);
    }
}
void bridge_init(void){
    started=time_us_64();boot_id=get_rand_32();watchdog_enable(8000,true);
    if(cyw43_arch_init()!=0)return;
    initialized=true;cyw43_arch_enable_sta_mode();
    cyw43_wifi_pm(&cyw43_state,CYW43_NO_POWERSAVE_MODE);
    cyw43_arch_wifi_connect_async(bridge_ssid,bridge_key,CYW43_AUTH_WPA2_AES_PSK);
    last_join=time_us_64();join_attempts=1;
    server=udp_new();
    if(server && udp_bind(server,IP_ADDR_ANY,49724)==ERR_OK)udp_recv(server,receive,NULL);
    else if(server){udp_remove(server);server=NULL;}
}
void bridge_poll(bool upstream,bool vibration){
    active=upstream && !draining;enabled=vibration && !draining;
    if(initialized){
        cyw43_arch_poll();
        // A failed asynchronous association otherwise remains failed forever.
        // Retry only before a PC session exists; never resume output implicitly.
        int link=cyw43_tcpip_link_status(&cyw43_state,CYW43_ITF_STA);
        if(!last_client && join_attempts<3 && link<=0 && time_us_64()-last_join>8000000){
            cyw43_arch_wifi_connect_async(bridge_ssid,bridge_key,CYW43_AUTH_WPA2_AES_PSK);
            last_join=time_us_64();join_attempts++;
        }
    }
}
void bridge_record(uint8_t const *motors){
    if(draining)return;
    if(count<CAPACITY){
        motor_event *event=events+(head+count)%CAPACITY;
        event->at=source_time();event->sequence=produced;memcpy(event->motors,motors,8);count++;
    }else dropped++;
    produced++;
}
void bridge_begin_drain(void){draining=true;active=false;enabled=false;}
bool bridge_drain_confirmed(void){return draining && drain_confirmed && count==0 && time_us_64()-confirmed_at>=50000;}
bool bridge_client_ready(void){return initialized && !dropped && last_client && time_us_64()-last_client<250000;}
uint8_t bridge_diagnostic_byte(uint32_t offset){
    uint8_t d[64]={0};memcpy(d,"BRD2",4);d[4]=2;d[5]=initialized;d[6]=active;d[7]=enabled;
    if(initialized)memcpy(d+8,&netif_ip4_addr(&cyw43_state.netif[CYW43_ITF_STA])->addr,4);
    put32(d+12,produced);put32(d+16,count);put32(d+20,dropped);put32(d+24,requests);put32(d+28,boot_id);
    put32(d+32,(uint32_t)last_client);put32(d+36,initialized?(uint32_t)cyw43_tcpip_link_status(&cyw43_state,CYW43_ITF_STA):UINT32_MAX);
    put64(d+40,BRIDGE_SESSION);put32(d+48,input_sequence);
    d[52]=input_valid && !draining && time_us_64()-input_at<80000;d[53]=input_valid;
    put32(d+56,input_updates);put32(d+60,input_valid?(uint32_t)(time_us_64()-input_at):UINT32_MAX);
    return offset<64?d[offset]:0xff;
}
bool bridge_copy_input(uint8_t *out){
    if(draining || !input_valid || time_us_64()-input_at>=80000)return false;
    memcpy(out,input_state,9);return true;
}
void bridge_close(void){
    active=false;enabled=false;
    if(server){udp_remove(server);server=NULL;}
    if(initialized){cyw43_arch_disable_sta_mode();cyw43_arch_deinit();initialized=false;}
}
