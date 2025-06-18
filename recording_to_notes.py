#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''This file aims to implement a convertion from a recording to stave notes using spotify's basic-pitch tool'''

##-Imports
from basic_pitch.inference import predict
from music21 import converter, instrument, chord, note, stream

from random import randint
import os

##-Init
duration_note_with_dots = {
    '32': 1/32,         # thirty-second (triple croche)
    '32d': 1/32 + 1/64, # dotted thirty-second (triple croche pointée)
    '16': 1/16,         # sixteenth (double croche)
    '16d': 1/16 + 1/32, # dotted sixteenth (double croche pointée)
    '8': 1/8,           # eighth (croche)
    '8d': 1/8 + 1/16,   # dotted eighth (croche pointée)
    'q': 1/4,           # (quarter)
    'qd': 1/4 + 1/8,    # (dotted quarter)
    'h': 1/2,           # (half)
    'hd': .5 + .25,     # (dotted half)
    'w': 1              # (whole)
}
duration_note = {
    '32': 1/32,         # thirty-second (triple croche)
    '16': 1/16,         # sixteenth (double croche)
    '8': 1/8,           # eighth (croche)
    'q': 1/4,           # (quarter)
    'h': 1/2,           # (half)
    'w': 1              # (whole)
}

convert_music21_duration_types = {
    'whole': 'w',
    'half': 'h',
    'quarter': 'q',
    'eighth': '8',
    '16th': '16',
    '32nd': '32'
}

##-Functions
def midi_to_note(pitch: int) -> str:
    '''
    Convert a midi pitch to a note.
    E.g 72 -> 'C/5'

    In:
        pitch: the midi pitch

    Out:
        note: the string representation of the note
    '''

    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    octave = pitch // 12 - 1
    note = notes[pitch % 12]

    return f'{note}/{octave}'

def get_notes_chords_rests(midi_input) -> list[tuple[str | list[str], str, int]]:
    '''
    Gets the notes from a midi file.
    More precisely, gets the notes, rests and chords.

    In:
        - midi_input: the input midi file

    Out:
        note_list: the list of notes, in the following format:
            `[(class, duration, dots, duration_fraction), ...]`

        `class` is the class of the note (e.g 'C4'), or the list of notes (for a chord, e.g ['C4', 'E4'])
        `duration` is the type of duration (e.g 'quarter')
        `dots` is the number of dots
        `duration_fraction` is the duration as a float, including the dots (quarter = 1, eight = 0.5, eight with one dot = 0.75, ...)
    '''

    try:
        midi = converter.parse(midi_input)
        parts = instrument.partitionByInstrument(midi)

    except Exception as e:
        print(f'Exception: {e}')
        raise ValueError(f'Midi file not well formatted !')

    note_list = []

    for music_instrument in parts:
        for element_by_offset in stream.iterator.OffsetIterator(music_instrument):
            for entry in element_by_offset:
                if entry.duration.isComplex:
                    dur = entry.duration.components[0].type
                else:
                    dur = entry.duration.type

                if isinstance(entry, note.Note):
                    note_list.append((str(entry.pitch), dur, entry.duration.dots))

                elif isinstance(entry, chord.Chord):
                    notes = [str(n.pitch) for n in entry.notes]
                    note_list.append((notes, dur, entry.duration.dots))

                elif isinstance(entry, note.Rest):
                    note_list.append(('r', dur, entry.duration.dots))

    return note_list

##-Main class
class RecordingToNotes:
    '''Uses basic-pitch to convert recording to notes readable by the backend'''

    def __init__(self, min_freq: float = 146, max_freq: float = 880):
        '''
        Instanciates the object.

        In:
            - min_freq           : the minimum frequency for the output notes, in Hertz (defaults to D3 at 146Hz)
            - max_freq           : the maximum frequency for the output notes, in Hertz (defaults to A5 at 880Hz)
            - duration_with_dots : if True, can use dots for duration (e.g 8d). Otherwise, only use powers of two.
        '''
    
        self.min_freq = min_freq
        self.max_freq = max_freq

        # duration_with_dots = False
        # if duration_with_dots:
        #     self.dur_convertion_dict = duration_note_with_dots
        # else:
        #     self.dur_convertion_dict = duration_note

    def _find_duration(self, dur: float) -> str:
        '''
        From a duration in seconds, find the closest duration in the array [`w`, `h`, `q`, `8`, `16`, `32`] (depending on `dct`: it is `dct.keys()`).

        In:
            dur: the duration in seconds

        Out:
            the corresponding note duration (as a string).
        '''

        for d in self.dur_convertion_dict:
            if dur <= self.dur_convertion_dict[d]:
                return d

        return 'w'

    def get_notes_old(self, fn: str) -> list[tuple[str, str]]:
        '''
        Uses basic_pitch's predict function to convert the input audio file `fn`, and make a list of notes.

        In:
            fn: the path to the input wav file

        Out:
            notes_list: `[(note, duration), ...]`, where `note` is in the form `C#/5`, and `duration` is in `w`, `h`, `hd`, ...
        '''

        # Get note_events, in the format (start_time_s, end_time_s, pitch_midi, amplitude, bends)
        # Bends is in unit of 1/3 semitones
        _, _, note_events = predict(fn, minimum_frequency=self.min_freq, maximum_frequency=self.max_freq)

        # Sort notes by start time
        notes_data = sorted(note_events, key=lambda x: x[0])

        ret = []
        for n in notes_data:
            note = midi_to_note(n[2])
            duration = self._find_duration((n[1] - n[0]) / 2)

            ret.append((note, duration))

        return ret

    def get_notes(self, fn: str) -> list[tuple[tuple[str | list[str]], str, int]]:
        '''
        Uses basic_pitch's predict function to convert the input audio file `fn`, and make a list of notes.
        To make the list of notes, it uses `music21` (to read the midi data).

        In:
            fn: the path to the input wav file

        Out:
            notes_list: `[(note, duration, dots), ...]`, where
            `note` is in the form `C#/5`, or is a list of notes (for a chord),
            `duration` is in `w`, `h`, ...
            `dots` is the number of dots for the note
        '''

        # Get the midi data, and write it to a temporary file
        _, midi_event, _ = predict(fn, minimum_frequency=self.min_freq, maximum_frequency=self.max_freq)

        nonce = randint(100000, 9999999)
        fn = f'uploads/tmp_{nonce}.mid'
        midi_event.write(fn)

        # Analyse the midi file
        notes = get_notes_chords_rests(fn)

        # Delete the temporary midi file
        os.remove(fn)

        ret = []
        beg = True # Used to remove the silences at the beginning
        for n in notes:
            # Remove trailing silences
            if beg and n[0] == 'r':
                continue

            beg = False

            # Convert duration
            dur = convert_music21_duration_types[n[1]]

            # Add a slash in the pitches, and repalce '-' by 'b' (flat)
            if n[0] == 'r':
                pitch = 'r'
            elif type(n[0]) == str:
                pitch = n[0][:-1].replace('-', 'b') + '/' + n[0][-1]
            else:
                pitch = [k[:-1].replace('-', 'b') + '/' + k[-1] for k in n[0]]

            if pitch != 'r': # Removing all the silences from the notes, it gives a better result.
                ret.append((pitch, dur, n[2]))

        return ret

##-Run
if __name__ == '__main__':
    from sys import argv

    C = RecordingToNotes()
    notes = C.get_notes(argv[1])

    print()
    print(notes)
