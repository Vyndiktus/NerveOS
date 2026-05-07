/*
 * hci-info: Read controller info via MGMT READ_INFO (0x0004).
 * Reads cached state from kernel — no HCI chip response needed.
 * Cross-compile: aarch64-linux-gnu-gcc -static -o hci-info hci-info.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
#include <stdint.h>

#define AF_BLUETOOTH    31
#define BTPROTO_HCI     1
#define HCI_CHANNEL_CONTROL 3
#define MGMT_INDEX_NONE 0xFFFF

/* Management opcodes */
#define MGMT_OP_READ_INFO          0x0004
#define MGMT_OP_READ_CONFIG_INFO   0x0037
#define MGMT_OP_START_DISCOVERY    0x0023
#define MGMT_OP_STOP_DISCOVERY     0x0024

#define MGMT_EV_CMD_COMPLETE 0x0001
#define MGMT_EV_CMD_STATUS   0x0002
#define MGMT_EV_DISCOVERING  0x0013
#define MGMT_EV_DEVICE_FOUND 0x0012

/* current_settings bits */
#define MGMT_SETTING_POWERED       (1 << 0)
#define MGMT_SETTING_CONNECTABLE   (1 << 1)
#define MGMT_SETTING_DISCOVERABLE  (1 << 3)
#define MGMT_SETTING_SSP           (1 << 6)
#define MGMT_SETTING_BREDR         (1 << 7)
#define MGMT_SETTING_LE            (1 << 9)

struct sockaddr_hci {
    uint16_t hci_family;
    uint16_t hci_dev;
    uint16_t hci_channel;
} __attribute__((packed));

struct mgmt_hdr {
    uint16_t opcode;
    uint16_t index;
    uint16_t len;
} __attribute__((packed));

struct mgmt_ev_hdr {
    uint16_t event;
    uint16_t index;
    uint16_t len;
} __attribute__((packed));

struct mgmt_ev_cmd_complete {
    uint16_t opcode;
    uint8_t  status;
    uint8_t  data[];
} __attribute__((packed));

/* mgmt_rp_read_info — exact kernel layout (include/net/bluetooth/mgmt.h):
 * bdaddr(6), version(1), manufacturer(2), supported_settings(4),
 * current_settings(4), dev_class(3), name(249), short_name(11) */
struct mgmt_rp_read_info {
    uint8_t  bdaddr[6];
    uint8_t  version;
    uint16_t manufacturer;
    uint32_t supported_settings;
    uint32_t current_settings;
    uint8_t  dev_class[3];
    uint8_t  name[249];
    uint8_t  short_name[11];
} __attribute__((packed));

static int mgmt_sock = -1;

