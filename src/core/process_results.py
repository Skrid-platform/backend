#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Processes the results of crisp queries in order to rank them'''

##-Imports
#---General
import os
import shutil
import json

from neo4j import Record

#---Project
from src.core.extract_notes_from_query import (
    extract_fuzzy_parameters,
    extract_attributes_with_membership_functions,
    extract_fuzzy_membership_functions,
    extract_notes_from_query_dict
)
from src.core.fuzzy_computation import (
    pitch_degree,
    get_notes_from_source_and_time_interval,
    sequencing_degree,
    aggregate_note_degrees,
    aggregate_sequence_degrees,
    aggregate_degrees,
    pitch_degree_with_intervals,
    duration_degree_with_multiplicative_factor
)
from src.representation.chord import Chord, Duration, Pitch
from src.core.note_calculations import calculate_intervals_list, calculate_dur_ratios_list
from src.audio.generate_audio import generate_mp3


##-Types
#---For the internal representation of the results (output of `process_results_to_dict`)
pitch_type = dict[str, str | int | None]                    # {'class': str, 'octave': int, 'accid': str | None}
note_type = dict[str, int | float | str | list[pitch_type]] # {'dur': int, 'dots': int, 'start': float, 'end': float, 'id': str, 'pitches': list[pitch_type]}
note_match_type = dict[str, int | str | note_type]          # {'note_deg': int, 'pitch_deg': int, 'duration_deg': int, 'sequencing_deg': int, 'membership_functions_degrees': str, 'note': note_type}
match_type = dict[str, str | float | list[note_match_type]] # {'source': str, 'start': float, 'end': float, 'overall_degree': float, 'notes': list[note_match_type]}

#---For the output of the API (output of `unify_results`)
note_match_out_type = dict[str, int | str] # {'pitch_deg': int, 'duration_deg': int, 'sequencing_deg': int, 'id': str}
match_out_type = dict[str, int | list[note_match_out_type]] # {'overall_degree': int, 'notes': list[note_match_out_type]}
file_matches_out_type = dict[str, str | int | list[match_out_type]] # {'source': str, 'number_of_occurrences': int, 'max_match_degree': int, 'matches': list[match_out_type]}


##-Functions
def min_aggregation(*degrees):
    return min(degrees)

def average_aggregation(*degrees):
    return sum(degrees) / len(degrees)

def almost_all(degree):
    high_bound, low_bound = 1.0, 0.5
    if degree > high_bound:
        return 1.0
    elif degree < low_bound:
        return 0.0
    else:
        return (degree - low_bound) / (high_bound - low_bound)

def almost_all_aggregation(*degrees):
    average = sum(degrees) / len(degrees)
    return almost_all(average)


def almost_all_aggregation_yager(*degrees):
    # Sort the degrees in ascending order and get distinct values
    sorted_degrees = sorted(set(degrees))

    # Initialize the result
    max_min_alpha_degree = 0

    # Iterate over all distinct alpha cuts
    for alpha in sorted_degrees:
        # Compute the alpha cut
        A_alpha = [degree for degree in degrees if degree >= alpha]
        # Calculate the degree of the alpha cut
        A_alpha_degree = almost_all(sum(A_alpha) / len(degrees))
        # Calculate min
        min_alpha_degree = min(alpha, A_alpha_degree)
        # Update the maximum of these minimum values
        max_min_alpha_degree = max(max_min_alpha_degree, min_alpha_degree)

    return max_min_alpha_degree

