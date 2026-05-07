/*
 * qrfs.c — Qualcomm Remote File System Access (RFSA) server
 *
 * Registers as QMI service 0x28 on AF_QIPCRTR and serves firmware file
 * read requests from the modem's wlan_pd.  The modem calls this to load
 * wlanmdsp.mbn (WCN3990 Q6 firmware) via its internal PIL before starting
 * the WLFW QMI stack that ath10k_snoc waits for.
 *
 * Protocol: QMI over AF_QIPCRTR (no QMUX framing)
 *   QMI header (7 bytes): flags(1) txn_id(2LE) msg_id(2LE) msg_len(2LE)
 *   TLVs follow: type(1) length(2LE) value(N)
 *
 * RFSA message IDs:
 *   0x0020  FILE_STAT
 *   0x0021  FILE_OPEN
 *   0x0024  FILE_CLOSE
 *   0x0027  FILE_READ
 *
 * Build (cross): aarch64-linux-gnu-gcc -O2 -static -o qrfs qrfs.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <stdint.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <time.h>

/* AF_QIPCRTR is 42 on all Linux architectures */
#ifndef AF_QIPCRTR
#define AF_QIPCRTR 42
#endif

#define QRTR_PORT_CTRL   0xFFFFFFFEu
#define QRTR_NODE_BCAST  0xFFFFFFFFu
#define QRTR_TYPE_NEW_SERVER 4u

/* Must match kernel's uapi/linux/qrtr.h — NOT packed.
 * Natural alignment: sq_family(2) + pad(2) + sq_node(4) + sq_port(4) = 12 bytes.
 * The kernel's qrtr_bind() checks len >= sizeof(*addr) = 12; packed would give 10 → EINVAL. */
struct sockaddr_qrtr {
    uint16_t sq_family;
    /* 2 bytes implicit padding (uint32_t alignment) */
    uint32_t sq_node;
    uint32_t sq_port;
};

struct qrtr_ctrl_pkt {
    uint32_t cmd;
    uint32_t service;
    uint32_t instance;
    uint32_t node;
    uint32_t port;
} __attribute__((packed));

/* ── QMI ── */
#define QMI_REQUEST   0x00
#define QMI_RESPONSE  0x02

struct qmi_hdr {
    uint8_t  flags;
    uint16_t txn_id;
    uint16_t msg_id;
    uint16_t msg_len;
} __attribute__((packed));

#define RFSA_SVC_ID   0x28u
#define RFSA_INSTANCE 0x0001u   /* instance=1 (version=0, id=1 convention) */

/* RFSA message IDs */
#define RFSA_FILE_STAT  0x0020u
#define RFSA_FILE_OPEN  0x0021u
#define RFSA_FILE_CLOSE 0x0024u
#define RFSA_FILE_READ  0x0027u

/* QMI result TLV (type 0x02) */
#define QMI_TLV_RESULT  0x02

/* QMI result codes */
#define QMI_RESULT_SUCCESS 0x0000u
#define QMI_RESULT_FAILURE 0x0001u
#define QMI_ERR_NONE       0x0000u
#define QMI_ERR_INTERNAL   0x0003u
#define QMI_ERR_NO_EFFECT  0x0036u

/* Firmware search paths (tried in order, basename stripped then joined) */
static const char *fw_bases[] = {
    "/lib/firmware/qcom/sm8150",
    "/lib/firmware/qcom",
    "/lib/firmware",
    "/data/vendor/firmware",
    NULL
};

/* Open file handle table */
#define MAX_FD 32
static int fd_table[MAX_FD];

static void hexdump(const char *tag, const uint8_t *buf, int len)
{
    fprintf(stderr, "[qrfs] %s (%d bytes):", tag, len);
    for (int i = 0; i < len && i < 64; i++)
        fprintf(stderr, " %02x", buf[i]);
    if (len > 64) fprintf(stderr, " ...");
    fprintf(stderr, "\n");
}

/* Find a free handle slot; returns -1 if full */
static int alloc_handle(int fd)
{
    for (int i = 1; i < MAX_FD; i++) {
        if (fd_table[i] < 0) {
            fd_table[i] = fd;
            return i;
        }
    }
    return -1;
}

static void free_handle(int h)
{
    if (h > 0 && h < MAX_FD && fd_table[h] >= 0) {
        close(fd_table[h]);
        fd_table[h] = -1;
    }
}

/* Search for a firmware file across multiple base dirs.
 * `reqpath` may be absolute (e.g. /lib/firmware/wlanmdsp.mbn) or relative.
 * Returns fd on success, -1 on failure. */
