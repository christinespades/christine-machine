# Context Menu Tip
Each script has a corresponding .bat file.
This makes it easier to quickly process files via the OS context menu.
Press Win + R → type shell:sendto
Create shortcuts to the .bat.
Right-click file → Send to → choose the .bat.

## aud_fx.py ABOUT
effect processing
reverb, chorus, flanger, etc

## aud_fx.py TODO

## aud_proc.py ABOUT
easy, quick and handy stuff for processing/finalizing audio
ensuring a desired frequency distribution, dynamic range, LUFS, normalization, stereo image, etc.
batch processing

## aud_proc.py TODO

## aud_synth.py ABOUT
synthesis, sines, noise, FM, etc

## aud_synth.py TODO

## gui.py ABOUT
gui for the engine, basic tkinter?
fancy gothic text
3d gradients for nice background, buttons, titlebar, etc
console window + main gui + dropdowns

## gui.py TODO

## img.py ABOUT
image generation, batch processing, editing, compositing, upscaling, etc.

## img.py TODO
parts of this needs to be lifted out and moved into the gui.py module

## img_comp.py ABOUT
simple image compression and resizing.

## img_comp.py TODO

## vid.py ABOUT
for everything video processing. mp4, mov, avi, etc.. decode, encode, upscale, compress, etc..
just some ffmpeg, mp4 compression for now

## vid.py TODO

## viz.py ABOUT
- takes an audio file, outputs a visualizer with the audio
- randomized seed, can recreate if you --seed
- change res and fps, render preview

## viz.py TODO
add more variation, its all white and green mostly now
more variables, more complexity
smaller scale randomness, noise particles, blobs
refactor to improve performance, see what we can do
add a second stage, where we run through the video again and add more layers of different stuff, but still tied to the same seed

## vj.py ABOUT
audiovisual module
used for live performances/vjing
prerendered stems as wav files
prerendered visualizations
inputdevice + python code + OSC + touchdesigner
currently input support for gamepad only
planned to add motion sensors, maybe light detector, etc..
so e.g. the X button is tied to distortion, or noise, or bass, or a specific thing
so during performance you would coordinate your body with the given buttons
e.g. you want attention on the bass of the track synced with some kinda cool body movement
at the same time you want the visuals to do a specific thing

how to:
run .py
open touchdesigner project
pick a track folder (e.g. album/track)
all wavs are populated and detected etc (from album/track/stems)
video nodes are populated (from album/track/viz)
then you just hit play and start performing, and triggering inputs
when done, repeat
or maybe we make the touchdesigner project set up the whole set at the beginning, and not before each track, somehow?

automatic tempo detection
populate a list of floats based on the tempo
these floats are randomly chosen from whenever input is triggered
the floats are then used to jump/change cue point in a given wav file
thus we get randomized jumps, but they remain in sync with the beat

## vj.py TODO