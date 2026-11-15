#pragma once

#include <algorithm>
#include <cstdint>
#include <vector>

namespace sparse_guest {

struct Run {
    uint64_t offset = 0, size = 0;
};

inline bool bound(const std::vector<uint64_t>& words, uint64_t block) {
    return block / 64 < words.size() && (words[block / 64] >> (block & 63) & 1);
}

inline void set_bound(std::vector<uint64_t>& words, uint64_t first, uint64_t count) {
    for (uint64_t block = first; block < first + count; block++)
        words[block / 64] |= 1ull << (block & 63);
}

/// Whether [lo, hi) touches a block already bound to the sparse resource. The range may extend past the resource;
/// callers use this when deciding whether freed guest pages are still visible to the GPU.
inline bool overlaps_bound(const std::vector<uint64_t>& words, uint64_t resource_lo, uint64_t block_size,
                           uint64_t lo, uint64_t hi) {
    if (!block_size || hi <= lo || hi <= resource_lo || words.empty()) return false;
    lo = std::max(lo, resource_lo);
    const uint64_t first = (lo - resource_lo) / block_size;
    const uint64_t bytes = hi - resource_lo;
    const uint64_t limit = words.size() > UINT64_MAX / 64 ? UINT64_MAX : words.size() * 64;
    const uint64_t last = std::min<uint64_t>(limit, bytes / block_size + (bytes % block_size != 0));
    for (uint64_t block = first; block < last; block++)
        if (bound(words, block)) return true;
    return false;
}

/// Mark every sparse block touched by [lo, hi). The caller supplies ranges already clamped to the resource.
inline void mark(std::vector<uint8_t>& wanted, uint64_t resource_lo, uint64_t block_size, uint64_t lo, uint64_t hi) {
    if (!block_size || hi <= lo || lo < resource_lo) return;
    const uint64_t first = (lo - resource_lo) / block_size;
    const uint64_t bytes = hi - resource_lo;
    const uint64_t last = std::min<uint64_t>(wanted.size(), bytes / block_size + (bytes % block_size != 0));
    for (uint64_t block = first; block < last; block++) wanted[(size_t)block] = 1;
}

/// Merge consecutive wanted, not-yet-bound blocks into Vulkan sparse binding runs.
inline std::vector<Run> runs(const std::vector<uint8_t>& wanted, const std::vector<uint64_t>& bound_words,
                             uint64_t block_size) {
    std::vector<Run> result;
    for (uint64_t block = 0; block < wanted.size();) {
        while (block < wanted.size() && (!wanted[(size_t)block] || bound(bound_words, block))) block++;
        const uint64_t first = block;
        while (block < wanted.size() && wanted[(size_t)block] && !bound(bound_words, block)) block++;
        if (block > first) result.push_back({first * block_size, (block - first) * block_size});
    }
    return result;
}

}   // namespace sparse_guest
