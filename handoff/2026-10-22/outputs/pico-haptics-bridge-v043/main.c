// Bounded L+R registration candidate. No other buttons or actuator path.
#include <stdint.h>
#include <string.h>
#include "pico/stdlib.h"
#include "hardware/watchdog.h"
#include "pico/bootrom.h"
#include "tusb.h"
#include "virtual_spi.h"
#include "capture_journal.h"
#include "bridge_transport.h"
#include "session_policy.h"

enum { DATA_LEN=63,QUEUE_LEN=16,TRACE_LEN=64 };
typedef struct {uint8_t id,p[DATA_LEN];} frame_t;
static frame_t queue[QUEUE_LEN];
static uint8_t head,tail,count,timer,mode,usb_stage,lights,imu,vibration;
static uint8_t last_rumble[8],last_reply[DATA_LEN];
static uint8_t trace[TRACE_LEN][4];
static uint32_t received,replies,rejected,overflow,short_packets,rumble_packets,trace_count;
static bool have_rumble,identify_pending;
static bool ending,end_requested,journal_sealed;
#if PICO_NO_FLASH && BRIDGE_RAM_DIAGNOSTIC_RECOVERY
static bool ram_snapshot_ready;
#endif
static uint64_t rumble_at,reboot_at,input_at;
static uint64_t registration_at;
static bool registration_scheduled,registration_cancelled,registration_requested;
static uint8_t registration_flags,mounts,unmounts,suspends;
static uint32_t input_reports,pressed_reports,released_reports;
static uint8_t const mac[6]={0x02,0x00,0x00,0x23,0x50,0x01};
static uint64_t now_ms(void){return time_us_64()/1000;}
static void reboot_board(void){
#if PICO_NO_FLASH && defined(BRIDGE_RAM_END_BOOTSEL) && BRIDGE_RAM_END_BOOTSEL
    reset_usb_boot(0,0);
#else
    watchdog_reboot(0,0,10);
#endif
    while(true)tight_loop_contents();
}
static void put32(uint8_t *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(8*i));}
static uint32_t get32(uint8_t const *p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static void clear_rumble(void){have_rumble=false;memset(last_rumble,0,8);}
static bool registration_pressed(void){
    uint64_t now=now_ms();
    return registration_at && !registration_cancelled && mode==0x30 &&
        usb_stage==5 && now>=registration_at && now<registration_at+400;
}
static void registration_cancel(void){
    if(registration_scheduled || registration_requested){registration_cancelled=true;registration_flags|=8;}
}
static void state_reset(void){registration_cancel();head=tail=count=0;mode=0;usb_stage=0;lights=imu=vibration=0;clear_rumble();}
// Stationary-only mode 2 layout follows switch-pico, MIT, commit
// 7449d6d029a0d3aa1ff1ce80d524a8f7b1e08ba8. See refs/switch-pico-LICENSE.
// No measured motion is claimed: quaternion (x,y,z,w) = (0,0,0,1).
static void put_bits(uint8_t *p,unsigned offset,uint32_t value,unsigned bits){
    for(unsigned i=0;i<bits;i++){
        unsigned at=offset+i;
        if(value & (1u<<i))p[at/8]|=(uint8_t)(1u<<(at%8));
    }
}
static void neutral(uint8_t *p,bool motion){
    memset(p,0,DATA_LEN);p[0]=timer++;p[1]=0x81;
    p[5]=0;p[6]=8;p[7]=0x80;p[8]=0;p[9]=8;p[10]=0x80;p[11]=0x80;
    bridge_copy_input(p+2);
    if(registration_pressed()){p[2]|=0x40;p[4]|=0x40;}
    if(motion && imu==1)for(unsigned i=0;i<3;i++)p[17+12*i]=0x10;
    if(motion && imu==2){
        uint8_t *d=p+12;d[5]=0x10; // Synthetic stationary +1g Z, Y/X/Z order.
        put_bits(d,48,2,2); // Mode 2.
        put_bits(d,50,3,2); // Omitted largest component w=+1; x/y/z=0.
        put_bits(d,271,(uint32_t)(now_ms()&0x7ffu),11);
        put_bits(d,282,3,6);
    }
}
static bool enqueue(uint8_t id,uint8_t const *p){
    if(count==QUEUE_LEN){overflow++;return false;}
    queue[tail].id=id;memcpy(queue[tail].p,p,DATA_LEN);tail=(tail+1)%QUEUE_LEN;count++;return true;
}
static void identify(uint8_t *p){
    memset(p,0,DATA_LEN);p[0]=1;p[2]=3;
    for(unsigned i=0;i<6;i++)p[3+i]=mac[5-i];
}
static void receive_rumble(uint8_t const *p){
    bridge_record(p);memcpy(last_rumble,p,8);rumble_at=now_ms();have_rumble=true;rumble_packets++;
}
static void diagnostics(uint8_t *p){
    memset(p,0,64);memcpy(p,"BCAP",4);p[4]=5;p[5]=mode;p[6]=have_rumble;p[7]=PICO_NO_FLASH;
    put32(p+8,received);put32(p+12,replies);put32(p+16,rumble_packets);put32(p+20,rejected);
    put32(p+24,overflow);put32(p+28,short_packets);memcpy(p+32,last_rumble,8);
    p[40]=usb_stage;p[41]=lights;p[42]=imu;p[43]=vibration;put32(p+44,trace_count);
    put32(p+48,input_reports);put32(p+52,pressed_reports);put32(p+56,released_reports);
    p[60]=registration_flags;p[61]=mounts;p[62]=unmounts;p[63]=suspends;
}
static bool read_virtual(uint32_t address,uint8_t *p,uint8_t size){
    if(size>29 || (size && address>UINT32_MAX-(size-1u)))return false;
    uint8_t snapshot[64];diagnostics(snapshot);
    for(uint8_t i=0;i<size;i++){
        uint32_t at=address+i;
        if(at>=0x9000 && at<0x9040)p[i]=snapshot[at-0x9000];
        else if(at>=0x9200 && at<0x9268)p[i]=bridge_diagnostic_byte(at-0x9200);
        else if(at>=0x9100 && at<0x9200)p[i]=((uint8_t*)trace)[at-0x9100];
        else if(at>=0xa000 && at<0x1a000)p[i]=capture_preview_byte(at-0xa000);
        else if(!virtual_spi_read(at,p+i,1))return false;
    }
    return true;
}
void tud_hid_set_report_cb(uint8_t instance,uint8_t id,hid_report_type_t type,uint8_t const *p,uint16_t n){
    (void)instance;
    if(type!=HID_REPORT_TYPE_OUTPUT){rejected++;return;}
    if(!id){if(!n){short_packets++;return;}id=*p++;n--;}
    if(n>DATA_LEN){rejected++;return;}
#if PICO_NO_FLASH && BRIDGE_RAM_DIAGNOSTIC_RECOVERY
    if(ram_snapshot_ready){
        if(id==0x80 && n>=9 && p[0]==0xfe && !memcmp(p+1,"RESETLAB",8)){reboot_at=now_ms()+120;return;}
        // Immutable snapshot-only phase: no normal mode/input/motor commands.
        if(id==1 && n>=15 && p[9]==0x10 && p[14]>0 && p[14]<=29){
            uint32_t address=get32(p+10);uint8_t length=p[14];
            uint8_t response[DATA_LEN];neutral(response,false);response[13]=0x10;
            if(address==0x9280 && length==8)memcpy(response+19,"SNAP043\1",8);
            else if(address>=0xa000 && address<=0x1a000u-length){
                for(unsigned i=0;i<length;i++)response[19+i]=capture_preview_byte(address-0xa000+i);
            }else return;
            response[12]=0x90;memcpy(response+14,p+10,5);enqueue(0x21,response);
        }
        return;
    }
#endif
    if(ending || journal_sealed)return;
    if(id==0x80 && n>=9 && p[0]==0xfc && !memcmp(p+1,"ENDLAB42",8)){
#if PICO_NO_FLASH
        end_requested=true;
#else
        rejected++;
#endif
        return;
    }
    received++;
    bool debug_read=id==1 && n>=15 && p[9]==0x10 && ((get32(p+10)>=0x9000 && get32(p+10)<0x9268) || (get32(p+10)>=0xa000 && get32(p+10)<0x1a000));
    if(!debug_read){
        uint8_t *entry=trace[trace_count++%TRACE_LEN];entry[0]=id;entry[1]=n?p[0]:0;entry[2]=(uint8_t)n;entry[3]=(id==1 && n>=10)?p[9]:0;
        if(!(id==0x80 && n && (p[0]==0xfd || p[0]==0xfe))){
            capture_record(now_ms(),id,p,n);
            // Process this final recorded report, then admit no further USB
            // output callbacks before main disconnects and drains the ring.
            if(capture_at_capacity())journal_sealed=true;
        }
    }
    uint8_t response[DATA_LEN]={0};
    if(id==0x80){
        if(!n){short_packets++;return;}
        response[0]=p[0];
        switch(p[0]){
            case 1:identify(response);usb_stage=1;break;
            case 2:usb_stage=usb_stage>=3?4:2;break;
            case 3:usb_stage=3;break;
            case 4:usb_stage=5;if(!mode)mode=0x30;return;
            case 5:registration_cancel();mode=0;usb_stage=0;clear_rumble();return;
            case 0xfd:
#if PICO_NO_FLASH
                if(n>=9 && !memcmp(p+1,"SNAPLOG5",8)){uint8_t d[64];diagnostics(d);capture_preview(d,now_ms());}
                else rejected++;
#else
                rejected++;
#endif
                return;
            case 0xfe:
                if(n>=9 && !memcmp(p+1,"RESETLAB",8)){mode=0;clear_rumble();reboot_at=now_ms()+120;}
                else rejected++;
                return;
            default:rejected++;return;
        }
        enqueue(0x81,response);return;
    }
    if(id==0x10){if(n<9){short_packets++;return;}receive_rumble(p+1);return;}
    if(id!=1){rejected++;return;}
    if(n<10){short_packets++;return;}
    // Laboratory diagnostic reads must not replace the captured host rumble.
    if(!debug_read)receive_rumble(p+1);
    uint8_t sub=p[9];neutral(response,false);response[12]=0;response[13]=sub;
    switch(sub){
        case 0:case 0x33:response[12]=0x80;response[14]=3;break;
        case 1:
            // Minimal USB compatibility ACK, as used by the MIT GP2040-CE
            // Pro driver. No Bluetooth radio, LTK, host key or Flash operation.
            response[12]=0x81;response[14]=3;break;
        case 2:
            response[12]=0x82;response[14]=4;response[15]=0x91;response[16]=3;response[17]=2;
            memcpy(response+18,mac,6);response[24]=1;response[25]=2;break;
        case 3:
            if(n<11){short_packets++;return;}
            if(p[10]==0 || p[10]==0x30){mode=p[10];if(!mode)registration_cancel();response[12]=0x80;response[14]=mode;}
            else rejected++;
            break;
        case 4:response[12]=0x83;break; // All trigger elapsed times remain zero.
        case 8:
            if(n>=11 && p[10]==0)response[12]=0x80;else rejected++;
            break; // Volatile no-op for shipment-disable; never persists to Flash.
        case 0x10:
            if(n<15){short_packets++;return;}
            if(read_virtual(get32(p+10),response+19,p[14])){
                response[12]=0x90;memcpy(response+14,p+10,5);
            }else rejected++;
            break;
        case 0x21:{
            // Compatibility-only ACK as used by MIT GP2040-CE at pinned
            // f2932283ddd58a3dad9c8c4d076c5bf05522d4bf and switch-pico.
            // Only the observed 21 + zero-padded payload is supported.
            // No MCU, NFC, firmware update, radio or persistent operation.
            bool observed=n>=11 && p[10]==0x21;
            for(unsigned i=11;i<n;i++)if(p[i])observed=false;
            if(observed)response[12]=0x80;else rejected++;
            break;
        }
        case 0x30:
            if(n<11){short_packets++;return;}
            lights=p[10];response[12]=0x80;
            // Arm only once per power-on after the observed initialization path.
            // A USB suspend/release cancels permanently until the next power-on.
            if(!registration_requested && lights==0 && mode==0x30 &&
                usb_stage==5 && imu==2 && now_ms()<BRIDGE_REGISTRATION_LIMIT_MS){
                registration_requested=true;
            }
            break;
        case 0x31:response[12]=0xb0;response[14]=lights;break;
        case 0x38:
            if(n<13){short_packets++;return;}
            response[12]=0x80;break; // No physical LEDs are driven.
        case 0x40:case 0x48:
            if(n<11){short_packets++;return;}
            if(p[10]>(sub==0x40?2:1)){rejected++;break;}
            if(sub==0x40)imu=p[10];else vibration=p[10];
            response[12]=0x80;break;
        case 0x41:
            if(n<14){short_packets++;return;}
            if(p[10]>3 || p[11]>3 || p[12]>1 || p[13]>1){rejected++;break;}
            response[12]=0x80;break;
        case 0x50:response[12]=0xd0;response[14]=0x40;response[15]=6;break;
        default:rejected++;break; // Pairing, upgrade, SPI write/erase, NFC unsupported.
    }
    memcpy(last_reply,response,DATA_LEN);enqueue(0x21,response);
}
uint16_t tud_hid_get_report_cb(uint8_t instance,uint8_t id,hid_report_type_t type,uint8_t *p,uint16_t requested){
    (void)instance;
    if(id!=2 || type!=HID_REPORT_TYPE_FEATURE)return 0;
    uint16_t n=requested<DATA_LEN?requested:DATA_LEN;memcpy(p,last_reply,n);return n;
}
void tud_mount_cb(void){if(mounts<255)mounts++;state_reset();identify_pending=true;capture_mounted();}
void tud_umount_cb(void){if(unmounts<255)unmounts++;state_reset();identify_pending=false;}
void tud_suspend_cb(bool wake){(void)wake;if(suspends<255)suspends++;state_reset();identify_pending=false;}
int main(void){
    bridge_init();
    virtual_spi_init();
    capture_init(now_ms());
    tusb_rhport_init_t init={.role=TUSB_ROLE_DEVICE,.speed=TUSB_SPEED_FULL};tusb_init(0,&init);
    uint64_t start=now_ms();
    uint64_t bridge_capture_at=0;
    uint64_t drain_started=0;
    uint8_t final_diagnostics[64];
    while(true){
        tud_task();bridge_poll(mode==0x30 && usb_stage==5,vibration!=0);watchdog_update();uint64_t now=now_ms();
        if(!bridge_capture_at && bridge_client_ready() && mode==0x30 && usb_stage==5)bridge_capture_at=now;
        if(registration_requested && !registration_scheduled && !registration_cancelled && now<BRIDGE_REGISTRATION_LIMIT_MS && bridge_client_ready()){
            registration_scheduled=true;registration_at=now+3000;registration_flags|=1;
        }
        // End immediately at capacity; never silently discard an accepted word.
        // 120 seconds live, at most 180 seconds since USB initialization.
        if(!ending && (end_requested || session_due(now-start,bridge_capture_at!=0,
            bridge_capture_at?now-bridge_capture_at:0,journal_sealed))){
            diagnostics(final_diagnostics);ending=true;drain_started=now;
#if !PICO_NO_FLASH
            capture_mark_boot_limit(now-start>=BRIDGE_BOOT_MS);
#endif
            mode=0;clear_rumble();
#if PICO_NO_FLASH && BRIDGE_RAM_DIAGNOSTIC_RECOVERY
            head=tail=count=0;
#else
            tud_disconnect();
#endif
            bridge_begin_drain();
        }
        if(ending){
#if PICO_NO_FLASH && BRIDGE_RAM_DIAGNOSTIC_RECOVERY
            if(ram_snapshot_ready){
                if((reboot_at && now>=reboot_at) || now-drain_started>=90000)reboot_board();
                if(count && tud_hid_ready() && tud_hid_report(queue[head].id,queue[head].p,DATA_LEN)){
                    head=(head+1)%QUEUE_LEN;count--;replies++;
                }
                continue;
            }
#endif
            if(bridge_drain_confirmed() || now-drain_started>=1000){
                capture_mark_stream_end(bridge_drain_confirmed());
                bridge_close();
#if PICO_NO_FLASH
                // Preserve a CRC-protected RAM snapshot for BOOTSEL readback.
                capture_finish(final_diagnostics,now);
#if BRIDGE_RAM_DIAGNOSTIC_RECOVERY
                ram_snapshot_ready=true;drain_started=now;
#else
                reboot_board();
#endif
#else
                capture_finish(final_diagnostics,now);
#endif
            }
            continue;
        }
        if(have_rumble && now-rumble_at>=80)clear_rumble();
        if((reboot_at && now>=reboot_at) || now-start>=BRIDGE_REBOOT_MS){bridge_close();reboot_board();}
        if(!tud_hid_ready())continue;
        if(identify_pending){uint8_t p[DATA_LEN];identify(p);enqueue(0x81,p);identify_pending=false;}
        if(count){
            if(tud_hid_report(queue[head].id,queue[head].p,DATA_LEN)){head=(head+1)%QUEUE_LEN;count--;replies++;}
        }else if(mode==0x30 && now-input_at>=(imu==2?15u:8u)){
            uint8_t p[DATA_LEN];neutral(p,true);if(tud_hid_report(0x30,p,DATA_LEN)){
                input_at=now;input_reports++;
                if(p[2]==0x40 && p[4]==0x40){pressed_reports++;registration_flags|=2;}
                else if(registration_flags&2){released_reports++;registration_flags|=4;}
            }
        }
    }
}
