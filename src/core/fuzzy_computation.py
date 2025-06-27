#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Creates fuzzy queries from given parameters'''

##-Imports
#---General
from math import ceil, floor, log2
import re

#---Project
from src.db.neo4j_connection import run_query
from src.representation.chord import Chord
from src.representation.duration import Duration
from src.representation.pitch import Pitch

##-Functions
def find_duration_range(duration, max_distance):
    actual_duration = 1/duration

    actual_min_duration = max(actual_duration - max_distance, 1/16)
    actual_max_duration = actual_duration + max_distance

    min_duration = round(1/actual_min_duration)
    max_duration = round(1/actual_max_duration)

    return min_duration, max_duration

def find_duration_range_decimal(duration, max_distance):
    actual_duration = duration

    actual_min_duration = max(actual_duration - max_distance, 1/16)
    actual_max_duration = actual_duration + max_distance

    return actual_min_duration, actual_max_duration

def find_duration_range_multiplicative_factor_sym(duration, factor, alpha = 0.0):
    """
    Calculates the range of durations for a triangular membership function with a given factor and alpha cut.

    Parameters:
        duration (float): The base duration value.
        factor (float): The multiplicative factor for duration (compression/expansion).
        alpha (float): The alpha cut value (0 <= alpha <= 1).

    Returns:
        tuple: A tuple containing the minimum and maximum durations.
    """
    if not (0 <= alpha <= 1):
        raise ValueError("Alpha must be between 0 and 1.")


    if factor < 1:
        factor = 1.0 /factor
    
    # Compute the distances between the peak and bounds
    if factor != 1:
        factor = (factor - 1) * (1 - alpha) + 1
        low_distance = duration - (duration * (1 / factor))
        high_distance = (duration * factor) - duration
    else:
        return duration, duration  # No range if factor == 1

    # Scale the distances by (1 - alpha)
    effective_low_distance = low_distance * (1 - alpha)
    effective_high_distance = high_distance * (1 - alpha)

    # Compute the effective bounds
    min_duration = duration - effective_low_distance
    max_duration = duration + effective_high_distance

    return min_duration, max_duration

def frequency_to_note(frequency):
    # Notes de référence pour une octave (Do = C)
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    # La fréquence de référence est A4 = 440 Hz
    A4_freq = 440.0
    A4_index = note_names.index('A') + 4 * 12  # Position de A4 dans la gamme

    # Calcul du nombre de demi-tons par rapport à A4
    n = round(12 * log2(frequency / A4_freq))

    # Calcul de la position dans la gamme
    note_index = (A4_index + n) % len(note_names)  # Cycle des notes
    octave = (A4_index + n) // len(note_names)     # Calcul de l'octave

    # Note et octave
    note = note_names[note_index]
    return f"{note}{octave:.0f}"

def find_nearby_pitches_old(pitch, octave, max_distance):
    pitch = convert_note_to_sharp(pitch)

    # Define pitches and their relative semitone positions from C
    # notes = ['c', 'd', 'e', 'f', 'g', 'a', 'b']
    # semitones_from_c = [0, 2, 4, 5, 7, 9, 11]  # C to B, cumulative semitone distance

    notes = ['c', 'c#', 'd', 'd#', 'e', 'f', 'f#', 'g', 'g#', 'a', 'a#', 'b']
    semitones_from_c = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    
    # Create a mapping from note to its index and semitone offset
    note_to_index = {note: idx for idx, note in enumerate(notes)}
    note_to_semitone = {note: semitones for note, semitones in zip(notes, semitones_from_c)}
    
    # Find the base semitone position for the given pitch and octave
    base_semitone = note_to_semitone[pitch] + (octave * 12)
    
    # Compute nearby notes within the maximum distance
    result = []
    oct_shift = 0
    keep_searching = True

    while keep_searching:
        keep_searching = False  # Assume no more octaves are needed unless we find one within range
        for note in notes:
            # Check higher octaves
            target_semitone_high = note_to_semitone[note] + ((octave + oct_shift) * 12)
            distance_high = abs(target_semitone_high - base_semitone)

            if distance_high <= max_distance:
                result.append((note, octave + oct_shift))
                keep_searching = True  # Continue searching (search space is symmetric)

            # Check lower octaves (only if oct_shift is not zero to avoid double counting the base octave)
            if oct_shift != 0:
                target_semitone_low = note_to_semitone[note] + ((octave - oct_shift) * 12)
                distance_low = abs(target_semitone_low - base_semitone)
                
                if distance_low <= max_distance:
                    result.append((note, octave - oct_shift))
                    keep_searching = True  # Continue searching (search space is symmetric)

        oct_shift += 1  # Increase the octave shift for the next loop iteration

    return result

