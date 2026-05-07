/*
 * hci-mgmt: Bring up hci0 on WCN3990 (SM8150) via management socket.
 *
 * Problem: WCN3990 NVM (crnv01.bin) contains all-zero BD_ADDR.
 * Kernel marks hci0 HCI_UNCONFIGURED → HCIDEVUP returns EOPNOTSUPP.
 *
 * Solution:
 *  1. MGMT_OP_SET_PUBLIC_ADDRESS (0x0039) — only command that works on
 *     unconfigured devices and has HCI_MGMT_UNCONFIGURED flag. Assigns a
 *     derived-from-machine-id address, clears HCI_UNCONFIGURED.
 *  2. HCIDEVUP ioctl — now works since HCI_UNCONFIGURED is cleared.
 *  3. Read BD_ADDR via raw HCI socket to confirm controller is live.
 *
 * Cross-compile: aarch64-linux-gnu-gcc -static -o hci-mgmt hci-mgmt.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <stdint.h>
#include <time.h>

#define AF_BLUETOOTH    31
#define BTPROTO_HCI     1
#define HCI_CHANNEL_CONTROL 3
#define SOL_HCI         0
#define HCI_FILTER      2

/* HCI ioctls */
#define HCIDEVUP    _IOW('H', 201, int)
#define HCIDEVDOWN  _IOW('H', 202, int)

/* HCI packet types */
#define HCI_COMMAND_PKT 0x01
#define HCI_EVENT_PKT   0x04

/* HCI Read BD_ADDR command */
#define OGF_INFO_PARAM  0x04
#define OCF_READ_BD_ADDR 0x0009

/* Management protocol opcodes */
#define MGMT_OP_SET_POWERED          0x0005
#define MGMT_OP_READ_UNCONF_LIST     0x0036
#define MGMT_OP_READ_CONFIG_INFO     0x0037
#define MGMT_OP_SET_PUBLIC_ADDRESS   0x0039

/* Management event codes */
#define MGMT_EV_CMD_COMPLETE   0x0001
#define MGMT_EV_CMD_STATUS     0x0002

/* MGMT status codes */
#define MGMT_STATUS_SUCCESS         0x00
#define MGMT_STATUS_UNKNOWN_COMMAND 0x01
#define MGMT_STATUS_REJECTED        0x0b
#define MGMT_STATUS_NOT_POWERED     0x0f
#define MGMT_STATUS_INVALID_INDEX   0x11

#define MGMT_INDEX_NONE  0xFFFF

struct sockaddr_hci {
    uint16_t hci_family;
    uint16_t hci_dev;
    uint16_t hci_channel;
};

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

struct hci_filter {
    uint32_t type_mask;
    uint64_t event_mask;
    uint16_t opcode;
};

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
        perror("bind(HCI_CHANNEL_CONTROL)"); close(mgmt_sock); return -1;
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
    if (n < 0) { perror("send mgmt"); return -1; }
    return 0;
}

static int mgmt_recv(uint8_t *raw_buf, size_t bufsz,
                     uint16_t *ev, uint16_t *idx) {
    ssize_t n = recv(mgmt_sock, raw_buf, bufsz, 0);
    if (n < 0) {
        if (errno == EAGAIN || errno == EWOULDBLOCK) fprintf(stderr, "  [timeout]\n");
        else perror("recv");
        return -1;
    }
    if (n < (ssize_t)sizeof(struct mgmt_ev_hdr)) {
        fprintf(stderr, "  [short read: %zd]\n", n); return -1;
    }
    struct mgmt_ev_hdr *eh = (struct mgmt_ev_hdr *)raw_buf;
    if (ev)  *ev  = eh->event;
    if (idx) *idx = eh->index;
    printf("  ev=0x%04x idx=0x%04x len=%u data:", eh->event, eh->index, eh->len);
    for (int i = sizeof(*eh); i < n && i < (int)(sizeof(*eh) + 16); i++)
        printf(" %02x", raw_buf[i]);
    printf("\n");
    return (int)(n - sizeof(*eh));
}

