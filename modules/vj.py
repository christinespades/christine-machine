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
