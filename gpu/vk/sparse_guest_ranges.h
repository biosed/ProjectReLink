#pragma once

#include <algorithm>
#include <cstdint>
#include <utility>
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

inline void clear_bound(std::vector<uint64_t>& words, uint64_t first, uint64_t count) {
    for (uint64_t block = first; block < first + count; block++)
        if (block / 64 < words.size()) words[block / 64] &= ~(1ull << (block & 63));
}

/// Whether any byte backed by these runs touches [lo, hi). `resource_lo` is the guest address represented by offset 0.
inline bool touches(const std::vector<Run>& runs, uint64_t resource_lo, uint64_t lo, uint64_t hi) {
    if (hi <= lo) return false;
    for (const Run& r : runs) {
        if (r.offset > UINT64_MAX - resource_lo) return true;
        const uint64_t a = resource_lo + r.offset;
        const uint64_t b = r.size > UINT64_MAX - a ? UINT64_MAX : a + r.size;
        if (a < hi && b > lo) return true;
    }
    return false;
}

/// Whether every byte backed by these runs is outside the sorted live ranges. A sparse allocation may pack several
/// disjoint runs into one VkDeviceMemory, so it can be freed only when none of them is live.
template <class Ranges>
inline bool all_outside(const std::vector<Run>& runs, uint64_t resource_lo, const Ranges& live) {
    for (const Run& r : runs) {
        if (r.offset > UINT64_MAX - resource_lo) return false;
        const uint64_t a = resource_lo + r.offset;
        const uint64_t b = r.size > UINT64_MAX - a ? UINT64_MAX : a + r.size;
        for (const auto& span : live) {
            if (span.lo >= b) break;
            if (span.lo < b && span.hi > a) return false;
        }
    }
    return true;
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

/// Split aligned runs into the packed allocations accepted by UDMABUF_CREATE_LIST.  Both the packed byte total and
/// extent count are per ioctl; a single contiguous run may therefore become several allocations.  An empty result for
/// non-empty input means the limits or the input alignment are invalid.
inline std::vector<std::vector<Run>> batches(const std::vector<Run>& input, uint64_t max_bytes,
                                             uint64_t max_runs, uint64_t alignment) {
    std::vector<std::vector<Run>> result;
    if (input.empty()) return result;
    if (!max_bytes || !max_runs || !alignment) return result;
    const uint64_t byte_limit = max_bytes / alignment * alignment;
    if (!byte_limit) return result;
    std::vector<Run> batch;
    uint64_t bytes = 0;
    const auto finish = [&] {
        if (!batch.empty()) result.push_back(std::move(batch));
        batch.clear();
        bytes = 0;
    };
    for (const Run& r : input) {
        if (!r.size || r.offset % alignment || r.size % alignment || r.size > UINT64_MAX - r.offset) {
            result.clear();
            return result;
        }
        uint64_t offset = r.offset, left = r.size;
        while (left) {
            if (bytes == byte_limit || batch.size() >= max_runs) finish();
            const uint64_t take = std::min(left, byte_limit - bytes);
            if (!take || take % alignment) {
                result.clear();
                return result;
            }
            batch.push_back({offset, take});
            bytes += take;
            offset += take;
            left -= take;
        }
    }
    finish();
    return result;
}

}   // namespace sparse_guest
