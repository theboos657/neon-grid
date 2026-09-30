"""GLSL sources.  All shaders target GLSL 1.50 (OpenGL 3.2), which every
Windows GPU from the last decade supports through Panda3D's GL renderer."""

from panda3d.core import Shader

# ---------------------------------------------------------------------------
# Shared snippets
# ---------------------------------------------------------------------------
_HUE = """
vec3 hueRotate(vec3 c, float a) {
    // rotate hue in YIQ space; a in radians
    const mat3 toYIQ = mat3(0.299, 0.596, 0.211, 0.587, -0.274, -0.523, 0.114, -0.322, 0.312);
    const mat3 toRGB = mat3(1.0, 1.0, 1.0, 0.956, -0.272, -1.106, 0.621, -0.647, 1.703);
    vec3 yiq = toYIQ * c;
    float h = atan(yiq.z, yiq.y) + a;
    float ch = length(yiq.yz);
    return max(toRGB * vec3(yiq.x, ch * cos(h), ch * sin(h)), 0.0);
}
"""

_LIGHTS = """
uniform vec4 u_lightPos[8];   // xyz position, w radius
uniform vec4 u_lightCol[8];   // rgb colour * intensity
uniform int u_numLights;
uniform vec3 u_camPos;
uniform vec3 u_ambient;
uniform vec4 u_fog;           // rgb, density
uniform float u_mirror;       // 1 when rendered through the floor reflection
uniform vec4 u_sunDir;        // xyz towards the sun (outdoor maps), w unused
uniform vec3 u_sunCol;        // black indoors

vec3 shade(vec3 P, vec3 N, vec3 base, float gloss, float specAmt) {
    vec3 V = normalize(u_camPos - P);
    vec3 acc = u_ambient * base;
    vec3 sd = u_sunDir.xyz;
    if (u_mirror > 0.5) sd.z = -sd.z;
    acc += u_sunCol * base * max(dot(N, sd), 0.0);
    for (int i = 0; i < 8; ++i) {
        if (i >= u_numLights) break;
        vec3 lp = u_lightPos[i].xyz;
        if (u_mirror > 0.5) lp.z = -lp.z;
        vec3 Ld = lp - P;
        float d = length(Ld);
        float r = u_lightPos[i].w;
        if (d > r) continue;
        vec3 L = Ld / d;
        float att = 1.0 - d / r;
        att *= att;
        float ndl = max(dot(N, L), 0.0);
        vec3 H = normalize(L + V);
        float spec = pow(max(dot(N, H), 0.0), gloss) * specAmt;
        acc += u_lightCol[i].rgb * att * (base * ndl + spec);
    }
    return acc;
}

vec3 applyFog(vec3 c, vec3 P) {
    float d = length(u_camPos - P);
    float f = 1.0 - exp(-pow(d * u_fog.a, 2.0));
    return mix(c, u_fog.rgb, clamp(f, 0.0, 1.0));
}
"""

# ---------------------------------------------------------------------------
# World (lit + emissive) shader
# ---------------------------------------------------------------------------
WORLD_VERT = """
#version 150
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec4 p3d_Color;
in vec2 p3d_MultiTexCoord0;
out vec3 v_wpos;
out vec3 v_wnrm;
out vec4 v_col;
out vec2 v_uv;
void main() {
    vec4 w = p3d_ModelMatrix * p3d_Vertex;
    v_wpos = w.xyz;
    v_wnrm = normalize(mat3(p3d_ModelMatrix) * p3d_Normal);
    v_col = p3d_Color;
    v_uv = p3d_MultiTexCoord0;
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
}
"""

