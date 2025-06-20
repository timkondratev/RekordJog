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


class PitchRider:
    """
    It is assumed that tempo range is set to WIDE in Rekordbox.
    WIDE range goes +-100%.

    Rekordbox accepts hi-res fader values as MSB and LSB.
    In case WIDE range is selected:
        When msb==0 and lsb==0 the tempo is 0%.
        When msb==0x7f and lsb==0x7f the tempo is 200%.


    TEXT DUMP:
    0x2000 is 8192 in decimal. That's ~ half of 16383 which is max 14 bit value.

    """

    def __init__(self):

        # SETTINGS
        self.should_reverse_tempo_fader = False

        # RESOURCES
        self.tempos_roster = [0.06, 0.1, 0.16, 1.0] # For ranges 6%, 10%, 16%, and WIDE (100%) the values are 0.06, 0.1, 0.16, and 1.0 accordingly.

        # INTERNAL STATE      
        self.tempo_range = 0.1 # Tempo range that the user controls.
        self.tempo = 1.0 # Tempo is represented as float for convenience.
        self.pitch_amount = 0.0 # 0.0 for the neutral, -1.0 for the slowest, 1.0 for the fastest tempo.
        self.nudge_amount = 0.0 # Increases or decreases when the jog is rotating.

        # MIDI VALUES
        self.tempo_fader_msb = 0 # Physical tempo fader MSB.
        self.tempo_fader_lsb = 0 # Physical tempo fader LSB.
        # tempo_fader_lsb can be represented by a separate fader to achieve hi-res pitch bend.




    def select_next_tempo_range(self):
        """
        Iterate over TEMPOS_ROSTER
        """
        i = self.tempos_roster.index(self.tempo_range)
        # 3 in this case is the last index in TEMPOS_ROSTER.
        self.tempo_range = self.tempos_roster[i + 1] if i < 3 else self.tempos_roster[0]

    def process_jog(self):
        pass

    def tempo_transformation(self):
        """
        Apply pitch first, nudge second.
        """

        self.tempo = (1.0 + (self.pitch_amount * self.tempo_range)) * (1.0 + self.nudge_amount)






def tempo_to_msb_lsb(tempo):
    pass




def jog(midi_out, msg):
    deck_id = JOG_CODES[tuple(msg.bytes()[:2])]
    v = msg.bytes()[2]

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
