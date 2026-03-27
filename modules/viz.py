import argparse
import os
import signal
import sys
import random
import numpy as np
import librosa
import cv2
import moderngl
from scipy.interpolate import interp1d

# ====================== GRACEFUL CTRL+C ======================
output_path = None

def signal_handler(sig, frame):
    print("\n\n🛑 Interrupted. Cleaning up...")
    global output_path
    if output_path and os.path.exists(output_path):
        try:
            os.remove(output_path)
            print(f"   Deleted incomplete: {output_path}")
        except:
            pass
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# ====================== CLI ======================
parser = argparse.ArgumentParser(description="GLSL-powered trippy gothic music visualizer")
parser.add_argument("audio_path", type=str, help="Path to audio file")
parser.add_argument("--resolution", "-r", type=str, default="320x180",
                    help="Resolution (default 320x180 for fast previews)")
parser.add_argument("--seed", "-s", type=int, default=None,
                    help="Random seed for reproducibility")
parser.add_argument("--fps", type=int, default=15, help="FPS (default 15)")
parser.add_argument("--full", action="store_true",
                    help="Render the full track instead of first 5 seconds")
args = parser.parse_args()

audio_path = os.path.abspath(args.audio_path)
if not os.path.exists(audio_path):
    print(f"❌ File not found: {audio_path}")
    sys.exit(1)

audio_dir = os.path.dirname(audio_path)
base_name = os.path.splitext(os.path.basename(audio_path))[0]

if args.seed is None:
    seed = random.randint(0, 2**32 - 1)
    print(f"🌱 Random seed: {seed}")
else:
    seed = args.seed
    print(f"🌱 Using seed: {seed}")

np.random.seed(seed)
random.seed(seed)

try:
    w_str, h_str = args.resolution.split("x")
    width, height = int(w_str), int(h_str)
except:
    print("❌ Invalid resolution. Use WIDTHxHEIGHT")
    sys.exit(1)

print(f"🎨 Rendering {width}x{height} @ {args.fps} fps (GLSL GPU shader)")

# ====================== AUDIO ANALYSIS ======================
print("🔬 Analyzing audio...")
y, sr = librosa.load(audio_path, sr=None, mono=False)
if y.ndim == 1:
    y = np.stack([y, y], axis=0)

full_duration = librosa.get_duration(y=y[0], sr=sr)
y_mono = librosa.to_mono(y)

duration = 5.0 if not args.full else full_duration
print(f"   Rendering {'FULL track' if args.full else 'first 5 seconds'}")

hop_length = 512
n_fft = 2048
rms = librosa.feature.rms(y=y_mono, hop_length=hop_length)[0]
times = librosa.times_like(rms, sr=sr, hop_length=hop_length)
stft = librosa.stft(y_mono, n_fft=n_fft, hop_length=hop_length)
freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
bass_energy = np.sqrt(np.sum(np.abs(stft[freqs < 300])**2, axis=0))
treble_energy = np.sqrt(np.sum(np.abs(stft[freqs > 3000])**2, axis=0))
rms_left = librosa.feature.rms(y=y[0], hop_length=hop_length)[0]
rms_right = librosa.feature.rms(y=y[1], hop_length=hop_length)[0]
onset_env = librosa.onset.onset_strength(y=y_mono, sr=sr, hop_length=hop_length)
tempo, _ = librosa.beat.beat_track(y=y_mono, sr=sr)
tempo = float(tempo[0]) if hasattr(tempo, '__len__') and len(tempo) > 0 else float(tempo)
beat_period = 60.0 / tempo if tempo > 0 else 2.0
print(f"   BPM ≈ {tempo:.1f} | Duration: {duration:.2f}s")

rms_interp = interp1d(times, rms, kind="linear", bounds_error=False, fill_value=0)
bass_interp = interp1d(times, bass_energy, kind="linear", bounds_error=False, fill_value=0)
treble_interp = interp1d(times, treble_energy, kind="linear", bounds_error=False, fill_value=0)
left_interp = interp1d(times, rms_left, kind="linear", bounds_error=False, fill_value=0)
right_interp = interp1d(times, rms_right, kind="linear", bounds_error=False, fill_value=0)
onset_interp = interp1d(times, onset_env, kind="linear", bounds_error=False, fill_value=0)

max_rms = np.max(rms) or 1
max_bass = np.max(bass_energy) or 1
max_treble = np.max(treble_energy) or 1
max_left = np.max(rms_left) or 1
max_right = np.max(rms_right) or 1
max_onset = np.max(onset_env) or 1

