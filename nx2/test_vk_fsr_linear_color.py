"""Verify v0.7.9.4 FSR linear-colour, pre-SMAA, reactive-mask, and pre-HUD sharpening contracts.

Run with: python3 -I -B nx2/test_vk_fsr_linear_color.py
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
    dlss = (ROOT / "gpu" / "vk" / "vk_dlss.cpp").read_text(encoding="utf-8")
    upscale = function(dlss, "bool dlss_upscale(")
    out_pass = function(dlss, "void out_pass(")
    assert 'env_switch("RX_VK_FSR_LINEAR")' in upscale
    assert "const bool fsr_linear = fsr && !fsr4_used && fsr_linear_env > 0 && !hdr_path;" in upscale
    assert "(fsr_linear ? 8 : 0)" in upscale
    assert "(from_composite ? 16 : 0)" in upscale
    assert "(hdr_path ? 32 : 0)" in upscale
    assert "if (use_mask) f.reactive =" in upscale
    assert "f.perceptual = !linear && !fsr_linear && !hdr_path;" in upscale
    assert "out_pass(cmd, s, picture, !native, out_view, ow, oh, fsr_linear);" in upscale
    assert "int32_t linear;" in out_pass and "linear ? 1 : 0" in out_pass

    prep = (ROOT / "gpu" / "vk" / "shaders" / "dlss_prep.comp").read_text(encoding="utf-8")
    output = (ROOT / "gpu" / "vk" / "shaders" / "dlss_out.comp").read_text(encoding="utf-8")
    assert "if ((pc.flags & 16) != 0) c = sqrt(c);" in prep
    assert "if ((pc.flags & 8) != 0) c *= c;" in prep
    assert "if ((pc.flags & 32) != 0)" in prep or "(pc.flags & 32) != 0" in prep
    assert "int linear;" in output
    assert "pc.linear != 0 ? sqrt(max(c, vec3(0.0)))" in output
    assert "c *= c;" in output

    fsr = (ROOT / "gpu" / "vk" / "vk_fsr.cpp").read_text(encoding="utf-8")
    dispatch = function(fsr, "uint32_t fsr_dispatch(")
    assert "if (f.reactive.image) d.reactive = resource(f.reactive, FFX_API_RESOURCE_STATE_COMPUTE_READ);" in dispatch
    assert "d.enableSharpening = false;" in dispatch
    assert "d.flags = f.perceptual ? FFX_UPSCALE_FLAG_NON_LINEAR_COLOR_SRGB : 0u;" in dispatch

    # Pre-HUD sharpening in dlss_out.comp suppresses the post-HUD sharpening pass in framegen_scale.
    framegen = (ROOT / "gpu" / "vk" / "vk_framegen.cpp").read_text(encoding="utf-8")
    scale = function(framegen, "VkImage framegen_scale(")
    assert "const int sharpness = upscaler_sharpens() ? 0 : opts.sharpness;" in scale

    # Pre-SMAA composite (linear) -> sqrt (perceptual) -> linear (when fsr_linear) -> dlss_out -> linear output.
    for sample in (0.0, 0.1, 0.5, 0.9, 1.0):
        # composite is linear s^2; prep bit 4 gives s, bit 3 gives s^2
        after_prep = (sample * sample) ** 0.5
        after_prep_fsr_lin = after_prep * after_prep
        assert abs(after_prep_fsr_lin - sample * sample) < 1e-12
        after_out = (after_prep_fsr_lin ** 0.5) ** 2
        assert abs(after_out - sample * sample) < 1e-12

    print("vk_fsr_linear_color: v0.7.9.4 FSR linear, pre-SMAA, reactive, and pre-HUD sharpen contracts ok")


if __name__ == "__main__":
    main()
