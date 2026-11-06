"""RekordJog controller scaffold for an unmapped controller (working name: Mixtrack Quad).

Nothing about the controller is known in advance: not the channel it transmits
on, not whether a jog is sent as notes or CCs, not whether jog values are
absolute speeds or +1/-1 pulses, not the tempo polarity. Only the DDJ-SX side
below comes from this repository; the controller side is filled in from
--monitor output and must be verified on the hardware.

RekordJog never talks to Rekordbox directly. It emulates a Pioneer DDJ-SX on a
virtual MIDI port (loopMIDI on Windows) and Rekordbox applies its DDJ-SX profile
to whatever arrives there. A controller script therefore has two jobs:

  1. read the messages the physical controller sends,
  2. turn the few controls Rekordbox cannot get elsewhere -- jog rotate, jog
     touch, tempo slider -- into DDJ-SX messages.

Everything else (play/cue, pads, faders, EQ) is mapped inside Rekordbox itself,
not here.

Start with discovery mode, which needs neither loopMIDI nor Rekordbox:

    .\\.venv\\Scripts\\python.exe RekordJog_MixtrackQuad.py --monitor

Move one control at a time, note the printed tuple, and paste it into the
matching table below. Then run the script without --monitor.
"""

import os
import sys

import mido

from functions.check_config import check_config
from functions.rekordjog_start_sequence import rekordjog_start_sequence

# ---------------------------------------------------------------------------
# DDJ-SX side -- what Rekordbox listens for on the emulated port.
# Taken from pioneer_mappings/PIONEER DDJ-SX.midi.csv:
#   B00A = JogScratch, 9008 = JogTouch, B070 = TempoSlider.
# The older profile (PIONEER DDJ-SX.midi.csv.old, used by
# RekordJog_Mixtrack3.py) uses 0x22 for jog and 0x36 for touch instead.
# These constants must match the profile installed in Rekordbox.
# ---------------------------------------------------------------------------
PIONEER_JOG_CC = 0x0A
PIONEER_JOG_TOUCH = 0x08
PIONEER_TEMPO_CC = 0x70

# Some controllers send jog pulses much faster than a real DDJ-SX. If a single
# scratch movement stutters or overshoots, raise this. Unverified here: the
# Mixtrack 3 script uses 1, the Xone:4D needs 15.
JOG_MULTIPLIER = 1

# Tempo polarity is also controller specific. The Mixtrack 3/Xone scripts
# invert the DDJ-SX value (127 - raw), which is the usual case for controllers
# whose fader travels opposite to the DDJ-SX one. Verify before trusting it.
INVERT_TEMPO = True

# DDJ-SX centre value for the jog wheel.
JOG_NEUTRAL = 64

# ---------------------------------------------------------------------------
# Controller side -- fill these in from the --monitor output.
#
# Keys are (status_byte, first_data_byte) exactly as printed by monitor mode.
#   0xB0 + channel = control_change   (0xB0 = deck 1, 0xB1 = deck 2, ...)
#   0x90 + channel = note_on          (0x90 = deck 1, 0x91 = deck 2, ...)
# Values are the DDJ-SX deck to send to: 0 = deck 1 ... 3 = deck 4.
#
# The shipped DDJ-SX profile only has entries for decks 1 and 2, so sending
# deck 3/4 jobs requires extending pioneer_mappings/PIONEER DDJ-SX.midi.csv.
#
# The tables are intentionally empty: no code below is guessed for your unit.
# ---------------------------------------------------------------------------
JOG_CODES = {
}

TOUCH_CODES = {
}

TEMPO_CODES = {
}

# raw controller jog value -> DDJ-SX value (65 = slow CW ... 63 = slow CCW).
# Empty until --monitor shows what the wheel actually sends. Unknown values are
# reported on stderr, never silently turned into a neutral jog.
JOG_VALUE_MAP = {
    # 1: 65,
    # 127: 63,
}

# Forward messages we do not translate? Useful while the DDJ-SX profile still
# covers the buttons you care about; set False once Rekordbox does its own
# mapping for them.
PASS_THROUGH_UNMAPPED = False

_UNKNOWN_JOG_VALUES = set()


def report_unknown_jog(raw_value):
    """Warn once per unseen jog value so a bad mapping is visible, not silent."""
    if raw_value in _UNKNOWN_JOG_VALUES:
        return
    _UNKNOWN_JOG_VALUES.add(raw_value)
    print(f"[jog] raw value {raw_value} is not in JOG_VALUE_MAP; "
          f"add it once you know the DDJ-SX value it should send.",
          file=sys.stderr)


