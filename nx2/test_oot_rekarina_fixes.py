"""Regression tests for nx2/oot_rekarina_fixes.py, host/oot_fps.c, and a64_lift.py override/replace hooks.

Run with:
  python3 -I -B nx2/test_oot_rekarina_fixes.py [--cc clang]
"""

import argparse
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
sys.path.insert(0, str(ROOT / "third_party" / "a64-kit" / "lift"))

import a64_lift  # noqa: E402
import oot_rekarina_fixes  # noqa: E402
import oot_ripples  # noqa: E402
import oot_step_cuts  # noqa: E402


class MockImg:
    def __init__(self, words, entries=(), mem=None):
        self.words = dict(words)
        self.entries = set(entries)
        self.mem = dict(mem or {})
        self.hooks = {}
        self.names = {}

    def in_code(self, pc):
        return pc in self.words

    def word(self, pc):
        if pc not in self.words:
            raise KeyError(pc)
        return self.words[pc]

    def read(self, addr, size):
        return self.mem[addr][:size]


def sx(val, bits):
    sign = 1 << (bits - 1)
    return (val ^ sign) - sign


def check_site_tables():
    assert len(oot_rekarina_fixes.RINGPOST_SITES) == 77
    ring_offs = [s[0] for s in oot_rekarina_fixes.RINGPOST_SITES]
    assert len(set(ring_offs)) == 77
    for off, w in oot_rekarina_fixes.RINGPOST_SITES:
        pc = oot_rekarina_fixes.MAIN + off
        assert (w >> 26) == 0x5, (hex(off), hex(w))
        target = pc + sx(w & 0x3FFFFFF, 26) * 4
        assert target == oot_rekarina_fixes.RINGPOST_ABORT_TARGET, (hex(pc), hex(target))

    assert len(oot_rekarina_fixes.RESGUARD_SITES) == 3
    res_target = oot_rekarina_fixes.MAIN + 0xC93A18
    for off, old_w, new_w in oot_rekarina_fixes.RESGUARD_SITES:
        pc = oot_rekarina_fixes.MAIN + off
        if (new_w & 0x7E000000) == 0x36000000:      # tbnz/tbz (imm14 at bits 5..18)
            assert pc + sx((new_w >> 5) & 0x3FFF, 14) * 4 == res_target
        elif (new_w & 0xFE000000) == 0x54000000 or (new_w & 0x7E000000) == 0x34000000:
            assert pc + sx((new_w >> 5) & 0x7FFFF, 19) * 4 == res_target
        else:
            raise AssertionError((hex(pc), hex(old_w), hex(new_w)))

    offs = oot_rekarina_fixes.all_offsets()
    assert len(offs) == 3 + 77 + 3 + 8 == 91
    assert len(set(offs)) == 91
    assert "memcpy(c->vreg[0], &_t, 4)" in oot_rekarina_fixes._CLOTHTIME_C
    assert "a64_vset64" not in oot_rekarina_fixes._CLOTHTIME_C

    # Zero overlap with upstream v0.7.9.4 oot_ripples.py and oot_step_cuts.py sites.
    upstream_pcs = {oot_ripples.MAIN + oot_ripples.SITE}
    for pcs in oot_step_cuts.sites().values():
        upstream_pcs.update(pcs)
    rekarina_pcs = {oot_rekarina_fixes.MAIN + off for off in offs}
    assert not (upstream_pcs & rekarina_pcs), upstream_pcs & rekarina_pcs


def check_install_and_opt_out():
    words = {}
    for off, old_w, _ in oot_rekarina_fixes.RESGUARD_SITES:
        words[oot_rekarina_fixes.MAIN + off] = old_w
    for off, old_w in oot_rekarina_fixes.RINGPOST_SITES:
        words[oot_rekarina_fixes.MAIN + off] = old_w
    for off, old_w, _ in oot_rekarina_fixes.REPLACE_SITES:
        words[oot_rekarina_fixes.MAIN + off] = old_w
    for off, old_w, _ in oot_rekarina_fixes.AFTER_SITES:
        words[oot_rekarina_fixes.MAIN + off] = old_w

    img = MockImg(words)
    L = a64_lift.Lifter(img)
    buf = io.StringIO()
    with redirect_stdout(buf):
        n = oot_rekarina_fixes.install(L, img)
    assert n == 91, (n, buf.getvalue())
    assert "91 of 91 sites" in buf.getvalue()

    # Mismatch leaves bad site out without failing.
    first_off = oot_rekarina_fixes.RESGUARD_SITES[0][0]
    words[oot_rekarina_fixes.MAIN + first_off] = 0xD503201F
    L2 = a64_lift.Lifter(MockImg(words))
    buf2 = io.StringIO()
    with redirect_stdout(buf2):
        n2 = oot_rekarina_fixes.install(L2, MockImg(words))
    assert n2 == 90 and "left out" in buf2.getvalue()

    prev = os.environ.get("OOT_REKARINA_FIXES")
    try:
        os.environ["OOT_REKARINA_FIXES"] = "0"
        L3 = a64_lift.Lifter(img)
        with redirect_stdout(io.StringIO()):
            assert oot_rekarina_fixes.install(L3, img) == 0
            assert not L3.override and not L3.replace and not L3.after
    finally:
        if prev is None:
            os.environ.pop("OOT_REKARINA_FIXES", None)
        else:
            os.environ["OOT_REKARINA_FIXES"] = prev


