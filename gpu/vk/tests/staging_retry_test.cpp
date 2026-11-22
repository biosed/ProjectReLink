// Game-, GPU- and SDK-free regression for texture staging arena OOM recovery (staging_retry.h).
//   clang++ -std=c++20 -O2 -Wall -Wextra -Werror gpu/vk/tests/staging_retry_test.cpp -o staging_retry_test
#include <cstdint>
#include <cstdio>

#include "../staging_retry.h"

#define CHECK(cond)                                                                                                    \
    do {                                                                                                               \
        if (!(cond)) {                                                                                                 \
            std::fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #cond);                                               \
            return 1;                                                                                                  \
        }                                                                                                              \
    } while (0)

struct FakeArena {
    uint64_t value = 0;
};

int main() {
    using namespace mkwvk::staging_retry;

    CHECK(exact_arena_size(0) == 4096ull);
    CHECK(exact_arena_size(1) == 4096ull);
    CHECK(exact_arena_size(4096) == 4096ull);
    CHECK(exact_arena_size(4097) == 8192ull);
    CHECK(exact_arena_size(512ull << 10) == (512ull << 10));
    CHECK(exact_arena_size((1ull << 20) - 1) == (1ull << 20));
    CHECK(exact_arena_size(1ull << 20) == (1ull << 20));
    CHECK(exact_arena_size((1ull << 20) + 1) == (2ull << 20));
    CHECK(exact_arena_size((64ull << 20) + 16) == (65ull << 20));

    const FakeArena empty[1]{};
    CHECK(find_oldest_inflight(empty, 0, 10, 5) == SIZE_MAX);

    // Only current recording and completed entries present -> none waiting.
    const FakeArena no_wait[] = {{10}, {5}, {4}, {0}};
    CHECK(find_oldest_inflight(no_wait, 4, 10, 5) == SIZE_MAX);

    // Picks smallest value strictly between completed (5) and excluding rec_value (8 or 12).
    const FakeArena mixed[] = {{10}, {9}, {5}, {7}, {8}};
    CHECK(find_oldest_inflight(mixed, 5, 10, 5) == 3);
    CHECK(find_oldest_inflight(mixed, 5, 7, 5) == 4);

    // Edge where rec_value is lower than in-flight value (out-of-order / wrapped).
    const FakeArena ooo[] = {{6}, {15}, {12}};
    CHECK(find_oldest_inflight(ooo, 3, 6, 10) == 2);
    return 0;
}
