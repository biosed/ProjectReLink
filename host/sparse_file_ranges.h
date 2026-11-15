#pragma once

#if defined(__linux__)
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

// Zero only allocated extents of [lo, hi) in a sparse file's shared mapping. Holes already read as zero; writing
// across them would instantiate pages just as a guest region is being freed. Reopening through proc gives this scan
// an independent file offset, unlike dup(), whose offset is shared with concurrent SEEK_DATA users.
static inline int hos_sparse_file_zero_data(int fd, void *mapping, uint64_t lo, uint64_t hi) {
    if (fd < 0 || !mapping || hi < lo || hi > (uint64_t)INT64_MAX) return -1;
    if (hi == lo) return 0;
    char path[64];
    const int path_n = snprintf(path, sizeof path, "/proc/self/fd/%d", fd);
    if (path_n <= 0 || (size_t)path_n >= sizeof path) return -1;
    const int scan = open(path, O_RDONLY | O_CLOEXEC);
    if (scan < 0) return -1;
    uint64_t at = lo;
    while (at < hi) {
        const off_t data = lseek(scan, (off_t)at, SEEK_DATA);
        if (data < 0) {
            if (errno == ENXIO) break;
            close(scan);
            return -1;
        }
        if ((uint64_t)data >= hi) break;
        const off_t hole = lseek(scan, data, SEEK_HOLE);
        if (hole <= data) {
            close(scan);
            return -1;
        }
        const uint64_t end = (uint64_t)hole < hi ? (uint64_t)hole : hi;
        memset((uint8_t *)mapping + (uint64_t)data, 0, (size_t)(end - (uint64_t)data));
        at = end;
    }
    close(scan);
    return 0;
}
#endif