def check_lifter_override_replace_and_locals():
    RET = 0xD65F03C0
    NOP = 0xD503201F
    MAIN = oot_rekarina_fixes.MAIN

    # Synthetic functions covering ringpost override, resguard override, looppose/turnrate replace, clothtime after.
    ring_entry = MAIN + 0xD25078
    res_entry = MAIN + 0xC93918
    res_dest = MAIN + 0xC93A18
    looppose_entry = MAIN + 0x924E50
    turn_entry = MAIN + 0x261EB18
    cloth_entry = MAIN + 0x1B1AC68
    abort_entry = oot_rekarina_fixes.RINGPOST_ABORT_TARGET

    words = {
        ring_entry: NOP,
        MAIN + 0xD2507C: 0x149F5C81,      # b main+0x34fc280 -> overridden to ret
        abort_entry: RET,

        MAIN + 0xC93918: 0x37F80148,
        MAIN + 0xC9391C: NOP,
        MAIN + 0xC93920: NOP,
        MAIN + 0xC93924: 0x540000ED,
        MAIN + 0xC93928: NOP,
        MAIN + 0xC9392C: NOP,
        MAIN + 0xC93930: 0xB4000093,
        MAIN + 0xC93934: 0x14000039,      # b res_dest (skip gap)
        res_dest: RET,

        looppose_entry: 0xBD0002C0,       # str s0, [x22]
        looppose_entry + 4: RET,

        turn_entry: 0x1E210801,           # fmul s1, s0, s1
        turn_entry + 4: 0x1E280800,       # fmul s0, s0, s8
        turn_entry + 8: RET,

        cloth_entry: 0xFD4006C0,          # ldr d0, [x22, #8]
        cloth_entry + 4: RET,
    }
    entries = {ring_entry, res_entry, looppose_entry, turn_entry, cloth_entry, abort_entry}
    # Include a PLT stub to ensure plt_target() exercises self.img.read() cleanly.
    plt_entry = MAIN + 0x100
    words.update({
        plt_entry: 0x90000010,       # adrp x16, #0 (page = 0x80120000)
        plt_entry + 4: 0xF9400211,   # ldr x17, [x16, #0]
        plt_entry + 8: 0x91000210,   # add x16, x16, #0
        plt_entry + 12: 0xD61F0220,  # br x17
    })
    entries.add(plt_entry)
    plt_slot = plt_entry & ~0xFFF
    plt_mem = {plt_slot: int(abort_entry).to_bytes(8, "little")}

    for local_cfg in ({"A64_LOCAL_REGS": "0", "A64_LOCAL_VREGS": "0"},
                      {"A64_LOCAL_REGS": "6", "A64_LOCAL_VREGS": "1"}):
        old_env = {k: os.environ.get(k) for k in local_cfg}
        try:
            os.environ.update(local_cfg)
            img = MockImg(words, entries, plt_mem)
            L = a64_lift.Lifter(img)
            with redirect_stdout(io.StringIO()):
                oot_rekarina_fixes.install(L, img)
            L.discover()
            assert plt_entry in L.plt and L.plt[plt_entry] == (abort_entry, plt_slot)
            texts = a64_lift.instruction_texts(L.funcs, set())

            ring_c, _ = L.emit_function(ring_entry, texts)
            assert "return;" in ring_c and ("f_%08x" % abort_entry) not in ring_c, ring_c

            res_c, _ = L.emit_function(res_entry, texts)
            assert "L_%08x:;" % res_dest in res_c and "goto L_%08x;" % res_dest in res_c, res_c

            lp_c, _ = L.emit_function(looppose_entry, texts)
            assert "hos_oot_loop_pose(" in lp_c and "recomp_store32(" in lp_c, lp_c

            turn_c, _ = L.emit_function(turn_entry, texts)
            assert turn_c.count("hos_oot_turn_bound(_t,") == 2 and "a64_fpx_mul32" not in turn_c, turn_c
            if local_cfg["A64_LOCAL_VREGS"] == "1":
                assert "c->vreg[0][0] = v0_[0]; c->vreg[0][1] = v0_[1];" in turn_c, turn_c
                assert "c->vreg[1][0] = v1_[0]; c->vreg[1][1] = v1_[1];" in turn_c, turn_c

            cloth_c, _ = L.emit_function(cloth_entry, texts)
            assert "hos_oot_cloth_time(" in cloth_c
            assert "memcpy(" in cloth_c and ", &_t, 4)" in cloth_c, cloth_c

            assert L.stats["replace_patches"] == 3, L.stats
        finally:
            for k, v in old_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


