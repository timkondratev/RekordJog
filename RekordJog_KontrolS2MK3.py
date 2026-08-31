import os
import mido
from functions.check_config import check_config
from functions.rekordjog_start_sequence import rekordjog_start_sequence


# =============================================================================
# RekordJog for Native Instruments Traktor Kontrol S2 MK3
# =============================================================================
# MIDI Mode: Hold LEFT FLX button while connecting USB cable.
#            Pads flash green to confirm MIDI mode is active.
#
# S2 MK3 MIDI channel scheme:
#   Ch1  (0x91/0xB1) = Deck A (left)        → DDJ-SX ch0
#   Ch3  (0x93/0xB3) = Deck B (right)       → DDJ-SX ch1
#   Ch2  (0x92/0xB2) = Deck A + Shift       → DDJ-SX ch0 (shift variants)
#   Ch4  (0x94/0xB4) = Deck B + Shift       → DDJ-SX ch1 (shift variants)
#   Ch5  (0x95/0xB5) = Left mixer channel
#   Ch6  (0x96/0xB6) = Right mixer channel
#   Ch7  (0x97/0xB7) = Global mixer
#
# DDJ-SX pad channel scheme:
#   Deck A pads → ch7 (0x97), Deck B pads → ch8 (0x98)
# =============================================================================

# Amplify jog sensitivity. S2 sends values centered at 64 (range ~56-70).
# Factor of 3 maps ±6 to ±18 for DDJ-SX. Increase for more aggressive scratch.
JOG_AMPLIFY = 3

# How many DDJ-SX jog messages per S2 jog message. Start with 1.
JOG_MULTIPLIER = 1


# ---------------------------------------------------------------------------
# Jogwheel rotation  (S2: CC 0x1E on Ch1/Ch3, relative, center=64)
# ---------------------------------------------------------------------------
JOG_CODES = {
    (0xB1, 0x1E): 0,  # Deck A (left)
    (0xB3, 0x1E): 1,  # Deck B (right)
}

# ---------------------------------------------------------------------------
# Jogwheel touch  (S2: Note 0x14, vel 127=on / 0=off, Ch1/Ch3)
# ---------------------------------------------------------------------------
TOUCH_CODES = {
    (0x91, 0x14): 0,  # Deck A
    (0x93, 0x14): 1,  # Deck B
}

# ---------------------------------------------------------------------------
# Tempo/Pitch fader  (S2: CC 0x2A on Ch1/Ch3, absolute 0-127)
# DDJ-SX: 14-bit via CC 0x00 (MSB) + CC 0x20 (LSB)
# ---------------------------------------------------------------------------
TEMPO_CODES = {
    (0xB1, 0x2A): 0,  # Deck A
    (0xB3, 0x2A): 1,  # Deck B
}

# ---------------------------------------------------------------------------
# Per-deck buttons  (S2: Note on Ch1=Deck A, Ch3=Deck B)
# Maps S2_note → DDJ_note, sent on DDJ deck channel (ch0=A, ch1=B)
# Verified via learn_buttons.py capture.
# ---------------------------------------------------------------------------
DECK_BUTTON_MAP = {
    # Transport
    0x01: 0x0B,  # Play/Pause          → DDJ PlayPause
    0x02: 0x0C,  # Cue                 → DDJ Cue
    0x10: 0x58,  # Sync                → DDJ Sync
    0x15: 0x15,  # Reverse/Slip        → DDJ SlipReverse/Censor
    0x0F: 0x1A,  # KeyLock/Master      → DDJ MasterTempo/KeyLock
    # Loop encoder press (touch 0x28 is in IGNORED_NOTES)
    0x1C: 0x14,  # Loop Encoder press  → DDJ AutoLoop
    # Pad mode buttons (above pads)
    0x0B: 0x1B,  # HotCues             → DDJ HotCueMode
    0x0C: 0x22,  # Samples             → DDJ SamplerMode
    # FLX
    0x16: 0x1E,  # FLX                 → DDJ PadFx1Mode
    # Grid
    0x0D: 0x0A,  # Grid                → DDJ GridSlide
}

