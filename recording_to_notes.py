#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''This file aims to implement a convertion from a recording to stave notes using spotify's basic-pitch tool'''

##-Imports
from basic_pitch.inference import predict

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

##-Main class
class RecordingToNotes:
    '''Uses basic-pitch to convert recording to notes readable by the backend'''

    def __init__(self, min_freq: float = 146, max_freq: float = 880, duration_with_dots: bool = False):
        '''
        Instanciates the object.

        In:
            - min_freq           : the minimum frequency for the output notes, in Hertz (defaults to D3 at 146Hz)
            - max_freq           : the maximum frequency for the output notes, in Hertz (defaults to A5 at 880Hz)
            - duration_with_dots : if True, can use dots for duration (e.g 8d). Otherwise, only use powers of two.
        '''
    
        self.min_freq = min_freq
        self.max_freq = max_freq

        if duration_with_dots:
            self.dur_convertion_dict = duration_note_with_dots
        else:
            self.dur_convertion_dict = duration_note

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

    def get_notes(self, fn: str) -> list[tuple[str, str]]:
        '''
        Uses basic_pitch's predict function to convert the input audio file `fn`, and make a list of notes.

        In:
            fn: the path to the input wav file

        Out:
            notes_list: `[(note, duration), ...]`, where `note` is in the form `C#/5`, and `duration` is in `w`, `h`, `hd`, ...
        '''

        _, _, note_events = predict(fn, minimum_frequency=self.min_freq, maximum_frequency=self.max_freq)

        # Sort notes by start time
        notes_data = sorted(note_events, key=lambda x: x[0])

        ret = []
        for n in notes_data:
            note = midi_to_note(n[2])
            duration = self._find_duration((n[1] - n[0]) / 2)

            ret.append((note, duration))

        return ret

##-Run
if __name__ == '__main__':
    from sys import argv

    C = RecordingToNotes()
    notes = C.get_notes(argv[1])

    print()
    print(notes)
