/* test_qrtr.c — minimal AF_QIPCRTR socket test */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <sys/socket.h>
#include <stdint.h>

#ifndef AF_QIPCRTR
#define AF_QIPCRTR 42
#endif

/* Test with the system's proper sockaddr structure (no packed) */
struct sq {
    uint16_t sq_family;
    uint32_t sq_node;
    uint32_t sq_port;
};

int main(void)
{
    printf("sizeof(struct sq) = %zu\n", sizeof(struct sq));
    printf("AF_QIPCRTR = %d\n", (int)AF_QIPCRTR);

    int sock = socket(AF_QIPCRTR, SOCK_DGRAM, 0);
    if (sock < 0) { perror("socket"); return 1; }
    printf("socket() OK fd=%d\n", sock);

    /* Approach 1: our struct */
    {
        struct sq sa;
        memset(&sa, 0, sizeof(sa));
        sa.sq_family = AF_QIPCRTR;
        sa.sq_node = 0;
        sa.sq_port = 0;
        printf("bind len=%zu family=0x%04x node=%u port=%u\n",
               sizeof(sa), sa.sq_family, sa.sq_node, sa.sq_port);
        int r = bind(sock, (struct sockaddr*)&sa, sizeof(sa));
        if (r < 0)
            printf("bind errno=%d (%s)\n", errno, strerror(errno));
        else
            printf("bind OK!\n");
    }

    /* Approach 2: use a 16-byte struct (adding extra pad after family) */
    close(sock);
    sock = socket(AF_QIPCRTR, SOCK_DGRAM, 0);
    {
        char buf[16] = {0};
        /* family at [0..1], pad at [2..3], node at [4..7], port at [8..11] */
        buf[0] = (char)(AF_QIPCRTR & 0xFF);
        buf[1] = (char)(AF_QIPCRTR >> 8);
        /* node=0, port=0 already zeroed */
        printf("bind2 len=12 family=0x%02x%02x\n", (unsigned char)buf[1], (unsigned char)buf[0]);
        int r2 = bind(sock, (struct sockaddr*)buf, 12);
        if (r2 < 0)
            printf("bind2 errno=%d (%s)\n", errno, strerror(errno));
        else
            printf("bind2 OK!\n");
    }

    /* Approach 3: use 10-byte (packed size) */
    close(sock);
    sock = socket(AF_QIPCRTR, SOCK_DGRAM, 0);
    {
        char buf[10] = {0};
        buf[0] = (char)(AF_QIPCRTR & 0xFF);
        buf[1] = (char)(AF_QIPCRTR >> 8);
        /* node at [2..5], port at [6..9] */
        printf("bind3 len=10 (packed layout)\n");
        int r3 = bind(sock, (struct sockaddr*)buf, 10);
        if (r3 < 0)
            printf("bind3 errno=%d (%s)\n", errno, strerror(errno));
        else
            printf("bind3 OK!\n");
    }

    close(sock);
    return 0;
}
