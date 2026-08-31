#!/usr/bin/env python3
"""
S2 MK3 Button-Dump: Zeigt ALLE eingehenden MIDI-Nachrichten an.
Druecke jeden Button einzeln und notiere die Ausgabe.
"""
import mido
from functions.check_config import check_config

BUTTONS = [
    "PLAY / PAUSE",
    "CUE",
    "SYNC",
    "REVERSE / SLIP",
    "KEYLOCK / MASTER",
    "LOOP SIZE MINUS",
    "LOOP SIZE PLUS",
    "AUTO LOOP",
    "HOT CUE MODE",
    "SAMPLER MODE",
    "FLX1",
    "FLX2",
    "Taste UNTER FLX1",
    "Taste UNTER FLX2",
]

def main():
    midi_inp_conf, _ = check_config()
    midi_inp = mido.open_input(midi_inp_conf)

    print("=" * 50)
    print("  S2 MK3 — Button-Dump")
    print("=" * 50)
    print()
    print("Druecke die Buttons auf der LINKEN Seite (Deck A)")
    print("in dieser Reihenfolge, EINEN nach dem anderen:")
    print()
    for i, name in enumerate(BUTTONS, 1):
        print(f"  {i:2d}. {name}")
    print()
    print("Jeder Knopfdruck erzeugt Ausgabe.")
    print("Ctrl+C zum Beenden. Dann die Ausgabe hier posten.")
    print()
    print("-" * 50)
    print()

    while True:
        msg = midi_inp.receive()
        b = msg.bytes()
        raw = ' '.join(f'0x{x:02X}' for x in b)

        # Only show Note On with velocity > 0 (skip releases)
        if len(b) >= 3 and (b[0] & 0xF0) == 0x90 and b[2] > 0:
            ch = b[0] & 0x0F
            note = b[1]
            vel = b[2]
            print(f"Ch{ch+1}  Note 0x{note:02X}  vel={vel}   [{raw}]")


if __name__ == "__main__":
    main()
