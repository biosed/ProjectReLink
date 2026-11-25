/* (relink) NVIDIA DLSS's camera math, as plain functions: the jitter's sequence (host/rx_backend.c, in C) and the motion
   vectors' reprojection (gpu/vk/vk_dlss.cpp). No Vulkan, no NGX: tests/test_dlss_math.cpp checks them. */
#pragma once

#ifdef __cplusplus
#include <cmath>
#include <limits>
#include <utility>
#endif

/* The radical inverse of index in base: the Halton sequence's index-th value, in [0, 1) */
static inline float dlss_halton(int index, int base) {
    float f = 1.0f, r = 0.0f;
    for (int i = index; i > 0; i /= base) {
        f /= (float)base;
        r += f * (float)(i % base);
    }
    return r;
}

/* The frame's sub-pixel jitter, in pixels, each in [-0.5, 0.5): the Halton (2, 3) sequence over `phases` frames (from 1: its
   first value, 0, would put every phase's start on the pixel's corner) */
static inline void dlss_jitter_pixels(unsigned frame, int phases, float out[2]) {
    const int i = (int)(frame % (unsigned)(phases > 0 ? phases : 1)) + 1;
    out[0] = dlss_halton(i, 2) - 0.5f;
    out[1] = dlss_halton(i, 3) - 0.5f;
}

/* The frame's jitter for a projection matrix p (row major, as the game fills its views' uniform buffers: nx2/oot_jitter.py),
   in clip space (what p[0][2] and p[1][2] get) into out, for a scene of w x h pixels; 0 (none) when p is not one of the
   picture's: not perspective (its w row is not 0 0 -1 0: a shadow map's, the HUD's) or not of 16:9 or the window's ratio
   wide (0: 16:9 only), or when there is no scene size (DLSS not drawing) */
static inline int dlss_jitter_clip(const float p[16], float wide, unsigned frame, int phases, float w, float h, float out[2]) {
    if (!(w >= 1.0f) || !(h >= 1.0f)) return 0;
    if (p[12] != 0.0f || p[13] != 0.0f || p[14] != -1.0f || p[15] != 0.0f || !(p[0] > 0.0f)) return 0;
    const float r = p[5] / p[0], d = r - 16.0f / 9.0f, e = wide > 0.0f ? r - wide : 1.0f;
    if (!((d <= 0.01f && d >= -0.01f) || (e <= 0.01f && e >= -0.01f))) return 0;
    float px[2];
    dlss_jitter_pixels(frame, phases, px);
    out[0] = 2.0f * px[0] / w, out[1] = 2.0f * px[1] / h;
    return 1;
}

/* How many frames the jitter's sequence takes: NVIDIA's guide, 8 times the share of pixels DLSS fills in, (output / render)
   squared, so each output pixel is covered about 8 times; 8 at least (DLAA), 64 at most (a long sequence is seen less of
   before the camera moves) */
static inline int dlss_jitter_phases(unsigned render_w, unsigned render_h, unsigned out_w, unsigned out_h) {
    if (!render_w || !render_h) return 8;
    const double area = (double)out_w * (double)out_h / ((double)render_w * (double)render_h);
    const int n = (int)(8.0 * area + 0.5);
    return n < 8 ? 8 : n > 64 ? 64 : n;
}