# ====================== SEED-LOCKED STYLE ======================
np.random.seed(seed)
cloud_mult     = 0.75 + np.random.rand() * 1.15
line_mult      = 0.85 + np.random.rand() * 1.35
fractal_mult   = 0.60 + np.random.rand() * 1.40
scan_mult      = 0.07 + np.random.rand() * 0.19
vignette_mult  = 3.60 + np.random.rand() * 2.40
chromatic_mult = 1.80 + np.random.rand() * 2.20
print(f"   Style locked by seed {seed} (clouds×{cloud_mult:.2f}, fractal×{fractal_mult:.2f})")

# ====================== OUTPUT PATHS ======================
output_path = os.path.join(audio_dir, f"{base_name}_{seed}.mp4")
temp_raw = os.path.join(audio_dir, f"{base_name}_{seed}_raw.avi")

# ====================== MODERNGL GLSL ======================
ctx = moderngl.create_standalone_context()
print("   GPU context created")

vertex_shader = """
#version 330
in vec2 in_vert;
void main() {
    gl_Position = vec4(in_vert, 0.0, 1.0);
}
"""

fragment_shader = """
#version 330
uniform float time;
uniform vec2 resolution;
uniform float bass;
uniform float treble;
uniform float onset;
uniform float left;
uniform float right;
uniform float cloud_mult;
uniform float line_mult;
uniform float fractal_mult;
uniform float scan_mult;
uniform float vignette_mult;
uniform float chromatic_mult;

out vec4 fragColor;

float hash(vec2 p) {
    p = fract(p * vec2(0.3183099, 0.3678794));
    p = p * p * (3.0 - 2.0 * p);
    return fract(p.x * p.y * (p.x + p.y));
}

float fbm(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    for (int i = 0; i < 6; i++) {
        value += amplitude * hash(p);
        p *= 2.02;
        amplitude *= 0.5;
    }
    return value;
}

float sdCircle(vec2 p, vec2 center, float r) {
    return length(p - center) - r;
}

void main() {
    vec2 p = (gl_FragCoord.xy - resolution.xy * 0.5) / resolution.y;

    float t = time * 0.85;
    float b = bass * 1.8;
    float tr = treble * 1.5;
    float on = onset * 2.5;

    // Deep gothic base
    vec3 col = vec3(0.07, 0.03, 0.11);

    // Clouds
    vec2 cloud_uv = p * 3.5 + vec2(t * 0.12, t * 0.09) * cloud_mult;
    float clouds = fbm(cloud_uv * 1.8) * cloud_mult;
    col = mix(col, vec3(0.45, 0.12, 0.65), clouds * tr * 0.85);
    col = mix(col, vec3(0.85, 0.25, 0.95), clouds * b * 0.45);

    vec2 center = vec2(0.0, 0.0);

    // Fractal web
    float angle = t * 0.65 + on * 0.9;
    float web = 0.0;
    float scale = 1.0;
    for (int i = 0; i < 7; i++) {
        vec2 q = p * scale;
        float a = atan(q.y, q.x) + angle * (1.0 + float(i) * 0.32) * fractal_mult;
        q = vec2(cos(a), sin(a)) * length(q);
        web += 0.16 / (abs(length(q) - 0.38 - b * 0.45) + 0.025);
        scale *= 0.64;
        angle += 0.85;
    }
    col = mix(col, vec3(0.95, 0.45, 1.0), web * line_mult * 0.75);

    // Rotating geometric lines
    float lines = 0.0;
    for (int i = 0; i < 14; i++) {
        float a = float(i) * 3.14159 * 2.0 / 14.0 + t * 0.95 * line_mult;
        vec2 dir = vec2(cos(a), sin(a));
        float d = abs(dot(p - center, vec2(-dir.y, dir.x)));
        lines += 0.009 / (d + 0.018);
    }
    col = mix(col, vec3(0.65, 0.95, 1.0), lines * (1.0 + b * 1.3));

    // Stereo orbs
    float orbL = sdCircle(p, vec2(-0.45, 0.0), 0.13 + left * 0.28 + b * 0.12);
    float orbR = sdCircle(p, vec2( 0.45, 0.0), 0.13 + right * 0.28 + b * 0.12);
    col = mix(col, vec3(1.0, 0.45, 0.15), 1.0 - smoothstep(0.0, 0.035, orbL));
    col = mix(col, vec3(0.15, 1.0, 0.55), 1.0 - smoothstep(0.0, 0.035, orbR));

    // Chromatic aberration on strong bass
    if (b > 0.65) {
        float ca = chromatic_mult * b * 0.018;
        vec3 ca_col = col;
        ca_col.r = mix(ca_col.r, col.g, ca * 0.6);
        ca_col.b = mix(ca_col.b, col.r, ca * 0.7);
        col = ca_col;
    }

    // Scanlines
    float scan = 0.85 + scan_mult * sin(gl_FragCoord.y * 4.0 + t * 25.0) * 0.18;
    col *= scan;

    // Vignette
    float vig = vignette_mult * (1.0 - length(p) * 0.85);
    col *= vig * vig;

    // Final glow
    col += vec3(0.12, 0.06, 0.22) * (b + tr * 0.7);

    fragColor = vec4(col, 1.0);
}
"""