static int open_fw(const char *reqpath)
{
    char buf[512];
    int fd;

    /* Try as-is first */
    fd = open(reqpath, O_RDONLY);
    if (fd >= 0) {
        fprintf(stderr, "[qrfs] opened '%s' directly\n", reqpath);
        return fd;
    }

    /* Extract basename */
    const char *base = strrchr(reqpath, '/');
    base = base ? base + 1 : reqpath;

    for (int i = 0; fw_bases[i]; i++) {
        snprintf(buf, sizeof(buf), "%s/%s", fw_bases[i], base);
        fd = open(buf, O_RDONLY);
        if (fd >= 0) {
            fprintf(stderr, "[qrfs] opened '%s' as '%s'\n", reqpath, buf);
            return fd;
        }
    }

    fprintf(stderr, "[qrfs] file not found: '%s' (basename='%s')\n", reqpath, base);
    return -1;
}

/* Build a simple QMI response in `out`, return total length.
 * result_code: 0=success, 1=failure; qmi_err: see QMI_ERR_* */
static int build_qmi_resp(uint8_t *out, size_t outsz,
                           uint8_t flags_orig, uint16_t txn_id,
                           uint16_t msg_id,
                           uint16_t result_code, uint16_t qmi_err,
                           const uint8_t *extra_tlvs, uint16_t extra_len)
{
    uint16_t payload_len = 3 + 4 + extra_len; /* result TLV: hdr(3) + val(4) + extras */
    if (7 + payload_len > (int)outsz) return -1;

    struct qmi_hdr *hdr = (struct qmi_hdr *)out;
    hdr->flags   = QMI_RESPONSE;
    hdr->txn_id  = txn_id;
    hdr->msg_id  = msg_id;
    hdr->msg_len = payload_len;

    uint8_t *p = out + 7;
    /* TLV 0x02: result(2) + error(2) */
    *p++ = QMI_TLV_RESULT;
    *p++ = 4; *p++ = 0;  /* length = 4 LE */
    *p++ = result_code & 0xFF; *p++ = result_code >> 8;
    *p++ = qmi_err & 0xFF;     *p++ = qmi_err >> 8;

    if (extra_tlvs && extra_len)
        memcpy(p, extra_tlvs, extra_len);

    return 7 + payload_len;
}

/* Parse TLV from buf+offset, return new offset or -1 */
static int tlv_next(const uint8_t *buf, int buflen, int off,
                    uint8_t *type, uint16_t *len, const uint8_t **val)
{
    if (off + 3 > buflen) return -1;
    *type = buf[off];
    *len  = buf[off+1] | ((uint16_t)buf[off+2] << 8);
    *val  = buf + off + 3;
    if (off + 3 + *len > buflen) return -1;
    return off + 3 + *len;
}

/* ── Handler: FILE_STAT (0x0020) ── */
static int handle_stat(int sock, const struct sockaddr_qrtr *from,
                        const struct qmi_hdr *hdr,
                        const uint8_t *tlvs, int tlvlen)
{
    char filename[256] = {0};
    uint8_t type; uint16_t vlen; const uint8_t *val;
    int off = 0;

    while ((off = tlv_next(tlvs, tlvlen, off, &type, &vlen, &val)) >= 0) {
        if (type == 0x01 && vlen >= 2) {
            /* string TLV: 2-byte length prefix + chars */
            uint16_t slen = val[0] | ((uint16_t)val[1] << 8);
            if (slen > sizeof(filename)-1) slen = sizeof(filename)-1;
            memcpy(filename, val+2, slen);
            filename[slen] = 0;
        } else if (type == 0x02 && vlen < sizeof(filename)) {
            /* alternate: raw string (null-terminated or length-prefixed) */
            if (vlen >= 2) {
                uint16_t slen2 = val[0] | ((uint16_t)val[1] << 8);
                if (slen2 < sizeof(filename) && slen2 + 2 <= vlen) {
                    memcpy(filename, val+2, slen2);
                    filename[slen2] = 0;
                }
            }
        }
    }

    fprintf(stderr, "[qrfs] STAT '%s'\n", filename);

    struct stat st;
    int fd = open_fw(filename);
    uint8_t resp[64]; uint8_t extras[16]; int elen = 0;

    if (fd >= 0) {
        fstat(fd, &st);
        close(fd);
        /* TLV 0x10: file size (uint64_t) */
        uint64_t fsz = st.st_size;
        extras[elen++] = 0x10;
        extras[elen++] = 8; extras[elen++] = 0;
        memcpy(extras + elen, &fsz, 8); elen += 8;
        int n = build_qmi_resp(resp, sizeof(resp), hdr->flags, hdr->txn_id,
                               hdr->msg_id, QMI_RESULT_SUCCESS, QMI_ERR_NONE,
                               extras, elen);
        sendto(sock, resp, n, 0, (struct sockaddr*)from, sizeof(*from));
    } else {
        int n = build_qmi_resp(resp, sizeof(resp), hdr->flags, hdr->txn_id,
                               hdr->msg_id, QMI_RESULT_FAILURE, QMI_ERR_INTERNAL,
                               NULL, 0);
        sendto(sock, resp, n, 0, (struct sockaddr*)from, sizeof(*from));
    }
    return 0;
}

