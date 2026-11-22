// Opt-in policy for compute-after-compute pipeline barriers (Rekarina roadmap-100fps.md, GPL-3.0).
#pragma once

#include <cctype>
#include <cstdint>
#include <cstring>

namespace mkwvk::dispatch_barrier {

enum class Mode : uint8_t { Full = 0, Game = 1, None = 2 };
enum WorkKind : uint8_t { kWorkNone = 0, kWorkDispatch = 1, kWorkOther = 2 };

inline bool ieq(const char* a, const char* b) {
    if (!a || !b) return false;
    while (*a && *b) {
        if (std::tolower((unsigned char)*a) != std::tolower((unsigned char)*b)) return false;
        ++a, ++b;
    }
    return *a == *b;
}

inline Mode parse_mode(const char* dispatch_barrier_env, const char* no_dispatch_order_env) {
    if (no_dispatch_order_env && *no_dispatch_order_env && std::strcmp(no_dispatch_order_env, "0") != 0)
        return Mode::None;
    if (dispatch_barrier_env && *dispatch_barrier_env) {
        if (ieq(dispatch_barrier_env, "game")) return Mode::Game;
        if (ieq(dispatch_barrier_env, "none") || std::strcmp(dispatch_barrier_env, "0") == 0) return Mode::None;
    }
    return Mode::Full;
}

inline const char* mode_name(Mode mode) {
    switch (mode) {
    case Mode::Game: return "game";
    case Mode::None: return "none";
    default: return "full";
    }
}

/// Whether `dispatch()` needs a full barrier given `work_kind` recorded since the last full barrier:
/// - Full: any prior GPU work (`work_kind != kWorkNone`)
/// - Game: graphics pass or transfer work only (`work_kind == kWorkOther`); compute-to-compute uses explicit game barriers
/// - None: never
inline bool need_dispatch_barrier(Mode mode, uint8_t work_kind) {
    switch (mode) {
    case Mode::Full: return work_kind != kWorkNone;
    case Mode::Game: return work_kind == kWorkOther;
    case Mode::None: return false;
    }
    return true;
}

/// Monotonically upgrades tracked work kind since last barrier (`0 -> 1 -> 2`, never downgrading `2 -> 1`).
inline uint8_t note_work_kind(uint8_t current, uint8_t added) {
    return added > current ? added : current;
}

} // namespace mkwvk::dispatch_barrier
