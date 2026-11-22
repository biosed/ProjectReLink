"""OoT v1.1.1 stability & FPS fixes ported from Rekarina v1.2.10 (ff6548e8, GPL-3.0).

Covers the 12 Rekarina fixes that ProjectReLink v0.7.9.2 did not yet have:
  - resguard   (3): handle lookup invalid-path guards against null-entry dereference (any FPS)
  - ringpost  (77): lock-free ring writer guards returning instead of aborting (any FPS)
  - ripple     (1): round interactive water ripple pass count instead of truncating to 0 (>60 FPS)
  - pickup     (1): round up HUD pickup count step (>60 FPS; cause Hookshot PR #2006)
  - solver     (2): anti-jitter ceiling on physics solver step count (>60 FPS; cause Hookshot PR #2470)
  - daytime    (1): fractional carry on day/night clock seconds (>60 FPS)
  - looppose   (3): stabilize 1-frame looped animations against phase twitch (45-58 & >60 FPS)
  - clothtime  (1): scale fixed 1/60 cloth substep delta by frame step (>60 FPS)
  - webstep    (1): fractional carry on dungeon floor-web simulation steps (>60 FPS)
  - horsejump  (1): recognize whole-frame step during fence jump blend (>60 FPS)
  - floorcarry (3): scale 100 Hz moving-floor 1/dt carry limit by step (>60 FPS)
  - inputstep  (1): scale global input repeat step above 60 FPS
  - turnrate   (2): fix Gohma / steering saved turn-rate clamp bounds above 60 FPS

Every site verifies the original instruction word before patching; OOT_REKARINA_FIXES=0 opts out at lift time.
"""

import os

MAIN = 0x80020000

# Resource lookup by handle (main+0xc938d0): jump to the function's own invalid-handle path (main+0xc93a18).
RESGUARD_SITES = (
    (0xc93918, 0x37f80148, 0x37f80808),   # tbnz w8, #31 -> main+0xc93a18
    (0xc93924, 0x540000ed, 0x540007ad),   # b.le         -> main+0xc93a18
    (0xc93930, 0xb4000093, 0xb4000753),   # cbz x19      -> main+0xc93a18
)