def get_ordered_results_2(result, query) -> list[
    tuple[
        str,
        float,
        float,
        float,
        list[tuple[Chord, float, float, float, float, str]]
    ]
]:
    """
    Extracts and ranks query results based on fuzzy degrees, handling cases with or without transposition,
    and supporting arbitrary membership functions.

    Parameters:
        result (list): The list of records returned from the query execution.
        query (str): The original query string.

    Returns:
        list: A sorted list of sequences, each containing source, start, end, degree, and note details.
    """

    # Extract the query notes and fuzzy parameters
    query_notes = extract_notes_from_query_dict(query)
    fact_nodes = {node_name: attrs for node_name, attrs in query_notes.items() if 'type' in attrs and attrs['type'] == 'Fact'}
    event_nodes = {node_name: attrs for node_name, attrs in query_notes.items() if 'type' in attrs and attrs['type'] == 'Event'}

    pitch_gap, duration_factor, sequencing_gap, alpha, allow_transpose, allow_homothety = extract_fuzzy_parameters(query)
    
    # Extract membership functions and their associated attributes
    attributes_with_membership_functions = extract_attributes_with_membership_functions(query)
    membership_functions = extract_fuzzy_membership_functions(query)
    
    # Build the aliases used in the return clause for these attributes
    attribute_aliases = []
    for node_name, attribute_name, membership_function_name in attributes_with_membership_functions:
        alias = f"{attribute_name}_{node_name}_{membership_function_name}"
        attribute_aliases.append((alias, node_name, attribute_name, membership_function_name))

    if allow_transpose:
        intervals = calculate_intervals_list(query_notes)
    if allow_homothety:
        duration_ratios = calculate_dur_ratios_list(query_notes)

    note_sequences: list[tuple[
        list[tuple[Chord, float|None, float|None]], # note, interval, duration_ratio
        str, # source
        float, # start
        float # end
    ]] = []
    stored_attribute_values = []  # To store attribute values for membership function computation
    
    # Fill `note_sequences`
    for record in result:
        note_sequence: list[tuple[Chord, float | None, float | None]] = []
        
        attribute_values = {}  # Store attribute values for this record
        fact_nb = 0

        for event_nb, event in enumerate(event_nodes):
            # Add all the attributes from the Event node
            duration = record[f"duration_{event_nb}"]
            dots = record[f"dots_{event_nb}"]
            start = record[f"start_{event_nb}"]
            end = record[f"end_{event_nb}"]
            id_ = record[f"id_{event_nb}"]

            interval, duration_ratio = None, None
            if allow_transpose:
                if event_nb > 0:
                    interval = record[f"interval_{event_nb - 1}"]

            if allow_homothety:
                if event_nb > 0:
                    duration_ratio = record[f"duration_ratio_{event_nb - 1}"]

            # Add all the attributes from the Facts nodes
            pitches = []
            for fact_var_name in event_nodes[event]['children']:
                pitch = record[f"pitch_{fact_nb}"]
                octave = record[f"octave_{fact_nb}"]

                accid = record[f"accid_{fact_nb}"]
                if accid is None:
                    accid = record[f"accid_ges_{fact_nb}"]

                fact_nb += 1

                pitches.append(Pitch((pitch, octave, accid)))

            note = Chord(pitches, Duration(duration), dots, start, end, id_)

            note_sequence.append((note, interval, duration_ratio))
        
            # Store membership function attribute values
            for alias, node_name, attribute_name, membership_function_name in attribute_aliases:
                attribute_values[alias] = record[alias]

        stored_attribute_values.append(attribute_values)
        note_sequences.append((note_sequence, record['source'], record['start'], record['end']))
    
    sequence_details: list[
        tuple[
            str,
            float,
            float,
            float,
            list[tuple[Chord, float, float, float, float, str]]
        ]
    ] = []
    for seq_idx, (note_sequence, source, start, end) in enumerate(note_sequences):
        note_degrees = [[] for _ in range(len(note_sequence))]  # Store degrees per note
        interval_degrees  = [[] for _ in range(len(note_sequence)-1)] # Store degrees per interval
        p_d_g_note_degrees = [[] for _ in range(len(note_sequence))] # Store pitch, duration and gap degrees for rendering purposes
        
        for idx, note_data in enumerate(note_sequence):
            note = note_data[0]
            interval = note_data[1]
            duration_ratio = note_data[2]
            query_note = query_notes[f'f{idx}']
            pitch_deg, duration_deg, sequencing_deg = 1.0, 1.0, 1.0 # Values for rendering

            # Compute pitch or interval degree
            if pitch_gap > 0:
                if allow_transpose:
                    if idx > 0:  # Skip first note for interval comparison
                        pitch_deg = pitch_degree_with_intervals(intervals[idx - 1], interval, pitch_gap)
                        interval_degrees[idx - 1].append(pitch_deg)
                else:
                    if 'class' in query_note.keys() and 'octave' in query_note.keys():
                        note_from_query = Pitch((str(query_note['class']), int(query_note['octave'])))
                        note_from_result = Pitch((note.pitches[0].class_, note.pitches[0].octave)) #TODO: chords are ignored, and only the first pitch is taken here

                        pitch_deg = pitch_degree(note_from_query, note_from_result, pitch_gap)
                        note_degrees[idx].append(pitch_deg)
            
            # Compute duration degree
            if duration_factor != 1:
                if 'dur' in query_note.keys() and query_note['dur'] is not None:
                    expected_duration = 1.0 / query_note['dur']
                    if query_note.get('dots', None):
                        expected_duration *= 1.5
                    if allow_homothety:
                        if idx > 0:  # Skip first note
                            duration_deg = duration_degree_with_multiplicative_factor(Duration(duration_ratios[idx - 1]), Duration(duration_ratio), duration_factor)
                            note_degrees[idx].append(duration_deg)
                    else:
                        duration_deg = duration_degree_with_multiplicative_factor(Duration(expected_duration), note.dur, duration_factor)
                        note_degrees[idx].append(duration_deg) 
            
            # Compute sequencing degree
            if sequencing_gap > 0:
                if idx > 0:
                    prev_note = note_sequence[idx - 1][0]
                    sequencing_deg = sequencing_degree(prev_note.end, note.start, sequencing_gap)
                    note_degrees[idx].append(sequencing_deg)
            
            p_d_g_note_degrees[idx] = [pitch_deg, duration_deg, sequencing_deg]

        # Compute degrees from membership functions
        attribute_values = stored_attribute_values[seq_idx]
        membership_function_degrees = [[] for _ in range(len(note_sequence))]
        for alias, node_name, attribute_name, membership_function_name in attribute_aliases:
            attribute_value = attribute_values[alias]
            membership_function = membership_functions[membership_function_name]
            degree = membership_function(attribute_value)
            
            idx = int(node_name[1:])
            if node_name.startswith("n"):  # Interval-based
                interval_degrees[idx].append(degree)
                membership_function_degrees[idx+1].append(f'{membership_function_name}-> {round(degree, 3)}')
            else:  # Note-based (f or e)
                note_degrees[idx].append(degree)
                membership_function_degrees[idx].append(f'{membership_function_name}-> {round(degree, 3)}')
        membership_function_degrees = ["| ".join(mem_degs) for mem_degs in membership_function_degrees]

        for idx in range(len(note_degrees)):
            if idx > 0:
                note_degrees[idx].extend(interval_degrees[idx - 1])
        
        # Aggregate all degrees per note
        aggregated_degrees = [aggregate_degrees(min_aggregation, degrees) if degrees else 1.0 for degrees in note_degrees]
        
        # Compute sequence degree
        sequence_degree = aggregate_degrees(average_aggregation, aggregated_degrees)
        
        if sequence_degree >= alpha:
            note_details = [(note_data[0], pitch_deg, duration_deg, sequencing_deg, deg, mem_degs) for note_data, deg, (pitch_deg, duration_deg, sequencing_deg), mem_degs in zip(note_sequence, aggregated_degrees, p_d_g_note_degrees, membership_function_degrees)]
            sequence_details.append([source, start, end, sequence_degree, note_details])
    
    # Sort the sequences by their overall degree in descending order
    sequence_details.sort(key=lambda x: x[3], reverse=True)
    
    return sequence_details