#ifdef __cplusplus
namespace mkwvk::dlss_math {

struct CameraProjection {
    float near_z = 0.0f;
    float far_z = 0.0f;
    float fov_y = 0.0f;
    bool infinite = false;
};

/// The camera values represented by the perspective projection's y scale and z row. The game's projection maps an
/// OpenGL -1..1 clip depth to the depth buffer's 0..1 range; FSR takes the equivalent non-inverted 0..1 camera values.
/// An infinite non-inverted projection must use max-float as its far plane, which is part of FSR's dispatch contract.
inline bool camera_projection(float p11, float a, float b, CameraProjection& out) {
    if (!(p11 > 0.0f) || !std::isfinite(p11)) return false;
    const float near_z = b / (a - 1.0f);
    const bool infinite = std::fabs(a + 1.0f) < 1e-6f;
    const float far_z = infinite ? std::numeric_limits<float>::max() : b / (a + 1.0f);
    const float fov_y = 2.0f * std::atan(1.0f / p11);
    if (!std::isfinite(near_z) || !(near_z > 0.0f) || !std::isfinite(far_z) || !(far_z > near_z) ||
        !std::isfinite(fov_y) || !(fov_y > 0.0f))
        return false;
    out = {near_z, far_z, fov_y, infinite};
    return true;
}

/// This frame's clip space to the frame before's: previous * inverse(current), both row major (clip = M * position); false
/// when current is singular or the result is not finite
inline bool reprojection(const float* current, const float* previous, float out[16]) {
    double a[4][8];
    for (int r = 0; r < 4; r++)
        for (int c = 0; c < 8; c++) a[r][c] = c < 4 ? current[r * 4 + c] : (c - 4 == r ? 1.0 : 0.0);
    for (int c = 0; c < 4; c++) {   // (Gauss-Jordan with partial pivoting)
        int p = c;
        for (int r = c + 1; r < 4; r++)
            if (std::fabs(a[r][c]) > std::fabs(a[p][c])) p = r;
        if (std::fabs(a[p][c]) < 1e-12) return false;
        if (p != c)
            for (int k = 0; k < 8; k++) std::swap(a[p][k], a[c][k]);
        const double inv = 1.0 / a[c][c];
        for (int k = 0; k < 8; k++) a[c][k] *= inv;
        for (int r = 0; r < 4; r++) {
            if (r == c || a[r][c] == 0.0) continue;
            const double f = a[r][c];
            for (int k = 0; k < 8; k++) a[r][k] -= f * a[c][k];
        }
    }
    for (int r = 0; r < 4; r++)
        for (int c = 0; c < 4; c++) {
            double v = 0;
            for (int k = 0; k < 4; k++) v += previous[r * 4 + k] * a[k][c + 4];
            if (!std::isfinite(v)) return false;
            out[r * 4 + c] = (float)v;
        }
    return true;
}

/// (relink, 0.7.9.3) A camera cut, from the reprojection (this frame's clip space to the frame before's): the middle of the
/// picture, far away (three depths from the far hundredth of the depth range to its end), was off the picture in the frame
/// before, or behind its camera. Turning the camera as fast as the stick allows moves those points a few hundredths of the
/// picture a frame, and walking or riding does not move something that far at all; a cut in a cutscene, a door or a warp
/// puts them somewhere else altogether. The upscaler's history is of another view then, and has to be dropped: kept, it
/// is blended into the new view for several frames (ghosts of the scene before)
inline bool camera_cut(const float reproject[16]) {
    const float depths[3] = {0.99f, 0.999f, 1.0f};
    for (const float z : depths) {
        const float x = reproject[2] * z + reproject[3], y = reproject[6] * z + reproject[7];
        const float w = reproject[14] * z + reproject[15];
        if (!(w > 1e-6f)) return true;
        if (!(std::fabs(x) <= w && std::fabs(y) <= w)) return true;
    }
    return false;
}

/// A view-projection's jitter taken off (row major): a jitter moves clip x and y by jitter * w, so jitter times the w row
/// comes off the first two rows
inline void unjitter(float m[16], const float jitter[2]) {
    for (int c = 0; c < 4; c++) {
        m[0 * 4 + c] -= jitter[0] * m[3 * 4 + c];
        m[1 * 4 + c] -= jitter[1] * m[3 * 4 + c];
    }
}

/// A jitter in clip space as DLSS takes it: in render pixels, x right and y down (clip y is up)
inline void jitter_to_pixels(const float clip[2], unsigned width, unsigned height, float out[2]) {
    out[0] = clip[0] * 0.5f * (float)width;
    out[1] = -clip[1] * 0.5f * (float)height;
}

/// a * b, row major 4 x 4 (clip = M * position: a after b)
inline void mul4(const float* a, const float* b, float out[16]) {
    float t[16];
    for (int r = 0; r < 4; r++)
        for (int c = 0; c < 4; c++) {
            double v = 0;
            for (int k = 0; k < 4; k++) v += (double)a[r * 4 + k] * b[k * 4 + c];
            t[r * 4 + c] = (float)v;
        }
    for (int i = 0; i < 16; i++) out[i] = t[i];
}
/// The inverse of m (row major); false when it is singular
inline bool invert4(const float* m, float out[16]) {
    static const float id[16] = {1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1};
    return reprojection(m, id, out);   // (identity * inverse(m))
}

/// (relink, 0.7.9.3) The camera as NVIDIA DLSS Frame Generation takes it (vk_dlss.cpp dlssg_generate): its matrices from the
/// game's view-projections and projection, all without the jitter, and in Vulkan's clip space, where the depth the frame
/// generator reads lives. The game's clip space is OpenGL's (y up, depth -1 to 1); the hardware's is y down, depth 0 to 1:
/// vulkan = C * game with C = (x, -y, (z + w) / 2, w). Out in NGX's layout: float[4][4] "row-major, assuming
/// post-multiplication" (a row vector times the matrix: the transpose of ours) unless `ours` (RX_VK_DLSSG_MATRIX=plain, in case
/// a tester shows the other reading is NGX's). The camera's place and axes in the world: view = inverse(projection) * view-projection
struct FgCamera {
    float view_to_clip[16], clip_to_view[16], clip_to_prev[16], prev_to_clip[16];
    float pos[3], up[3], right[3], fwd[3];
};
inline bool fg_camera(const float* vp, const float* vp_before, const float* proj, bool ours, FgCamera* f) {
    static const float C[16] = {1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 0.5f, 0.5f, 0, 0, 0, 1};
    static const float Ci[16] = {1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 2, -1, 0, 0, 0, 1};
    float r[16], ri[16], t[16], pi[16], view[16], vi[16];
    if (!reprojection(vp, vp_before, r) || !invert4(r, ri) || !invert4(proj, pi)) return false;
    mul4(pi, vp, view);   // (world to the camera's view)
    if (!invert4(view, vi)) return false;
    const auto out = [&](const float* m, float* dst) {
        for (int i = 0; i < 4; i++)
            for (int j = 0; j < 4; j++) dst[i * 4 + j] = ours ? m[i * 4 + j] : m[j * 4 + i];
    };
    mul4(C, r, t), mul4(t, Ci, t), out(t, f->clip_to_prev);
    mul4(C, ri, t), mul4(t, Ci, t), out(t, f->prev_to_clip);
    mul4(C, proj, t), out(t, f->view_to_clip);
    mul4(pi, Ci, t), out(t, f->clip_to_view);
    // (the camera's place: where view space's origin is in the world; its axes: the view's rows, OpenGL's camera looking
    // down its -z)
    const float w = vi[15];
    if (!(std::fabs(w) > 1e-12f)) return false;
    for (int i = 0; i < 3; i++) f->pos[i] = vi[i * 4 + 3] / w;
    const auto unit = [](const float* row, float s, float* dst) {
        const float n = std::sqrt(row[0] * row[0] + row[1] * row[1] + row[2] * row[2]);
        for (int i = 0; i < 3; i++) dst[i] = n > 0 ? s * row[i] / n : 0.0f;
    };
    unit(view + 0, 1.0f, f->right), unit(view + 4, 1.0f, f->up), unit(view + 8, -1.0f, f->fwd);
    for (const float* a : {f->clip_to_prev, f->prev_to_clip, f->view_to_clip, f->clip_to_view})
        for (int i = 0; i < 16; i++)
            if (!std::isfinite(a[i])) return false;
    return true;
}

} // namespace mkwvk::dlss_math
#endif
