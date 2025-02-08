import mido
import threading
import queue

class MidiRecorder:
    def __init__(self, input_port_name):
        self.input_port_name = input_port_name
        self.recording = False
        self.messages = []
        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.lock = threading.Lock()
        self.running = True  # Controls the listener thread

    def _listen(self):
        """Background thread that listens for MIDI messages."""
        with mido.open_input(self.input_port_name) as port:
            for msg in port:
                if not self.running:  # Exit if stopped
                    break
                if self.recording:
                    self.queue.put(msg)

    def start(self):
        """Start recording messages."""
        with self.lock:
            self.messages.clear()
            self.recording = True

    def stop(self):
        """Stop recording and retrieve messages."""
        with self.lock:
            self.recording = False
            while not self.queue.empty():
                self.messages.append(self.queue.get())
            return self.messages  # Return captured messages

    def start_listener(self):
        """Start the listener thread."""
        self.thread.start()

    def stop_listener(self):
        """Stop the listener thread."""
        self.running = False
        self.thread.join()

# Example Usage
if __name__ == "__main__":
    # input_devices = mido.get_input_names()
    # print(f"Input Devices:{input_devices}")
    input_port = "controller"  # Change to your MIDI device name
    recorder = MidiRecorder(input_port)
    recorder.start_listener()

    input("Press Enter to start recording...")
    recorder.start()

    input("Press Enter to stop recording...")
    messages = recorder.stop()

    print("Recorded Messages:")
    for msg in messages:
        print(msg)

    recorder.stop_listener()
