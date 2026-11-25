"""Verify opt-in RX_VK_LTO=thin wiring for relink_vk.so renderer TUs only.

Run with: python3 -I -B nx2/test_vk_lto_flag.py
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
sys.path.insert(0, str(ROOT / "third_party" / "a64-kit" / "tools"))

import build  # noqa: E402


def main() -> None:
    assert build.vk_lto_flags({}) == []
    assert build.vk_lto_flags({"RX_VK_LTO": ""}) == []
    assert build.vk_lto_flags({"RX_VK_LTO": "0"}) == []
    assert build.vk_lto_flags({"RX_VK_LTO": "thin"}) == ["-flto=thin"]
    assert build.vk_lto_flags({"RX_VK_LTO": " THIN "}) == ["-flto=thin"]

    vk_dir = ROOT / "gpu" / "vk"
    assert build.vk_is_renderer_tu(str(vk_dir / "vk_draw.cpp"), str(vk_dir))
    assert build.vk_is_renderer_tu(str(vk_dir / "vk_replay.cpp"), str(vk_dir))
    assert not build.vk_is_renderer_tu(str(vk_dir / "eden" / "foo.cpp"), str(vk_dir))
    assert not build.vk_is_renderer_tu(str(vk_dir / "sirit" / "src" / "bar.cpp"), str(vk_dir))
    assert not build.vk_is_renderer_tu(str(ROOT / "gpu" / "third_party" / "astcenc" / "a.cpp"), str(vk_dir))
    assert not build.vk_is_renderer_tu(str(ROOT / "gpu" / "third_party" / "suyu" / "video_core" / "textures" / "decoders.cpp"), str(vk_dir))

    build_py = (ROOT / "nx2" / "build.py").read_text(encoding="utf-8")
    assert "tu_lto = lto_flags if (not lib and vk_is_renderer_tu(src, vk)) else []" in build_py
    assert '"-fuse-ld=lld"] + vk_lto_flags() + ["-shared"' in build_py

    make_game_py = (ROOT / "nx2" / "make_game.py").read_text(encoding="utf-8")
    assert '"RX_VK_LTO"' in make_game_py

    print("vk_lto_flag: ok")


if __name__ == "__main__":
    main()
