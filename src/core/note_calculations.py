#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Defines functions that realise calculations on notes'''

##-Imports
from src.representation.pitch import Pitch

##-Functions
def calculate_pitch_interval(note1: Pitch, note2: Pitch) -> float:
    '''
    Calculates the *interval* between `note1` and `note2`, in *tones*: `note2 - note1`.

    In:
        - note1: the first note
        - note2: the second note
    Out:
        the interval between `note1` and `note2`, in *tones*.
    '''

    return (note2 - note1) / 2

def calculate_intervals(notes: list[list[tuple[str|None, int|None] | int|float|None]]) -> list[float]:
    '''
    Compute the list of intervals between consecutive notes.

    - notes: the array of notes, following the format given in `extract_notes_from_query` ;

    Out: a list of intervals.
    '''

    intervals = []
    for i, event in enumerate(notes[:-1]):
        note1, octave1 = notes[i][0] # Taking only the first note for a chord.
        note2, octave2 = notes[i + 1][0]

        if None in (note1, octave1, note2, octave2):
            interval = None
        else:
            interval = calculate_pitch_interval(note1, octave1, note2, octave2)

        intervals.append(interval)

    return intervals

def calculate_intervals_list(notes_dict: dict) -> list[float]:
    '''
    Compute the list of intervals between consecutive notes.

    - notes_dict: a dictionary of nodes with their attributes, as returned by `extract_notes_from_query`.

    Output: a list of intervals between consecutive notes.
    '''
    # Extract Fact nodes (notes) from the dictionary
    fact_nodes = {node_name: attrs for node_name, attrs in notes_dict.items() if attrs.get('type') in ('Fact', 'rest') }

    # Initialize a list to hold pitches
    pitches = []


    for node_name, attrs in fact_nodes.items():
        note_class = attrs.get('class')
        octave = attrs.get('octave')
        type_ = attrs.get('type')
        if type_ == 'rest':
            pitches.append(None)
        elif note_class is not None and octave is not None:
            pitches.append([note_class, octave])
        else:
            # If note class or octave is missing, append 'NA'
            pitches.append('NA')

    # Compute intervals between consecutive pitches
    intervals = []
    for i in range(len(pitches) - 1):
        if pitches[i] is None or pitches[i+1] is None:
            interval = None
        elif pitches[i] == 'NA' or pitches[i+1] == 'NA':
            interval = 'NA'
        else:
            interval = calculate_pitch_interval(pitches[i][0], pitches[i][1], pitches[i+1][0], pitches[i+1][1])
        intervals.append(interval)

    return intervals

def calculate_dur_ratios_list(notes_dict: dict) -> list[float]:
    '''
    Compute the list of duration ratios between consecutive notes.

    - notes_dict: a dictionary of nodes with their attributes, as returned by `extract_notes_from_query`.

    Output: a list of duration ratios between consecutive notes.
    '''
    # Extract Fact nodes
    fact_nodes = {node_name: attrs for node_name, attrs in notes_dict.items() if attrs.get('type') in ('Fact', 'rest') }
    
    # Retrieve durations
    durations = [1.0/notes_dict[node].get('dur', None) for node in fact_nodes]
    dots = [notes_dict[node].get('dots', None) for node in fact_nodes]
    for idx, dot in enumerate(dots):
        if dot is not None:
            durations[idx] = durations[idx]*1.5
    
    # Compute duration ratios between consecutive events
    dur_ratios = []
    for i in range(len(durations) - 1):
        if durations[i] is None or durations[i+1] is None or durations[i] == 0:
            dur_ratio = None
        else:
            dur_ratio = durations[i+1] / durations[i]
        dur_ratios.append(dur_ratio)
    
    return dur_ratios

