#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Defines functions that realise calculations on notes'''

##-Imports
from src.representation.chord import Chord, Duration, Pitch

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

def calculate_intervals_list(notes_dict: dict) -> list[float]:
    '''
    Compute the list of intervals between consecutive notes.

    - notes_dict: a dictionary of nodes with their attributes, as returned by `extract_notes_from_query`.

    Output: a list of intervals between consecutive notes.
    '''

    # Extract Fact nodes (notes) from the dictionary
    event_nodes = {node_name: attrs for node_name, attrs in notes_dict.items() if attrs.get('type') == 'Event' }

    # Initialize a list to hold pitches
    pitches = []


    for event_name in event_nodes:
        # Get the first Fact child of the Event node
        fact_name = event_nodes[event_name]['children'][0]

        attrs = notes_dict[fact_name]

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
            interval = calculate_pitch_interval(Pitch((pitches[i][0], pitches[i][1])), Pitch((pitches[i+1][0], pitches[i+1][1])))
        intervals.append(interval)

    return intervals

def calculate_chord_intervals(query_nodes: dict[str, dict[str, int | str | list[str]]]) -> list[str]:
    '''
    Creates the conditions for the WHERE clause for the chords when using transposition.

    When transposition is allowed, the search is made on intervals between Events.
    For chords, we use the lowest note of the chord as a reference to calculate the intervals with other Events (should be done in data-ingestion).
    It is also needed to check, in the query, that the intervals between the pitches in the same chord are the same. This is what does this function (calculate conditions to ensure this).

    In:
        - query_nodes: the dictionary of notes, as returned by `extract_notes_from_query`
    Out:
        the conditions to add to the WHERE clause (will need to be separated by 'AND')
    '''

    conditions = []

    for var_name in query_nodes:
        attrs = query_nodes[var_name]

        if attrs['type'] == 'Event':
            if len(attrs['children']) >= 2: # at least two pitches to make a chord
                pitches_and_name = []

                # Retreive all the pitches of the chord
                for pitch_name in attrs['children']:
                    p_attrs = query_nodes[pitch_name]

                    accid = None
                    if 'accid' in p_attrs:
                        accid = p_attrs['accid']
                    elif 'accid_ges' in p_attrs:
                        accid = p_attrs['accid_ges']

                    p = Pitch((p_attrs['class'], p_attrs['octave'], accid))

                    pitches_and_name.append((pitch_name, p))

                # Calculate the intervals and make the conditions
                n0 = pitches_and_name[0][0] # first pitch of the chord (name)
                p0 = pitches_and_name[0][1] # (pitch)

                for name, p in pitches_and_name[1:]:
                    cond = f'{name}.halfTonesFromA4 - {n0}.halfTonesFromA4 = {p - p0}'
                    conditions.append(cond)

    
    return conditions


def calculate_dur_ratios_list(notes_dict: dict) -> list[float]:
    '''
    Compute the list of duration ratios between consecutive notes.

    - notes_dict: a dictionary of nodes with their attributes, as returned by `extract_notes_from_query` (needs at least the `Event` nodes).

    Output: a list of duration ratios between consecutive notes.
    '''

    # Extract Event nodes
    # fact_nodes = {node_name: attrs for node_name, attrs in notes_dict.items() if attrs.get('type') in ('Fact', 'rest') }
    event_nodes = {node_name: attrs for node_name, attrs in notes_dict.items() if attrs.get('type') == 'Event' }
    
    # Retrieve durations
    durations = [1.0/notes_dict[node].get('dur', None) for node in event_nodes]
    dots = [notes_dict[node].get('dots', None) for node in event_nodes]
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

