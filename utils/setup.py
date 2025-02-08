import os
import json

from setup_jogwheels import setup_jogwheels

def main():
    # ASK: Select MIDI input device from list
    device_list = ["Device 1", "Device 2", "Device 3"] # TODO get list of devices
    while True:
        device_str = input("Select MIDI input device from list [enter number]: ")
        try:
            device = int(device_str)
        except ValueError:
            print("Please enter a valid number")
            continue
        if device < 1 or device > len(device_list):
            print("Please enter a valid number")
            continue
        device_name = device_list[device-1]
        print(f"Selected device: {device_name}")
        break

    # TODO: Connect to MIDI device

    # TODO: Start MIDI listener thread

    while True:  
        num_decks_str = input("How many decks would you like to setup? (1-4): ")
        try:
            num_decks = int(num_decks_str)
        except ValueError:
            print("Please enter a valid number")
            continue
    
        if num_decks < 1:
            print("Please enter a valid number")
            continue
        break
    
    decks_parameters = []
    for deck in range(num_decks):
        decks_parameters.append(deck_setup(deck+1))

    # Save a config file with the parameters
    conf_list = os.listdir("configs")
    print("Enter the name of the config file to save: ")
    while True:
        config_name = input()
        # Save the config file
        #if config_name is already used, ask to overwrite

        # list config names in the folder "configs"
        if config_name in conf_list:
            print(f"Config file {config_name} already exists. Overwrite? [y/n]")
            overwrite = input()
            if overwrite.lower() != "y":
                print("Please enter a different name: ")
                continue
            else:
                print("Overwriting config file")
                break
    
    # Save the config file
    with open(f"configs/{config_name}.json", "w") as f:
        f.write(json.dumps(decks_parameters))


    print(f"Saved config file {config_name}")

def deck_setup(deck_number):
    print(f"Setting up deck {deck_number}")
    set_tempo_fader()
    set_jog()



# Set tempo faders

def set_tempo_fader():
    input("Set tempo fader to bottom. Press Enter when ready.")
    print("Move tempo fader to the top")
    # START RECORDING MIDI MESSAGES
    bottom_to_top_messages = [] # RECORD MIDI MESSAGES

    # STOP RECORDING MIDI MESSAGES WHEN PRESSED ENTER

    print("Move tempo fader to the bottom")
    # START RECORDING MIDI MESSAGES
    top_to_bottom_messages = [] # RECORD MIDI MESSAGES






    # Ask user to move fader down (fastest tempo) then up (slowest tempo)


def set_jog():
    pass
    # 
    # 1. Get jog touch code
    # 
    # 2. Turn wheel on edge
    # 3. Turn wheel on top

    # (check if it changes behaviour when touched)
    # if they are hte same we can rely on ON OFF note
    # else we can rely on MIDI code
    
    # 


if __name__ == "__main__":
    main()
