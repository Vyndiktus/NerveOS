/*
 * hci-up: bring up hci0 and read BD_ADDR via raw socket syscalls.
 * No BlueZ dependency — uses kernel HCIDEVUP ioctl directly.
 * Cross-compile: aarch64-linux-gnu-gcc -static -o hci-up hci-up.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <stdint.h>

/* HCI socket constants */
#define AF_BLUETOOTH    31
#define BTPROTO_HCI     1
#define SOL_HCI         0
#define HCI_FILTER      2

/* HCI ioctls */
#define HCIDEVUP        _IOW('H', 201, int)
#define HCIDEVDOWN      _IOW('H', 202, int)
#define HCIGETDEVINFO   _IOR('H', 211, int)

/* HCI packet types */
#define HCI_COMMAND_PKT 0x01
#define HCI_EVENT_PKT   0x04

/* HCI commands */
#define OGF_INFO_PARAM  0x04
#define OCF_READ_BD_ADDR 0x0009

struct sockaddr_hci {
    uint16_t hci_family;
    uint16_t hci_dev;
    uint16_t hci_channel;
};

struct hci_filter {
    uint32_t type_mask;
    uint64_t event_mask;
    uint16_t opcode;
};

static int open_hci_raw(int dev_id) {
    int s;
    struct sockaddr_hci addr;
    struct hci_filter flt;

    s = socket(AF_BLUETOOTH, SOCK_RAW, BTPROTO_HCI);
    if (s < 0) {
        perror("socket(AF_BLUETOOTH)");
        return -1;
    }

    memset(&addr, 0, sizeof(addr));
    addr.hci_family = AF_BLUETOOTH;
    addr.hci_dev = dev_id;
    addr.hci_channel = 0; /* HCI_CHANNEL_RAW */

    if (bind(s, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind");
        close(s);
        return -1;
    }

    /* Accept all event types */
    memset(&flt, 0, sizeof(flt));
    flt.type_mask = ~0u;
    flt.event_mask = ~0ull;
    if (setsockopt(s, SOL_HCI, HCI_FILTER, &flt, sizeof(flt)) < 0) {
        perror("setsockopt(HCI_FILTER)");
        close(s);
        return -1;
    }

    return s;
}

static int hci_devup(int dev_id) {
    int s, ret;
    s = socket(AF_BLUETOOTH, SOCK_RAW, BTPROTO_HCI);
    if (s < 0) {
        perror("socket for devup");
        return -1;
    }
    ret = ioctl(s, HCIDEVUP, dev_id);
    if (ret < 0 && errno != EALREADY) {
        perror("HCIDEVUP ioctl");
        close(s);
        return -1;
    }
    close(s);
    return 0;
}

static void read_bd_addr(int s) {
    uint8_t cmd[4];
    uint8_t buf[256];
    int n;
    struct timeval tv = { .tv_sec = 3, .tv_usec = 0 };

    /* Build HCI command: Read BD_ADDR */
    uint16_t opcode = ((OGF_INFO_PARAM & 0x3f) << 10) | (OCF_READ_BD_ADDR & 0x3ff);
    cmd[0] = HCI_COMMAND_PKT;
    cmd[1] = opcode & 0xff;
    cmd[2] = (opcode >> 8) & 0xff;
    cmd[3] = 0; /* no params */

    if (write(s, cmd, 4) < 0) {
        perror("write HCI cmd");
        return;
    }

    setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

    while (1) {
        n = read(s, buf, sizeof(buf));
        if (n < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                printf("Timeout waiting for BD_ADDR response\n");
            } else {
                perror("read HCI event");
            }
            return;
        }
        /* Look for HCI event 0x0e (Command Complete) with opcode match */
        if (n >= 7 && buf[0] == HCI_EVENT_PKT && buf[1] == 0x0e) {
            uint16_t resp_op = buf[4] | (buf[5] << 8);
            if (resp_op == opcode && buf[6] == 0x00 && n >= 13) {
                uint8_t *addr = &buf[7];
                printf("BD_ADDR: %02X:%02X:%02X:%02X:%02X:%02X\n",
                       addr[5], addr[4], addr[3], addr[2], addr[1], addr[0]);
                return;
            }
        }
    }
}

int main(int argc, char *argv[]) {
    int dev_id = 0;
    int s;

    if (argc > 1) dev_id = atoi(argv[1]);

    printf("Bringing up hci%d...\n", dev_id);
    if (hci_devup(dev_id) < 0) {
        fprintf(stderr, "Failed to bring up hci%d\n", dev_id);
        return 1;
    }
    printf("hci%d is UP\n", dev_id);

    printf("Opening raw HCI socket...\n");
    s = open_hci_raw(dev_id);
    if (s < 0) return 1;

    printf("Reading BD_ADDR...\n");
    read_bd_addr(s);

    close(s);
    printf("Done.\n");
    return 0;
}
