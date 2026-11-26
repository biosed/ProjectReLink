"""Verify ProjectReLink PR #208 (vertex input types in graphics_key),
longshot-oberon CM1/CM1b reflection cubemap throttling, RX_VK_MARCH + Linux PGO_RT,
and timeline semaphore counter device-loss guards.

Run with: python3 -I -B nx2/test_vk_bc250_maxout.py
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
sys.path.insert(0, str(ROOT / "third_party" / "a64-kit" / "tools"))

import build  # noqa: E402


def main() -> None:
    vk_shader = (ROOT / "gpu" / "vk" / "vk_shader.cpp").read_text(encoding="utf-8")
    assert 'getenv("RX_VK_KEY_HEADER_TYPES")' in vk_shader
    assert "const bool read = !header_only || used[0] || used[1] || used[2] || used[3];" in vk_shader

    vk_draw = (ROOT / "gpu" / "vk" / "vk_draw.cpp").read_text(encoding="utf-8")
    assert 'getenv("RX_VK_CUBEMAP_EVERY")' in vk_draw
    assert "const int v = e ? std::max(1, atoi(e)) : 1;" in vk_draw
    assert "const bool settling = frame - busy_since < 90;" in vk_draw
    assert "bool cubemap_face_skipped(const Targets& at)" in vk_draw
    assert vk_draw.count("cubemap_face_skipped(at)") == 3

    assert build.vk_cpu_flags({}) is None
    assert build.vk_cpu_flags({"RX_VK_MARCH": ""}) is None
    assert build.vk_cpu_flags({"RX_VK_MARCH": " znver2 "}) == ["-march=znver2", "-mtune=znver2", "-ffp-contract=off"]
    assert build.vk_march_link_flags({}) == []
    assert build.vk_march_link_flags({"RX_VK_MARCH": "znver2"}) == ["-march=znver2", "-mtune=znver2"]

    build_py = (ROOT / "nx2" / "build.py").read_text(encoding="utf-8")
    assert '["-fPIC", "-I" + POSIX, "-D_GNU_SOURCE"] if LINUX else []' in build_py
    assert "vk_march_link_flags()" in build_py

    vk_replay = (ROOT / "gpu" / "vk" / "vk_replay.cpp").read_text(encoding="utf-8")
    assert "const uint64_t ceiling = q_values.load(std::memory_order_acquire);" in vk_replay
    assert "if (v == UINT64_MAX || v > rec_sent_pub.load(std::memory_order_acquire))" in vk_replay
    assert "void note_rec_sent(uint64_t seq)" in vk_replay

    vk_jobs = (ROOT / "gpu" / "vk" / "vk_jobs.cpp").read_text(encoding="utf-8")
    assert 'getenv("RX_VK_WORKERS")' in vk_jobs

    assert "__builtin_expect(g_fine, 0)" in vk_draw
    assert "std::memcmp(raw, craw, (size_t)nb)" in vk_draw

    print("vk_bc250_maxout: ok")


if __name__ == "__main__":
    main()