# ---------------------------------------------------------------------------
# Shift-layer buttons  (S2: same notes but on Ch2=A+Shift, Ch4=B+Shift)
# Maps S2_note → DDJ shift-variant note, sent on DDJ deck channel
# ---------------------------------------------------------------------------
SHIFT_BUTTON_MAP = {
    0x01: 0x47,  # Shift+Play          → DDJ PlayPause+Shift
    0x02: 0x48,  # Shift+Cue           → DDJ JumpToTrackStart
    0x10: 0x5C,  # Shift+Sync          → DDJ Master On/Off
    0x15: 0x38,  # Shift+Reverse       → DDJ Reverse
    0x0F: 0x60,  # Shift+KeyLock       → DDJ TempoRange
    0x1C: 0x50,  # Shift+LoopPress     → DDJ ActiveLoop toggle
    0x0B: 0x69,  # Shift+HotCues(MOVE) → DDJ BeatJump mode
    0x0C: 0x41,  # Shift+Samples(LOOP) → DDJ VelocitySampler mode
    0x16: 0x6B,  # Shift+FLX           → DDJ PadFx2Mode
    0x0D: 0x65,  # Shift+Grid          → DDJ GridAdjustDouble
}

# ---------------------------------------------------------------------------
# Performance pads  (S2: Notes 0x03-0x0A on Ch1/Ch3, 8 pads)
# DDJ-SX HotCue pads: Notes 0x00-0x07 on ch7 (Deck A) / ch8 (Deck B)
# Shift+pads (delete hotcue): Notes 0x08-0x0F on ch7/ch8
# ---------------------------------------------------------------------------
PAD_FIRST_NOTE = 0x03   # S2 pad 1 starts at note 0x03
PAD_LAST_NOTE  = 0x0A   # S2 pad 8 ends at note 0x0A

# ---------------------------------------------------------------------------
# Browse encoder  (S2: CC 0x19 on Ch1/Ch3, relative, center=64)
# DDJ-SX Browse: CC 0x40 on ch6
# Both encoders (left/right deck) control the same browser.
# ---------------------------------------------------------------------------
BROWSE_CODES = {
    (0xB1, 0x19),  # Left deck browse encoder
    (0xB3, 0x19),  # Right deck browse encoder
}

# Browse encoder press (S2 note TBD — press generates a Note, not CC)
# DDJ-SX: Forward/Browse+Press = Note 0x41 on ch6 (0x96 0x41)
# Set to None to disable; set to the S2 note number once identified.
BROWSE_PRESS_NOTE = None  # e.g. 0x1D or whatever note is sent on Ch1/Ch3

# Load button (S2 browse-encoder press, note 0x18) — identified and confirmed.
# DDJ-SX: ch6 Note 0x46 (Deck A), ch6 Note 0x47 (Deck B)
LOAD_NOTE = 0x18  # S2 browse-encoder press → Load track into deck

