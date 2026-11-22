// Game-, GPU- and SDK-free regression for opt-in compute dispatch barrier relaxation.
//   clang++ -std=c++20 -O2 -Wall -Wextra -Werror gpu/vk/tests/dispatch_barrier_test.cpp -o dispatch_barrier_test
#include <cstdint>
#include <cstdio>

#include "../dispatch_barrier.h"

#define CHECK(cond)                                                                                                    \
    do {                                                                                                               \
        if (!(cond)) {                                                                                                 \
            std::fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #cond);                                               \
            return 1;                                                                                                  \
        }                                                                                                              \
    } while (0)

int main() {
    using namespace mkwvk::dispatch_barrier;

    // Default preserves full dispatch ordering whenever any work preceded it.
    CHECK(parse_mode(nullptr, nullptr) == Mode::Full);
    CHECK(parse_mode("", "") == Mode::Full);
    CHECK(parse_mode("full", "0") == Mode::Full);
    CHECK(parse_mode("game", nullptr) == Mode::Game);
    CHECK(parse_mode("Game", "0") == Mode::Game);
    CHECK(parse_mode("none", nullptr) == Mode::None);
    CHECK(parse_mode("0", nullptr) == Mode::None);
    // Legacy RX_VK_NO_DISPATCH_ORDER wins when enabled.
    CHECK(parse_mode("game", "1") == Mode::None);
    CHECK(parse_mode("full", "1") == Mode::None);

    CHECK(!need_dispatch_barrier(Mode::Full, kWorkNone));
    CHECK(need_dispatch_barrier(Mode::Full, kWorkDispatch));
    CHECK(need_dispatch_barrier(Mode::Full, kWorkOther));

    // Game mode relaxes back-to-back dispatches, but keeps barriers after graphics/transfer.
    CHECK(!need_dispatch_barrier(Mode::Game, kWorkNone));
    CHECK(!need_dispatch_barrier(Mode::Game, kWorkDispatch));
    CHECK(need_dispatch_barrier(Mode::Game, kWorkOther));

    CHECK(!need_dispatch_barrier(Mode::None, kWorkNone));
    CHECK(!need_dispatch_barrier(Mode::None, kWorkDispatch));
    CHECK(!need_dispatch_barrier(Mode::None, kWorkOther));

    // Monotonic work-kind progression between full barriers.
    CHECK(note_work_kind(kWorkNone, kWorkDispatch) == kWorkDispatch);
    CHECK(note_work_kind(kWorkNone, kWorkOther) == kWorkOther);
    CHECK(note_work_kind(kWorkDispatch, kWorkOther) == kWorkOther);
    CHECK(note_work_kind(kWorkOther, kWorkDispatch) == kWorkOther);
    return 0;
}
