#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Defines functions that realise calculations on notes'''

##-Imports
from src.core.fuzzy_computation import convert_note_to_sharp

##-Functions
def calculate_base_stone(pitch, octave, accid=None):
    # Convert flat to sharp
    pitch = convert_note_to_sharp(pitch)

    # Define pitches and their relative semitone positions from C (piano changes octave on C)
    # notes_from_a = ['a', 'a#', 'b', 'c', 'c#', 'd', 'd#', 'e', 'f', 'f#', 'g', 'g#']
    notes_from_c = ['c', 'c#', 'd', 'd#', 'e', 'f', 'f#', 'g', 'g#', 'a', 'a#', 'b']
    # semitones_from_a = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    semitones_from_c = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

    # # Define pitches and their relative semitone positions from A
    # notes = ['a', 'b', 'c', 'd', 'e', 'f', 'g']
    # semitones_from_a = [0, 2, 3, 5, 7, 8, 10]  # A to G, cumulative semitone distance
    
    # Create a mapping from note to its index and semitone offset
    # note_to_semitone = {note: semitones for note, semitones in zip(notes, semitones_from_a)}
    note_to_semitone = {note: semitones for note, semitones in zip(notes_from_c, semitones_from_c)}
    
    # Find the base semitone position for the given pitch and octave
    # if pitch == 'a' or pitch == 'b' : # this is not needed as we do from c now (and not from a)
    #     base_semitone = note_to_semitone[pitch] + (octave * 12) + 21
    # else :
    #     base_semitone = note_to_semitone[pitch] + ((octave - 1) * 12) + 21

    base_semitone = note_to_semitone[pitch] + (octave * 12) + 21
    
    return base_semitone / 2.0

def calculate_pitch_interval(note1, octave1, note2, octave2):
    return calculate_base_stone(note2, octave2) - calculate_base_stone(note1, octave1)

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