# ---------------------------------------------------------------------------
# Mixer faders/knobs  (S2: CC on Ch5=left, Ch6=right, absolute 0-127)
# Maps (S2_status_byte, S2_cc) → (DDJ_channel, DDJ_cc)
# All sent as 14-bit HiRes (MSB + LSB=0) to match DDJ-SX KnobSliderHiRes type
# ---------------------------------------------------------------------------
MIXER_MAP = {
    # Left channel mixer (Ch5=0xB5 → DDJ ch0)
    # S2 CCs are numbered bottom-to-top: Fader=0x01, Filter=0x02, Low=0x03, Mid=0x04, High=0x05, Gain=0x06
    # Left channel mixer (Ch5=0xB5 → DDJ ch0)
    (0xB5, 0x01): (0, 0x13),  # Left Ch Fader  → DDJ CC13 on ch0
    (0xB5, 0x03): (0, 0x0F),  # Left EQ Low    → DDJ CC0F on ch0
    (0xB5, 0x04): (0, 0x0B),  # Left EQ Mid    → DDJ CC0B on ch0
    (0xB5, 0x05): (0, 0x07),  # Left EQ High   → DDJ CC07 on ch0
    (0xB5, 0x06): (0, 0x04),  # Left Gain      → DDJ CC04 on ch0
    # Right channel mixer (Ch6=0xB6 → DDJ ch1)
    (0xB6, 0x01): (1, 0x13),  # Right Ch Fader → DDJ CC13 on ch1
    (0xB6, 0x03): (1, 0x0F),  # Right EQ Low   → DDJ CC0F on ch1
    (0xB6, 0x04): (1, 0x0B),  # Right EQ Mid   → DDJ CC0B on ch1
    (0xB6, 0x05): (1, 0x07),  # Right EQ High  → DDJ CC07 on ch1
    (0xB6, 0x06): (1, 0x04),  # Right Gain     → DDJ CC04 on ch1
    # Global mixer (Ch7=0xB7)
    (0xB7, 0x01): (6, 0x1F),  # Crossfader     → DDJ CC1F on ch6
}

# ---------------------------------------------------------------------------
# Headphone Cue buttons  (S2: Note 0x08 on Ch5=left, Ch6=right)
# DDJ-SX: Note 0x54 on ch0 (Deck A) / ch1 (Deck B)
# ---------------------------------------------------------------------------
HEADPHONE_CUE_CODES = {
    (0x95, 0x08): 0,  # Left deck headphone cue
    (0x96, 0x08): 1,  # Right deck headphone cue
}

# ---------------------------------------------------------------------------
# FX Select buttons  (S2: Note on Ch7=0x97, global mixer)
# DDJ-SX: FX Assign buttons on ch6
#   Layout:  [1] [2]    →  FX1/FX2 for CH1 (top row)
#            [3] [4]    →  FX1/FX2 for CH2 (bottom row)
# ---------------------------------------------------------------------------
FX_SELECT_MAP = {
    (0x97, 0x04): (4, 0x47),  # FX Select 1 → DDJ FX1-1 On/Off
    (0x97, 0x05): (4, 0x48),  # FX Select 2 → DDJ FX1-2 On/Off
    (0x97, 0x02): (4, 0x49),  # FX Select 3 → DDJ FX1-3 On/Off
    (0x97, 0x03): (4, 0x43),  # FX Select 4 → DDJ FX1 Release FX
}

# S2 FX button note → active FX slot (1/2/3 or 0 for release/none)
FX_NOTE_TO_SLOT = {0x04: 1, 0x05: 2, 0x02: 3, 0x03: 0}

# ---------------------------------------------------------------------------
# FX/Filter knob  (S2: CC 0x02 on Ch5=left, Ch6=right)
# Routes to active FX slot depth on DDJ FX1 unit (ch4) when an FX is active,
# falls back to CFX filter (ch6 CC 0x17/0x18) when no FX is selected.
# DDJ FX depth CCs: FX1-1=0x02, FX1-2=0x04, FX1-3=0x06  (KnobSliderHiRes)
# ---------------------------------------------------------------------------
FX_KNOB_CODES = {
    (0xB5, 0x02): 0,  # Left deck  → FX1 unit (ch4) or CFXParameterCH1
    (0xB6, 0x02): 1,  # Right deck → FX1 unit (ch4) or CFXParameterCH2
}

FX_DEPTH_CC = {1: 0x02, 2: 0x04, 3: 0x06}  # FX slot → DDJ FX1 depth CC

# Active FX slot state (updated when FX select buttons are pressed)
_active_fx = 0  # 0=none, 1=FX1-1, 2=FX1-2, 3=FX1-3