WORLD_FRAG = """
#version 150
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
uniform vec4 u_mat;         // x gloss, y spec, z rim, w emission
uniform float u_hue;        // global neon hue shift (radians)
uniform float u_neonGain;   // global neon intensity
uniform float u_time;
""" + _LIGHTS + _HUE + """
in vec3 v_wpos;
in vec3 v_wnrm;
in vec4 v_col;
in vec2 v_uv;
out vec4 fragColor;
void main() {
    vec4 tex = texture(p3d_Texture0, v_uv);
    vec4 base = tex * v_col * p3d_ColorScale;
    vec3 N = normalize(v_wnrm);
    if (!gl_FrontFacing) N = -N;
    vec3 col = shade(v_wpos, N, base.rgb, u_mat.x, u_mat.y);
    // cyan rim light keeps silhouettes readable against black walls
    vec3 V = normalize(u_camPos - v_wpos);
    float rim = pow(1.0 - max(dot(N, V), 0.0), 3.0) * u_mat.z;
    col += hueRotate(vec3(0.0, 0.55, 0.65), u_hue) * rim * u_neonGain;
    // emissive part (neon strips, screens, glowing bits)
    col += hueRotate(base.rgb, u_hue) * u_mat.w * u_neonGain;
    col = applyFog(col, v_wpos);
    if (u_mirror > 0.5) col *= 0.55;
    fragColor = vec4(col, base.a);
}
"""

# ---------------------------------------------------------------------------
# Wet reflective floor.  Drawn semi-transparent on top of the mirrored world.
# Texture channels: r = wetness/puddles, g = grid lines, b = grime noise.
# ---------------------------------------------------------------------------
FLOOR_FRAG = """
#version 150
uniform sampler2D p3d_Texture0;
uniform float u_hue;
uniform float u_neonGain;
uniform float u_time;
uniform float u_reflect;     // 0 when reflections are disabled (low quality)
""" + _LIGHTS + _HUE + """
in vec3 v_wpos;
in vec3 v_wnrm;
in vec4 v_col;
in vec2 v_uv;
out vec4 fragColor;
void main() {
    vec4 t = texture(p3d_Texture0, v_uv);
    float wet = smoothstep(0.35, 0.75, t.r);
    vec3 base = mix(vec3(0.028, 0.032, 0.038), vec3(0.012, 0.014, 0.018), wet) * (0.8 + 0.4 * t.b);
    vec3 N = vec3(0.0, 0.0, 1.0);
    float gloss = mix(40.0, 400.0, wet);
    float spec = mix(0.6, 3.5, wet);
    vec3 col = shade(v_wpos, N, base, gloss, spec);
    // faint emissive grid, pulsing slowly
    float pulse = 0.75 + 0.25 * sin(u_time * 0.8 + v_wpos.x * 0.05 + v_wpos.y * 0.05);
    col += hueRotate(vec3(0.0, 0.8, 1.0), u_hue) * t.g * 0.55 * pulse * u_neonGain * (1.0 - wet * 0.6);
    col = applyFog(col, v_wpos);
    vec3 V = normalize(u_camPos - v_wpos);
    float fres = pow(1.0 - max(V.z, 0.0), 2.0);
    float alpha = mix(0.93, 0.42, wet);
    alpha = mix(alpha, alpha * 0.55, fres);
    alpha = mix(1.0, alpha, u_reflect);
    fragColor = vec4(col, alpha);
}
"""

# ---------------------------------------------------------------------------
# Additive / alpha FX meshes (beams, light cones, rings, holograms)
#   mode 0 beam: gaussian across u      mode 1 cone: soft edges, fade along v
#   mode 2 ring: gaussian across v      mode 3 textured hologram (scanlines)
#   mode 4 flat colour                  mode 5 soft radial disc (u,v centred)
# ---------------------------------------------------------------------------
FX_VERT = """
#version 150
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec4 p3d_Color;
in vec2 p3d_MultiTexCoord0;
out vec4 v_col;
out vec2 v_uv;
out vec3 v_wpos;
void main() {
    v_col = p3d_Color;
    v_uv = p3d_MultiTexCoord0;
    v_wpos = (p3d_ModelMatrix * p3d_Vertex).xyz;
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
}
"""

