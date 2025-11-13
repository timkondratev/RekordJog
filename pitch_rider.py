import os
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

        # The following only applies to certain types of jogs.
        # The other type sends messages with a capped rate and increased magnitude (data byte).
        self.jog_messages_per_revolution = 120
        self.messages_per_second = self.jog_messages_per_revolution / (60 / 33)

        self.tick_delta_time = 0.1
        self.nudge_coefficient = (
            self.tick_delta_time * self.messages_per_second
        )  # The coefficient used in nudge_amount calculation.

        # Applied when nudging a track (instead of scratching).
        self.nudge_reducer_coefficient = 0.02


        self.tempo_range_options = [
            # For ranges 6%, 10%, 16%, and WIDE (100%) the values are 0.06, 0.1, 0.16, and 1.0 accordingly.
            0.06,
            0.1,
            0.16,
            1.0,
        ]


        # EXTERNAL RESOURCES

        # From actual controller
        self.deck_play_pause_codes_orig = {
            (0xB0, 0x07): 0,  # Deck 1.
            (0xB0, 0x27): 1,  # Deck 2.
            (0xB0, 0x47): 2,  # Deck 3.
            (0xB0, 0x67): 3,  # Deck 4.
        }

        # Below are the first two bytes of controller-specific MIDI messages for jog rotation (decks 1 to 4 are indexed as 0 to 3).
        # The third byte carries value that indicates speed and direction of rotation. Different controllers use different ways to encode this value.
        self.jog_turn_codes_orig = {
            (0xB0, 0x05): 0,  # Deck 1.
            (0xB0, 0x25): 1,  # Deck 2.
            (0xB0, 0x45): 2,  # Deck 3.
            (0xB0, 0x65): 3,  # Deck 4.
        }
        self.jog_middle_value_orig = 0x40
        self.jog_touch_codes_orig = {
            (0xB0, 0x06): 0,  # Deck 1.
            (0xB0, 0x26): 1,  # Deck 2.
            (0xB0, 0x46): 2,  # Deck 3.
            (0xB0, 0x66): 3,  # Deck 4.
        }

        # TODO Tempo codes

        # INTERNAL STATE
        self.running = True

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

        self.deck_play_button = [
            False,
            False,
            False,
            False,
        ]

        # Ensures play is activated for scratching when track is actually paused
        self.scratch_play_toggle = [
            False,
            False,
            False,
            False,
        ]

        self.jog_touch = [
            False,
            False,
            False,
            False,
        ]

        self.last_reverse_flick = [
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
            threading.Lock(),
            threading.Lock(),
            threading.Lock(),
            threading.Lock(),
        ]

    def run(self):
        input_thread = threading.Thread(target=self.midi_input_thread)
        tick_thread = threading.Thread(target=self.tick_thread)

        input_thread.start()
        tick_thread.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping...")
            self.running = False
            input_thread.join()
            tick_thread.join()

    def midi_input_thread(self):
        for ims in self.midi_inp:
            ims_2b = tuple(ims.bytes()[:2])

            if ims_2b in self.jog_turn_codes_orig:
                self.process_jog(ims)

            elif ims_2b in self.jog_touch_codes_orig:
                deck_id = self.jog_touch_codes_orig[ims_2b]
                self.jog_touch[deck_id] = True if ims.bytes()[2] == 127 else False
                print(f" Jog id {deck_id} is touched: {self.jog_touch[deck_id]}")

            elif ims_2b in self.deck_play_pause_codes_orig:
                deck_id = self.deck_play_pause_codes_orig[ims_2b]
                self.send_play_pause(deck_id)

            if not self.running:
                break

            # TODO elif tempo codes...

    def tick_thread(self):
        """
        Calculate self.nudge_amount for each deck and send a MIDI message.
        """

        while self.running:
            for deck_id, msg_sum in enumerate(self.nudge_msg_accumulator):
                self.nudge_amount[deck_id] = msg_sum / self.nudge_coefficient

                # print(f"Nudge acc: {self.nudge_msg_accumulator[deck_id]}")
                # print(f"Nudge amount: {self.nudge_amount[deck_id]}")
                self.nudge_msg_accumulator[deck_id] = 0

            old_tempo = self.tempo.copy()

            for deck_id in range(4):
                self.tempo_transformation(deck_id)

                # HANDLE PLAY/PAUSE ON JOG TOUCH
                if (self.jog_touch[deck_id] 
                    and not self.deck_play_button[deck_id] 
                    and not self.scratch_play_toggle[deck_id]
                    ):
                    self.send_play_pause(deck_id)
                    self.scratch_play_toggle[deck_id] = True

                elif not self.jog_touch[deck_id] and self.scratch_play_toggle[deck_id]:
                    self.send_play_pause(deck_id)
                    self.scratch_play_toggle[deck_id] = False


                # HANDLE SCRATCHING
                if self.tempo[deck_id] < 0 and not self.last_reverse_flick[deck_id]:
                    self.send_reverse_flick(deck_id)

                elif self.tempo[deck_id] >= 0 and self.last_reverse_flick[deck_id]:
                    self.send_reverse_flick(deck_id)
                ####################

                    

                if not self.tempo[deck_id] == old_tempo[deck_id]:
                    print(f"Nudge amt: {self.nudge_amount[deck_id]}")
                    self.send_tempo_msg(deck_id)

            time.sleep(self.tick_delta_time)

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

        if not self.jog_touch[deck_id]:
            self.tempo[deck_id] = (
                1.0 + (self.pitch_amount[deck_id] * self.tempo_range[deck_id])
            ) * (1.0 + self.nudge_amount[deck_id] * self.nudge_reducer_coefficient)
        else:
            self.tempo[deck_id] = self.nudge_amount[deck_id]

    def send_play_pause(self, deck_id):
        play_msg = mido.Message.from_bytes([0x80 + deck_id, 0x00,  0x7F])
        self.midi_out.send(play_msg)
        self.deck_play_button[deck_id] = not self.deck_play_button[deck_id]
        print(f" Deck id {deck_id} is playing: {self.deck_play_button[deck_id]}")


    def send_reverse_flick(self, deck_id):
        """
        Send Reverse message in case of scratching
        """
        rev_msg = mido.Message.from_bytes([0x90 + deck_id, 0x00,  0x7F])
        self.midi_out.send(rev_msg)
        self.last_reverse_flick[deck_id] = not self.last_reverse_flick[deck_id]
        print(f"REVERSE DECK {deck_id}: {self.last_reverse_flick[deck_id]}")


    def send_tempo_msg(self, deck_id):
        """
        Transform inner tempo float value into a midi message and send it out.
        """

        print(f"Tempos: {self.tempo}\n")

        tempo_norm = max(0.0, min(2.0, abs(self.tempo[deck_id]))) / 2.0  # 0.0..1.0
        tempo_14_bit = int(tempo_norm * 16383 + 0.5)  # yields 0..16383

        msb = (tempo_14_bit >> 7) & 0x7F  # 0..127
        lsb = tempo_14_bit & 0x7F  # 0..127
        # print(f"MSB: {msb}\n")
        # print(f"LSB: {lsb}\n")

        # TODO Remove hard-coded midi message values
        msb_msg = mido.Message.from_bytes([0xB0 + deck_id, 0x00, msb])
        lsb_msg = mido.Message.from_bytes([0xB0 + deck_id, 0x20, lsb])
        self.midi_out.send(msb_msg)
        self.midi_out.send(lsb_msg)

    def process_jog(self, msg):
        """
        Process jog nudging. Works for every jog.
        """
        deck_id = self.jog_turn_codes_orig[tuple(msg.bytes()[:2])]
        v = msg.bytes()[2]  # Value from jog

        with self.nudge_msg_accumulator_lock[deck_id]:
            self.nudge_msg_accumulator[deck_id] -= self.get_jog_value_delta(v)
            # print(f"MIDI message value: {self.get_jog_value_delta(v)}")

    def get_jog_value_delta(self, value):
        """
        The current implementation only works for jogs with middle value of 0x40.
        """
        return self.jog_middle_value_orig - value


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

        pitch_rider = PitchRider(midi_inp=midi_inp, midi_out=midi_out)
        pitch_rider.run()

        # while True:
        #     ims = midi_inp.receive()
        #     ims_2b = tuple(ims.bytes()[:2])

        #     if ims_2b in JOG_CODES:
        #         jog(midi_out, ims)

        #     elif ims_2b in TEMPO_BIG_CODES:
        #         deck_id = math.floor(TEMPO_BIG_CODES[ims_2b] / 2)
        #         tempo_values[deck_id][0] = 127 - ims.bytes()[2]
        #         tempo(midi_out, deck_id)

    except KeyboardInterrupt:
        print("\nClosing RekordJog, bye.")


if __name__ == "__main__":
    main()