static int mgmt_open(void) {
    struct sockaddr_hci addr;
    struct timeval tv = { .tv_sec = 5, .tv_usec = 0 };
    mgmt_sock = socket(AF_BLUETOOTH, SOCK_RAW | SOCK_CLOEXEC, BTPROTO_HCI);
    if (mgmt_sock < 0) { perror("socket"); return -1; }
    setsockopt(mgmt_sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    memset(&addr, 0, sizeof(addr));
    addr.hci_family  = AF_BLUETOOTH;
    addr.hci_dev     = MGMT_INDEX_NONE;
    addr.hci_channel = HCI_CHANNEL_CONTROL;
    if (bind(mgmt_sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind"); close(mgmt_sock); return -1;
    }
    return 0;
}

static int mgmt_send(uint16_t opcode, uint16_t index,
                     const void *param, uint16_t param_len) {
    uint8_t buf[512];
    struct mgmt_hdr *hdr = (struct mgmt_hdr *)buf;
    hdr->opcode = opcode;
    hdr->index  = index;
    hdr->len    = param_len;
    if (param && param_len > 0)
        memcpy(buf + sizeof(*hdr), param, param_len);
    ssize_t n = send(mgmt_sock, buf, sizeof(*hdr) + param_len, 0);
    return (n < 0) ? -1 : 0;
}

static int mgmt_recv_loop(uint8_t *out, size_t outsz,
                           uint16_t want_ev, uint16_t want_op) {
    uint8_t buf[1024];
    for (int tries = 0; tries < 30; tries++) {
        ssize_t n = recv(mgmt_sock, buf, sizeof(buf), 0);
        if (n < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) break;
            perror("recv"); break;
        }
        if (n < (ssize_t)sizeof(struct mgmt_ev_hdr)) continue;
        struct mgmt_ev_hdr *eh = (struct mgmt_ev_hdr *)buf;
        if (eh->event == want_ev) {
            struct mgmt_ev_cmd_complete *cc =
                (struct mgmt_ev_cmd_complete *)(buf + sizeof(*eh));
            if (n >= (ssize_t)(sizeof(*eh) + 3) && cc->opcode == want_op) {
                if (cc->status != 0) {
                    fprintf(stderr, "CMD_COMPLETE status=0x%02x\n", cc->status);
                    return -1;
                }
                size_t data_len = n - sizeof(*eh) - 3;
                if (out && data_len > 0)
                    memcpy(out, cc->data, data_len < outsz ? data_len : outsz);
                return (int)data_len;
            }
        }
        /* Print other events for diagnostics */
        printf("  [skip ev=0x%04x idx=0x%04x]\n", eh->event, eh->index);
    }
    return -1;
}

static void print_settings(uint32_t s) {
    if (s & MGMT_SETTING_POWERED)      printf(" POWERED");
    if (s & MGMT_SETTING_CONNECTABLE)  printf(" CONNECTABLE");
    if (s & MGMT_SETTING_DISCOVERABLE) printf(" DISCOVERABLE");
    if (s & MGMT_SETTING_SSP)          printf(" SSP");
    if (s & MGMT_SETTING_BREDR)        printf(" BREDR");
    if (s & MGMT_SETTING_LE)           printf(" LE");
    printf(" (0x%08x)\n", s);
}

int main(int argc, char *argv[]) {
    uint16_t index = 0;
    if (argc > 1) index = (uint16_t)atoi(argv[1]);

    if (mgmt_open() < 0) return 1;

    /* Drain initial events */
    {
        struct timeval tv = { .tv_sec = 0, .tv_usec = 200000 };
        setsockopt(mgmt_sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
        uint8_t b[512];
        for (int i = 0; i < 16; i++)
            if (recv(mgmt_sock, b, sizeof(b), 0) < 0) break;
        tv.tv_sec = 5; tv.tv_usec = 0;
        setsockopt(mgmt_sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    }

    /* READ_INFO for configured device (index 0 = hci0) */
    printf("=== MGMT READ_INFO for hci%u ===\n", index);
    if (mgmt_send(MGMT_OP_READ_INFO, index, NULL, 0) < 0) {
        perror("send READ_INFO"); close(mgmt_sock); return 1;
    }

    struct mgmt_rp_read_info info;
    memset(&info, 0, sizeof(info));
    int r = mgmt_recv_loop((uint8_t *)&info, sizeof(info),
                           MGMT_EV_CMD_COMPLETE, MGMT_OP_READ_INFO);
    if (r < 0) {
        fprintf(stderr, "READ_INFO failed or timed out\n");

        /* Try READ_CONFIG_INFO for unconfigured device */
        printf("\n=== Trying READ_CONFIG_INFO (unconfigured path) ===\n");
        if (mgmt_send(MGMT_OP_READ_CONFIG_INFO, index, NULL, 0) < 0) {
            perror("send READ_CONFIG_INFO"); close(mgmt_sock); return 1;
        }
        uint8_t cfg[64] = {0};
        r = mgmt_recv_loop(cfg, sizeof(cfg),
                           MGMT_EV_CMD_COMPLETE, MGMT_OP_READ_CONFIG_INFO);
        if (r >= 10) {
            uint16_t manufacturer = cfg[0] | (cfg[1] << 8);
            uint32_t supported    = cfg[2] | (cfg[3]<<8) | (cfg[4]<<16) | (cfg[5]<<24);
            uint32_t missing      = cfg[6] | (cfg[7]<<8) | (cfg[8]<<16) | (cfg[9]<<24);
            printf("  manufacturer:       0x%04x\n", manufacturer);
            printf("  supported_options:  0x%08x\n", supported);
            printf("  missing_options:    0x%08x %s\n", missing,
                   missing ? "(device UNCONFIGURED)" : "(device configured OK)");
        }
        close(mgmt_sock); return 1;
    }

    /* Print controller info */
    printf("BD_ADDR:             %02X:%02X:%02X:%02X:%02X:%02X\n",
           info.bdaddr[5], info.bdaddr[4], info.bdaddr[3],
           info.bdaddr[2], info.bdaddr[1], info.bdaddr[0]);
    printf("Version:             0x%02x  Manufacturer: 0x%04x\n",
           info.version, info.manufacturer);
    printf("Device class:        %02X:%02X:%02X\n",
           info.dev_class[2], info.dev_class[1], info.dev_class[0]);
    printf("Name:                %.248s\n", info.name);
    printf("Supported settings: ");
    print_settings(info.supported_settings);
    printf("Current settings:   ");
    print_settings(info.current_settings);

    int powered = (info.current_settings & MGMT_SETTING_POWERED) != 0;
    printf("\nhci%u is %s\n", index, powered ? "POWERED (UP)" : "NOT POWERED (DOWN)");

    close(mgmt_sock);
    return 0;
}