/* ── Handler: FILE_OPEN (0x0021) ── */
static int handle_open(int sock, const struct sockaddr_qrtr *from,
                        const struct qmi_hdr *hdr,
                        const uint8_t *tlvs, int tlvlen)
{
    char filename[256] = {0};
    uint32_t flags = 0;
    uint8_t type; uint16_t vlen; const uint8_t *val;
    int off = 0;

    while ((off = tlv_next(tlvs, tlvlen, off, &type, &vlen, &val)) >= 0) {
        if (type == 0x01 && vlen == 4)
            memcpy(&flags, val, 4);
        else if (type == 0x02 && vlen >= 2) {
            /* string: 2-byte length + chars */
            uint16_t slen = val[0] | ((uint16_t)val[1] << 8);
            if (slen > sizeof(filename)-1) slen = sizeof(filename)-1;
            memcpy(filename, val+2, slen);
            filename[slen] = 0;
        }
        /* Some firmware versions put filename in TLV 0x01 and flags in 0x02 */
    }

    /* If filename is still empty, try alternate: TLV 0x01 as filename string */
    if (!filename[0]) {
        off = 0;
        while ((off = tlv_next(tlvs, tlvlen, off, &type, &vlen, &val)) >= 0) {
            if (type == 0x01 && vlen >= 2) {
                uint16_t slen = val[0] | ((uint16_t)val[1] << 8);
                if (slen > sizeof(filename)-1) slen = sizeof(filename)-1;
                memcpy(filename, val+2, slen);
                filename[slen] = 0;
                break;
            }
        }
    }

    fprintf(stderr, "[qrfs] OPEN '%s' flags=0x%x\n", filename, flags);

    int fd = open_fw(filename);
    uint8_t resp[64]; uint8_t extras[16]; int elen = 0;

    if (fd >= 0) {
        int h = alloc_handle(fd);
        if (h < 0) { close(fd); goto fail; }
        /* TLV 0x10: handle (uint32_t) */
        uint32_t handle = (uint32_t)h;
        extras[elen++] = 0x10;
        extras[elen++] = 4; extras[elen++] = 0;
        memcpy(extras + elen, &handle, 4); elen += 4;
        int n = build_qmi_resp(resp, sizeof(resp), hdr->flags, hdr->txn_id,
                               hdr->msg_id, QMI_RESULT_SUCCESS, QMI_ERR_NONE,
                               extras, elen);
        sendto(sock, resp, n, 0, (struct sockaddr*)from, sizeof(*from));
        return 0;
    }

fail:;
    int n = build_qmi_resp(resp, sizeof(resp), hdr->flags, hdr->txn_id,
                           hdr->msg_id, QMI_RESULT_FAILURE, QMI_ERR_INTERNAL,
                           NULL, 0);
    sendto(sock, resp, n, 0, (struct sockaddr*)from, sizeof(*from));
    return 0;
}

/* ── Handler: FILE_CLOSE (0x0024) ── */
static int handle_close(int sock, const struct sockaddr_qrtr *from,
                         const struct qmi_hdr *hdr,
                         const uint8_t *tlvs, int tlvlen)
{
    uint32_t handle = 0;
    uint8_t type; uint16_t vlen; const uint8_t *val;
    int off = 0;

    while ((off = tlv_next(tlvs, tlvlen, off, &type, &vlen, &val)) >= 0) {
        if (type == 0x01 && vlen == 4)
            memcpy(&handle, val, 4);
    }

    fprintf(stderr, "[qrfs] CLOSE handle=%u\n", handle);
    free_handle((int)handle);

    uint8_t resp[32];
    int n = build_qmi_resp(resp, sizeof(resp), hdr->flags, hdr->txn_id,
                           hdr->msg_id, QMI_RESULT_SUCCESS, QMI_ERR_NONE,
                           NULL, 0);
    sendto(sock, resp, n, 0, (struct sockaddr*)from, sizeof(*from));
    return 0;
}