static int wait_complete(uint16_t opcode) {
    uint8_t buf[512];
    for (int tries = 0; tries < 20; tries++) {
        uint16_t ev, idx;
        int n = mgmt_recv(buf, sizeof(buf), &ev, &idx);
        if (n < 0) return -1;
        if (ev == MGMT_EV_CMD_COMPLETE && n >= 3) {
            struct mgmt_ev_cmd_complete *cc =
                (struct mgmt_ev_cmd_complete *)(buf + sizeof(struct mgmt_ev_hdr));
            if (cc->opcode == opcode) {
                printf("  CMD_COMPLETE opcode=0x%04x status=0x%02x\n",
                       cc->opcode, cc->status);
                return cc->status;
            }
        }
        if (ev == MGMT_EV_CMD_STATUS && n >= 3) {
            struct mgmt_ev_cmd_complete *cs =
                (struct mgmt_ev_cmd_complete *)(buf + sizeof(struct mgmt_ev_hdr));
            if (cs->opcode == opcode) {
                printf("  CMD_STATUS opcode=0x%04x status=0x%02x\n",
                       cs->opcode, cs->status);
                return cs->status;
            }
        }
    }
    fprintf(stderr, "  No response for opcode 0x%04x\n", opcode);
    return -1;
}

static void drain_events(void) {
    struct timeval tv = { .tv_sec = 0, .tv_usec = 200000 };
    setsockopt(mgmt_sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    uint8_t buf[512];
    printf("Draining initial events:\n");
    for (int i = 0; i < 32; i++) {
        int n = mgmt_recv(buf, sizeof(buf), NULL, NULL);
        if (n < 0) break;
    }
    tv.tv_sec = 5; tv.tv_usec = 0;
    setsockopt(mgmt_sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
}

static void make_public_addr(uint8_t addr[6]) {
    int fd = open("/etc/machine-id", O_RDONLY);
    if (fd >= 0) {
        char id[64] = {0};
        int n = read(fd, id, sizeof(id) - 1);
        close(fd);
        uint8_t h[32] = {0};
        for (int i = 0; i < n && id[i] != '\n'; i++)
            h[i % 32] ^= (uint8_t)id[i];
        for (int i = 0; i < 6; i++)
            addr[i] = h[i] ^ h[i + 6] ^ h[i + 12] ^ h[i + 18];
    } else {
        srand((unsigned)time(NULL));
        for (int i = 0; i < 6; i++) addr[i] = (uint8_t)rand();
    }
    addr[5] &= ~0x02;
    addr[5] &= ~0x01;
    /* Qualcomm OUI prefix */
    addr[5] = 0x00; addr[4] = 0x17; addr[3] = 0xF2;
    printf("Using public BT address: %02X:%02X:%02X:%02X:%02X:%02X\n",
           addr[5], addr[4], addr[3], addr[2], addr[1], addr[0]);
}

/* Try HCIDEVUP ioctl; returns 0 on success, errno on failure. */
static int try_hcidevup(int dev_id) {
    int s = socket(AF_BLUETOOTH, SOCK_RAW, BTPROTO_HCI);
    if (s < 0) { perror("socket for HCIDEVUP"); return errno; }
    int ret = ioctl(s, HCIDEVUP, dev_id);
    int saved = errno;
    close(s);
    if (ret < 0 && saved != EALREADY) {
        fprintf(stderr, "  HCIDEVUP errno=%d (%s)\n", saved, strerror(saved));
        return saved;
    }
    printf("  HCIDEVUP: success%s\n", (saved == EALREADY) ? " (already UP)" : "");
    return 0;
}

/* Open raw HCI channel to dev_id and read BD_ADDR via HCI command. */
static void read_bd_addr_raw(int dev_id) {
    struct sockaddr_hci addr;
    struct hci_filter flt;
    struct timeval tv = { .tv_sec = 5, .tv_usec = 0 };
    uint8_t buf[256];

    int s = socket(AF_BLUETOOTH, SOCK_RAW, BTPROTO_HCI);
    if (s < 0) { perror("socket(raw HCI)"); return; }

    memset(&addr, 0, sizeof(addr));
    addr.hci_family  = AF_BLUETOOTH;
    addr.hci_dev     = dev_id;
    addr.hci_channel = 0; /* HCI_CHANNEL_RAW */

    if (bind(s, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind(raw HCI)"); close(s); return;
    }

    memset(&flt, 0, sizeof(flt));
    flt.type_mask  = ~0u;
    flt.event_mask = ~0ull;
    setsockopt(s, SOL_HCI, HCI_FILTER, &flt, sizeof(flt));
    setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

    /* Build HCI Read BD_ADDR command */
    uint16_t opcode = ((OGF_INFO_PARAM & 0x3f) << 10) | (OCF_READ_BD_ADDR & 0x3ff);
    uint8_t cmd[4] = { HCI_COMMAND_PKT, opcode & 0xff, (opcode >> 8) & 0xff, 0 };

    if (write(s, cmd, 4) < 0) { perror("write HCI cmd"); close(s); return; }

    for (int tries = 0; tries < 10; tries++) {
        int n = read(s, buf, sizeof(buf));
        if (n < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK)
                fprintf(stderr, "  Timeout waiting for BD_ADDR response\n");
            else
                perror("read HCI event");
            break;
        }
        /* HCI Command Complete event (0x0e), opcode match, status=0 */
        if (n >= 13 && buf[0] == HCI_EVENT_PKT && buf[1] == 0x0e) {
            uint16_t resp_op = buf[4] | (buf[5] << 8);
            if (resp_op == opcode && buf[6] == 0x00) {
                uint8_t *a = &buf[7];
                printf("  BD_ADDR: %02X:%02X:%02X:%02X:%02X:%02X\n",
                       a[5], a[4], a[3], a[2], a[1], a[0]);
                close(s);
                return;
            }
        }
    }
    close(s);
}

int main(int argc, char *argv[]) {
    uint16_t hci_index = 0;
    if (argc > 1) hci_index = (uint16_t)atoi(argv[1]);

    printf("=== hci-mgmt: bringing up hci%u ===\n", hci_index);
    if (mgmt_open() < 0) return 1;
    drain_events();

    /* Step 1: Read config info (diagnostic; works on unconfigured devices) */
    printf("\nStep 1: READ_CONFIG_INFO for hci%u...\n", hci_index);
    if (mgmt_send(MGMT_OP_READ_CONFIG_INFO, hci_index, NULL, 0) < 0) return 1;
    int r = wait_complete(MGMT_OP_READ_CONFIG_INFO);
    if (r < 0) {
        fprintf(stderr, "  READ_CONFIG_INFO timed out\n");
    } else if (r != MGMT_STATUS_SUCCESS) {
        fprintf(stderr, "  READ_CONFIG_INFO failed: 0x%02x\n", r);
    } else {
        printf("  Config info read OK.\n");
    }

    /* Step 2: Set public address — clears HCI_UNCONFIGURED */
    printf("\nStep 2: SET_PUBLIC_ADDRESS for hci%u...\n", hci_index);
    uint8_t addr[6];
    make_public_addr(addr);
    if (mgmt_send(MGMT_OP_SET_PUBLIC_ADDRESS, hci_index, addr, 6) < 0) return 1;
    r = wait_complete(MGMT_OP_SET_PUBLIC_ADDRESS);
    if (r < 0) {
        fprintf(stderr, "  SET_PUBLIC_ADDRESS timed out\n");
        return 1;
    } else if (r == MGMT_STATUS_REJECTED) {
        fprintf(stderr, "  REJECTED — device may be powered (try after reboot)\n");
        return 1;
    } else if (r != MGMT_STATUS_SUCCESS) {
        fprintf(stderr, "  SET_PUBLIC_ADDRESS failed: 0x%02x\n", r);
        return 1;
    }
    printf("  HCI_UNCONFIGURED cleared. Draining post-address events...\n");

    /* Drain UNCONF_INDEX_REMOVED + INDEX_ADDED events */
    {
        struct timeval tv = { .tv_sec = 0, .tv_usec = 500000 };
        setsockopt(mgmt_sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
        uint8_t buf[512];
        for (int i = 0; i < 10; i++) {
            int n = mgmt_recv(buf, sizeof(buf), NULL, NULL);
            if (n < 0) break;
        }
    }

    close(mgmt_sock);
    mgmt_sock = -1;

    /* Step 3: HCIDEVUP ioctl — now that UNCONFIGURED is cleared this must work.
     * Using the synchronous ioctl path instead of async MGMT SET_POWERED to get
     * a real errno on failure. */
    printf("\nStep 3: HCIDEVUP ioctl for hci%d...\n", (int)hci_index);
    if (try_hcidevup((int)hci_index) != 0) {
        fprintf(stderr, "  HCIDEVUP failed — see errno above\n");
        return 1;
    }

    /* Step 4: Read BD_ADDR to confirm controller is live and responding */
    printf("\nStep 4: Reading BD_ADDR from hci%d...\n", (int)hci_index);
    read_bd_addr_raw((int)hci_index);

    printf("\n=== Done! hci%u is UP. ===\n", hci_index);
    return 0;
}
