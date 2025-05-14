import os
import mido
import math
from functions.check_config import check_config
from functions.rekordjog_start_sequence import rekordjog_start_sequence
import threading
import time


# The JOG_MULTIPLIER is required for smooth jog operation. 
# Pioneer controllers seem to be sending MIDI signal at a much higher rate than XONE:4D. 
# If you send one fake Pioneer message for each Xone jog message, scratching sounds unnatural.
# You need to test different values for other controllers.
JOG_MULTIPLIER = 1

CONV_J_VAL = {
    # Clockwise (CW) rotation: 1 -> 25
    1: 65,   # Low speed
    2: 66,
    3: 67,
    4: 68,
    5: 69,
    6: 70,
    7: 71,
    8: 72,
    9: 73,
    10: 74,
    11: 75,
    12: 76,
    13: 77,
    14: 78,
    15: 79,
    16: 80,
    17: 81,
    18: 82,
    19: 83,
    20: 84,
    21: 85,
    22: 86,
    23: 87,
    24: 88,
    25: 89,  # High speed

    # Counter-clockwise (CCW) rotation: 127 -> 98
    127: 63,  # Low speed
    126: 62,
    125: 61,
    124: 60,
    123: 59,
    122: 58,
    121: 57,
    120: 56,
    119: 55,
    118: 54,
    117: 53,
    116: 52,
    115: 51,
    114: 50,
    113: 49,
    112: 48,
    111: 47,
    110: 46,
    109: 45,
    108: 44,
    107: 43,
    106: 42,
    105: 41,
    104: 40,
    103: 39,
    102: 38,
    101: 37,
    100: 36,
    99: 35,
    98: 34   # High speed
}

tempo_values = [
    [63, 63],
    [63, 63],
    [63, 63],
    [63, 63],
]

JOG_CODES = {
    (0xB2, 0x11): 1,  
    (0xB1, 0x11): 0,
}

TOUCH_ON_CODES = {
    (0x92, 0x0C): 1,  
    (0x91, 0x0C): 0,  
}

TOUCH_OFF_CODES = {
    (0x92, 0x0C): 1,  
    (0x91, 0x0C): 0, 
}


TEMPO_BIG_CODES = {
    (0xbf, 0x11):0,
    (0xbe, 0x11):1,
    (0xbf, 0x1f):2,
    (0xbe, 0x1f):3,
    (0xbf, 0x13):4,
    (0xbe, 0x13):5,
    (0xbf, 0x1d):6,
    (0xbe, 0x1d):7,
}


TEMPO_SMALL_CODES = {
    (0xbf, 0x10):0,
    (0xbe, 0x10):1,
    (0xbf, 0x1e):2,
    (0xbe, 0x1e):3,
    (0xbf, 0x12):4,
    (0xbe, 0x12):5,
    (0xbf, 0x1c):6,
    (0xbe, 0x1c):7,
}
def map_jog_value(midi_value):
    if 1 <= midi_value <= 25:  # CW
        return 65 + (midi_value - 1)
    elif 98 <= midi_value <= 127:  # CCW
        return 63 - (127 - midi_value)
    else:
        return 64  # Neutral

def jog(midi_out, msg):
    id = JOG_CODES[tuple(msg.bytes()[:2])]
    jog_value = msg.bytes()[2]
    v = map_jog_value(jog_value)
    ms = mido.Message.from_bytes([176 + id, 0x22, v])

    for i in range(JOG_MULTIPLIER):
        midi_out.send(ms)


def tempo(midi_out, id):
    msb = mido.Message.from_bytes([0xB0+id, 0x00, tempo_values[id][0]])
    lsb = mido.Message.from_bytes([0xB0+id, 0x20, tempo_values[id][1]])
    midi_out.send(msb)
    midi_out.send(lsb)
current_values = [0, 0, 0, 0]
def vuMeter(midi_out, midi_inp):
    msg = midi_out.receive()
    if msg.type == 'control_change' and msg.control == 2 and msg.channel == 0:
        if current_values[2] != msg.value:
            smooth_transition(midi_inp, 0, 2, current_values, msg.value)
    elif msg.type == 'control_change' and msg.control == 2 and msg.channel == 1:
        if current_values[3] != msg.value:
            smooth_transition(midi_inp, 0, 3, current_values, msg.value)

def smooth_transition(midi_inp, channel, control, current_values, target_value, step=1, delay=0.001):
    current_value = current_values[control] 
    if current_value < target_value:
        for value in range(current_value, target_value + 1, step):
            midi_inp.send(mido.Message('control_change', channel=channel, control=control, value=value))
            current_values[control] = value
            time.sleep(delay)
    elif current_value > target_value:
        for value in range(current_value, target_value - 1, -step):
            midi_inp.send(mido.Message('control_change', channel=channel, control=control, value=value))
            current_values[control] = value
            time.sleep(delay)

def jogWheel(midi_out, midi_inp):
    ims = midi_inp.receive()
    ims_2b = tuple(ims.bytes()[:2])
    if ims_2b in JOG_CODES:
        jog(midi_out, ims)

    elif ims_2b in TOUCH_ON_CODES and ims.type == 'note_on' and ims.velocity == 127:
        deck_id = TOUCH_ON_CODES[ims_2b]
        touch = mido.Message.from_bytes([0x90 + deck_id, 0x36, 0x7F])
        midi_out.send(touch)

    elif ims_2b in TOUCH_ON_CODES and ims.type == 'note_on' and ims.velocity == 0:
        deck_id = TOUCH_ON_CODES[ims_2b]
        release = mido.Message.from_bytes([0x90 + deck_id, 0x36, 0x00])
        midi_out.send(release)

    elif ims_2b in TEMPO_BIG_CODES:
        deck_id = math.floor(TEMPO_BIG_CODES[ims_2b] / 2)
        tempo_values[deck_id][0] = 127 - ims.bytes()[2]
        tempo(midi_out, deck_id)

    elif ims_2b in TEMPO_SMALL_CODES:
        deck_id = math.floor(TEMPO_SMALL_CODES[ims_2b] / 2)
        tempo_values[deck_id][1] =  127 - ims.bytes()[2]
        tempo(midi_out, deck_id)
def main():
    midi_inp, midi_out = check_config()
    try:
        midi_inp_conf, midi_out_conf = check_config()
        midi_inp = mido.open_ioport(midi_inp_conf)
        if os.name == 'nt':
            midi_out = mido.open_ioport(midi_out_conf)
        else:
            midi_out = mido.open_ioport("Pioneer DDJ-SX", True)
        
        rekordjog_start_sequence()
        max_jog_value = 127
        while True:
            t1 = threading.Thread(target=vuMeter, args=(midi_out, midi_inp))
            t2 = threading.Thread(target=jogWheel, args=(midi_out, midi_inp))
            t1.start()
            t2.start()  

    except KeyboardInterrupt:
        t1.join()
        t2.join()
        print("\nClosing RekordJog, bye.")

if __name__ == "__main__":
    main()