def find_nearby_pitches(pitch, octave, pitch_distance):
    '''
    Return a list of all the notes in the range `pitch_distance` of the center note (`pitch` / `octave`).

    The distance function is the interval (number of semitones) between notes.

    - pitch          : the base pitch. Format example: 'c', 'cs', 'c#' ;
    - octave         : the octave of the note ;
    - pitch_distance : the maximum distance allowed, in tones.

    Out: a list of all near notes, in the format: `[(pitch, octave), ...]`.
    '''

    # Notes semitone by semitone from c
    notes = ['c', 'c#', 'd', 'd#', 'e', 'f', 'f#', 'g', 'g#', 'a', 'a#', 'b']

    pitch = convert_note_to_sharp(pitch)
    i = notes.index(pitch) # The relative semitone of the center note
    max_semitone_dist = int(2 * pitch_distance)

    res = []

    for semitone in range(i - max_semitone_dist, i + max_semitone_dist + 1):
        p = notes[semitone % len(notes)]
        o = octave + (semitone // len(notes))

        res.append((p, o))

    return res

def find_frequency_bounds(pitch: str, octave: int, max_distance: int, alpha: float = 0.0) -> tuple[int, int]:
    """
    Calculates the frequency bounds for a given pitch, octave, and maximum semitone distance.

    Parameters:
        pitch (str): The note name (e.g., 'c', 'c#', 'd', 'd#', ..., 'b').
        octave (int): The octave number.
        max_distance (int): The maximum number of tones away from the base note.
        alpha (float): The alpha threshold (0 ≤ alpha ≤ 1).

    Returns:
        tuple: A tuple containing the minimum and maximum frequencies (in Hz) as integers.
    """

    # Ensure pitch is in sharps
    pitch = convert_note_to_sharp(pitch)

    # Define note to semitone offset mapping from A
    note_to_semitone = {'a': 0, 'a#': 1, 'b': 2, 'c': 3, 'c#': 4, 'd': 5, 'd#': 6, 'e': 7, 'f': 8, 'f#': 9, 'g': 10, 'g#': 11}

    if pitch not in note_to_semitone:
        raise ValueError(f"Invalid pitch name: {pitch}")
        
    # Find the base semitone position for the given pitch and octave
    if pitch in ['a', 'a#', 'b']:
        base_semitone = note_to_semitone[pitch] + (octave * 12) + 21
    else :
        base_semitone = note_to_semitone[pitch] + ((octave - 1) * 12) + 21

    # Adjust max_distance based on alpha
    effective_distance_semitone =  2 * max_distance * (1 - alpha)

    # Compute the semitone bounds where the membership function equals alpha
    lower_bound_semitone = base_semitone - effective_distance_semitone
    upper_bound_semitone = base_semitone + effective_distance_semitone
    
    # Convert semitone bounds to frequencies
    min_frequency = 440 * 2 ** ((lower_bound_semitone - 69) / 12)
    max_frequency = 440 * 2 ** ((upper_bound_semitone - 69) / 12)
    
    return floor(min_frequency), ceil(max_frequency)

def split_note_accidental(note: str) -> tuple[str, str | None]:
    """
    Splits a note string into its base note and accidental.

    Accidentals:
        # or s: sharp
        b: flat
        n: natural
        x: double sharp
        bb: double flat

    Parameters:
        note (str): The note string (e.g., 'c', 'c#', 'db', 'cx', 'cn', 'ebb').

    Returns:
        tuple: A tuple containing the base note and accidental.
    """

    match = re.match(r'^([a-gA-G])((#|s|b|n|x|bb)?)$', note)

    if match:
        base_note = match.group(1).lower()
        accidental = match.group(2)

        if accidental == '':
            accidental = None

        elif accidental == '#': # Sharps are written with s here (in the database) (can be # or s in find_nearby_pitches)
            accidental = 's'

        return base_note.lower(), accidental

    else:
        raise ValueError(f"Invalid note name: {note}")

def sharpen(base_note: str) -> str:
    '''
    Sharpens `base_note`
    Calculates the enharmonically equivalent note to `base_note`#.

    In:
        - base_note: the base pitch, without any accidental.
    Out:
        the enharmonically equivalent note to `base_note`#, using a sharp notation.
    '''

    notes_semitones = ['c', 'c#', 'd', 'd#', 'e', 'f', 'f#', 'g', 'g#', 'a', 'a#', 'b']

    return notes_semitones[(notes_semitones.index(base_note) + 1) % len(notes_semitones)]

def flatten(base_note: str) -> str:
    '''
    Flattens `base_note`
    Calculates the enharmonically equivalent note to `base_note`b.

    In:
        - base_note: the base pitch, without any accidental.
    Out:
        the enharmonically equivalent note to `base_note`b, using a sharp notation.
    '''

    notes_semitones = ['c', 'c#', 'd', 'd#', 'e', 'f', 'f#', 'g', 'g#', 'a', 'a#', 'b']

    return notes_semitones[(notes_semitones.index(base_note) - 1) % len(notes_semitones)]

def convert_note_to_sharp(note: str) -> str: #TODO: remove this function and use Pitch
    '''
    Convert a note to its equivalent in sharp (if it is a flat).
    If the note has no accidental, it is not modified.

    If there is a natural, the accidental is removed.
    If there is a double sharp or a double flat, it is converted to remove the accidental.

    - note: a string of length 1 or 2 representing a musical note class (no octave).
             Sharp can be represented either with 's' or '#'.
             Flat can be represented either with 'f' of 'b'.

    Output: `note` with sharp represented as '#', or `note` unchanged if there was no accidental.
    '''

    base_note, accidental = split_note_accidental(note)

    if accidental == None:
        return base_note

    elif accidental in ('s', '#'): # Sharp
        return sharpen(base_note)

    elif accidental in ('b', 'f'): # Flat
        return flatten(base_note)

    elif accidental == 'n': # Natural
        return base_note

    elif accidental == 'x': # Double sharp
        return sharpen(sharpen(base_note))

    elif accidental == 'bb': # Double flat
        return flatten(flatten(base_note))

    else:
        raise ValueError(f'convert_note_to_sharp: accidental "{accidental}" not found!')


def note_distance_in_tones(note1, octave1, note2, octave2):
    '''Calculate the distance (in tones) between two notes.'''

    if note1 == None or note2 == None: # If one note is None, it means that the note is unspecified, so only check for octave distance
        if octave1 == None or octave2 == None:
            return 0

        else:
            return 12 * abs(octave2 - octave1) / 2

    #---Define the semitone distance from C for each note
    semitones_from_c = {
        'c': 0, 'c#': 1, 'd': 2, 'd#': 3, 'e': 4, 'f': 5, 'f#': 6, 
        'g': 7, 'g#': 8, 'a': 9, 'a#': 10, 'b': 11
    }

    #---Replace 's' with '#' and convert flat to sharp
    note1 = convert_note_to_sharp(note1)
    note2 = convert_note_to_sharp(note2)

    #---Manages when octave is None
    if octave1 == None and octave2 == None: # In this case, return the distance between notes as if it was in the same octave.
        octave1 = 4
        octave2 = 4

    # If one octave in None, set it to the other (so that the distance will be )
    elif octave1 == None:
        octave1 = octave2
    elif octave2 == None:
        octave2 = octave1
    
    #---Calculate the distances
    # Calculate the semitone position for each note
    semitone1 = semitones_from_c[note1] + (octave1 * 12)
    semitone2 = semitones_from_c[note2] + (octave2 * 12)
    
    # Calculate the absolute distance in semitones
    distance_in_semitones = abs(semitone2 - semitone1)
    
    # Convert semitones to tones (1 tone = 2 semitones)
    distance_in_tones = distance_in_semitones / 2
    
    return distance_in_tones

def pitch_degree(note1, octave1, note2, octave2, pitch_gap):
    if pitch_gap == 0:
        return 1.0

    # d = 1 - (note_distance_in_tones(note1, octave1, note2, octave2) / (pitch_gap + pitch_gap*0.1))
    d = 1 - (note_distance_in_tones(note1, octave1, note2, octave2) / pitch_gap)
    return max(d, 0)

def pitch_degree_with_intervals(interval1, interval2, pitch_gap):
    if pitch_gap == 0 or interval1 == None or interval2 == None:
        return 1.0

    # d = 1 - (abs(interval1 - interval2) / (pitch_gap + pitch_gap*0.1))
    d = 1 - (abs(interval1 - interval2) / pitch_gap)
    return max(d, 0)


def duration_degree(duration1, duration2, max_duration_distance):
    if max_duration_distance == 0:
        return 1.0
    # Calculate the absolute difference between the two durations
    duration_difference = abs(duration1 - duration2)
    
    # Calculate the degree based on the duration gap
    # degree = max(1 - (duration_difference / (max_duration_distance + max_duration_distance*0.1)), 0)
    degree = max(1 - (duration_difference / max_duration_distance), 0)
    
    return degree

def duration_degree_with_multiplicative_factor(expected_duration, duration, factor):
    if factor == 1.0 or expected_duration is None:
        return 1.0
    
    a = -1 / (factor - 1)
    b = 1 - a

    z = max(expected_duration / duration, duration / expected_duration)
    return a * z + b


def sequencing_degree(end_time1, start_time2, max_gap):
    if max_gap == 0:
        return 1.0
    
    # Calculate the gap between the end time of the first note and the start time of the second note
    time_gap = start_time2 - end_time1
    
    # Calculate the degree based on the maximum allowed gap
    # degree = max(1 - (time_gap / (max_gap + max_gap*0.1)), 0)
    degree = max(1 - (time_gap / max_gap), 0)
    
    return degree

def aggregate_note_degrees(aggregation_fn, pitch_degree, duration_degree, sequencing_degree):
    return aggregation_fn(pitch_degree, duration_degree, sequencing_degree)

def aggregate_sequence_degrees(aggregation_fn, degree_list):
    return aggregation_fn(*degree_list)

def aggregate_degrees(aggregation_fn, degree_list):
    return aggregation_fn(*degree_list)

def get_notes_from_source_and_time_interval(driver, source: str, start_time: float, end_time: float) -> list[Chord]:
    '''
    Queries the database to get the notes between `start_time` and `end_time` from `source`

    In:
        - driver: DB driver connection
        - source: a source to identify one score (the mei file name)
        - start_time: starting time
        - end_time: ending time

    Out:
        a list of notes
    '''

    query = f"""
    MATCH (e:Event)-[:IS]->(f:Fact)
    WHERE e.start >= {start_time} AND e.end <= {end_time} AND e.source = '{source}'
    RETURN f.class AS class, f.octave AS octave, f.type as type, f.accid as accid, f.accid_ges as accid_ges, e.dur AS dur, e.dots as dots, e.start as start, e.end as end
    ORDER BY e.start
    """

    results = run_query(driver, query)

    notes = []

    for record in results:
        # Note or rest
        if record['type'] == 'rest':
            p = Pitch('r', None, None)

        else:
            # Accidental
            if record['accid'] != None:
                accid = record['accid']
            elif record['accid_ges'] != None:
                accid = record['accid_ges']
            else:
                accid = None

            p = Pitch(record['class'], record['octave'], accid)

        c = Chord([p], Duration(record['dur']), record['dots'], record['start'], record['end'])

        notes.append(c)

    return notes

##-Run
if __name__ == "__main__":
    duration = 1.0
    factor = 2.0
    print(find_duration_range_multiplicative_factor_sym(duration, factor, 0.75))

    frequencies = [440, 261.63, 329.63, 493.88, 880, 30.87]
    for freq in frequencies:
        print(f"{freq:.2f} Hz -> {frequency_to_note(freq)}")

    print(duration_degree_with_multiplicative_factor(0.25, 0.125, 0.5))