def convert_jog(value):
    """Return the DDJ-SX value for a raw jog value, or None if unknown.

    Fill JOG_VALUE_MAP with the exact pairs you observe in --monitor. Mapping
    the observed values explicitly (like CONV_J_VAL in
    RekordJog_AllenAndHeath.py) is safer than deriving a formula, because
    "absolute speed" and "+1/-1 pulse" jogs both arrive as plain 0..127 values.
    """
    return JOG_VALUE_MAP.get(value)


def send_jog(midi_out, deck, raw_value):
    value = convert_jog(raw_value)
    if value is None:
        report_unknown_jog(raw_value)
        return

    message = mido.Message('control_change', channel=deck,
                           control=PIONEER_JOG_CC, value=value)
    for _ in range(JOG_MULTIPLIER):
        midi_out.send(message)


def send_touch(midi_out, deck, pressed):
    midi_out.send(mido.Message('note_on', channel=deck, note=PIONEER_JOG_TOUCH,
                               velocity=0x7F if pressed else 0x00))


def send_tempo(midi_out, deck, raw_value):
    value = 127 - raw_value if INVERT_TEMPO else raw_value
    midi_out.send(mido.Message('control_change', channel=deck,
                               control=PIONEER_TEMPO_CC, value=value))


def handle(msg, midi_out):
    key = tuple(msg.bytes()[:2])

    if msg.type == 'control_change':
        deck = JOG_CODES.get(key)
        if deck is not None:
            send_jog(midi_out, deck, msg.value)
            return
        deck = TEMPO_CODES.get(key)
        if deck is not None:
            send_tempo(midi_out, deck, msg.value)
            return

    if msg.type in ('note_on', 'note_off'):
        deck = TOUCH_CODES.get(key)
        if deck is not None:
            send_touch(midi_out, deck, msg.type == 'note_on' and msg.velocity > 0)
            return

    if PASS_THROUGH_UNMAPPED and msg.type in ('note_on', 'note_off', 'control_change'):
        midi_out.send(msg)


# --- discovery mode --------------------------------------------------------

REALTIME_TYPES = {'clock', 'start', 'continue', 'stop', 'active_sensing',
                  'reset', 'songpos', 'quarter_frame'}


def describe(msg):
    raw = ' '.join(f'{byte:02X}' for byte in msg.bytes())
    if msg.type in ('note_on', 'note_off'):
        return (f"{msg.type:<15} ch={msg.channel + 1} note=0x{msg.note:02X} "
                f"velocity={msg.velocity:<3} bytes=[{raw}]")
    if msg.type == 'control_change':
        return (f"{msg.type:<15} ch={msg.channel + 1} control=0x{msg.control:02X} "
                f"value={msg.value:<3} bytes=[{raw}]")
    return f"{msg.type:<15} bytes=[{raw}]"


def table_entry(msg):
    """Return a ready-to-paste dict line, or None for non-channel messages."""
    if msg.type not in ('note_on', 'note_off', 'control_change'):
        return None
    status, data = msg.bytes()[0], msg.bytes()[1]
    return f"    (0x{status:02X}, 0x{data:02X}): {msg.channel},"


def monitor(midi_inp):
    print("Listening for MIDI input -- move one control at a time.")
    print("Press Ctrl+C to stop.\n")
    try:
        for msg in midi_inp:
            if msg.type in REALTIME_TYPES:
                continue
            print(describe(msg))
            hint = table_entry(msg)
            if hint:
                print(hint + "   # <- paste into JOG_CODES / TOUCH_CODES / TEMPO_CODES")
    except KeyboardInterrupt:
        print("\nStopped monitoring.")


def warn_if_tables_empty():
    if JOG_CODES or TOUCH_CODES or TEMPO_CODES:
        return
    print("No controller codes configured yet, so nothing will be translated.")
    print("Run this script with --monitor to discover them.\n")


def main():
    monitor_only = '--monitor' in sys.argv[1:]

    midi_inp_name, midi_out_name = check_config()

    if monitor_only:
        with mido.open_input(midi_inp_name) as midi_inp:
            monitor(midi_inp)
        return

    try:
        with mido.open_input(midi_inp_name) as midi_inp:
            if os.name == 'nt':
                midi_out = mido.open_output(midi_out_name)
            else:
                midi_out = mido.open_output('Pioneer DDJ-SX', virtual=True)

            with midi_out:
                rekordjog_start_sequence()
                warn_if_tables_empty()
                for msg in midi_inp:
                    handle(msg, midi_out)
    except KeyboardInterrupt:
        print("\nClosing RekordJog, bye.")


if __name__ == "__main__":
    main()
