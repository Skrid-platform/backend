#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Creates fuzzy queries from given parameters'''

##-Imports
#---General
import neo4j

#---Project
from src.db.neo4j_connection import run_query
from src.representation.chord import Chord
from src.representation.duration import Duration
from src.representation.pitch import Pitch

##-Functions
def find_duration_range_multiplicative_factor_sym(duration: float, factor: float, alpha: float = 0.0) -> tuple[float, float]:
    '''
    Calculates the range of durations for a triangular membership function with a given factor and alpha cut.

    Parameters:
        duration (float): The base duration value.
        factor (float): The multiplicative factor for duration (compression/expansion).
        alpha (float): The alpha cut value (0 <= alpha <= 1).

    Returns:
        tuple: A tuple containing the minimum and maximum durations.
    '''

    if not (0 <= alpha <= 1):
        raise ValueError('Alpha must be between 0 and 1.')


    if factor < 1:
        factor = 1.0 / factor
    
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

def pitch_degree(note1: Pitch, note2: Pitch, pitch_gap: float) -> float:
    '''
    Calculates the matching degree between `note1` and `note2`.
    It is used in the result processing in order to give a score to the found note compared to the query note.

    In:
        - note1: the first note to compare
        - note2: the second note to compare
        - pitch_gap: the pitch gap (fuzzy parameter)
    Out:
        a number in [0 ; 1] representing the match degree between `note1` and `note2`
    '''

    if pitch_gap == 0:
        return 1.0

    dist_in_tones = abs(note2 - note1) / 2
    d = 1 - (dist_in_tones / pitch_gap)

    return max(d, 0.0)

def pitch_degree_with_intervals(interval1: float | None, interval2: float | None, pitch_gap: float) -> float:
    '''
    Calculates the matching degree between `interval1` and `interval2`.
    It is used in the result processing in order to give a score to the found note compared to the query note.

    In:
        - interval1: the first interval to compare
        - interval2: the second interval to compare
        - pitch_gap: the pitch gap (fuzzy parameter)
    Out:
        a number in [0 ; 1] representing the match degree between both intervals
    '''

    if pitch_gap == 0 or interval1 == None or interval2 == None:
        return 1.0

    # d = 1 - (abs(interval1 - interval2) / (pitch_gap + pitch_gap*0.1))
    d = 1 - (abs(interval1 - interval2) / pitch_gap)
    return max(d, 0.0)


def duration_degree_with_multiplicative_factor(expected_duration: Duration, duration: Duration, factor: float) -> float:
    '''
    Calculates the matching degree between `expected_duration` and `duration`.
    It is used in the result processing in order to give a score to the found note compared to the query note.

    In:
        - expected_duration: the expected duration (from the query)
        - duration: the actual duration (from the result)
        - factor: the duration factor (fuzzy parameter)
    Out:
        a number in [0 ; 1] representing the match degree between both durations
    '''

    if factor == 1.0 or expected_duration.dur is None:
        return 1.0
    
    a = -1 / (factor - 1)
    b = 1 - a

    z = max(expected_duration.to_float() / duration.to_float(), duration.to_float() / expected_duration.to_float())
    return a * z + b


def sequencing_degree(end_time1: float, start_time2: float, max_gap: float) -> float:
    '''
    Calculates the matching degree between `end_time1` and `start_time2`.
    It is used in the result processing in order to give a score to the found note compared to the query note.

    In:
        - end_time1: the time at the end of the previous note
        - start_time2: the time at the start of the current note
        - max_gap: the maximum gap allowed (fuzzy parameter)
    Out:
        a number in [0 ; 1] representing the match degree concerning the time sequencing.
    '''

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


def get_notes_from_source_and_time_interval(driver: neo4j.Driver, source: str, start_time: float, end_time: float) -> list[Chord]:
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
        # print(f"{freq:.2f} Hz -> {frequency_to_note(freq)}")
        print(f"{freq:.2f} Hz -> {Pitch(None, None).from_frequency(freq)}")

    print(duration_degree_with_multiplicative_factor(0.25, 0.125, 0.5))
