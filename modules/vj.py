'''
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



'''
import pygame
from pythonosc import udp_client
from pyo import Server, SfPlayer

pygame.init()
pygame.joystick.init()
joystick = pygame.joystick.Joystick(0)
joystick.init()

button_states = [False] * joystick.get_numbuttons()
axis_values = [0.0] * joystick.get_numaxes()

while True:
    pygame.event.pump()
    for i in range(joystick.get_numbuttons()):
        button_states[i] = joystick.get_button(i)
    for i in range(joystick.get_numaxes()):
        axis_values[i] = joystick.get_axis(i)
    
    # Example logic: count pressed buttons
    pressed_buttons = sum(button_states)
    # Use pressed_buttons, axis_values, stems playing etc. to calculate OSC messages

client = udp_client.SimpleUDPClient("127.0.0.1", 8000)

# Example: map axis to color
client.send_message("/visual/red", axis_values[0])
client.send_message("/visual/green", axis_values[1])


s = Server().boot()
s.start()

stems = {
    "kick": SfPlayer("stems/kick.wav", loop=True),
    "snare": SfPlayer("stems/snare.wav", loop=True),
    "loop1": SfPlayer("stems/loop1.wav", loop=True)
}

playing_stems = set()

def trigger_stem(name):
    if name not in playing_stems:
        stems[name].out()
        playing_stems.add(name)
    else:
        stems[name].stop()
        playing_stems.remove(name)

def update_state(buttons, axes):
    # Example: if button 0 pressed, trigger "kick"
    if buttons[0]:
        trigger_stem("kick")
    
    # Axis mapping: change visual brightness
    visual_brightness = (axes[1] + 1) / 2  # normalize -1 → 1 to 0 → 1
    return visual_brightness
