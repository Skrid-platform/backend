#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Manages audio generation from notes'''

##-Imports
#---General
from pydub import AudioSegment
from pydub.generators import Sine
import numpy as np
import os

#---Project
from src.representation.chord import Chord, Duration, Pitch

##-Init
# Frequency mapping for notes (A4 = 440 Hz)
note_frequencies = {
    'c': 261.63, 'c#': 277.18, 'd': 293.66, 'd#': 311.13, 'e': 329.63, 'f': 349.23,
    'f#': 369.99, 'g': 392.00, 'g#': 415.30, 'a': 440.00, 'a#': 466.16, 'b': 493.88
}

##-Functions
# Helper function to convert duration from beats to seconds
def convert_duration_to_seconds(note_duration, bpm=60):
    beat_duration = 60.0 / bpm
    duration_in_beats = 4 * note_duration  # Whole note is 4 beats, quarter note is 1 beat, etc.
    return duration_in_beats * beat_duration # Adjusted for beats per measure

def generate_piano_like_wave(frequency: float, duration_ms, sample_rate=44100):
    # Generate primary sine wave for the fundamental frequency
    t = np.linspace(0, duration_ms / 1000, int(sample_rate * duration_ms / 1000), False)
    wave = 0.6 * np.sin(2 * np.pi * frequency * t)
    
    # Adding harmonics with reduced amplitude to simulate piano timbre
    wave += 0.3 * np.sin(2 * np.pi * frequency * 2 * t)  # First overtone
    wave += 0.2 * np.sin(2 * np.pi * frequency * 3 * t)  # Second overtone
    wave += 0.1 * np.sin(2 * np.pi * frequency * 4 * t)  # Third overtone
    
    # Applying ADSR Envelope
    attack_time = int(0.05 * sample_rate)  # 5% of the sample rate for attack
    decay_time = int(0.1 * sample_rate)    # 10% for decay
    sustain_level = 0.7                    # Sustain level at 70% of peak
    release_time = int(0.2 * sample_rate)  # 20% for release

    envelope = np.ones_like(wave)
    
    # Attack: Linear increase
    envelope[:attack_time] = np.linspace(0, 1, attack_time)
    
    # Decay: Linear decrease to sustain level
    envelope[attack_time:attack_time + decay_time] = np.linspace(1, sustain_level, decay_time)
    
    # Sustain: Constant level
    sustain_end = -release_time
    envelope[attack_time + decay_time:sustain_end] = sustain_level
    
    # Release: Linear decrease to zero
    envelope[sustain_end:] = np.linspace(sustain_level, 0, release_time)

    # Apply the envelope to the wave
    wave = wave * envelope
    
    return wave

def generate_piano_like_note(frequencies: list[float], duration_ms, sample_rate=44100):
    wave = sum(generate_piano_like_wave(f, duration_ms, sample_rate) for f in frequencies)

    # Convert to 16-bit audio segment
    audio_segment = AudioSegment(
        (wave * 32767).astype(np.int16).tobytes(),
        frame_rate=sample_rate,
        sample_width=2,
        channels=1
    )
    
    return audio_segment

def generate_note_audio(note, bpm=60):
    pitch, octave, dur = note.pitch, note.octave, note.dur
    
    if pitch is None or octave is None:
        # Generate silence for the duration of the rest
        duration_in_seconds = convert_duration_to_seconds(dur, bpm)
        silence = AudioSegment.silent(duration=duration_in_seconds * 1000)  # duration in milliseconds
        return silence
    else:
        # Generate the sine wave for the note
        frequency = note_frequencies[pitch.lower()] * (2 ** (octave - 4))
        duration_in_seconds = convert_duration_to_seconds(dur, bpm)
        # sine_wave = Sine(frequency).to_audio_segment(duration=duration_in_seconds * 1000)  # duration in milliseconds
        sine_wave = generate_piano_like_note(frequency, duration_in_seconds * 1000)
        return sine_wave

def generate_mp3(notes: list[Chord], file_name: str, audio_dir: str, bpm=60, overlap_ms=200, sample_rate=44100):
    song = AudioSegment.silent(duration=0)  # Initialize an empty song

    # Process each note
    for idx, note in enumerate(notes):
        duration = note.get_duration_dots_float()
        pitch = note.pitches[0].get_class_accid() # Get the first note of the chord to see if it is a silence or None

        # Check if it's a rest
        if pitch in (None, 'r') and duration is not None:
            duration_ms = int(convert_duration_to_seconds(duration, bpm) * 1000)
            rest_audio = AudioSegment.silent(duration=duration_ms)
            song = song.append(rest_audio, crossfade=0)  # Append rest without crossfade
            continue

        # frequency = note_frequencies[pitch.lower()] * (2 ** (octave - 4))
        frequencies = [p.get_frequency() for p in note.pitches]
        if 0 not in frequencies:
            duration_ms = int(convert_duration_to_seconds(duration, bpm) * 1000)
            note_audio = generate_piano_like_note(frequencies, duration_ms + overlap_ms, sample_rate=sample_rate)

            # Append the note, overlapping the release with the previous note
            if idx == 0:
                song = song.append(note_audio, crossfade=0)
            else:
                song = song.append(note_audio, crossfade=overlap_ms)

    file_path = os.path.join(audio_dir, file_name)
    song.export(file_path, format="mp3")
    print(f"Generated MP3: {file_path}")


if __name__ == "__main__":
    # Example usage
    # notes = [Note('c', 5, 8), Note('d', 5, 4), Note('e', 5, 8), Note('f', 5, 4), Note('g', 5, 16)]
    notes = [
        Chord([Pitch(('c', 5))], Duration(8), 0),
        Chord([Pitch(('d', 5))], Duration(4), 0),
        Chord([Pitch(('e', 5))], Duration(8), 0),
        Chord([Pitch(('f', 5))], Duration(4), 0),
        Chord([Pitch(('g', 5))], Duration(16), 0)
    ]
    generate_mp3(notes, "output.mp3", "./audio/output/", bpm=60)
