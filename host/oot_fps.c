/* OoT v1.1.1 high-FPS logic & timing fixes (ported from Rekarina v1.2.10, GPL-3.0).

   Covers the 6 host-assisted fixes not already in upstream v0.7.9.4
   (oot_ripples.py / oot_step_cuts.py handle ripple, pickup, solver, daytime,
   webstep): looppose (45-58 & >60 FPS), clothtime, horsejump, floorcarry,
   inputstep, and turnrate.

   All helpers receive and return values by argument/return rather than taking Ctx *,
   keeping A64_LOCAL_REGS and A64_LOCAL_VREGS completely sound without register spills.
   Every guest address read is bounds-checked via guest_ok() before calling GP(). */

#ifndef OOT_FPS_UNIT_TEST
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include "hos.h"
#include <windows.h>
#endif

#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#ifdef OOT_FPS_UNIT_TEST
#include <pthread.h>
typedef pthread_mutex_t SRWLOCK;
#define SRWLOCK_INIT PTHREAD_MUTEX_INITIALIZER
#define AcquireSRWLockExclusive(l) pthread_mutex_lock(l)
#define ReleaseSRWLockExclusive(l) pthread_mutex_unlock(l)
#endif

extern volatile int hos_step_fps;

#define OOT_MAIN_BASE 0x80020000ULL
#define OOT_VFR_SLOT  (OOT_MAIN_BASE + 0x4c7e890ULL)

static int env_flag_enabled(volatile int *cache, const char *name) {
    int v = __atomic_load_n(cache, __ATOMIC_RELAXED);
    if (v < 0) {
        const char *e = getenv(name);
        v = (e && e[0] == '0' && e[1] == '\0') ? 0 : 1;
        __atomic_store_n(cache, v, __ATOMIC_RELAXED);
    }
    return v;
}

static volatile int g_master_on = -1;
static volatile int g_looppose_on = -1;
static volatile int g_clothtime_on = -1;
static volatile int g_horsejump_on = -1;
static volatile int g_floorcarry_on = -1;
static volatile int g_inputstep_on = -1;
static volatile int g_turnrate_on = -1;

static int oot_fix_on(volatile int *per_fix, const char *name) {
    return env_flag_enabled(&g_master_on, "HOS_OOT_FIXES") && env_flag_enabled(per_fix, name);
}

static int guest_ok(uint64_t a, uint64_t n) {
    if (a < 0x10000ULL || n == 0 || a > HOS_GUEST_SPACE - n) return 0;
    const uint64_t end = a + n;
    if (a >= hos_image_base && end <= hos_image_end) return 1;
    if (a >= HOS_HEAP_BASE && end <= HOS_HEAP_BASE + hos_heap_size) return 1;
    return hos_mem_region(a, n) != 0;
}

static int g_read32(uint64_t a, uint32_t *out) {
    if (!guest_ok(a, 4)) return 0;
    memcpy(out, GP(a), 4);
    return 1;
}

static int g_read64(uint64_t a, uint64_t *out) {
    if (!guest_ok(a, 8)) return 0;
    memcpy(out, GP(a), 8);
    return 1;
}

static int g_readf(uint64_t a, float *out) {
    uint32_t bits = 0;
    if (!g_read32(a, &bits)) return 0;
    memcpy(out, &bits, 4);
    return 1;
}

static float frame_step(void) {
    uint64_t manager = 0, time_obj = 0;
    float step = NAN;
    if (!g_read64(OOT_VFR_SLOT, &manager) || !manager) return NAN;
    if (!g_read64(manager, &time_obj) || !time_obj) return NAN;
    if (!g_readf(time_obj + 0x10ULL, &step)) return NAN;
    return step;
}

static int short_frame(float step) { return step > 0.0f && step < 1.0f; }

static void first_run(volatile int *seen, const char *what) {
    if (!__atomic_exchange_n(seen, 1, __ATOMIC_RELAXED)) hos_log("oot fps: %s", what);
}

static int log_due_20s(uint64_t *next_ns) {
    const int64_t now_s = hos_now_ns();
    if (now_s <= 0) return 0;
    const uint64_t now = (uint64_t)now_s;
    uint64_t due = __atomic_load_n(next_ns, __ATOMIC_RELAXED);
    if (due == 0) {
        uint64_t expected = 0;
        __atomic_compare_exchange_n(next_ns, &expected, now + 20000000000ULL, 0, __ATOMIC_RELAXED, __ATOMIC_RELAXED);
        return 0;
    }
    if (now < due) return 0;
    return __atomic_compare_exchange_n(next_ns, &due, now + 20000000000ULL, 0, __ATOMIC_RELAXED, __ATOMIC_RELAXED);
}

/* ---- 1-frame loop animation pose stabilization (<= 1 frame loops at non-integer step) ---- */

#define LOOP_SLOTS 4096
#define LOOP_PROBE 32
static struct {
    uint64_t at;
    float part;
} loop_carry[LOOP_SLOTS];
static SRWLOCK loop_lock = SRWLOCK_INIT;
static struct {
    volatile int seen[2];
    uint64_t next_ns;
    long long steps;
    long long poses;
} loops;

static int loop_is_pose(float start, float end) { return end > start && (end - start) <= 1.0f; }

static int loop_fraction(float step) { return step > 0.0f && fabsf(step - roundf(step)) > 1e-3f; }