C_HARNESS = r"""
#define _POSIX_C_SOURCE 200112L
#define OOT_FPS_UNIT_TEST
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define HOS_HEAP_BASE   0x1000000000ULL
#define HOS_GUEST_SPACE (1ULL << 39)

const uint64_t hos_image_base = 0x80000000ULL;
const uint64_t hos_image_end  = 0x86000000ULL;
uint64_t hos_heap_size = 0x100000ULL;
volatile int hos_step_fps = 0;

static uint8_t fake_image[0x5000000];
static uint8_t fake_heap[0x100000];
static uint8_t fake_region[0x10000];
static const uint64_t REGION_BASE = 0x200000000ULL;

void *GP(uint64_t a) {
    if (a >= hos_image_base && a < hos_image_end)
        return fake_image + (a - hos_image_base);
    if (a >= HOS_HEAP_BASE && a < HOS_HEAP_BASE + hos_heap_size)
        return fake_heap + (a - HOS_HEAP_BASE);
    if (a >= REGION_BASE && a < REGION_BASE + sizeof(fake_region))
        return fake_region + (a - REGION_BASE);
    return NULL;
}

int hos_mem_region(uint64_t a, uint64_t n) {
    return a >= REGION_BASE && n > 0 && a + n <= REGION_BASE + sizeof(fake_region);
}

static int64_t fake_ns = 1000000000LL;
int64_t hos_now_ns(void) { return fake_ns; }

static int log_count = 0;
void hos_log(const char *fmt, ...) { (void)fmt; log_count++; }

#include "oot_fps.c"

static void set_vfr_step(float step) {
    const uint64_t vfr_slot = 0x80020000ULL + 0x4c7e890ULL;
    const uint64_t mgr = HOS_HEAP_BASE + 0x1000ULL;
    const uint64_t time_obj = HOS_HEAP_BASE + 0x2000ULL;
    memcpy(GP(vfr_slot), &mgr, 8);
    memcpy(GP(mgr), &time_obj, 8);
    memcpy(GP(time_obj + 0x10ULL), &step, 4);
}

static int feq(float a, float b) { return fabsf(a - b) < 1e-5f; }

int main(void) {
    /* 1. Null/invalid VFR & pointers never crash. */
    assert(feq(hos_oot_cloth_time(0.016f), 0.016f));
    assert(hos_oot_loop_pose(0x100, 0x12345678u) == 0x12345678u);
    assert(feq(hos_oot_loop_step(0xdeadbeef00ULL, 0.5f, 1.0f, 0.5f), 0.5f));

    /* 2. 60 FPS (step = 1.0): game-identical values. */
    set_vfr_step(1.0f);
    assert(feq(hos_oot_cloth_time(1.0f / 60.0f), 1.0f / 60.0f));
    assert(feq(hos_oot_floor_carry(150.0f, 100.0f), 100.0f));
    assert(feq(hos_oot_turn_bound(2.0f, 1.0f, 1.0f), 2.0f));
    assert(feq(hos_oot_input_step(1.0f), 1.0f));

    /* 3. 45 FPS (step = 1.3333333f): >60 fixes stay off, looppose stabilizes 1-frame loops. */
    set_vfr_step(60.0f / 45.0f);
    assert(feq(hos_oot_cloth_time(1.0f / 60.0f), 1.0f / 60.0f));
    assert(feq(hos_oot_horse_jump(1.333f, 1.0f), 1.0f));
    const uint64_t anim_entry = HOS_HEAP_BASE + 0x4000;
    const float anim_s = 10.0f, anim_e = 11.0f;
    memcpy(GP(anim_entry + 0x10), &anim_s, 4);
    memcpy(GP(anim_entry + 0x14), &anim_e, 4);
    assert(feq(hos_oot_loop_step(anim_entry, 0.6f, 2.0f, 1.2f), 0.0f));
    assert(feq(hos_oot_loop_step(anim_entry, 0.6f, 2.0f, 1.2f), 2.0f));

    const uint64_t pose_obj = REGION_BASE + 0x100;
    const float pose_s = 4.0f, pose_e = 5.0f;
    uint32_t pose_s_bits = 0;
    memcpy(&pose_s_bits, &pose_s, 4);
    memcpy(GP(pose_obj + 4), &pose_s, 4);
    memcpy(GP(pose_obj + 8), &pose_e, 4);
    assert(hos_oot_loop_pose(pose_obj, 0x3f800000u) == pose_s_bits);

    /* 4. 100 FPS (step = 0.6) and 120 FPS (step = 0.5). */
    oot_fps_reset_for_test();
    set_vfr_step(0.5f);
    assert(feq(hos_oot_cloth_time(1.0f / 60.0f), (1.0f / 60.0f) * 0.5f));
    assert(feq(hos_oot_horse_jump(0.5f, 1.0f), 0.5f));
    assert(feq(hos_oot_horse_jump(0.2f, 1.0f), 1.0f));
    assert(feq(hos_oot_floor_carry(150.0f, 100.0f), 200.0f));
    hos_step_fps = 120;
    assert(feq(hos_oot_input_step(1.0f), 0.5f));
    hos_step_fps = 0;
    set_vfr_step(0.6f);
    assert(feq(hos_oot_input_step(1.0f), 0.6f));
    assert(feq(hos_oot_turn_bound(2.0f, 0.5f, 0.5f), 4.0f));
    assert(feq(hos_oot_turn_bound(2.0f, 0.5f, NAN), 1.0f));

    /* 5. NaN / -1 steps fallback safely. */
    set_vfr_step(NAN);
    assert(feq(hos_oot_cloth_time(0.25f), 0.25f));
    set_vfr_step(-1.0f);
    assert(feq(hos_oot_floor_carry(100.0f, 100.0f), 100.0f));

    /* 6. HOS_OOT_FIXES=0 master disable switch. */
    setenv("HOS_OOT_FIXES", "0", 1);
    oot_fps_reset_for_test();
    set_vfr_step(0.5f);
    assert(feq(hos_oot_cloth_time(0.25f), 0.25f));
    assert(feq(hos_oot_floor_carry(150.0f, 100.0f), 100.0f));
    assert(feq(hos_oot_turn_bound(2.0f, 0.5f, 0.5f), 1.0f));
    assert(log_count > 0);
    return 0;
}
"""


