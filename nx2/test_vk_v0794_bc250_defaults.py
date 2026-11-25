"""Check v0.7.9.4 BC-250 safe defaults, native FP, disk_stamp sorting, and replay vcore boost invariants.

Run with: python3 -I -B nx2/test_vk_v0794_bc250_defaults.py
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def function(source: str, signature: str) -> str:
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unterminated function: {signature}")


def main() -> None:
    internal_h = (ROOT / "gpu" / "vk" / "vk_internal.h").read_text(encoding="utf-8")
    fast_sync = function(internal_h, "inline bool fast_sync_all()")
    assert 'getenv("RX_VK_FAST_SYNC") ? atoi(getenv("RX_VK_FAST_SYNC")) != 0 : false;' in fast_sync

    draw_cpp = (ROOT / "gpu" / "vk" / "vk_draw.cpp").read_text(encoding="utf-8")
    draw_fn = function(draw_cpp, "void draw(VkCommandBuffer cmd, NvnState& s, const DrawArgs& d)")
    assert 'getenv("RX_VK_PIPE_WAIT_MS") ? std::max(0, atoi(getenv("RX_VK_PIPE_WAIT_MS"))) : 2;' in draw_fn

    hos_thread = (ROOT / "host" / "hos_thread.c").read_text(encoding="utf-8")
    assert "#include <emmintrin.h>" in hos_thread
    fpcr_sync = function(hos_thread, "void hos_fpcr_sync(Ctx *c)")
    assert "__x86_64__" in fpcr_sync and "_mm_setcsr" in fpcr_sync
    assert "hos_fpcr_sync(c);" in function(hos_thread, "static DWORD WINAPI thread_main(void *p)")
    assert "hos_fpcr_sync(c);" in function(hos_thread, "static void WINAPI fiber_main(void *p)")

    sys.path.insert(0, str(ROOT / "third_party" / "a64-kit" / "lift"))
    import a64_lift

    header = a64_lift.native_header(
        {("add32", "add32", 2, 2), ("mul32", "fma32", 2, 3), ("sqrt32", "sqrt32", 1, 1)}
    )
    assert "#if RECOMP_FPX_HOST == 2" in header
    assert "a64_fpx_nat_add32_add32(" in header
    assert "A64_NAT_VEC(add32, _mm_add_ps, k == 4 ? 15 : 3)" in header
    assert "a64_nat_fp_to_int(" in header
    assert "#define a64_fpx_nat_add32_add32 a64_fpx_hot_add32_add32" in header

    shader_cpp = (ROOT / "gpu" / "vk" / "vk_shader.cpp").read_text(encoding="utf-8")
    disk_stamp_fn = function(shader_cpp, "uint64_t disk_stamp()")
    assert "std::sort(vars.begin(), vars.end()," in disk_stamp_fn
    assert "strcmp(a, b) < 0" in disk_stamp_fn

    nvn_native = (ROOT / "host" / "nvn_native.c").read_text(encoding="utf-8")
    submit_fn = function(nvn_native, "NV(nvnQueueSubmitCommands)")
    assert "if (away) hos_vcore_back_first();" in submit_fn
    vcp_fn = function(hos_thread, "static int vcp(const HosThread *t)")
    assert "- t->vc_boost" in vcp_fn
    back_first_fn = function(hos_thread, "void hos_vcore_back_first(void)")
    assert "HOS_VCORE_REPLAY_BOOST" in back_first_fn
    assert "t->vc_boost = 0;" in function(hos_thread, "static void vc_release(HosThread *t)")
    assert "t->vc_boost = 0;" in function(hos_thread, "static void vc_acquire(HosThread *t)")
    assert "t->vc_boost = 0;" in function(hos_thread, "void hos_vcore_back(void)")

    print("vk_v0794_bc250_defaults: ok")


if __name__ == "__main__":
    main()