def process_crisp_results_to_dict(result):
    '''
    Processes `result` from a crisp query to a python dict

    - result : the result of `run_query`.
    '''

    d_lst = [dict(k) for k in result]

    res = []
    for song in d_lst:
        seq_dict = {}
        seq_dict['source'] = song['source']
        seq_dict['start'] = song['start']
        seq_dict['end'] = song['end']
        # seq_dict['overall_degree'] = song[3]

        seq_dict['notes'] = []
        n = 0
        while f'pitch_{n}' in song.keys():
            note_dict = {}
            note_dict['note'] = {
                'pitch': song[f'pitch_{n}'],
                'octave': song[f'octave_{n}'],
                'duration': song[f'duration_{n}'],
                'start': song[f'start_{n}'],
                'end': song[f'end_{n}']
            }

            # note_dict['pitch_deg'] = note_details[1]
            # note_dict['duration_deg'] = note_details[2]
            # note_dict['sequencing_deg'] = note_details[3]
            # note_dict['note_deg'] = note_details[4]

            seq_dict['notes'].append(note_dict)
            n += 1

        res.append(seq_dict)

    return res

def process_crisp_results_to_json(result):
    '''
    Processes `result` from a crisp query to json.

    - result : the result of `run_query`.
    '''

    return json.dumps(process_crisp_results_to_dict(result))