# Lock-free ring writers: 77 functions whose failure branch `b main+0x34fc280` (nn::diag abort) becomes `ret`.
RET_INSN = 0xd65f03c0
RINGPOST_ABORT_TARGET = MAIN + 0x34fc280
RINGPOST_SITES = (
    (0xd2507c, 0x149f5c81),
    (0x163cc8, 0x14ce616e),
    (0x3e0ad4, 0x14c46deb),
    (0x444a80, 0x14c2de00),
    (0x44c788, 0x14c2bebe),
    (0x4b48c0, 0x14c11e70),
    (0x57b080, 0x14be0480),
    (0x57be18, 0x14be011a),
    (0x608bd0, 0x14bbcdac),
    (0x682c7c, 0x14b9e581),
    (0x9b3020, 0x14ad2498),
    (0x9b3b94, 0x14ad21bb),
    (0x9b3d3c, 0x14ad2151),
    (0xba6ed8, 0x14a554ea),
    (0xba70cc, 0x14a5546d),
    (0xba7e88, 0x14a550fe),
    (0xbf8f80, 0x14a40cc0),
    (0xcc2efc, 0x14a0e4e1),
    (0xd5e9c4, 0x149e762f),
    (0xf07244, 0x1497d40f),
    (0xf6a188, 0x1496483e),
    (0xfc4420, 0x1494df98),
    (0x10a5f44, 0x149158cf),
    (0x1100b7c, 0x148fedc1),
    (0x1116a44, 0x148f960f),
    (0x111b79c, 0x148f82b9),
    (0x11d57ec, 0x148c9aa5),
    (0x11dd938, 0x148c7a52),
    (0x3745680, 0x17f6db00),
    (0x37484f8, 0x17f6cf62),
    (0x374af44, 0x17f6c4cf),
    (0x3759598, 0x17f68b3a),
    (0x375d9e0, 0x17f67a28),
    (0x375f4cc, 0x17f6736d),
    (0x376a0a8, 0x17f64876),
    (0x376a144, 0x17f6484f),
    (0x376a1d8, 0x17f6482a),
    (0x376a274, 0x17f64803),
    (0x376a584, 0x17f6473f),
    (0x376a618, 0x17f6471a),
    (0x376a6ac, 0x17f646f5),
    (0x376a73c, 0x17f646d1),
    (0x376a7c8, 0x17f646ae),
    (0x376a85c, 0x17f64689),
    (0x376a8ec, 0x17f64665),
    (0x376a980, 0x17f64640),
    (0x376aa2c, 0x17f64615),
    (0x376aabc, 0x17f645f1),
    (0x376ab48, 0x17f645ce),
    (0x376abdc, 0x17f645a9),
    (0x376ac6c, 0x17f64585),
    (0x376acf0, 0x17f64564),
    (0x376ad8c, 0x17f6453d),
    (0x376ae18, 0x17f6451a),
    (0x376aeac, 0x17f644f5),
    (0x376af40, 0x17f644d0),
    (0x376afe4, 0x17f644a7),
    (0x376b090, 0x17f6447c),
    (0x376b134, 0x17f64453),
    (0x376b1dc, 0x17f64429),
    (0x376b27c, 0x17f64401),
    (0x376b314, 0x17f643db),
    (0x376b3b4, 0x17f643b3),
    (0x376b4c0, 0x17f64370),
    (0x376b614, 0x17f6431b),
    (0x376b744, 0x17f642cf),
    (0x376b874, 0x17f64283),
    (0x376b9a4, 0x17f64237),
    (0x376bad4, 0x17f641eb),
    (0x376bc18, 0x17f6419a),
    (0x376bcb4, 0x17f64173),
    (0x376bd54, 0x17f6414b),
    (0x376bdf8, 0x17f64122),
    (0x376be8c, 0x17f640fd),
    (0x376bf1c, 0x17f640d9),
    (0x376bfb4, 0x17f640b3),
    (0x376c04c, 0x17f6408d),
)

_RIPPLE_C = (
    "{ extern uint32_t hos_oot_ripple_steps(uint32_t, uint32_t, float); "
    "float _r; memcpy(&_r, c->vreg[0], 4); "
    "c->x[8] = hos_oot_ripple_steps((uint32_t)c->x[8], (uint32_t)c->x[9], _r); }"
    "   /* (nx2/oot_rekarina_fixes.py: ripple) */"
)
_LOOP_POSE_C = (
    "{ extern uint32_t hos_oot_loop_pose(uint64_t, uint32_t); "
    "uint32_t _t; memcpy(&_t, c->vreg[0], 4); "
    "recomp_store32(c, c->x[22], hos_oot_loop_pose(c->x[22], _t)); }"
    "   /* (nx2/oot_rekarina_fixes.py: looppose store) */"
)


def _turn_bound_c(dst_vreg, denom_vreg):
    return (
        "{ extern float hos_oot_turn_bound(float, float, float); "
        "float _t, _d, _s; memcpy(&_t, c->vreg[0], 4); memcpy(&_d, c->vreg[%d], 4); memcpy(&_s, c->vreg[8], 4); "
        "const float _o = hos_oot_turn_bound(_t, _d, _s); uint32_t _u; memcpy(&_u, &_o, 4); "
        "a64_vset64(c->vreg[%d], _u); }   /* (nx2/oot_rekarina_fixes.py: turnrate) */"
        % (denom_vreg, dst_vreg)
    )


REPLACE_SITES = (
    (0x4760c, 0x1b097d08, _RIPPLE_C),                   # mul w8, w8, w9
    (0x924e50, 0xbd0002c0, _LOOP_POSE_C),               # str s0, [x22]
    (0x261eb18, 0x1e210801, _turn_bound_c(1, 1)),       # fmul s1, s0, s1
    (0x261eb1c, 0x1e280800, _turn_bound_c(0, 8)),       # fmul s0, s0, s8
)