def check_c_unit_and_syntax(cc):
    with tempfile.TemporaryDirectory(prefix="oot-fps-test-") as tmp:
        (Path(tmp) / "a64_suyu.h").write_text("/* stub for standalone syntax check */\n", encoding="utf-8")
        (Path(tmp) / "a64_fpx.h").write_text("/* stub for standalone syntax check */\n", encoding="utf-8")
        subprocess.run(
            [
                cc, "-std=c11", "-fsyntax-only", "-Wall", "-Wextra", "-Werror",
                "-I" + str(ROOT / "host" / "posix"),
                "-I" + str(ROOT / "host"),
                "-I" + str(ROOT / "third_party" / "a64-kit" / "rt"),
                "-I" + str(tmp),
                str(ROOT / "host" / "oot_fps.c"),
            ],
            check=True,
        )
        src = Path(tmp) / "harness.c"
        exe = Path(tmp) / "harness"
        src.write_text(C_HARNESS, encoding="utf-8")
        subprocess.run(
            [cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-I" + str(ROOT / "host"),
             str(src), "-lm", "-pthread", "-o", str(exe)],
            check=True,
        )
        subprocess.run([str(exe)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="clang")
    args = parser.parse_args()
    check_site_tables()
    check_install_and_opt_out()
    check_lifter_override_replace_and_locals()
    check_c_unit_and_syntax(args.cc)
    print("oot_rekarina_fixes: ok")


if __name__ == "__main__":
    main()