static float loop_whole(uint64_t entry, float step) {
    const uint32_t h = (uint32_t)((entry * 0x9E3779B97F4A7C15ULL) >> 40) % LOOP_SLOTS;
    uint32_t k = 0;
    AcquireSRWLockExclusive(&loop_lock);
    while (k < LOOP_PROBE) {
        const uint32_t idx = (h + k) % LOOP_SLOTS;
        if (!loop_carry[idx].at || loop_carry[idx].at == entry) break;
        k++;
    }
    const uint32_t i = (h + (k < LOOP_PROBE ? k : 0)) % LOOP_SLOTS;
    if (loop_carry[i].at != entry) loop_carry[i].at = entry, loop_carry[i].part = 0.0f;
    const float sum = loop_carry[i].part + step;
    const float whole = floorf(sum);
    loop_carry[i].part = sum - whole;
    ReleaseSRWLockExclusive(&loop_lock);
    return whole;
}

/* ---- exported host callbacks ---- */

static volatile int g_seen_cloth, g_seen_horse, g_seen_floor, g_seen_input, g_seen_turn;

float hos_oot_loop_step(uint64_t entry, float step, float speed, float orig) {
    first_run(&loops.seen[0], "1-frame loops step by whole frames at non-integer frame rates");
    float start = 0.0f, end = 0.0f;
    if (oot_fix_on(&g_looppose_on, "HOS_OOT_LOOPPOSE") && loop_fraction(frame_step()) && step > 0.0f &&
        g_readf(entry + 0x10ULL, &start) && g_readf(entry + 0x14ULL, &end) && loop_is_pose(start, end)) {
        const float whole = loop_whole(entry, step);
        __atomic_add_fetch(&loops.steps, 1, __ATOMIC_RELAXED);
        return whole * speed;
    }
    return orig;
}

uint32_t hos_oot_loop_pose(uint64_t at, uint32_t time_bits) {
    first_run(&loops.seen[1], "1-frame loops hold start pose at non-integer frame rates");
    uint32_t out_bits = time_bits;
    float start = 0.0f, end = 0.0f;
    if (oot_fix_on(&g_looppose_on, "HOS_OOT_LOOPPOSE") && loop_fraction(frame_step()) &&
        g_readf(at + 4ULL, &start) && g_readf(at + 8ULL, &end) && loop_is_pose(start, end)) {
        memcpy(&out_bits, &start, 4);
        __atomic_add_fetch(&loops.poses, 1, __ATOMIC_RELAXED);
    }
    if (log_due_20s(&loops.next_ns)) {
        const long long s = __atomic_exchange_n(&loops.steps, 0, __ATOMIC_RELAXED);
        const long long p = __atomic_exchange_n(&loops.poses, 0, __ATOMIC_RELAXED);
        if (s > 0 || p > 0) hos_log("oot fps: looppose: %lld steps made whole, %lld poses drawn at start in 20 s", s, p);
    }
    return out_bits;
}

float hos_oot_cloth_time(float dt) {
    first_run(&g_seen_cloth, "cloth simulation scales fixed 1/60 step by frame step above 60 fps");
    if (!oot_fix_on(&g_clothtime_on, "HOS_OOT_CLOTHTIME")) return dt;
    const float step = frame_step();
    if (short_frame(step)) return dt * step;
    return dt;
}

float hos_oot_horse_jump(float step, float orig) {
    first_run(&g_seen_horse, "horse jump treats whole-frame step as normal speed above 60 fps");
    if (!oot_fix_on(&g_horsejump_on, "HOS_OOT_HORSEJUMP")) return orig;
    const float frame = frame_step();
    if (short_frame(frame) && step > 0.0f && step >= frame * 0.999f) return step;
    return orig;
}

float hos_oot_floor_carry(float inv_dt, float limit) {
    (void)inv_dt;
    first_run(&g_seen_floor, "moving floor carry scales 1/dt limit by frame step above 60 fps");
    if (!oot_fix_on(&g_floorcarry_on, "HOS_OOT_FLOORCARRY")) return limit;
    const float step = frame_step();
    if (short_frame(step)) return limit / step;
    return limit;
}

float hos_oot_input_step(float orig) {
    first_run(&g_seen_input, "input repeat step tracks frame step above 60 fps");
    if (!oot_fix_on(&g_inputstep_on, "HOS_OOT_INPUTSTEP")) return orig;
    const int fps = hos_step_fps;
    const float step = (fps > 60 && fps <= 240) ? (60.0f / (float)fps) : frame_step();
    if (short_frame(step)) return step;
    return orig;
}

float hos_oot_turn_bound(float turn, float denom, float step) {
    first_run(&g_seen_turn, "steering turn-rate bounds scale by 1/step above 60 fps");
    if (oot_fix_on(&g_turnrate_on, "HOS_OOT_TURNRATE") && short_frame(step)) return turn / denom;
    return turn * denom;
}

#ifdef OOT_FPS_UNIT_TEST
void oot_fps_reset_for_test(void) {
    g_master_on = g_looppose_on = g_clothtime_on = g_horsejump_on = g_floorcarry_on = g_inputstep_on = g_turnrate_on = -1;
    memset(loop_carry, 0, sizeof loop_carry);
    memset(&loops, 0, sizeof loops);
}
#endif