_PICKUP_C = (
    "{ extern uint32_t hos_oot_pickup_step(uint32_t, float); "
    "float _v; memcpy(&_v, c->vreg[0], 4); c->x[12] = hos_oot_pickup_step((uint32_t)c->x[12], _v); }"
    "   /* (nx2/oot_rekarina_fixes.py: pickup) */"
)
_SOLVER_C = (
    "{ extern uint32_t hos_oot_solver_steps(uint32_t, float, float); "
    "float _t, _b; memcpy(&_t, c->vreg[0], 4); memcpy(&_b, c->vreg[1], 4); "
    "c->x[1] = hos_oot_solver_steps((uint32_t)c->x[1], _t, _b); }"
    "   /* (nx2/oot_rekarina_fixes.py: solver) */"
)
_DAYTIME_C = (
    "{ extern float hos_oot_day_clock(uint64_t, float); "
    "float _a; memcpy(&_a, c->vreg[0], 4); const float _o = hos_oot_day_clock(c->x[19], _a); "
    "uint32_t _u; memcpy(&_u, &_o, 4); a64_vset64(c->vreg[0], _u); }"
    "   /* (nx2/oot_rekarina_fixes.py: daytime) */"
)


def _loop_step_c(dst_vreg, speed_vreg):
    return (
        "{ extern float hos_oot_loop_step(uint64_t, float, float, float); "
        "float _st, _sp, _or; memcpy(&_st, c->vreg[8], 4); memcpy(&_sp, c->vreg[%d], 4); memcpy(&_or, c->vreg[%d], 4); "
        "const float _o = hos_oot_loop_step(c->x[20], _st, _sp, _or); uint32_t _u; memcpy(&_u, &_o, 4); "
        "a64_vset64(c->vreg[%d], _u); }   /* (nx2/oot_rekarina_fixes.py: looppose step) */"
        % (speed_vreg, dst_vreg, dst_vreg)
    )


# CRITICAL: ldr d0, [x22, #8] loads 64 bits (two packed floats); memcpy low 4 bytes only so bits 32..63 stay intact.
_CLOTHTIME_C = (
    "{ extern float hos_oot_cloth_time(float); "
    "float _dt; memcpy(&_dt, c->vreg[0], 4); const float _t = hos_oot_cloth_time(_dt); "
    "memcpy(c->vreg[0], &_t, 4); }   /* (nx2/oot_rekarina_fixes.py: clothtime) */"
)
_WEBSTEP_C = (
    "{ extern float hos_oot_web_steps(uint64_t, float); "
    "float _a; memcpy(&_a, c->vreg[0], 4); const float _o = hos_oot_web_steps(c->x[19], _a); "
    "uint32_t _u; memcpy(&_u, &_o, 4); a64_vset64(c->vreg[0], _u); }"
    "   /* (nx2/oot_rekarina_fixes.py: webstep) */"
)
_HORSEJUMP_C = (
    "{ extern float hos_oot_horse_jump(float, float); "
    "float _st, _or; memcpy(&_st, c->vreg[10], 4); memcpy(&_or, c->vreg[9], 4); "
    "const float _o = hos_oot_horse_jump(_st, _or); uint32_t _u; memcpy(&_u, &_o, 4); "
    "a64_vset64(c->vreg[9], _u); }   /* (nx2/oot_rekarina_fixes.py: horsejump) */"
)
_FLOORCARRY_C = (
    "{ extern float hos_oot_floor_carry(float, float); "
    "float _i, _l; memcpy(&_i, c->vreg[0], 4); memcpy(&_l, c->vreg[1], 4); "
    "const float _o = hos_oot_floor_carry(_i, _l); uint32_t _u; memcpy(&_u, &_o, 4); "
    "a64_vset64(c->vreg[1], _u); }   /* (nx2/oot_rekarina_fixes.py: floorcarry) */"
)
_INPUTSTEP_C = (
    "{ extern float hos_oot_input_step(float); "
    "float _a; memcpy(&_a, c->vreg[0], 4); const float _o = hos_oot_input_step(_a); "
    "uint32_t _u; memcpy(&_u, &_o, 4); a64_vset64(c->vreg[0], _u); }"
    "   /* (nx2/oot_rekarina_fixes.py: inputstep) */"
)

