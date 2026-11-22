"""Build and run the game-free texture staging arena OOM recovery regression.

Run with: python3 -I -B nx2/test_staging_retry.py [--cxx clang++]
"""

import argparse
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def check_integration() -> None:
    tex = (ROOT / "gpu" / "vk" / "vk_texture.cpp").read_text(encoding="utf-8")
    assert '#include "staging_retry.h"' in tex
    start = tex.index("Staging staging(uint64_t n, uint64_t align = 256)")
    end = tex.index("\n}\n", start)
    fn = tex[start:end]
    assert "vk_timeline_completed()" in fn
    assert "vk_timeline_wait_for(" in fn
    assert "staging_retry::exact_arena_size(n)" in fn
    assert "staging_retry::find_oldest_inflight(" in fn


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="clang++")
    args = parser.parse_args()
    check_integration()
    source = ROOT / "gpu" / "vk" / "tests" / "staging_retry_test.cpp"
    with tempfile.TemporaryDirectory(prefix="staging-retry-") as temporary:
        executable = Path(temporary) / "staging_retry_test"
        subprocess.run(
            [args.cxx, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(executable)],
            check=True,
        )
        subprocess.run([str(executable)], check=True)
    print("staging_retry: ok")


if __name__ == "__main__":
    main()
