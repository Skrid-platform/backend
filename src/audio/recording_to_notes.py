#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''This file aims to implement a convertion from a recording to stave notes using spotify's basic-pitch tool'''

##-Imports
#---General
from basic_pitch.inference import predict
from music21 import converter, instrument, chord, note, stream

from random import randint
import os

#---Project
from src.representation.chord import Pitch, Duration, Chord

##-Functions
def get_notes_chords_rests(midi_input) -> list[Chord]:
    '''
    Gets the notes from a midi file.
    More precisely, gets the notes, rests and chords.

    In:
        - midi_input: the input midi file

    Out:
        chord_list: the list of notes
    '''

    try:
        midi = converter.parse(midi_input)
        parts = instrument.partitionByInstrument(midi)

    except Exception as e:
        print(f'Exception: {e}')
        raise ValueError(f'Midi file not well formatted !')

    chord_list = []

    for music_instrument in parts:
        for element_by_offset in stream.iterator.OffsetIterator(music_instrument):
            for entry in element_by_offset:
                if entry.duration.isComplex:
                    dur = entry.duration.components[0].type
                else:
                    dur = entry.duration.type

                if isinstance(entry, note.Note):
                    chord_list.append(Chord([Pitch(str(entry.pitch))], Duration(dur), entry.duration.dots))

                elif isinstance(entry, chord.Chord):
                    pitches = [Pitch(str(n.pitch)) for n in entry.notes]
                    chord_list.append(Chord(pitches, Duration(dur), entry.duration.dots))

                elif isinstance(entry, note.Rest):
                    chord_list.append(Chord([Pitch('r')], Duration(dur), entry.duration.dots))

    return chord_list

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

    def get_notes(self, fn: str) -> list[Chord]:
        '''
        Uses basic_pitch's predict function to convert the input audio file `fn`, and make a list of notes.
        To make the list of notes, it uses `music21` (to read the midi data).

        In:
            fn: the path to the input wav file

        Out:
            chord_list: the list of notes
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

        # Remove all the silences from the generated notes
        ret = [c for c in notes if not c.is_silence()]

        return ret

##-Run
if __name__ == '__main__':
    from sys import argv

    C = RecordingToNotes()
    notes = C.get_notes(argv[1])

    print()
    print(notes)