FX_FRAG = """
#version 150
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
uniform int u_fxMode;
uniform float u_time;
uniform float u_hue;
uniform float u_neonGain;
uniform float u_hueLock;     // 1 = ignore global hue shift (warnings stay red)
uniform float u_mirror;
""" + _HUE + """
in vec4 v_col;
in vec2 v_uv;
in vec3 v_wpos;
out vec4 fragColor;
void main() {
    vec4 c = v_col * p3d_ColorScale;
    float a = 1.0;
    if (u_fxMode == 0) {
        float x = (v_uv.x - 0.5) * 2.0;
        a = exp(-x * x * 5.0) + exp(-x * x * 60.0) * 1.5;
    } else if (u_fxMode == 1) {
        float x = (v_uv.x - 0.5) * 2.0;
        a = (1.0 - x * x) * pow(1.0 - v_uv.y, 1.6) * 0.8;
        a *= 0.85 + 0.15 * sin(u_time * 1.3 + v_wpos.x);
    } else if (u_fxMode == 2) {
        float y = (v_uv.y - 0.5) * 2.0;
        a = exp(-y * y * 6.0);
    } else if (u_fxMode == 3) {
        vec4 t = texture(p3d_Texture0, v_uv);
        float scan = 0.7 + 0.3 * sin(v_wpos.z * 60.0 - u_time * 6.0);
        float flick = 0.9 + 0.1 * sin(u_time * 37.0) * sin(u_time * 13.0);
        a = t.a * scan * flick;
    } else if (u_fxMode == 5) {
        vec2 d = (v_uv - 0.5) * 2.0;
        float r = length(d);
        a = exp(-r * r * 4.0);
    }
    vec3 rgb = c.rgb;
    if (u_hueLock < 0.5) rgb = hueRotate(rgb, u_hue) * u_neonGain;
    if (u_mirror > 0.5) { rgb *= 0.4; }
    fragColor = vec4(rgb * a * c.a, a * c.a);
}
"""

# ---------------------------------------------------------------------------
# GPU point-sprite particles
# ---------------------------------------------------------------------------
PARTICLE_VERT = """
#version 150
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ProjectionMatrix;
uniform float u_screenH;
in vec4 p3d_Vertex;
in vec4 p3d_Color;
in float size;
out vec4 v_col;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    float ps = size * u_screenH * p3d_ProjectionMatrix[1][1] * 0.5 / max(gl_Position.w, 0.05);
    gl_PointSize = clamp(ps, 0.0, 256.0);
    v_col = p3d_Color;
    if (size <= 0.0) gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
}
"""

PARTICLE_FRAG = """
#version 150
uniform int u_blendMode;   // 0 additive, 1 alpha, 2 hard square (debris)
uniform float u_mirror;
in vec4 v_col;
out vec4 fragColor;
void main() {
    vec2 d = gl_PointCoord - vec2(0.5);
    float r = length(d) * 2.0;
    float a;
    if (u_blendMode == 2) a = step(max(abs(d.x), abs(d.y)), 0.35);
    else a = pow(clamp(1.0 - r, 0.0, 1.0), 1.6);
    if (a <= 0.003) discard;
    if (u_mirror > 0.5) a *= 0.4;
    if (u_blendMode == 1) fragColor = vec4(v_col.rgb, v_col.a * a);
    else fragColor = vec4(v_col.rgb * v_col.a * a, 1.0);
}
"""

# ---------------------------------------------------------------------------
# Post-processing (bloom)
# ---------------------------------------------------------------------------
QUAD_VERT = """
#version 150
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
out vec2 uv;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uv = p3d_Vertex.xz * 0.5 + 0.5;
}
"""

BRIGHT_FRAG = """
#version 150
uniform sampler2D src;
uniform float u_threshold;
in vec2 uv;
out vec4 o;
void main() {
    vec2 px = 1.0 / vec2(textureSize(src, 0));
    vec3 c = texture(src, uv + px * vec2(-0.5, -0.5)).rgb + texture(src, uv + px * vec2(0.5, -0.5)).rgb
           + texture(src, uv + px * vec2(-0.5, 0.5)).rgb + texture(src, uv + px * vec2(0.5, 0.5)).rgb;
    c *= 0.25;
    float l = max(max(c.r, c.g), c.b);
    float k = clamp((l - u_threshold) / max(l, 1e-4), 0.0, 1.0);
    o = vec4(min(c * k, vec3(12.0)), 1.0);
}
"""