/* ── Handler: FILE_READ (0x0027) ── */
static int handle_read(int sock, const struct sockaddr_qrtr *from,
                        const struct qmi_hdr *hdr,
                        const uint8_t *tlvs, int tlvlen)
{
    uint32_t handle = 0, num_bytes = 0;
    uint64_t offset = 0;
    uint8_t type; uint16_t vlen; const uint8_t *val;
    int off = 0;

    while ((off = tlv_next(tlvs, tlvlen, off, &type, &vlen, &val)) >= 0) {
        if (type == 0x01 && vlen == 4)  memcpy(&handle, val, 4);
        if (type == 0x02 && vlen == 4)  memcpy((uint8_t*)&offset, val, 4);
        if (type == 0x02 && vlen == 8)  memcpy(&offset, val, 8);
        if (type == 0x03 && vlen == 4)  memcpy(&num_bytes, val, 4);
    }

    fprintf(stderr, "[qrfs] READ handle=%u offset=%llu bytes=%u\n",
            handle, (unsigned long long)offset, num_bytes);

    if (handle == 0 || handle >= MAX_FD || fd_table[handle] < 0) {
        uint8_t resp[32];
        int n = build_qmi_resp(resp, sizeof(resp), hdr->flags, hdr->txn_id,
                               hdr->msg_id, QMI_RESULT_FAILURE, QMI_ERR_INTERNAL,
                               NULL, 0);
        sendto(sock, resp, n, 0, (struct sockaddr*)from, sizeof(*from));
        return 0;
    }

    if (num_bytes > 4096) num_bytes = 4096;

    uint8_t *databuf = malloc(num_bytes);
    if (!databuf) { num_bytes = 0; }

    ssize_t nread = 0;
    if (databuf) {
        nread = pread(fd_table[handle], databuf, num_bytes, (off_t)offset);
        if (nread < 0) nread = 0;
    }

    /* Build response with data TLV */
    /* TLV 0x10: read_result (optional bool?) - skip, some impls don't have it */
    /* TLV 0x11: data (2-byte length + bytes) */
    size_t extra_len = 3 + 2 + nread;  /* TLV hdr + QMI string length + data */
    uint8_t *resp = malloc(7 + 7 + extra_len + 16);
    if (!resp) {
        free(databuf);
        return -1;
    }

    /* Build result TLV first (via helper), then append data TLV */
    uint8_t *ep = resp + 7 + 7; /* skip QMI header (7) + result TLV (7) */
    /* TLV 0x11: data */
    ep[0] = 0x11;
    uint16_t dlen = 2 + (uint16_t)nread;  /* 2-byte string length prefix + data */
    memcpy(ep+1, &dlen, 2);
    ep[3] = (uint8_t)(nread & 0xFF);
    ep[4] = (uint8_t)(nread >> 8);
    if (nread && databuf) memcpy(ep+5, databuf, nread);

    uint16_t extra_total = 3 + dlen;

    /* Now build the full response */
    struct qmi_hdr *rhdr = (struct qmi_hdr *)resp;
    rhdr->flags   = QMI_RESPONSE;
    rhdr->txn_id  = hdr->txn_id;
    rhdr->msg_id  = hdr->msg_id;
    /* payload = result TLV (7 bytes) + data TLV (3 + dlen bytes) */
    rhdr->msg_len = 7 + extra_total;

    /* result TLV */
    uint8_t *rp = resp + 7;
    *rp++ = QMI_TLV_RESULT;
    *rp++ = 4; *rp++ = 0;
    *rp++ = QMI_RESULT_SUCCESS & 0xFF; *rp++ = QMI_RESULT_SUCCESS >> 8;
    *rp++ = QMI_ERR_NONE & 0xFF;       *rp++ = QMI_ERR_NONE >> 8;

    /* data TLV already written at ep */
    int total = 7 + 7 + extra_total;
    sendto(sock, resp, total, 0, (struct sockaddr*)from, sizeof(*from));
    free(resp);
    free(databuf);
    return 0;
}

/* Register this process as RFSA service 0x28 on QRTR */
static int qrtr_register_service(int sock, uint32_t node, uint32_t port,
                                  uint32_t svc, uint32_t instance)
{
    struct sockaddr_qrtr ctrl = {
        .sq_family = AF_QIPCRTR,
        .sq_node   = node,
        .sq_port   = QRTR_PORT_CTRL,
    };
    struct qrtr_ctrl_pkt pkt = {
        .cmd      = QRTR_TYPE_NEW_SERVER,
        .service  = svc,
        .instance = instance,
        .node     = node,
        .port     = port,
    };
    int r = sendto(sock, &pkt, sizeof(pkt), 0,
                   (struct sockaddr*)&ctrl, sizeof(ctrl));
    if (r < 0)
        perror("[qrfs] sendto ctrl");
    return r;
}

