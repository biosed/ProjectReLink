"""Build and run the game-free dispatch barrier relaxation regression.

Run with: python3 -I -B nx2/test_dispatch_barrier.py [--cxx clang++]
"""

import argparse
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def check_integration() -> None:
    internal_h = (ROOT / "gpu" / "vk" / "vk_internal.h").read_text(encoding="utf-8")
    assert "void barrier_note_work_kind(uint8_t kind);" in internal_h
    assert "uint8_t barrier_work_kind();" in internal_h
    assert "void barrier_note_dispatch_relaxed();" in internal_h

    tex = (ROOT / "gpu" / "vk" / "vk_texture.cpp").read_text(encoding="utf-8")
    assert '#include "dispatch_barrier.h"' in tex
    assert "tl_barrier_work_kind = 0;" in tex
    assert "st_dispatch_barriers_relaxed" in tex

    draw = (ROOT / "gpu" / "vk" / "vk_draw.cpp").read_text(encoding="utf-8")
    assert '#include "dispatch_barrier.h"' in draw
    assert "dispatch_barrier::parse_mode(" in draw
    assert "need_dispatch_barrier(" in draw
    assert "RX_VK_DISPATCH_BARRIER" in draw
    assert "barrier_note_work_kind(dispatch_barrier::kWorkOther);" in draw
    assert "barrier_note_work_kind(dispatch_barrier::kWorkDispatch);" in draw

    replay = (ROOT / "gpu" / "vk" / "vk_replay.cpp").read_text(encoding="utf-8")
    assert "barrier_note_work_kind(2);" in replay
    assert "dispatch relaxed" in replay


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="clang++")
    args = parser.parse_args()
    check_integration()
    source = ROOT / "gpu" / "vk" / "tests" / "dispatch_barrier_test.cpp"
    with tempfile.TemporaryDirectory(prefix="dispatch-barrier-") as temporary:
        executable = Path(temporary) / "dispatch_barrier_test"
        subprocess.run(
            [args.cxx, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(executable)],
            check=True,
        )
        subprocess.run([str(executable)], check=True)
    print("dispatch_barrier: ok")


if __name__ == "__main__":
    main()
