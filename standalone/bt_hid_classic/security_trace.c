/* Allowlisted metadata only. Never dump packet bodies, keys, names or addresses. */
#include <stdio.h>
#include <stdarg.h>
#include "pico/time.h"
#include "btstack.h"
#include "hci_dump.h"
#include "security_trace.h"
static unsigned records;
static uint64_t start;
static int prefix(void){
    if(records>=96)return 0;
    records++;
    printf("BTH3 TRACE us=%llu ",(unsigned long long)(time_us_64()-start));
    return 1;
}
static void features(const uint8_t *p){
    for(unsigned i=0;i<8;i++)printf("%02x",p[i]);
    printf("\n");
}
static void packet(uint8_t type,uint8_t incoming,uint8_t *p,uint16_t n){
    if(!incoming && type==HCI_COMMAND_DATA_PACKET && n>=3 && (unsigned)p[2]+3<=n){
        uint16_t op=little_endian_read_16(p,0);
        switch(op){
        case HCI_OPCODE_HCI_IO_CAPABILITY_REQUEST_REPLY:
            if(n>=12 && prefix())printf("TX_IO_REPLY io=%u oob=%u authreq=%u\n",p[9],p[10],p[11]);
            break;
        case HCI_OPCODE_HCI_IO_CAPABILITY_REQUEST_NEGATIVE_REPLY:
            if(n>=10 && prefix())printf("TX_IO_NEGATIVE reason=0x%02x\n",p[9]);
            break;
        case HCI_OPCODE_HCI_AUTHENTICATION_REQUESTED:
        case HCI_OPCODE_HCI_LINK_KEY_REQUEST_NEGATIVE_REPLY:
        case HCI_OPCODE_HCI_USER_CONFIRMATION_REQUEST_REPLY:
        case HCI_OPCODE_HCI_USER_CONFIRMATION_REQUEST_NEGATIVE_REPLY:
            if(prefix())printf("TX_COMMAND opcode=0x%04x\n",op);
            break;
        case HCI_OPCODE_HCI_WRITE_SIMPLE_PAIRING_MODE:
        case HCI_OPCODE_HCI_WRITE_SECURE_CONNECTIONS_HOST_SUPPORT:
            if(n>=4 && prefix())printf("TX_CAPABILITY opcode=0x%04x enabled=%u\n",op,p[3]);
            break;
        default:break;
        }
    }
    if(!incoming || type!=HCI_EVENT_PACKET || n<2 || (unsigned)p[1]+2>n)return;
    switch(p[0]){
    case HCI_EVENT_READ_REMOTE_SUPPORTED_FEATURES_COMPLETE:
        if(n>=13 && prefix()) {printf("RX_REMOTE_FEATURES status=0x%02x page=0 bits=",p[2]);features(p+5);}
        break;
    case HCI_EVENT_READ_REMOTE_EXTENDED_FEATURES_COMPLETE:
        if(n>=15 && prefix()){printf("RX_REMOTE_FEATURES status=0x%02x page=%u max=%u bits=",p[2],p[5],p[6]);features(p+7);}
        break;
    case HCI_EVENT_SIMPLE_PAIRING_COMPLETE:
        if(n>=9 && prefix())printf("RX_SIMPLE_PAIRING status=0x%02x\n",p[2]);
        break;
    case HCI_EVENT_ENCRYPTION_CHANGE:
        if(n>=6 && prefix())printf("RX_ENCRYPTION status=0x%02x enabled=%u\n",p[2],p[5]);
        break;
    case HCI_EVENT_COMMAND_COMPLETE:
        if(n>=14 && little_endian_read_16(p,3)==0x1003 && prefix()){
            printf("RX_LOCAL_FEATURES status=0x%02x bits=",p[5]);features(p+6);
        }
        break;
    default:break;
    }
}
static void message(int level,const char *format,va_list args){
    (void)level;(void)format;(void)args; /* No unreviewed SDK text or secret payloads. */
}
static const hci_dump_t observer={.reset=NULL,.log_packet=packet,.log_message=message};
void security_trace_init(void){records=0;start=time_us_64();hci_dump_init(&observer);}
