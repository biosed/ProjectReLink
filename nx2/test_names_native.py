"""Test that native name-search loops preserve the guest scheduler checkpoint.

No game data, guest memory, renderer, or platform thread is used.

python nx2/test_names_native.py [--cc clang]
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="clang")
    args = parser.parse_args()
    fixture = r'''
#include <stdio.h>
#include <stdlib.h>
#include "host/hos.h"
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); exit(1); } } while (0)

static int checkpoints;
void hos_vcore_checkpoint(void) { checkpoints++; }
void hos_log(const char *fmt, ...) { (void)fmt; }

int hos_names_lower(Ctx *c);
int hos_names_upper(Ctx *c, int at_head);

int main(void) {
    Ctx c = {0};
    c.poll = 1;
    CHECK(hos_names_lower(&c) == 0);
    CHECK(c.poll == 0);
    CHECK(checkpoints == 1);
    CHECK(hos_names_lower(&c) == 0);
    CHECK(checkpoints == 1);
    c.poll = 1;
    CHECK(hos_names_upper(&c, 1) == 0);
    CHECK(c.poll == 0);
    CHECK(checkpoints == 2);
    CHECK(hos_names_upper(&c, 0) == 0);
    CHECK(checkpoints == 2);
    puts("PASS: native name-search entries preserve virtual-core preemption");
}
'''
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="names-native-", dir=work) as temp:
        directory = Path(temp).resolve()
        directory.relative_to(work.resolve())
        source = directory / "fixture.c"
        executable = directory / "fixture"
        # names_native includes the generated guest model through hos.h.  Keep
        # this scheduler test independent of a previous title lift while still
        # modelling the registers and interrupt flag it touches.
        (directory / "a64.h").write_text(
            "#include <stddef.h>\n"
            "#include <stdint.h>\n"
            "typedef struct GuestContext {\n"
            "    uint64_t x[32];\n"
            "    uint8_t n, z, c, v;\n"
            "    uint32_t poll;\n"
            "} GuestContext;\n"
            "typedef GuestContext Ctx;\n"
            "#define A64_PTR(a) ((uint8_t *)(uintptr_t)(a))\n",
            encoding="utf-8",
        )
        source.write_text(fixture, encoding="utf-8")
        subprocess.run(
            [
                args.cc,
                "-std=c11",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-I",
                str(ROOT),
                "-I",
                str(directory),
                "-I",
                str(ROOT / "third_party" / "a64-kit" / "rt"),
                str(ROOT / "host" / "names_native.c"),
                str(source),
                "-o",
                str(executable),
            ],
            check=True,
        )
        env = os.environ.copy()
        env["HOS_NAMES_NATIVE"] = "0"
        subprocess.run([str(executable)], check=True, env=env)


if __name__ == "__main__":
    main()