def process_results_to_dict(result: list[Record], query: str) -> list[match_type]:
    '''
    Process the results of the query and return a sorted list of dictionaries.

    Each dictionary represent a song.
    Note that there will be duplicates; use `unify_results` to merge them.

    In:
        - result: the result of the query (list from `run_query`) ;
        - query: the *fuzzy* query (to extract info from it).

    Out:
        the results, in the following format:
        ```
        [
            {
                'source': str,
                'start': float,
                'end': float,
                'overall_degree': float,

                'notes': [
                    {
                        'note_deg': int,
                        'pitch_deg': int,
                        'duration_deg': int,
                        'sequencing_deg': int,
                        'membership_functions_degrees': str, (opt)

                        'note': {
                            'dur': int,
                            'dots': int | None,
                            'start': float | None,
                            'end': float | None,
                            'id': str | None,

                            'pitches': [
                                {
                                    'class': str,
                                    'octave': int,
                                    'accid': str | None
                                },
                                .
                                .
                                .
                            ]
                        }

                    },
                    .
                    .
                    .
                ]
            },
            .
            .
            .
        ]
        ```
    '''

    sequence_details = get_ordered_results_2(result, query)

    res = []
    for source, start, end, sequence_degree, note_details in sequence_details:
        seq_dict = {}
        seq_dict['source'] = source
        seq_dict['start'] = start
        seq_dict['end'] = end
        seq_dict['overall_degree'] = sequence_degree

        seq_dict['notes'] = []
        for idx, (note, pitch_deg, duration_deg, sequencing_deg, note_deg, membership_functions_degrees) in enumerate(note_details):
            note_dict = {}
            note_dict['note'] = note.to_dict()
            note_dict['pitch_deg'] = pitch_deg
            note_dict['duration_deg'] = duration_deg
            note_dict['sequencing_deg'] = sequencing_deg
            note_dict['note_deg'] = note_deg

            if membership_functions_degrees:
                note_dict['membership_functions_degrees'] = membership_functions_degrees

            seq_dict['notes'].append(note_dict)

        res.append(seq_dict)

    return res

def process_results_to_json(result: list[Record], query: str) -> str:
    '''
    Process the results of the query and return a sorted list of dictionaries.
    Each dictionary represent a song.

    In:
        - result: the result of the query (list from `run_query`) ;
        - query: the *fuzzy* query (needed to extract info from it).

    Out:
        A string json representing the unified results (see `unify_results` for the data format)
    '''

    res_dict = process_results_to_dict(result, query)
    unified_results = unify_results(res_dict)

    return json.dumps(unified_results)

def process_results_to_text(result, query):
    '''
    Process the results of the query and return a readable string.

    - result : the result of the query (list from `run_query`) ;
    - query  : the *fuzzy* query (to extract info from it).
    '''

    sequence_details = get_ordered_results_2(result, query)

    res = ''
    for source, start, end, sequence_degree, note_details in sequence_details:
        res += f"Source: {source}, Start: {start}, End: {end}, Overall Degree: {sequence_degree}\n"

        for idx, (note, pitch_deg, duration_deg, sequencing_deg, note_deg, membership_functions_degrees) in enumerate(note_details):
            res += f"  Note {idx + 1}: {note}\n"
            res += f"    Pitch Degree: {pitch_deg}\n"
            res += f"    Duration Degree: {duration_deg}\n"
            res += f"    Sequencing Degree: {sequencing_deg}\n"

            if membership_functions_degrees:
                membership_functions_degrees_str = membership_functions_degrees
                res += f"    Fuzzy Fuctions Degrees: {membership_functions_degrees_str}\n"
            
            res += f"    Aggregated Note Degree: {note_deg}\n"

        res += "\n" # Add a blank line between sequences

    return res