int main(void)
{
    int i;
    for (i = 0; i < MAX_FD; i++) fd_table[i] = -1;

    int sock = socket(AF_QIPCRTR, SOCK_DGRAM, 0);
    if (sock < 0) { perror("socket"); return 1; }

    /* Autobind via sendto: sending any packet triggers qrtr_autobind() in the kernel,
     * assigning us a valid ephemeral port.  getsockname() alone (without a prior
     * send/connect) returns port=0 on sm8150-mainline, which is the control port
     * and causes the nameserver to ignore our service registration. */
    struct sockaddr_qrtr ns_addr = {AF_QIPCRTR, 1, QRTR_PORT_CTRL};
    /* Send a minimal (1-byte) packet to the nameserver to force autobind.
     * The nameserver will discard the invalid packet but our port gets assigned. */
    {
        uint8_t dummy = 0;
        sendto(sock, &dummy, 1, 0, (struct sockaddr*)&ns_addr, sizeof(ns_addr));
    }
    struct sockaddr_qrtr sa;
    memset(&sa, 0, sizeof(sa));
    socklen_t salen = sizeof(sa);
    if (getsockname(sock, (struct sockaddr*)&sa, &salen) < 0) {
        perror("getsockname"); return 1;
    }
    fprintf(stderr, "[qrfs] auto-bound to node=%u port=%u\n", sa.sq_node, sa.sq_port);
    if (sa.sq_port == 0) {
        fprintf(stderr, "[qrfs] ERROR: autobind returned port=0, service registration will fail\n");
        return 1;
    }

    /* Register as RFSA service */
    qrtr_register_service(sock, sa.sq_node, sa.sq_port, RFSA_SVC_ID, RFSA_INSTANCE);
    /* Also register with instance 0 in case modem expects that */
    qrtr_register_service(sock, sa.sq_node, sa.sq_port, RFSA_SVC_ID, 0);
    fprintf(stderr, "[qrfs] registered as service 0x%02x instance %u and 0\n",
            RFSA_SVC_ID, RFSA_INSTANCE);

    uint8_t buf[8192];
    for (;;) {
        struct sockaddr_qrtr from;
        socklen_t fromlen = sizeof(from);
        ssize_t n = recvfrom(sock, buf, sizeof(buf), 0,
                             (struct sockaddr*)&from, &fromlen);
        if (n < 0) { perror("recvfrom"); continue; }

        hexdump("rx", buf, (int)n);

        if (n < 7) {
            fprintf(stderr, "[qrfs] too short (%zd bytes), skipping\n", n);
            continue;
        }

        struct qmi_hdr *hdr = (struct qmi_hdr *)buf;
        uint16_t msg_id  = hdr->msg_id;
        uint16_t msg_len = hdr->msg_len;

        fprintf(stderr, "[qrfs] from=%u:%u flags=0x%02x txn=%u msg_id=0x%04x len=%u\n",
                from.sq_node, from.sq_port, hdr->flags,
                hdr->txn_id, msg_id, msg_len);

        if (hdr->flags != QMI_REQUEST) {
            fprintf(stderr, "[qrfs] not a request (flags=0x%02x), ignoring\n", hdr->flags);
            continue;
        }

        const uint8_t *tlvs = buf + 7;
        int tlvlen = (int)n - 7;
        if (tlvlen < 0) tlvlen = 0;

        switch (msg_id) {
        case RFSA_FILE_STAT:  handle_stat (sock, &from, hdr, tlvs, tlvlen); break;
        case RFSA_FILE_OPEN:  handle_open (sock, &from, hdr, tlvs, tlvlen); break;
        case RFSA_FILE_CLOSE: handle_close(sock, &from, hdr, tlvs, tlvlen); break;
        case RFSA_FILE_READ:  handle_read (sock, &from, hdr, tlvs, tlvlen); break;
        default:
            fprintf(stderr, "[qrfs] unknown msg_id=0x%04x\n", msg_id);
            /* Send generic failure */
            {
                uint8_t resp[32];
                int rn = build_qmi_resp(resp, sizeof(resp), hdr->flags,
                                        hdr->txn_id, msg_id,
                                        QMI_RESULT_FAILURE, QMI_ERR_INTERNAL,
                                        NULL, 0);
                sendto(sock, resp, rn, 0, (struct sockaddr*)&from, sizeof(from));
            }
            break;
        }
    }

    return 0;
}
