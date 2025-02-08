import mido
from tools import clear_terminal

def setup_jogwheels(deck_number, midi_port):
    clear_terminal()
    print("Let's set up the Jogwheel for deck {deck_number} now!")
    print("Please touch the top of deck {deck_number} once...")
    try:
        with mido.open_input(midi_port) as midi_inp:
            while True:
                ims = midi_inp.receive()
                if ims.type == 'note_on':
                    deck_hex=ims.channel
                    touch_top=ims.control
            break
    except KeyboardInterrupt:
        print("\nExiting RekordJog, bye.")



output = [
    touch_top,  #touching on top
    jog_side,   #turning on the side (beatmatch)
    jog_top,    #turning on top (scratching)
    inc_cw,     #turning incremental Jogs clockwise, value e.g. 7f
    inc_ccw,    #turning incremental Jogs counter clockwise, value e.g. 01
    nullpoint,  #e.g. 0x00 for the XONE:4D
    message_rate_multiplier,    #message rate limit/boost depending on wether jogs feel too slow/rb lags
    
]

return touch_top 




#Debug
testmidiport = "Mixon 4, 1"
if __name__ == "__main__":
    setup_jogwheels(1, testmidiport)