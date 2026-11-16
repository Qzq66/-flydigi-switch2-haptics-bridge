/* Build-only passive TinyUSB application driver for the known receiver.
 * No vendor requests, output reports, XInput activation, motor or config writes.
 * Standard USB host enumeration is owned by TinyUSB, not implemented here.
 */
#include <stdbool.h>
#include <string.h>
#include "tusb.h"
#include "host/usbh_pvt.h"
#include "receiver_input_probe.h"
static receiver_probe_snapshot_t snapshot;
static uint8_t address;
static bool pending;
CFG_TUSB_MEM_ALIGN static uint8_t input[RECEIVER_PROBE_PACKET_BYTES];
receiver_probe_snapshot_t const *receiver_probe_snapshot(void) { return &snapshot; }
static bool init(void) {
    memset(&snapshot, 0, sizeof snapshot); address=0; pending=false; return true;
}
static bool deinit(void) { address=0; pending=false; return true; }
static bool open_interface(uint8_t port, uint8_t dev, tusb_desc_interface_t const *itf, uint16_t limit) {
    (void)port;
    if (address || limit<sizeof(*itf) || itf->bLength!=sizeof(*itf) ||
        itf->bInterfaceClass!=0xff || itf->bInterfaceSubClass!=0x5d || itf->bInterfaceProtocol!=1) return false;
    uint16_t vid=0,pid=0;
    if (!tuh_vid_pid_get(dev,&vid,&pid) || vid!=0x37d7 || pid!=0x2502 || tuh_speed_get(dev)!=TUSB_SPEED_FULL) return false;
    uint8_t const *raw=(uint8_t const *)itf;
    tusb_desc_endpoint_t selected;
    uint8_t found=0;
    for (uint16_t offset=itf->bLength;offset<limit;) {
        if (limit-offset<2) return false;
        uint8_t length=raw[offset],type=raw[offset+1];
        if (length<2 || length>limit-offset) return false;
        if (type==TUSB_DESC_INTERFACE || type==TUSB_DESC_INTERFACE_ASSOCIATION) break;
        if (type==TUSB_DESC_ENDPOINT) {
            if (length<sizeof(tusb_desc_endpoint_t)) return false;
            tusb_desc_endpoint_t ep; memcpy(&ep,raw+offset,sizeof ep);
            if ((ep.bEndpointAddress&0x80) && ep.bmAttributes.xfer==TUSB_XFER_INTERRUPT) {
                uint16_t size=tu_edpt_packet_size(&ep);
                if (++found!=1 || size==0 || size>sizeof input || !(ep.bEndpointAddress&0x0f)) return false;
                selected=ep;
            }
        }
        offset=(uint16_t)(offset+length);
    }
    if (found!=1 || !tuh_edpt_open(dev,&selected)) return false;
    address=dev; snapshot.vid=vid;snapshot.pid=pid;
    snapshot.interface_number=itf->bInterfaceNumber;
    snapshot.endpoint_in=selected.bEndpointAddress;
    snapshot.packet_size=tu_edpt_packet_size(&selected);
    return true;
}
static bool receive_next(void) {
    if (!address || pending || snapshot.error || snapshot.complete || !(snapshot.endpoint_in&0x80)) return false;
    pending=usbh_edpt_xfer(address,snapshot.endpoint_in,input,snapshot.packet_size);
    if (!pending) snapshot.error=1; /* fail closed, no transfer retry */
    return pending;
}
static bool set_config(uint8_t dev,uint8_t itf) {
    if (dev!=address || itf!=snapshot.interface_number) return false;
    usbh_driver_set_config_complete(dev,itf);
    return receive_next();
}
static bool received(uint8_t dev,uint8_t ep,xfer_result_t result,uint32_t length) {
    if (dev!=address || ep!=snapshot.endpoint_in || !pending) return false;
    pending=false;
    if (result!=XFER_RESULT_SUCCESS || length>snapshot.packet_size) { snapshot.error=2;return false; }
    uint32_t index=snapshot.packets;
    if (index>=RECEIVER_PROBE_PACKETS) { snapshot.complete=1;return true; }
    snapshot.lengths[index]=(uint8_t)length;
    memcpy(snapshot.data[index],input,length); snapshot.packets++;
    if (snapshot.packets==RECEIVER_PROBE_PACKETS) { snapshot.complete=1;return true; }
    return receive_next(); /* normal bounded input polling; not a fault retry */
}
static void close_device(uint8_t dev) {
    if (dev==address) { address=0;pending=false;snapshot.disconnects++; }
}
static usbh_class_driver_t const driver={
    .name="flydigi-passive-input-probe",.init=init,.deinit=deinit,
    .open=open_interface,.set_config=set_config,.xfer_cb=received,.close=close_device
};
usbh_class_driver_t const *usbh_app_driver_get_cb(uint8_t *count) { *count=1;return &driver; }
