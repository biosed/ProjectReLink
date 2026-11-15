"""Test sparse guest-memory block rounding, merging, and already-bound filtering.

No Vulkan device, game data, or Linux udmabuf device is used.

python nx2/test_sparse_guest_ranges.py [--cxx clang++]
"""
import argparse
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="clang++")
    args = parser.parse_args()
    fixture = r'''
#include <cstdio>
#include <cstdlib>
#include <vector>
#include "gpu/vk/sparse_guest_ranges.h"
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); std::exit(1); } } while (0)

int main() {
    constexpr uint64_t base = 0x1000000000ull, block = 65536;
    std::vector<uint8_t> wanted(8);
    std::vector<uint64_t> bound(1);

    sparse_guest::mark(wanted, base, block, base + 4096, base + block + 4096);
    sparse_guest::mark(wanted, base, block, base + 3 * block, base + 4 * block);
    auto runs = sparse_guest::runs(wanted, bound, block);
    CHECK(runs.size() == 2);
    CHECK(runs[0].offset == 0 && runs[0].size == 2 * block);
    CHECK(runs[1].offset == 3 * block && runs[1].size == block);

    sparse_guest::set_bound(bound, 1, 1);
    runs = sparse_guest::runs(wanted, bound, block);
    CHECK(runs.size() == 2);
    CHECK(runs[0].offset == 0 && runs[0].size == block);
    CHECK(runs[1].offset == 3 * block && runs[1].size == block);
    CHECK(sparse_guest::bound(bound, 1) && !sparse_guest::bound(bound, 2));

    sparse_guest::set_bound(bound, 0, 1);
    sparse_guest::set_bound(bound, 3, 1);
    CHECK(sparse_guest::runs(wanted, bound, block).empty());
    CHECK(sparse_guest::overlaps_bound(bound, base, block, base + 1, base + block));
    CHECK(!sparse_guest::overlaps_bound(bound, base, block, base + 2 * block, base + 3 * block));
    CHECK(sparse_guest::overlaps_bound(bound, base, block, base + 2 * block, base + 3 * block + 1));
    CHECK(!sparse_guest::overlaps_bound(bound, base, block, base - block, base));
    CHECK(!sparse_guest::overlaps_bound(bound, base, 0, base, base + 1));

    std::fill(wanted.begin(), wanted.end(), 0);
    sparse_guest::mark(wanted, base, block, base + 7 * block + 1, base + 8 * block);
    runs = sparse_guest::runs(wanted, bound, block);
    CHECK(runs.size() == 1 && runs[0].offset == 7 * block && runs[0].size == block);
    sparse_guest::mark(wanted, base, block, base, base);
    sparse_guest::mark(wanted, base, 0, base, base + 1);

    std::puts("PASS: sparse guest ranges round, merge, exclude, and find bound blocks");
}
'''
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sparse-guest-ranges-", dir=work) as temp:
        directory = Path(temp).resolve()
        directory.relative_to(work.resolve())
        cpp = directory / "fixture.cpp"
        exe = directory / "fixture"
        cpp.write_text(fixture, encoding="utf-8")
        subprocess.run(
            [args.cxx, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT), str(cpp), "-o", str(exe)],
            check=True,
        )
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
