import os
import mido
from functions.check_config import check_config
from functions.rekordjog_start_sequence import rekordjog_start_sequence

JOG_MULTIPLIER = 1

CONV_J_VAL = {
    # Counter-Clockwise (CCW)
    46: 46, 47: 47, 48: 48, 49: 49, 50: 50,
    51: 51, 52: 52, 53: 53, 54: 54, 55: 55,
    56: 56, 57: 57, 58: 58, 59: 59, 60: 60,
    61: 61, 62: 62, 63: 63,

    # Clockwise (CW)
    65: 65, 66: 66, 67: 67, 68: 68, 69: 69,
    70: 70, 71: 71, 72: 72, 73: 73, 74: 74,
    75: 75, 76: 76, 77: 77, 78: 78, 79: 79,
    80: 80, 81: 81, 82: 82, 83: 83, 84: 84,
}

JOG_CODES = {
    (0xb1, 0x1e): 0,
    (0xb3, 0x1e): 1
}

TOUCH_ON_CODES = {
    (0x91, 0x14): 0,
    (0x93, 0x14): 1
}

TOUCH_OFF_CODES = {
    (0x91, 0x14): 0,
    (0x93, 0x14): 1
}

def map_jog_value(midi_value):
    return CONV_J_VAL.get(midi_value, 64)

def jog(midi_out, msg):
    try:
        id = JOG_CODES[tuple(msg.bytes()[:2])]
        v = map_jog_value(msg.bytes()[2])

        ms = mido.Message.from_bytes([176 + id, 0x22, v])

        for i in range(JOG_MULTIPLIER):
            midi_out.send(ms)
    except KeyError:
        pass

def main():
    midi_inp, midi_out = check_config()
    try:
        midi_inp_conf, midi_out_conf = check_config()
        midi_inp = mido.open_input(midi_inp_conf)
        if os.name == 'nt':
            midi_out = mido.open_output(midi_out_conf)
        else:
            midi_out = mido.open_output("Pioneer DDJ-SX", True)

        rekordjog_start_sequence()
        print("\nTraktor Kontrol S2 MK3 handler started.")

        while True:
            ims = midi_inp.receive()
            ims_2b = tuple(ims.bytes()[:2])

            if ims_2b in JOG_CODES:
                jog(midi_out, ims)

            elif ims_2b in TOUCH_ON_CODES:
                deck_id = TOUCH_ON_CODES[ims_2b]

                if hasattr(ims, 'type') and ims.type == 'note_on' and ims.velocity == 0:
                    release = mido.Message.from_bytes([0x90 + deck_id, 0x36, 0x00])
                    midi_out.send(release)
                else:
                    touch = mido.Message.from_bytes([0x90 + deck_id, 0x36, 0x7F])
                    midi_out.send(touch)

            elif ims_2b in TOUCH_OFF_CODES:
                deck_id = TOUCH_OFF_CODES[ims_2b]
                release = mido.Message.from_bytes([0x90 + deck_id, 0x36, 0x00])
                midi_out.send(release)

    except KeyboardInterrupt:
        print("\nClosing RekordJog, bye.")

if __name__ == "__main__":
    main()
