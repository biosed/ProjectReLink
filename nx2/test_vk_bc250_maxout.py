"""Verify ProjectReLink PR #208 (vertex input types in graphics_key) and
longshot-oberon CM1/CM1b reflection cubemap throttling contracts.

Run with: python3 -I -B nx2/test_vk_bc250_maxout.py
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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

    print("vk_bc250_maxout: ok")


if __name__ == "__main__":
    main()
