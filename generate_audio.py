from pydub import AudioSegment
from pydub.generators import Sine
import numpy as np

# Frequency mapping for notes (A4 = 440 Hz)
note_frequencies = {
    'c': 261.63, 'c#': 277.18, 'd': 293.66, 'd#': 311.13, 'e': 329.63, 'f': 349.23,
    'f#': 369.99, 'g': 392.00, 'g#': 415.30, 'a': 440.00, 'a#': 466.16, 'b': 493.88
}

def convert_duration_to_seconds(note_duration, bpm=60):
    beat_duration = 60.0 / bpm
    duration_in_beats = 4 / note_duration  # Whole note is 4 beats, quarter note is 1 beat, etc.
    return duration_in_beats * beat_duration

def generate_note_audio(note, bpm=60):
    pitch, octave, dur = note
    frequency = note_frequencies[pitch.lower()] * (2 ** (octave - 4))
    duration_in_seconds = convert_duration_to_seconds(dur, bpm)
    sine_wave = Sine(frequency).to_audio_segment(duration=duration_in_seconds * 1000)  # duration in milliseconds
    return sine_wave

def generate_mp3(notes, file_name="output.mp3", bpm=60):
    song = AudioSegment.silent(duration=0)
    for note in notes:
        note_audio = generate_note_audio(note, bpm)
        song += note_audio
    song.export(file_name, format="mp3")

if __name__ == "__main__":
    # Example usage
    notes = [('c', 5, 1), ('d', 5, 4), ('e', 5, 8), ('f', 5, 4), ('g', 5, 1)]
    generate_mp3(notes, "output.mp3", bpm=60)
