// Game- and GPU-free regression for direct uniform-buffer snapshot policy and reuse.
//   clang++ -std=c++20 -O2 -Wall -Wextra -Werror gpu/vk/tests/direct_ub_snapshot_test.cpp -o direct_ub_snapshot_test
#include <cstdint>

#include "../direct_ub_snapshot.h"

#define CHECK(condition) do { if (!(condition)) return __LINE__; } while (0)

int main() {
    using mkwvk::direct_ub::Mode;
    using mkwvk::direct_ub::mode;
    using mkwvk::direct_ub::should_snapshot;

    CHECK(mode(nullptr) == Mode::automatic);
    CHECK(mode("0") == Mode::disabled);
    CHECK(mode("1") == Mode::forced);
    CHECK(should_snapshot(Mode::automatic, true));
    CHECK(!should_snapshot(Mode::automatic, false));
    CHECK(!should_snapshot(Mode::disabled, true));
    CHECK(should_snapshot(Mode::forced, false));

    mkwvk::direct_ub::Cache<uintptr_t, 4> cache;
    uintptr_t buffer = 0;
    uint64_t offset = 0;
    CHECK(!cache.find(0x1000, 64, 1, &buffer, &offset));
    cache.reset();
    cache.keep(0x1000, 64, 1, 7, 256);
    CHECK(cache.find(0x1000, 64, 1, &buffer, &offset));
    CHECK(buffer == 7 && offset == 256);
    CHECK(!cache.find(0x1000, 64, 2, &buffer, &offset));
    CHECK(!cache.find(0x1000, 80, 1, &buffer, &offset));
    CHECK(!cache.find(0x2000, 64, 1, &buffer, &offset));

    cache.keep(0x1000, 64, 1, 9, 512);
    CHECK(cache.find(0x1000, 64, 1, &buffer, &offset));
    CHECK(buffer == 9 && offset == 512);
    cache.reset();
    CHECK(!cache.find(0x1000, 64, 1, &buffer, &offset));
    return 0;
}
