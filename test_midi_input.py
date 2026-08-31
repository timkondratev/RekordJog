#!/usr/bin/env python3
"""Quick test: list all MIDI devices and try to receive from S2 MK3."""
import mido

print("=== Available MIDI Inputs ===")
for name in mido.get_input_names():
    print(f"  IN:  {name}")

print("\n=== Available MIDI Outputs ===")
for name in mido.get_output_names():
    print(f"  OUT: {name}")

print("\n=== Available MIDI I/O Ports ===")
for name in mido.get_ioport_names():
    print(f"  I/O: {name}")

# Try opening as plain input
print("\nTrying to open S2 MK3 as INPUT (not ioport)...")
try:
    inp = mido.open_input("Traktor Kontrol S2 MK3")
    print("SUCCESS! Listening for 10 seconds -- touch a jogwheel or press a button...")
    import time
    start = time.time()
    while time.time() - start < 10:
        msg = inp.poll()
        if msg:
            print(f"  >> {msg}  |  raw: {' '.join(f'0x{b:02X}' for b in msg.bytes())}")
    inp.close()
    print("Done.")
except Exception as e:
    print(f"FAILED: {e}")