BLUR_FRAG = """
#version 150
uniform sampler2D src;
uniform vec2 u_dir;
in vec2 uv;
out vec4 o;
void main() {
    vec2 px = u_dir / vec2(textureSize(src, 0));
    vec3 c = texture(src, uv).rgb * 0.227027;
    c += texture(src, uv + px * 1.3846153846).rgb * 0.3162162162;
    c += texture(src, uv - px * 1.3846153846).rgb * 0.3162162162;
    c += texture(src, uv + px * 3.2307692308).rgb * 0.0702702703;
    c += texture(src, uv - px * 3.2307692308).rgb * 0.0702702703;
    o = vec4(c, 1.0);
}
"""

COMPOSITE_FRAG = """
#version 150
uniform sampler2D scene;
uniform sampler2D bloom1;
uniform sampler2D bloom2;
uniform float u_bloom;
uniform float u_exposure;
in vec2 uv;
out vec4 o;
vec3 aces(vec3 x) {
    return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
}
float lum(vec3 c) {
    c = c / (1.0 + c);                  // compress HDR before edge detection
    return dot(c, vec3(0.299, 0.587, 0.114));
}
vec3 fxaa(vec2 p) {
    // FXAA-lite: cheap edge-directed anti-aliasing (no MSAA needed)
    vec2 px = 1.0 / vec2(textureSize(scene, 0));
    vec3 rgbM = texture(scene, p).rgb;
    float lNW = lum(texture(scene, p + vec2(-1.0, -1.0) * px).rgb);
    float lNE = lum(texture(scene, p + vec2(1.0, -1.0) * px).rgb);
    float lSW = lum(texture(scene, p + vec2(-1.0, 1.0) * px).rgb);
    float lSE = lum(texture(scene, p + vec2(1.0, 1.0) * px).rgb);
    float lM = lum(rgbM);
    float lMin = min(lM, min(min(lNW, lNE), min(lSW, lSE)));
    float lMax = max(lM, max(max(lNW, lNE), max(lSW, lSE)));
    if (lMax - lMin < max(0.03, lMax * 0.12)) return rgbM;
    vec2 dir = vec2(-((lNW + lNE) - (lSW + lSE)), (lNW + lSW) - (lNE + lSE));
    float reduce = max((lNW + lNE + lSW + lSE) * 0.03125, 1.0 / 128.0);
    float rcp = 1.0 / (min(abs(dir.x), abs(dir.y)) + reduce);
    dir = clamp(dir * rcp, vec2(-8.0), vec2(8.0)) * px;
    vec3 a = 0.5 * (texture(scene, p + dir * (1.0 / 3.0 - 0.5)).rgb +
                    texture(scene, p + dir * (2.0 / 3.0 - 0.5)).rgb);
    vec3 b = a * 0.5 + 0.25 * (texture(scene, p - dir * 0.5).rgb + texture(scene, p + dir * 0.5).rgb);
    float lb = lum(b);
    return (lb < lMin || lb > lMax) ? a : b;
}
void main() {
    vec3 c = fxaa(uv);
    vec3 b = texture(bloom1, uv).rgb * 0.9 + texture(bloom2, uv).rgb * 1.2;
    c += b * u_bloom;
    c = aces(c * u_exposure);
    vec2 d = uv - 0.5;
    c *= 1.0 - dot(d, d) * 0.55;       // gentle vignette
    o = vec4(pow(c, vec3(1.0 / 1.1)), 1.0);
}
"""