# ---------------------------------------------------------------------------
# Notes/CCs to silently ignore (known controls with no DDJ-SX equivalent)
# ---------------------------------------------------------------------------
IGNORED_NOTES = {0x29, 0x28, 0x27}  # Shift button, Loop encoder touch, Move encoder touch

# ---------------------------------------------------------------------------
# Loop encoder rotation  (S2: CC 0x1D on Ch1/Ch3, relative, center=64)
# CW (>64) → LoopDouble (DDJ note 0x13), CCW (<64) → LoopHalf (DDJ note 0x12)
# ---------------------------------------------------------------------------
LOOP_ENCODER_CODES = {
    (0xB1, 0x1D): 0,  # Deck A loop encoder
    (0xB3, 0x1D): 1,  # Deck B loop encoder
}

# ---------------------------------------------------------------------------
# Move encoder rotation  (S2: CC 0x1B on Ch1/Ch3, relative, center=64)
# CW (>64) → LoopMoveRight (DDJ note 0x62), CCW (<64) → LoopMoveLeft (DDJ note 0x61)
# ---------------------------------------------------------------------------
MOVE_ENCODER_CODES = {
    (0xB1, 0x1B): 0,  # Deck A move encoder
    (0xB3, 0x1B): 1,  # Deck B move encoder
}

# ---------------------------------------------------------------------------
# Shift+Move encoder  (S2: CC 0x1B on Ch2/Ch4, relative, center=64)
# → DDJ-SX JogSearch (CC 0x1F, Difference type) — scrubs through track
# Works without active loop, unlike LoopMove.
# ---------------------------------------------------------------------------
SHIFT_MOVE_ENCODER_CODES = {
    (0xB2, 0x1B): 0,  # Deck A shift+move encoder
    (0xB4, 0x1B): 1,  # Deck B shift+move encoder
}

IGNORED_CCS = {
    (0xB2, 0x1D),  # Shift+Loop encoder rotation (Deck A) — no DDJ-SX equivalent
    (0xB4, 0x1D),  # Shift+Loop encoder rotation (Deck B) — no DDJ-SX equivalent
}


# =============================================================================
# Helper: deck channel → deck index
# =============================================================================
S2_DECK_CHANNELS = {
    0x91: 0,  # Ch1 Note = Deck A, no shift
    0x93: 1,  # Ch3 Note = Deck B, no shift
}
S2_SHIFT_CHANNELS = {
    0x92: 0,  # Ch2 Note = Deck A + Shift
    0x94: 1,  # Ch4 Note = Deck B + Shift
}


# =============================================================================
# Translation functions
# =============================================================================

def map_jog_value(midi_value):
    """Amplify S2 jog relative value for DDJ-SX."""
    delta = midi_value - 64
    amplified = 64 + (delta * JOG_AMPLIFY)
    return max(1, min(127, amplified))


def jog(midi_out, msg):
    deck_id = JOG_CODES[tuple(msg.bytes()[:2])]
    v = msg.bytes()[2]
    if v == 64:
        return
    v = map_jog_value(v)
    ms = mido.Message.from_bytes([0xB0 + deck_id, 0x22, v])
    for _ in range(JOG_MULTIPLIER):
        midi_out.send(ms)


def touch(midi_out, deck_id, on):
    vel = 0x7F if on else 0x00
    midi_out.send(mido.Message.from_bytes([0x90 + deck_id, 0x36, vel]))


def tempo(midi_out, deck_id, value):
    """Send DDJ-SX 14-bit tempo (MSB from S2 value, LSB=0)."""
    midi_out.send(mido.Message.from_bytes([0xB0 + deck_id, 0x00, value]))
    midi_out.send(mido.Message.from_bytes([0xB0 + deck_id, 0x20, 0]))


def send_button(midi_out, deck_id, note, velocity):
    """Send a DDJ-SX Note On/Off for a deck button."""
    midi_out.send(mido.Message.from_bytes([0x90 + deck_id, note, velocity]))


