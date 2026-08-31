#!/usr/bin/env python3
"""
S2 MK3 MIDI Capture Tool
=========================
Captures MIDI messages from the Kontrol S2 MK3 in MIDI mode
and outputs them in a format ready to paste into RekordJog_KontrolS2MK3.py.

Usage:
  1. Put S2 MK3 in MIDI mode (hold left FLX button + connect USB)
  2. Run: python3 capture_s2mk3_midi.py
  3. Select the S2 MK3 from the device list
  4. Follow the on-screen instructions for each control
  5. Copy the generated output into the main script
"""

import mido
import time
import sys


def select_device():
    """Let user pick the S2 MK3 from available MIDI inputs."""
    inputs = mido.get_input_names()
    if not inputs:
        print("No MIDI input devices found!")
        print("Is the S2 MK3 connected and in MIDI mode?")
        print("(Hold left FLX button while connecting USB)")
        sys.exit(1)

    print("\nAvailable MIDI input devices:")
    for i, name in enumerate(inputs, 1):
        print(f"  {i}. {name}")

    choice = int(input("\nSelect device number: ")) - 1
    return inputs[choice]


def capture_messages(port, duration=5, description=""):
    """Capture MIDI messages for a given duration."""
    print(f"\n>>> {description}")
    print(f"    Recording for {duration} seconds... GO!")

    messages = []
    start = time.time()
    while time.time() - start < duration:
        msg = port.poll()
        if msg is not None:
            messages.append({
                'type': msg.type,
                'bytes': msg.bytes(),
                'hex': ' '.join(f'0x{b:02X}' for b in msg.bytes()),
                'time': time.time() - start,
                'raw': msg,
            })

    print(f"    Captured {len(messages)} messages.")
    return messages


def print_messages(messages):
    """Print captured messages in a readable format."""
    for m in messages:
        b = m['bytes']
        status = b[0]
        ch = status & 0x0F
        msg_type = status & 0xF0

        type_name = {0x80: 'NoteOff', 0x90: 'NoteOn', 0xB0: 'CC', 0xE0: 'PitchBend'}
        t = type_name.get(msg_type, f'0x{msg_type:02X}')

        if len(b) >= 3:
            print(f"    [{m['time']:5.2f}s] {t} ch={ch} "
                  f"data1=0x{b[1]:02X}({b[1]:3d}) "
                  f"data2=0x{b[2]:02X}({b[2]:3d})  "
                  f"raw: {m['hex']}")
        elif len(b) >= 2:
            print(f"    [{m['time']:5.2f}s] {t} ch={ch} "
                  f"data1=0x{b[1]:02X}({b[1]:3d})  "
                  f"raw: {m['hex']}")


def analyze_jog(messages):
    """Analyze jog messages and extract the mapping pattern."""
    if not messages:
        return None, None

    # Group by first 2 bytes (status + data1)
    codes = {}
    values = set()
    for m in messages:
        b = m['bytes']
        if len(b) >= 3:
            key = (b[0], b[1])
            if key not in codes:
                codes[key] = []
            codes[key].append(b[2])
            values.add(b[2])

    return codes, sorted(values)