def process_results_to_mp3(result, query, max_files, driver):
    sequence_details = get_ordered_results_2(result, query)

    if len(sequence_details) > max_files:
        # Limit the number of files to generate
        sequence_details = sequence_details[:max_files]

    # Clear previous results in audio directory
    audio_dir = os.path.join(os.getcwd(), "audio/output")
    print(audio_dir)
    if os.path.exists(audio_dir):
        shutil.rmtree(audio_dir)
    os.makedirs(audio_dir)

    # Generate MP3 files
    for idx, (source, start, end, sequence_degree, note_details) in enumerate(sequence_details):
        notes = get_notes_from_source_and_time_interval(driver, source, start, end)
        file_name = f"{source}_{start}_{end}_{round(sequence_degree, 2)}.mp3"
        generate_mp3(notes, file_name, audio_dir, bpm=60)

def unify_results(query_results: list[match_type]) -> list[file_matches_out_type]:
    '''
    The results are returned match by match. This function groups the matches by source.

    It counts the number of occurrences, and add the IDs when possible.

    In:
        - query_results: the results of the query, as returned by `process_results_to_dict`.
    Out:
        The result array, grouped by source, in the following format:
            ```
            [
                {
                    'source': str,
                    'number_of_occurrences': int,
                    'max_match_degree': int,       (opt)
                    'matches': [                   (opt)
                        {
                            'overall_degree': int,
                            'notes': [
                                {
                                    'note_deg': int,
                                    'pitch_deg': int,
                                    'duration_deg': int,
                                    'sequencing_deg': int,
                                    'id': str
                                },
                                ...
                            ]
                        },
                        ...
                    ]
                },
                ...
            ]
            ```

            `max_match_degree` is the maximum of all the corresponding `overall_degree`s.
    '''

    #---Function that creates a match
    def make_match(match: match_type) -> match_out_type:
        '''
        Creates a match for the output.

        In:
            - match: the input match
        Out:
            The match in the good format for the output
        '''
    
        m = {}

        m['overall_degree'] = match['overall_degree']
        m['notes'] = []

        # Add the notes of the current match
        for note in match['notes']:
            n_entry = {}

            n_entry['id'] = note['note']['id']
            n_entry['note_deg'] = note['note_deg']
            n_entry['pitch_deg'] = note['pitch_deg']
            n_entry['duration_deg'] = note['duration_deg']
            n_entry['sequencing_deg'] = note['sequencing_deg']

            m['notes'].append(n_entry)

        return m

    #---Init
    results_dict = {} # Internal representation: {source: file_matches_out_type}. It is easier to add matches this way. It is then converted to a list.
    seen_sources = [] # Used to mark the viewed sources

    for match in query_results:
        src: str = match['source']

        #---New source
        if src not in seen_sources:
            seen_sources.append(src)

            # Create a new entry for the source
            res_entry = {}

            # Add source, occurrences and max degree
            res_entry['source'] = src
            res_entry['number_of_occurrences'] = 1
            res_entry['max_match_degree'] = match['overall_degree']

            # Add the current match
            m1 = make_match(match)
            res_entry['matches'] = [m1]

            results_dict[src] = res_entry

        #---Source already seen
        else:
            results_dict[src]['number_of_occurrences'] += 1
            
            if match['overall_degree'] > results_dict[src]['max_match_degree']:
                results_dict[src]['max_match_degree'] = match['overall_degree']

            # Make match
            m = make_match(match)
            results_dict[src]['matches'].append(m)

    # Convert `results_dict` to a list
    ret = list(results_dict.values())

    return ret




##-Run
if __name__ == "__main__":
    pass
    # test