AFTER_SITES = (
    (0xa68300, 0x1e38000c, _PICKUP_C),                  # fcvtzs w12, s0
    (0x38aebf4, 0x1e380001, _SOLVER_C),                 # fcvtzs w1, s0
    (0x38afd20, 0x1e380001, _SOLVER_C),                 # fcvtzs w1, s0
    (0x3cdfbc, 0x1e202800, _DAYTIME_C),                 # fadd s0, s0, s0
    (0x2afe04, 0x1e210902, _loop_step_c(2, 1)),         # fmul s2, s8, s1
    (0x2b01d0, 0x1e200901, _loop_step_c(1, 0)),         # fmul s1, s8, s0
    (0x1b1ac68, 0xfd4006c0, _CLOTHTIME_C),              # ldr d0, [x22, #8]
    (0x632cfc, 0x1e201900, _WEBSTEP_C),                 # fdiv s0, s8, s0
    (0x2c3ae18, 0x1e2e1009, _HORSEJUMP_C),              # fmov s9, #1.0
    (0x13a068, 0x1e270101, _FLOORCARRY_C),              # fmov s1, w8
    (0x13d708, 0x1e270101, _FLOORCARRY_C),              # fmov s1, w8
    (0x389ac24, 0x1e270101, _FLOORCARRY_C),             # fmov s1, w8
    (0x3b4eaf8, 0x1e201820, _INPUTSTEP_C),              # fdiv s0, s1, s0
)


def all_offsets():
    return (
        [s[0] for s in RESGUARD_SITES]
        + [s[0] for s in RINGPOST_SITES]
        + [s[0] for s in REPLACE_SITES]
        + [s[0] for s in AFTER_SITES]
    )


def _check_word(img, off, word, label):
    pc = MAIN + off
    try:
        have = img.word(pc)
    except Exception:
        have = None
    if have != word:
        print("oot_rekarina_fixes (%s): main+%#x holds %s, not %08x: left out"
              % (label, off, "?" if have is None else "%08x" % have, word))
        return None
    return pc


def install(lifter, img):
    """Install Rekarina stability & high-FPS sites into lifter.override / replace / after."""
    if os.environ.get("OOT_REKARINA_FIXES", "1") == "0":
        print("oot_rekarina_fixes: disabled (OOT_REKARINA_FIXES=0)")
        return 0
    n_res = n_ring = n_rep = n_aft = 0
    for off, old_w, new_w in RESGUARD_SITES:
        pc = _check_word(img, off, old_w, "resguard")
        if pc is not None:
            lifter.override[pc] = new_w
            n_res += 1
    for off, old_w in RINGPOST_SITES:
        pc = _check_word(img, off, old_w, "ringpost")
        if pc is not None:
            lifter.override[pc] = RET_INSN
            n_ring += 1
    for off, old_w, text in REPLACE_SITES:
        pc = _check_word(img, off, old_w, "replace")
        if pc is not None:
            lifter.replace[pc] = text
            n_rep += 1
    for off, old_w, text in AFTER_SITES:
        pc = _check_word(img, off, old_w, "after")
        if pc is not None:
            lifter.after[pc] = (lifter.after[pc] + "\n" + text) if pc in lifter.after else text
            n_aft += 1
    total = len(RESGUARD_SITES) + len(RINGPOST_SITES) + len(REPLACE_SITES) + len(AFTER_SITES)
    installed = n_res + n_ring + n_rep + n_aft
    print("oot_rekarina_fixes: %d of %d sites (resguard %d/%d, ringpost %d/%d, replace %d/%d, after %d/%d)"
          % (installed, total, n_res, len(RESGUARD_SITES), n_ring, len(RINGPOST_SITES),
             n_rep, len(REPLACE_SITES), n_aft, len(AFTER_SITES)))
    return installed
