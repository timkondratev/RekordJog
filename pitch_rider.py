import os
import math
import time
import threading
import mido
from functions.check_config import check_config
from functions.rekordjog_start_sequence import rekordjog_start_sequence

# TEMPO_BIG_CODES = {
#     (0xBF, 0x11): 0,
#     (0xBE, 0x11): 1,
#     (0xBF, 0x1F): 2,
#     (0xBE, 0x1F): 3,
#     (0xBF, 0x13): 4,
#     (0xBE, 0x13): 5,
#     (0xBF, 0x1D): 6,
#     (0xBE, 0x1D): 7,
# }


class PitchRider:
    """

    NOTES AND KNOWLEDGE BASE:

    It is assumed that tempo range is set to WIDE in Rekordbox.
    WIDE range goes +-100%.

    Rekordbox accepts hi-res fader values as MSB and LSB.
    In case WIDE range is selected:
        When msb==0 and lsb==0 the tempo is 0%.
        When msb==0x7f and lsb==0x7f the tempo is 200%.

    0x2000 is 8192 in decimal. That's ~ half of 16383 which is max 14 bit value.
    tempo_fader_lsb can be represented by a separate fader to achieve hi-res pitch bend.

    Jog send rate to achieve 100% of playback speed = 396.
    Jog send rate to achieve 200% of playback speed = 792.
    Messages per second (and per deck). Formula is: 720/(60/33)=396.
    DDJ FLX-4 sends 720 messages per revolution.
    33 is the speed of a turntable. 60 is seconds in one minute.
    The result could be multiplied by 2 to get the maximum scratching speed of 200%.
    This is the limitation of current approach since we are using WIDE tempo range to control playback.
    """

    def __init__(self, midi_inp, midi_out):
        # SETTINGS

        self.midi_inp = midi_inp
        self.midi_out = midi_out

        self.should_reverse_tempo_fader = False

        # The following only applies to certain types of jogs.
        # The other type sends messages with a capped rate and increased magnitude (data byte)
        self.jog_messages_per_revolution = 120

        # # Approximate value. TKFX tends to skip a lot of steps when turned fast.
        # self.jog_magnitude_coefficient = (
        #     # 720 is the default number of MIDI messages that DDJ FLX-4 sends per revolutin.
        #     720 / self.jog_messages_per_revolution #
        # )

        # self.delta_time = 1.0 / self.tempo_refresh_rate
        self.delta_time = 0.1

        # Applied when a track is playing so that the maximum tempo increase from nudging never exceeds +10%.
        self.nudge_coefficient = 0.1

        # RESOURCES

        self.tempo_range_options = [
            # For ranges 6%, 10%, 16%, and WIDE (100%) the values are 0.06, 0.1, 0.16, and 1.0 accordingly.
            0.06,
            0.1,
            0.16,
            1.0,
        ]

        # Below are the first two bytes of controller-specific MIDI messages for jog rotation (decks 1 to 4 are indexed as 0 to 3).
        # The third byte carries value that indicates speed and direction of rotation. Different controllers use different ways to encode this value.
        self.jog_turn_codes = {
            (0xB0, 0x05): 0,  # Deck 1.
            (0xB0, 0x25): 1,  # Deck 2.
            (0xB0, 0x45): 2,  # Deck 3.
            (0xB0, 0x65): 3,  # Deck 4.
        }
        self.jog_middle_value = 0x40
        self.jog_touch_on_codes = {
            # TODO Replace with actual values
            (0x9F, 0x26): 0,  # Deck 1.
            (0x9F, 0x46): 1,  # Deck 2.
            (0x9E, 0x26): 2,  # Deck 3.
            (0x9E, 0x46): 3,  # Deck 4.
        }
        self.jog_touch_off_codes = {
            # TODO Replace with actual values
            (0x8F, 0x26): 0,  # Deck 1.
            (0x8F, 0x46): 1,  # Deck 2.
            (0x8E, 0x26): 2,  # Deck 3.
            (0x8E, 0x46): 3,  # Deck 4.
        }

        # TODO Tempo codes

        # INTERNAL STATE

        self.tempo = [
            # Tempo is represented as float for convenience.
            1.0,
            1.0,
            1.0,
            1.0,
        ]
        self.tempo_range = [
            # Tempo range that the user controls. For each deck.
            self.tempo_range_options[1],
            self.tempo_range_options[1],
            self.tempo_range_options[1],
            self.tempo_range_options[1],
        ]

        self.pitch_amount = [
            # 0.0 for the neutral, -1.0 for the slowest, 1.0 for the fastest tempo.
            0.0,
            0.0,
            0.0,
            0.0,
        ]
        self.nudge_amount = [
            # Increases or decreases when the jog is rotating. Goes back to 0 when the rotation stops.
            # 0.0 for the neutral, -1.0 for the fasted CCW rotation, 1.0 for the fastest CW rotation.
            0.0,
            0.0,
            0.0,
            0.0,
        ]
        self.jog_touch = [
            False,
            False,
            False,
            False,
        ]

        self.nudge_msg_accumulator = [
            # Add up nudge values for each jog. Reset to 0 every tick.
            0,
            0,
            0,
            0,
        ]

        self.nudge_msg_accumulator_lock = [
            # Ensures only one thread writes to self.nudge_msg_accumulator
            threading.Lock,
            threading.Lock,
            threading.Lock,
            threading.Lock,
        ]

    def midi_input_thread(self):
        while True:
            ims = self.midi_inp.receive()
            ims_2b = tuple(ims.bytes()[:2])

            if ims_2b in self.jog_turn_codes:
                self.jog(ims)

            elif ims_2b in self.jog_touch_on_codes:
                deck_id = self.jog_touch_on_codes[ims_2b]
                self.jog_touch[deck_id] = True

            elif ims_2b in self.jog_touch_off_codes:
                deck_id = self.jog_touch_off_codes[ims_2b]
                self.jog_touch[deck_id] = False

            # TODO elif tempo codes...

    def select_next_tempo_range(self, deck_id):
        """
        Iterate over self.tempo_range_options
        """
        i = self.tempo_range_options.index(self.tempo_range[deck_id])
        # 3 in this case is the last index in self.tempo_range_options.
        self.tempo_range[deck_id] = (
            self.tempo_range_options[i + 1] if i < 3 else self.tempo_range_options[0]
        )

    def tempo_transformation(self, deck_id):
        """
        Apply pitch first, nudge second.
        """

        self.tempo[deck_id] = (
            1.0 + (self.pitch_amount[deck_id] * self.tempo_range[deck_id])
        ) * (1.0 + self.nudge_amount[deck_id] * self.nudge_coefficient)

    def jog(self, msg):
        """
        Process jog nudging.
        """
        deck_id = self.jog_turn_codes[tuple(msg.bytes()[:2])]
        v = msg.bytes()[2]  # Value from jog

        with self.nudge_msg_accumulator_lock[deck_id]:
            self.nudge_msg_accumulator[deck_id] += v

        self.nudge_amount[deck_id] += self.get_jog_value_delta(v)

    def get_jog_value_delta(self, value):
        """
        The current implementation only works for jogs with middle value of 0x40.
        """
        return self.jog_middle_value - value


def tempo(midi_out, deck_id):
    msb = mido.Message.from_bytes([0xB0 + deck_id, 0x00, tempo_values[deck_id][0]])
    lsb = mido.Message.from_bytes([0xB0 + deck_id, 0x20, tempo_values[deck_id][1]])
    midi_out.send(msb)
    midi_out.send(lsb)


def main():
    midi_inp, midi_out = check_config()
    try:
        midi_inp_conf, midi_out_conf = check_config()
        midi_inp = mido.open_input(midi_inp_conf)
        if os.name == "nt":
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