def send_pad(midi_out, deck_id, s2_note, velocity, shifted=False):
    """Translate S2 pad note to DDJ-SX pad on ch7/ch8."""
    pad_index = s2_note - PAD_FIRST_NOTE          # 0-7
    ddj_note = pad_index + (0x08 if shifted else 0x00)
    ddj_ch = 7 + deck_id                           # ch7=DeckA, ch8=DeckB
    midi_out.send(mido.Message.from_bytes([0x90 + ddj_ch, ddj_note, velocity]))


def send_browse(midi_out, value):
    """Forward browse encoder to DDJ-SX ch6 CC 0x40."""
    midi_out.send(mido.Message.from_bytes([0xB6, 0x40, value]))


def send_loop_size(midi_out, deck_id, value):
    """Translate loop encoder rotation to DDJ-SX LoopHalf/LoopDouble press."""
    if value > 64:
        ddj_note = 0x13  # LoopDouble (clockwise)
    elif value < 64:
        ddj_note = 0x12  # LoopHalf (counter-clockwise)
    else:
        return
    midi_out.send(mido.Message.from_bytes([0x90 + deck_id, ddj_note, 0x7F]))
    midi_out.send(mido.Message.from_bytes([0x90 + deck_id, ddj_note, 0x00]))


def send_loop_move(midi_out, deck_id, value):
    """Translate Move encoder rotation to DDJ-SX LoopMoveLeft/Right press."""
    if value > 64:
        ddj_note = 0x62  # LoopMoveRight (clockwise)
    elif value < 64:
        ddj_note = 0x61  # LoopMoveLeft (counter-clockwise)
    else:
        return
    midi_out.send(mido.Message.from_bytes([0x90 + deck_id, ddj_note, 0x7F]))
    midi_out.send(mido.Message.from_bytes([0x90 + deck_id, ddj_note, 0x00]))


def send_beatjump(midi_out, deck_id, value):
    """Jump forward/backward using DDJ-SX BeatJump pads (REV4/FWD4).
    Briefly activates BeatJump pad mode, sends the jump, restores HotCue mode.
    Default jump size for PAD7/8 in Rekordbox is configurable — set to 8 bars
    in Rekordbox Preferences > Controller > Pad tab > BeatJump.
    """
    if value > 64:
        pad_note = 0x47  # PAD8_BeatJump = FWD4 (largest forward jump)
    elif value < 64:
        pad_note = 0x46  # PAD7_BeatJump = REV4 (largest backward jump)
    else:
        return
    pad_ch = 7 + deck_id  # ch7=DeckA, ch8=DeckB
    # Activate BeatJump pad mode
    midi_out.send(mido.Message.from_bytes([0x90 + deck_id, 0x69, 0x7F]))
    midi_out.send(mido.Message.from_bytes([0x90 + deck_id, 0x69, 0x00]))
    # Send pad press + release
    midi_out.send(mido.Message.from_bytes([0x90 + pad_ch, pad_note, 0x7F]))
    midi_out.send(mido.Message.from_bytes([0x90 + pad_ch, pad_note, 0x00]))
    # Restore HotCue pad mode
    midi_out.send(mido.Message.from_bytes([0x90 + deck_id, 0x1B, 0x7F]))
    midi_out.send(mido.Message.from_bytes([0x90 + deck_id, 0x1B, 0x00]))


def send_mixer(midi_out, ddj_ch, ddj_cc, value):
    """Send DDJ-SX mixer CC as 14-bit HiRes (MSB + LSB=0)."""
    midi_out.send(mido.Message.from_bytes([0xB0 + ddj_ch, ddj_cc, value]))
    midi_out.send(mido.Message.from_bytes([0xB0 + ddj_ch, ddj_cc + 0x20, 0]))