prog = ctx.program(vertex_shader=vertex_shader, fragment_shader=fragment_shader)

vertices = np.array([-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0], dtype='f4')
vbo = ctx.buffer(vertices)
vao = ctx.vertex_array(prog, [(vbo, '2f', 'in_vert')])

fbo = ctx.framebuffer(color_attachments=[ctx.texture((width, height), 3)])

# ====================== RENDER LOOP ======================
writer = cv2.VideoWriter(
    temp_raw,
    cv2.VideoWriter_fourcc(*'MJPG'),
    args.fps,
    (width, height),
    True
)

print("🎥 Rendering with GLSL shader on GPU...")

total_frames = int(duration * args.fps) + 2
for frame_idx in range(total_frames):
    t = frame_idx / args.fps
    if t > duration:
        break

    volume = rms_interp(t)
    bass = bass_interp(t)
    treble = treble_interp(t)
    left_vol = left_interp(t)
    right_vol = right_interp(t)
    onset = onset_interp(t)

    nv = volume / max_rms
    nb = bass / max_bass
    nt = treble / max_treble
    nl = left_vol / max_left
    nr = right_vol / max_right
    no = onset / max_onset

    pulse_val = 0.5 + 0.5 * np.sin(2 * np.pi * t / beat_period * 1.15)

    # Set only uniforms that exist in the shader
    prog['time'].value = t
    prog['resolution'].value = (float(width), float(height))
    prog['bass'].value = float(nb)
    prog['treble'].value = float(nt)
    prog['onset'].value = float(no)
    prog['left'].value = float(nl)
    prog['right'].value = float(nr)
    prog['cloud_mult'].value = float(cloud_mult)
    prog['line_mult'].value = float(line_mult)
    prog['fractal_mult'].value = float(fractal_mult)
    prog['scan_mult'].value = float(scan_mult)
    prog['vignette_mult'].value = float(vignette_mult)
    prog['chromatic_mult'].value = float(chromatic_mult)

    fbo.use()
    ctx.clear(0.0, 0.0, 0.0)
    vao.render(moderngl.TRIANGLE_STRIP)

    frame_bytes = fbo.read(components=3)
    frame_np = np.frombuffer(frame_bytes, dtype=np.uint8).reshape((height, width, 3))
    frame_bgr = cv2.cvtColor(frame_np, cv2.COLOR_RGB2BGR)

    writer.write(frame_bgr)

    if frame_idx % max(1, args.fps * 8) == 0:
        print(f"   {int(t)}s / {duration:.1f}s")

writer.release()

# ====================== FINAL ENCODE ======================
print("🔊 Finalizing with GPU HEVC encoding...")
cmd = (
    f'ffmpeg -y -loglevel error -i "{temp_raw}" -i "{audio_path}" '
    f'-c:v hevc_nvenc -preset fast -crf 17 -b:v {"4000k" if width*height > 1000000 else "1500k"} '
    f'-c:a aac -b:a 192k -pix_fmt yuv420p -shortest '
    f'"{output_path}"'
)
os.system(cmd)

if os.path.exists(output_path):
    os.remove(temp_raw)
    print(f"\n✅ Finished! GLSL render complete")
    print(f"   Saved: {output_path}")
    print(f"   Seed: {seed}")
    if not args.full:
        print("   Tip: Add --full for the entire track")
else:
    print("⚠️ FFmpeg failed.")
    if os.path.exists(temp_raw):
        os.rename(temp_raw, output_path.replace(".mp4", "_noaudio.avi"))