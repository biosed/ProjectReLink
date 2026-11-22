// Recovery helpers when allocating a new texture staging arena hits memory/commit pressure.
// Adapted from Rekarina v1.2.10 (staging_retry, GPL-3.0).
#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>

namespace mkwvk::staging_retry {

/// Returns an allocation size tightly fitted to `need` when a full 64 MiB kArena block is refused:
/// 1 MiB-aligned for >= 1 MiB requests, 4 KiB-aligned below 1 MiB (minimum 4 KiB).
inline uint64_t exact_arena_size(uint64_t need) {
    if (need >= (1ull << 20)) return (need + 0xFFFFFull) & ~0xFFFFFull;
    const uint64_t rounded = (need + 0xFFFull) & ~0xFFFull;
    return std::max<uint64_t>(4096ull, rounded);
}

/// Returns the index of the oldest still-in-flight arena (`value != rec_value && value > completed`),
/// or SIZE_MAX if none of the arenas are waiting on an older submission.
template <typename ArenaLike>
inline size_t find_oldest_inflight(const ArenaLike* arenas, size_t count, uint64_t rec_value, uint64_t completed) {
    size_t best = SIZE_MAX;
    uint64_t best_value = UINT64_MAX;
    for (size_t i = 0; i < count; i++) {
        const uint64_t v = arenas[i].value;
        if (v != rec_value && v > completed && v < best_value) {
            best_value = v;
            best = i;
        }
    }
    return best;
}

} // namespace mkwvk::staging_retry
