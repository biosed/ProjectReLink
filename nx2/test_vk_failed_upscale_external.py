"""Keep external upscalers ahead of the failed-network RGB9E5 fallback.

Run with: python3 -I -B nx2/test_vk_failed_upscale_external.py
"""

from pathlib import Path


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
    source = (ROOT / "gpu" / "vk" / "vk_draw.cpp").read_text(encoding="utf-8")
    stub = function(source, "bool upscale_stub(")

    external = "dlss_upscale(cmd, key, gameplay_network(key), src, input_view, dst, output_view, 0)"
    fallback = 'typed_upscale(cmd, input_view, output_view, dst, 0, key, "generic RGB9E5 fallback", false)'
    assert stub.count(external) == 1
    assert stub.count(fallback) == 1
    assert stub.index(external) < stub.index(fallback)
    assert "dlss_wanted()" in stub
    assert "texture_written(dst);" in stub

    print("vk_failed_upscale_external: ok")


if __name__ == "__main__":
    main()