def main():
    device = select_device()
    port = mido.open_input(device)

    print("\n" + "=" * 60)
    print("  S2 MK3 MIDI Capture")
    print("=" * 60)

    results = {}

    # --- Left Jogwheel ---
    input("\nPress ENTER, then SLOWLY rotate LEFT jogwheel CLOCKWISE...")
    msgs = capture_messages(port, 5, "Left Jog - Slow CW")
    print_messages(msgs)
    results['left_jog_cw_slow'] = msgs

    input("\nPress ENTER, then FAST rotate LEFT jogwheel CLOCKWISE...")
    msgs = capture_messages(port, 5, "Left Jog - Fast CW")
    print_messages(msgs)
    results['left_jog_cw_fast'] = msgs

    input("\nPress ENTER, then SLOWLY rotate LEFT jogwheel COUNTER-CLOCKWISE...")
    msgs = capture_messages(port, 5, "Left Jog - Slow CCW")
    print_messages(msgs)
    results['left_jog_ccw_slow'] = msgs

    input("\nPress ENTER, then FAST rotate LEFT jogwheel COUNTER-CLOCKWISE...")
    msgs = capture_messages(port, 5, "Left Jog - Fast CCW")
    print_messages(msgs)
    results['left_jog_ccw_fast'] = msgs

    # --- Right Jogwheel ---
    input("\nPress ENTER, then SLOWLY rotate RIGHT jogwheel CLOCKWISE...")
    msgs = capture_messages(port, 5, "Right Jog - Slow CW")
    print_messages(msgs)
    results['right_jog_cw_slow'] = msgs

    input("\nPress ENTER, then FAST rotate RIGHT jogwheel CLOCKWISE...")
    msgs = capture_messages(port, 5, "Right Jog - Fast CW")
    print_messages(msgs)
    results['right_jog_cw_fast'] = msgs

    # --- Touch Detection ---
    input("\nPress ENTER, then TOUCH the LEFT jogwheel surface (don't rotate)...")
    msgs = capture_messages(port, 3, "Left Jog - Touch On")
    print_messages(msgs)
    results['left_touch_on'] = msgs

    input("\nPress ENTER, then LIFT finger from LEFT jogwheel...")
    msgs = capture_messages(port, 3, "Left Jog - Touch Off")
    print_messages(msgs)
    results['left_touch_off'] = msgs

    input("\nPress ENTER, then TOUCH the RIGHT jogwheel surface...")
    msgs = capture_messages(port, 3, "Right Jog - Touch On")
    print_messages(msgs)
    results['right_touch_on'] = msgs

    input("\nPress ENTER, then LIFT finger from RIGHT jogwheel...")
    msgs = capture_messages(port, 3, "Right Jog - Touch Off")
    print_messages(msgs)
    results['right_touch_off'] = msgs

    # --- Tempo Faders ---
    input("\nPress ENTER, then SLOWLY move LEFT tempo fader full range...")
    msgs = capture_messages(port, 8, "Left Tempo Fader")
    print_messages(msgs)
    results['left_tempo'] = msgs

    input("\nPress ENTER, then SLOWLY move RIGHT tempo fader full range...")
    msgs = capture_messages(port, 8, "Right Tempo Fader")
    print_messages(msgs)
    results['right_tempo'] = msgs

    # --- Summary ---
    print("\n" + "=" * 60)
    print("  CAPTURE COMPLETE - SUMMARY")
    print("=" * 60)

    # Analyze jog codes
    all_jog_msgs = (
        results.get('left_jog_cw_slow', []) +
        results.get('left_jog_cw_fast', []) +
        results.get('left_jog_ccw_slow', []) +
        results.get('left_jog_ccw_fast', []) +
        results.get('right_jog_cw_slow', []) +
        results.get('right_jog_cw_fast', [])
    )

    codes, values = analyze_jog(all_jog_msgs)
    if codes:
        print("\nJog rotation MIDI codes detected:")
        for key, vals in codes.items():
            unique_vals = sorted(set(vals))
            print(f"  (0x{key[0]:02X}, 0x{key[1]:02X}) -> values: "
                  f"min={min(unique_vals)}, max={max(unique_vals)}, "
                  f"unique count={len(unique_vals)}")
            print(f"    All unique values: {unique_vals}")

    print("\n--- Paste this into RekordJog_KontrolS2MK3.py ---\n")

    if codes:
        print("JOG_CODES = {")
        for i, key in enumerate(codes.keys()):
            print(f"    (0x{key[0]:02X}, 0x{key[1]:02X}): {i},  "
                  f"# Deck {'A (left)' if i == 0 else 'B (right)'}")
        print("}")

    # Touch codes
    for label, key in [("TOUCH_ON", 'left_touch_on'), ("TOUCH_ON", 'right_touch_on')]:
        msgs = results.get(key, [])
        if msgs:
            b = msgs[0]['bytes']
            print(f"# {label}: (0x{b[0]:02X}, 0x{b[1]:02X})")

    for label, key in [("TOUCH_OFF", 'left_touch_off'), ("TOUCH_OFF", 'right_touch_off')]:
        msgs = results.get(key, [])
        if msgs:
            b = msgs[0]['bytes']
            print(f"# {label}: (0x{b[0]:02X}, 0x{b[1]:02X})")

    # Tempo codes
    for label, key in [("TEMPO left", 'left_tempo'), ("TEMPO right", 'right_tempo')]:
        msgs = results.get(key, [])
        if msgs:
            b = msgs[0]['bytes']
            print(f"# {label}: (0x{b[0]:02X}, 0x{b[1]:02X})")

    print("\nDone! Copy the values above into the main script.")
    port.close()


if __name__ == "__main__":
    main()
