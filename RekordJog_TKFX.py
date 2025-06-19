import os
import mido
import math
from functions.check_config import check_config
from functions.rekordjog_start_sequence import rekordjog_start_sequence


# The JOG_MULTIPLIER is required for smooth jog operation. 
# Pioneer controllers seem to be sending MIDI signal at a much higher rate than XONE:4D. 
# If you send one fake Pioneer message for each Xone jog message, scratching sounds unnatural.
# You need to test different values for other controllers.
JOG_MULTIPLIER = 1

CONV_J_VAL = {
    65:65,   #0
    63:63,
    }

tempo_values = [
    [63, 63],
    [63, 63],
    [63, 63],
    [63, 63],
]

JOG_CODES = {
    (0xB0, 0x05):0,
    (0xB0, 0x25):1,
    (0xB0, 0x45):2,
    (0xB0, 0x65):3,
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


def jog(midi_out, msg):
    deck_id = JOG_CODES[tuple(msg.bytes()[:2])]
    v = CONV_J_VAL[msg.bytes()[2]]

    ms = mido.Message.from_bytes([176+deck_id, 0x22, v])

    for _ in range(JOG_MULTIPLIER):
        midi_out.send(ms)
        # TODO
        print(ms)

def tempo(midi_out, deck_id):
    msb = mido.Message.from_bytes([0xB0+deck_id, 0x00, tempo_values[deck_id][0]])
    lsb = mido.Message.from_bytes([0xB0+deck_id, 0x20, tempo_values[deck_id][1]])
    midi_out.send(msb)
    midi_out.send(lsb)

def main():
    midi_inp, midi_out = check_config()
    try:
        midi_inp_conf, midi_out_conf = check_config()
        midi_inp = mido.open_input(midi_inp_conf)
        if os.name == 'nt':
            midi_out = mido.open_output(midi_out_conf)
        else:
            midi_out = mido.open_output("RekordJog", True)
        
        rekordjog_start_sequence()
        while True:
                ims = midi_inp.receive()
                ims_2b = tuple(ims.bytes()[:2])

                if ims_2b in JOG_CODES:
                    jog(midi_out, ims)

                elif ims_2b in TEMPO_BIG_CODES:
                    deck_id = math.floor(TEMPO_BIG_CODES[ims_2b] / 2)
                    tempo_values[deck_id][0] = 127 - ims.bytes()[2]
                    tempo(midi_out, deck_id)

    except KeyboardInterrupt:
        print("\nClosing RekordJog, bye.")

if __name__ == "__main__":
    main()