def send_fx_or_filter(midi_out, deck_id, value):
    """Route FX/Filter knob to active FX slot depth, or CFX filter when no FX active."""
    if _active_fx in FX_DEPTH_CC:
        cc = FX_DEPTH_CC[_active_fx]
        midi_out.send(mido.Message.from_bytes([0xB4, cc, value]))
        midi_out.send(mido.Message.from_bytes([0xB4, cc + 0x20, 0]))
    else:
        cfx_cc = 0x17 + deck_id  # 0x17=CFXParameterCH1, 0x18=CFXParameterCH2
        midi_out.send(mido.Message.from_bytes([0xB6, cfx_cc, value]))
        midi_out.send(mido.Message.from_bytes([0xB6, cfx_cc + 0x20, 0]))


# =============================================================================
# Main loop
# =============================================================================

def main():
    global _active_fx
    try:
        midi_inp_conf, midi_out_conf = check_config()
        midi_inp = mido.open_input(midi_inp_conf)
        if os.name == 'nt':
            midi_out = mido.open_output(midi_out_conf)
        else:
            midi_out = mido.open_output("Pioneer DDJ-SX", True)

        rekordjog_start_sequence()
        print("Controller: Native Instruments Traktor Kontrol S2 MK3")
        print("Listening for MIDI messages... (Ctrl+C to quit)")
        print()
        print("Debug legend:")
        print("  [JOG]       Jogwheel rotation")
        print("  [TOUCH]     Jogwheel touch on/off")
        print("  [TEMPO]     Pitch/tempo fader")
        print("  [BTN]       Deck button (mapped)")
        print("  [SHIFT+BTN] Shift+button (mapped)")
        print("  [PAD]       Performance pad")
        print("  [BROWSE]    Browse encoder")
        print("  [MIXER]     Mixer fader/knob")
        print("  [HPCUE]     Headphone Cue button")
        print("  [FX DEP]    FX depth knob (routes to active FX slot or filter)")
        print("  [???]       Unrecognised — note it and add to mapping")
        print()

        while True:
            ims = midi_inp.receive()
            b = ims.bytes()
            status = b[0]
            msg_type = status & 0xF0
            ch = status & 0x0F      # 0-based channel index
            data1 = b[1] if len(b) > 1 else None
            data2 = b[2] if len(b) > 2 else None
            key2 = (b[0], b[1]) if len(b) >= 2 else None
            raw = ' '.join(f'0x{x:02X}' for x in b)

            # ---------------------------------------------------------------
            # Jogwheel rotation
            # ---------------------------------------------------------------
            if key2 in JOG_CODES:
                deck_id = JOG_CODES[key2]
                print(f"[JOG]    Deck {'A' if deck_id == 0 else 'B'} val={data2}  {raw}")
                jog(midi_out, ims)

            # ---------------------------------------------------------------
            # Jogwheel touch
            # ---------------------------------------------------------------
            elif key2 in TOUCH_CODES:
                deck_id = TOUCH_CODES[key2]
                on = (msg_type == 0x90 and data2 == 0x7F)
                state = "ON " if on else "OFF"
                print(f"[TOUCH {state}] Deck {'A' if deck_id == 0 else 'B'}  {raw}")
                touch(midi_out, deck_id, on)

            # ---------------------------------------------------------------
            # Tempo fader
            # ---------------------------------------------------------------
            elif key2 in TEMPO_CODES:
                deck_id = TEMPO_CODES[key2]
                print(f"[TEMPO]  Deck {'A' if deck_id == 0 else 'B'} val={data2}  {raw}")
                tempo(midi_out, deck_id, data2)

            # ---------------------------------------------------------------
            # Per-deck buttons (Ch1 = Deck A, Ch3 = Deck B, Note On/Off)
            # ---------------------------------------------------------------
            elif status in S2_DECK_CHANNELS and msg_type == 0x90:
                deck_id = S2_DECK_CHANNELS[status]
                note = data1
                vel = data2

                if PAD_FIRST_NOTE <= note <= PAD_LAST_NOTE:
                    print(f"[PAD]    Deck {'A' if deck_id == 0 else 'B'} pad={(note - PAD_FIRST_NOTE + 1)} vel={vel}  {raw}")
                    send_pad(midi_out, deck_id, note, vel, shifted=False)

                elif note in DECK_BUTTON_MAP:
                    ddj_note = DECK_BUTTON_MAP[note]
                    print(f"[BTN]    Deck {'A' if deck_id == 0 else 'B'} note=0x{note:02X}→0x{ddj_note:02X} vel={vel}  {raw}")
                    send_button(midi_out, deck_id, ddj_note, vel)

                elif LOAD_NOTE is not None and note == LOAD_NOTE:
                    # Load button: maps to DDJ ch6 note 0x46/0x47
                    ddj_load_note = 0x46 + deck_id
                    print(f"[LOAD]   Deck {'A' if deck_id == 0 else 'B'} vel={vel}  {raw}")
                    midi_out.send(mido.Message.from_bytes([0x96, ddj_load_note, vel]))

                elif note in IGNORED_NOTES:
                    pass  # Shift button etc — silently ignore

                else:
                    print(f"[???]    {raw}  (deck {'A' if deck_id == 0 else 'B'} note=0x{note:02X})")

            # ---------------------------------------------------------------
            # Shift-layer buttons (Ch2 = A+Shift, Ch4 = B+Shift)
            # ---------------------------------------------------------------
            elif status in S2_SHIFT_CHANNELS and msg_type == 0x90:
                deck_id = S2_SHIFT_CHANNELS[status]
                note = data1
                vel = data2

                if PAD_FIRST_NOTE <= note <= PAD_LAST_NOTE:
                    print(f"[PAD+SH] Deck {'A' if deck_id == 0 else 'B'} pad={(note - PAD_FIRST_NOTE + 1)} vel={vel}  {raw}")
                    send_pad(midi_out, deck_id, note, vel, shifted=True)

                elif note in SHIFT_BUTTON_MAP:
                    ddj_note = SHIFT_BUTTON_MAP[note]
                    print(f"[SHIFT+BTN] Deck {'A' if deck_id == 0 else 'B'} note=0x{note:02X}→0x{ddj_note:02X} vel={vel}  {raw}")
                    send_button(midi_out, deck_id, ddj_note, vel)

                elif note in IGNORED_NOTES:
                    pass  # Shift button etc — silently ignore

                else:
                    print(f"[???]    {raw}  (deck {'A' if deck_id == 0 else 'B'} shift note=0x{note:02X})")

            # ---------------------------------------------------------------
            # Loop encoder rotation (CC 0x1D on Ch1/Ch3)
            # ---------------------------------------------------------------
            elif key2 in LOOP_ENCODER_CODES:
                deck_id = LOOP_ENCODER_CODES[key2]
                direction = "CW +size" if data2 > 64 else "CCW -size"
                print(f"[LOOP]   Deck {'A' if deck_id == 0 else 'B'} val={data2} ({direction})  {raw}")
                send_loop_size(midi_out, deck_id, data2)

            # ---------------------------------------------------------------
            # Move encoder rotation (CC 0x1B on Ch1/Ch3) → Loop Move
            # ---------------------------------------------------------------
            elif key2 in MOVE_ENCODER_CODES:
                deck_id = MOVE_ENCODER_CODES[key2]
                direction = "CW →" if data2 > 64 else "CCW ←"
                print(f"[MOVE]   Deck {'A' if deck_id == 0 else 'B'} val={data2} ({direction})  {raw}")
                send_loop_move(midi_out, deck_id, data2)

            # ---------------------------------------------------------------
            # Shift+Move encoder (CC 0x1B on Ch2/Ch4) → BeatJump
            # ---------------------------------------------------------------
            elif key2 in SHIFT_MOVE_ENCODER_CODES:
                deck_id = SHIFT_MOVE_ENCODER_CODES[key2]
                direction = "FWD →→" if data2 > 64 else "BWD ←←"
                print(f"[JUMP]   Deck {'A' if deck_id == 0 else 'B'} val={data2} ({direction})  {raw}")
                send_beatjump(midi_out, deck_id, data2)

            # ---------------------------------------------------------------
            # Browse encoder (CC 0x19 on Ch1/Ch3)
            # ---------------------------------------------------------------
            elif key2 in BROWSE_CODES:
                print(f"[BROWSE] val={data2} ({'+1' if data2 > 64 else '-1'})  {raw}")
                send_browse(midi_out, data2)

            # Browse encoder press (Note — TBD)
            elif (BROWSE_PRESS_NOTE is not None
                  and msg_type == 0x90
                  and data1 == BROWSE_PRESS_NOTE
                  and status in (0x91, 0x93)):
                print(f"[BROWSE PRESS] vel={data2}  {raw}")
                midi_out.send(mido.Message.from_bytes([0x96, 0x41, data2]))

            # ---------------------------------------------------------------
            # FX/Filter knob (CC 0x02 on Ch5/Ch6 — dynamic routing)
            # ---------------------------------------------------------------
            elif key2 in FX_KNOB_CODES:
                deck_id = FX_KNOB_CODES[key2]
                target = f"FX{_active_fx} depth" if _active_fx in FX_DEPTH_CC else "filter"
                print(f"[FX DEP] Deck {'A' if deck_id == 0 else 'B'} val={data2} → {target}  {raw}")
                send_fx_or_filter(midi_out, deck_id, data2)

            # ---------------------------------------------------------------
            # Mixer faders/knobs (Ch5, Ch6, Ch7 — CC messages)
            # ---------------------------------------------------------------
            elif key2 in MIXER_MAP:
                ddj_ch, ddj_cc = MIXER_MAP[key2]
                print(f"[MIXER]  (0x{status:02X} CC0x{data1:02X}) val={data2} "
                      f"→ DDJ ch{ddj_ch} CC0x{ddj_cc:02X}  {raw}")
                send_mixer(midi_out, ddj_ch, ddj_cc, data2)

            # ---------------------------------------------------------------
            # Headphone Cue buttons
            # ---------------------------------------------------------------
            elif key2 in HEADPHONE_CUE_CODES:
                deck_id = HEADPHONE_CUE_CODES[key2]
                print(f"[HPCUE]  Deck {'A' if deck_id == 0 else 'B'} vel={data2}  {raw}")
                send_button(midi_out, deck_id, 0x54, data2)

            # ---------------------------------------------------------------
            # FX Select buttons (Ch7 = 0x97, Note On/Off)
            # ---------------------------------------------------------------
            elif key2 in FX_SELECT_MAP:
                ddj_ch, ddj_note = FX_SELECT_MAP[key2]
                if data2 > 0:  # Note On → update active FX slot
                    _active_fx = FX_NOTE_TO_SLOT.get(data1, _active_fx)
                slot_label = f"slot {_active_fx}" if _active_fx > 0 else "release"
                print(f"[FX SEL] note=0x{data1:02X} vel={data2} → DDJ ch{ddj_ch} note=0x{ddj_note:02X} ({slot_label})  {raw}")
                midi_out.send(mido.Message.from_bytes([0x90 + ddj_ch, ddj_note, data2]))

            # ---------------------------------------------------------------
            # Silently ignored CCs (FLX encoder etc.)
            # ---------------------------------------------------------------
            elif key2 in IGNORED_CCS:
                pass

            # ---------------------------------------------------------------
            # Unrecognised — print for identification
            # ---------------------------------------------------------------
            else:
                print(f"[???]    {raw}  type={ims.type} ch={ch}")

    except KeyboardInterrupt:
        print("\nClosing RekordJog, bye.")


if __name__ == "__main__":
    main()