# ---------------------------------------------------------------------------
# Scope lens: shows the scope camera's HDR render on the weapon's rear lens.
#   u_reticle 0 = sniper cross with mil ticks, 1 = combat chevron + red dot
# ---------------------------------------------------------------------------
SCOPE_LENS_FRAG = """
#version 150
uniform sampler2D scopeTex;
uniform float u_scopeActive;
uniform int u_reticle;
uniform float u_time;
in vec4 v_col;
in vec2 v_uv;
in vec3 v_wpos;
out vec4 fragColor;
void main() {
    vec2 d0 = v_uv - 0.5;
    float r0 = length(d0) * 2.0;
    if (r0 > 1.0) discard;
    // outer 18% is a round metal eyepiece ring around the glass
    if (r0 > 0.82) {
        float edge = smoothstep(0.84, 0.82, r0) + smoothstep(0.97, 1.0, r0) * 0.5;
        vec3 metal = vec3(0.04, 0.045, 0.05) * (0.7 + 0.3 * d0.y);
        metal += vec3(0.1, 0.8, 1.0) * smoothstep(0.02, 0.0, abs(r0 - 0.9)) * 0.6;
        fragColor = vec4(metal + vec3(0.0) * edge, 1.0);
        return;
    }
    vec2 uv = 0.5 + d0 / 0.82;
    vec2 d = uv - 0.5;
    float r = length(d) * 2.0;
    vec3 c;
    if (u_scopeActive > 0.5) {
        c = texture(scopeTex, uv).rgb;
        // lens vignette + dark eye-relief ring
        c *= smoothstep(1.0, 0.72, r);
        float px = 0.0035;
        float ret = 0.0;
        if (u_reticle == 0) {
            // thick outer posts, thin centre cross, mil ticks
            bool thick = (abs(d.x) < px * 2.2 && abs(d.y) > 0.16) || (abs(d.y) < px * 2.2 && abs(d.x) > 0.16);
            bool thin = (abs(d.x) < px * 0.6 && abs(d.y) < 0.16) || (abs(d.y) < px * 0.6 && abs(d.x) < 0.16);
            bool tick = (abs(d.y) < 0.012 && abs(mod(d.x + 0.0001, 0.04)) < px * 0.8 && abs(d.x) < 0.16)
                     || (abs(d.x) < 0.012 && abs(mod(d.y + 0.0001, 0.04)) < px * 0.8 && abs(d.y) < 0.16);
            if (thick || thin || tick) ret = 1.0;
            c = mix(c, vec3(0.0), ret * 0.95);
            float dot_ = smoothstep(0.009, 0.005, length(d));
            c = mix(c, vec3(4.0, 0.3, 0.2), dot_);
        } else {
            // chevron + illuminated dot
            vec2 q = d - vec2(0.0, -0.01);
            bool chev = (q.y < 0.0 && q.y > -0.07 && abs(abs(q.x) + q.y) < px * 1.4);
            bool stem = abs(d.x) < px * 0.7 && d.y < -0.09 && d.y > -0.35;
            if (chev) c = mix(c, vec3(4.0, 0.4, 0.25), 0.95);
            if (stem) c = mix(c, vec3(0.0), 0.9);
            float dot_ = smoothstep(0.008, 0.004, length(d));
            c = mix(c, vec3(4.0, 0.4, 0.25), dot_);
        }
    } else {
        // idle glass: dark tinted lens with a moving sheen
        float sheen = smoothstep(0.08, 0.0, abs(d.x + d.y * 0.6 - 0.25 + 0.05 * sin(u_time)));
        c = vec3(0.01, 0.03, 0.05) + vec3(0.2, 0.6, 0.8) * sheen * 0.6;
        c += vec3(0.05, 0.25, 0.35) * pow(r, 6.0);
    }
    // thin black rim
    c *= smoothstep(1.0, 0.96, r);
    fragColor = vec4(c, 1.0);
}
"""


_cache = {}


def get(name):
    """Return a compiled Shader object by name (cached)."""
    if name in _cache:
        return _cache[name]
    table = {
        "world": (WORLD_VERT, WORLD_FRAG),
        "floor": (WORLD_VERT, FLOOR_FRAG),
        "fx": (FX_VERT, FX_FRAG),
        "particle": (PARTICLE_VERT, PARTICLE_FRAG),
        "bright": (QUAD_VERT, BRIGHT_FRAG),
        "blur": (QUAD_VERT, BLUR_FRAG),
        "composite": (QUAD_VERT, COMPOSITE_FRAG),
        "scopelens": (FX_VERT, SCOPE_LENS_FRAG),
    }
    v, f = table[name]
    sh = Shader.make(Shader.SL_GLSL, vertex=v, fragment=f)
    _cache[name] = sh
    return sh
