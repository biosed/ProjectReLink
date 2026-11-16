// The ordering functions are copied verbatim from host/hos_thread.c by the Python test.
#include <cstdint>
#include <cstdio>
#include <cstdlib>

#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); std::exit(1); } } while (0)

struct Ctx { int poll = 0; };
struct HosThread {
    Ctx ctx;
    int priority = 16, ideal_core = -2;
    uint64_t core_mask = 0x3f;
    int vc_held = 0, vc_last = 0, vc_queued = 0, vc_escaped = 0;
    int vc_boost = 0, vc_kick = 0, vc_prio_over = 0;
    int64_t vc_since = 0, vc_cap_until = 0, vc_free_until = 0;
    int vc_cv = 0;
    Ctx *run_ctx = nullptr;
    int acquires = 0, boost_at_acquire = -1;
};

static int vc_lock;
static HosThread *vc_owner[8];
static HosThread *vc_queue[1024];
static int vc_nq;
static struct { long long kicks = 0, yields = 0; } vc_st;
static int vc_base_cores(void) { return 6; }
static int vc_overflow_cores(void) { return 0; }
static int vc_cores(void) { return 6; }
static int vc_bg_cap(void) { return 0; }
static int vc_held_n(void) { int n = 0; for (int k = 0; k < 6; k++) n += vc_owner[k] != nullptr; return n; }
static int64_t hos_now_ns(void) { return 0; }
static int vc_capped(const HosThread *) { return 0; }
static int hos_thread_core(HosThread *t) { return t->ideal_core >= 0 ? t->ideal_core : 0; }
#define AcquireSRWLockExclusive(lock) (void)(lock)
#define ReleaseSRWLockExclusive(lock) (void)(lock)
#define WakeConditionVariable(cv) (++*(cv))
static void vc_acquire(HosThread *t) { t->acquires++; t->boost_at_acquire = t->vc_boost; }

#include "actual_vcore.inc"

static void reset() {
    for (auto &owner : vc_owner) owner = nullptr;
    vc_nq = 0;
}
static void enqueue(HosThread *t, int64_t since) {
    t->vc_since = since;
    t->vc_queued = 1;
    vc_queue[vc_nq++] = t;
}
static HosThread executor() { HosThread t; t.priority = 16; t.core_mask = 1; return t; }
static HosThread presenter(int boost) { HosThread t; t.priority = 17; t.vc_boost = boost; return t; }

int main() {
    {
        reset();
        HosThread e = executor(), p = presenter(0);
        enqueue(&e, 1); enqueue(&p, 2); vc_grant(0);
        CHECK(vc_owner[0] == &e && !p.vc_held && p.vc_queued);
    }
    {
        reset();
        HosThread e = executor(), p = presenter(2);
        enqueue(&e, 1); enqueue(&p, 2); vc_grant(0);
        CHECK(vc_owner[0] == &p && !e.vc_held && e.vc_queued);
        CHECK(vcp(&p) == 15 && vcp(&e) == 16 && vc_better(&p, &e));
    }
    {
        reset();
        HosThread audio, p = presenter(2); audio.priority = 3;
        enqueue(&p, 1); enqueue(&audio, 2); vc_grant(0);
        CHECK(vc_owner[0] == &audio && !p.vc_held);
    }
    {
        reset(); vc_st.yields = 0;
        HosThread e = executor(), p = presenter(2);
        vc_take(&p, 0); enqueue(&e, 1); p.vc_kick = 1; vc_yield(&p, 1);
        CHECK(vc_owner[0] == &p && p.vc_held == 1 && p.acquires == 0 && vc_st.yields == 0);
    }
    {
        reset(); vc_st.yields = 0;
        HosThread e = executor(), p = presenter(0);
        vc_take(&p, 0); enqueue(&e, 1); vc_yield(&p, 1);
        CHECK(vc_owner[0] == &e && !p.vc_held && p.acquires == 1 && vc_st.yields == 1);
    }
    {
        reset(); vc_st.yields = 0;
        HosThread audio, p = presenter(2); audio.priority = 3;
        vc_take(&p, 0); enqueue(&audio, 1); vc_yield(&p, 1);
        CHECK(vc_owner[0] == &audio && p.acquires == 1 && p.boost_at_acquire == 2 && p.vc_boost == 2);
    }
    {
        reset();
        HosThread e = executor(), p = presenter(2);
        vc_take(&p, 0); enqueue(&e, 1); vc_release(&p);
        CHECK(p.vc_boost == 0 && !p.vc_held && vc_owner[0] == &e && vcp(&p) == 17);
    }
    std::puts("vcore replay first: ok");
    return 0;
}
