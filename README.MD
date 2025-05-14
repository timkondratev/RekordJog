# RekordJog: a translator from third-party controllers to Rekordbox.

## Description

This program allows jog wheels and pitch control on third-party controllers to work in Rekordbox 6 and 7. Currently out of the box supported and tested Devices are:
-   Allen & Heath
    -   Xone:4D
-   Hercules DJControl
    -   Inpulse 200
    -   Mix
- Numark
    -   Mixtrack 3

To use it with other controllers, you'll need to find the MIDI calls and their pattern using MIDI-OX or a similar tool and modify the source code accordingly. Feel free to send a Pull Request!

Please note that a paid subscription for AlphaTheta (Pioneer) Rekordbox 6 is required for this program to run properly.

## Installation MacOS/Linux

1. Download/Clone the repository and open the directory in Terminal.
2. Create a virtual environment:
```bash
python3 -m venv .venv
```
3. Activate the virtual environment:
```bash
source .venv/bin/activate
```
4. Install requirements:
```bash
pip3 install -r requirements.txt
```
5. Copy and replace the DDJ-SX Mapping in Rekordbox' installation folder with the files found in "pioneer_mappings"
```bash
MACOSPATH_HERE
```

## Installation Windows
### Prerequisites
    loopMIDI: https://www.tobias-erichsen.de/software/loopmidi.html
    Create a device in loopMIDI called "PIONEER DDJ-SX
    Note: The virtual DDJ-SX created in loopMIDI is only available while loopMIDI is running!

1. Download/Clone the repository and open the directory in Terminal.
2. Create a virtual environment:
```bash
python -m venv .venv
```
3. Activate the virtual environment:
```bash
.venv\Scripts\activate.bat
```
4. Install requirements:
```bash
pip install -r requirements.txt
```
5. Copy and replace the DDJ-SX Mapping in Rekordbox' installation folder with the files found in `pioneer_mappings`
```bash
"C:\Program Files\Pioneer\rekordbox [VERSION]\MidiMappings"
```

## Usage
1. Windows Only: Start loopMIDI
2. Open the RekordJog directory in Terminal.
3. Launch the app in Terminal:
```bash
python3 RekordJog_YourDevice.py
```
4. Select your Devices
5. Open Rekordbox.
6. (Optional) Import MIDI mapping for your controller from `midi_mappings` directory. Everything should work now.
5. When the DJ session is over, stop the app by pressing `Ctrl+C` in the Terminal where the app was launched. In some cases you need to touch a jogweel once if it isn't closing immediately.

## MIDI mappings and specialties for different controllers:
### Hercules DJControl
You need to go to "MIDI" and change the Setting for PIONEER DDJ-SX Tempo from 0h-3FFFh to 0h-7Fh in order for the tempo sliders to work!

### Allen & Heath Xone:4D

For better precision, 2 faders are used for each deck pitch control. 2-nd fader increments smaller values.

## For Developers:
### How to map jog wheels

First, you need to figure out what MIDI message is sent on your jog turn. Then analyze which values are sent at different rotation speed.

In my controller, the jogs send values between 1 and 30 clockwise and between 127 and 98 counter clockwise. Notice that the total number of possible values is limited and there was a noticeable gap between them, you can see all possible values and what I mapped them to in code below:

```
CONV_J_VAL = {
    1:65,
    2:66,
    4:67,
    7:69,
    11:71,
    16:73,
    20:75,
    30:80,
    
    127:63,
    126:62,
    124:61,
    121:59,
    117:57,
    112:55,
    108:53,
    98:48
    }
```

As you can see from this mapping, rekordbox expects neutral value to be 64 (although it is never used), and this value is increased for CW rotation and decreased for CCW rotation. The scale is also different, so for the value of 30 I add 16 to the neutral position.

I used this article as a reference. There is a lot of useful information. https://djtechtools.com/2017/05/08/hack-rekordbox-use-controllers-jogwheels/

And also these resources were handy:

Pioneer DDJ-SX reference for MIDI mapping: https://www.pioneerdj.com/-/media/pioneerdj/software-info/controller/ddj-sx/ddj-sx_list_of_midi_messages_e.pdf 

You can also find Pioneer DDJ-SX MIDI mapping in Rekordbox source files. For mac the file is at: `/Applications/rekordbox 6/rekordbox.app/Contents/Resources/MidiMappings/PIONEER DDJ-SX.midi.csv`

Hex to decimal converter: https://www.rapidtables.com/convert/number/hex-to-decimal.html

MIDI messages reference: https://www.midi.org/specifications-old/item/table-2-expanded-messages-list-status-bytes

https://www.midi.org/specifications-old/item/table-3-control-change-messages-data-bytes-2
