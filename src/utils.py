#!/usr/bin/env python3
# -*- coding: utf-8 -*-

##-Imports
#---General
import os
import argparse
from ast import literal_eval # safer than eval
import re

#---Project
from src.db.neo4j_connection import connect_to_neo4j, run_query
from src.audio.generate_audio import generate_mp3
from src.core.fuzzy_computation import convert_note_to_sharp
from src.core.note import Note
from src.core.refactor import move_attribute_values_to_where_clause
# from src.audio.audio_parser import extract_notes

def create_query_from_list_of_notes(notes, pitch_distance, duration_factor, duration_gap, alpha, allow_transposition, allow_homothety, incipit_only, collection=None):
    '''
    Create a fuzzy query.

    In :
        - notes                      : the note array (see below for the format) ;
        - pitch_distance (float)     : the `pitch distance` (fuzzy param) ;
        - duration_factor (float)    : the `duration factor` (fuzzy param) ;
        - duration_gap (float)       : the `duration gap` (fuzzy param) ;
        - alpha (float)              : the `alpha` param ;
        - allow_transposition (bool) : the `allow_transposition` param ;
        - allow_homothety (bool)     : the `allow_homothety` param ;
        - incipit_only (bool)        : restricts search to the incipit ;
        - collection (str | None)    : the collection filter.

    Out :
        a fuzzy query searching for the notes given in parameters.

    Description for the format of `notes` :
        `notes` should be a list of `note`s.
        A `note` is a list of the following format : `[(class_1, octave_1), ..., (class_n, octave_n), duration]`

        For example : `[[('c', 5), 4], [('b', 4), 8], [('b', 4), 8], [('a', 4), ('d', 5), 16]]`.

        duration is in the following format: 1 for whole, 2 for half, 4 for quarter, ...
    '''

    match_clause = 'MATCH\n'
    if allow_transposition:
        match_clause += ' ALLOW_TRANSPOSITION\n'
    if allow_homothety:
        match_clause += ' ALLOW_HOMOTHETY\n'

    match_clause += f' TOLERANT pitch={pitch_distance}, duration={duration_factor}, gap={duration_gap}\n ALPHA {alpha}\n'

    if incipit_only:
        match_clause += " (v:Voice)-[:timeSeries]->(e0:Event),\n"
    
    if collection is not None:
        match_clause += " (tp:TopRhythmic{{collection:'{}'}})-[:RHYTHMIC]->(m:Measure),\n (m)-[:HAS]->(e0:Event),\n".format(collection)
    
    events = []
    facts = []
    fact_nb = 0
    for i, note_or_chord in enumerate(notes):
        if len(note_or_chord) > 2:
            note = Note(note_or_chord[0][0], note_or_chord[0][1], note_or_chord[1], note_or_chord[2])
        else:
            note = Note(note_or_chord[0][0], note_or_chord[0][1], note_or_chord[1])

        event = '(e{}:Event)'.format(i)

        fact_properties = []

        if note.pitch is not None:
            fact_properties.append(f"class:'{note.pitch}'")

        if note.octave is not None:
            fact_properties.append(f"octave:{note.octave}")

        if note.dur is not None:
            fact_properties.append(f"dur:{note.dur}")

        if note.dots is not None:
            fact_properties.append(f"dots:{note.dots}")

        # Join all defined properties
        properties_str = ', '.join(fact_properties)

        # Construct the full Fact pattern
        fact = f"(e{i})--(f{fact_nb}:Fact{{{properties_str}}})"

        facts.append(fact)
        fact_nb += 1

        events.append(event)
    
    match_clause += " " + "".join(f"{events[i]}-[n{i}:NEXT]->" for i in range(len(events)-1)) + events[-1] + ",\n " + ",\n ".join(facts)
    
    return_clause = "\nRETURN e0.source AS source, e0.start AS start"

    query = match_clause + return_clause
    return move_attribute_values_to_where_clause(query)

def create_query_from_contour(contour, incipit_only, collection=None):
    """
    Constructs a fuzzy contour query based on the provided contour dictionary.

    Parameters:
        - contour (dict): A dictionary with 'rhythmic' and 'melodic' lists representing rhythmic and melodic contours.
        - incipit_only (bool)        : restricts search to the incipit.
        - collection (str | None)    : the collection filter.

    Returns:
        str: A fuzzy contour query string.
    """
    rhythmic_contours = contour['rhythmic']
    melodic_contours = contour['melodic']

    # Mapping of contour symbols to membership function names and definitions
    membership_functions = {}
    membership_definitions = []
    conditions = []

    # Helper function to define membership functions
    def add_membership_function(symbol):
        if symbol in membership_functions:
            return

        # 'X' is for absence of constraint on an interval or note duration
        if symbol == 'X' or symbol == 'x':
            return

        if symbol == 's':
            membership_functions[symbol] = 'shorterDuration'
            membership_definitions.append('DEFINETRAP shorterDuration AS (0.0, 0.5, 0.75, 1)')
        elif symbol == 'S':
            membership_functions[symbol] = 'muchShorterDuration'
            membership_definitions.append('DEFINEDESC muchShorterDuration AS (0.25, 0.5)')
        elif symbol == 'M':
            membership_functions[symbol] = 'sameDuration'
            membership_definitions.append('DEFINETRAP sameDuration AS (0.5, 1.0, 1.0, 2.0)')
        elif symbol == 'l':
            membership_functions[symbol] = 'longerDuration'
            membership_definitions.append('DEFINETRAP longerDuration AS (1.0, 1.5, 2.0, 4.0)')
        elif symbol == 'L':
            membership_functions[symbol] = 'muchLongerDuration'
            membership_definitions.append('DEFINEASC muchLongerDuration AS (2.0, 4.0)')
        elif symbol == 'u':
            membership_functions[symbol] = 'stepUp'
            membership_definitions.append('DEFINETRAP stepUp AS (0.0, 0.5, 1.0, 2)')
        elif symbol == 'U':
            membership_functions[symbol] = 'leapUp'
            membership_definitions.append('DEFINEASC leapUp AS (0.5, 2.0)')
        # elif symbol == '*U':
        #     membership_functions[symbol] = 'extremelyUp'
        #     membership_definitions.append('DEFINEASC extremelyUp AS (1, 2)')
        elif symbol == 'R':
            membership_functions[symbol] = 'repeat'
            membership_definitions.append('DEFINETRAP repeat AS (-1, 0.0, 0.0, 1)')
        elif symbol == 'd':
            membership_functions[symbol] = 'stepDown'
            membership_definitions.append('DEFINETRAP stepDown AS (-2, -1.0, -0.5, 0.0)')
        elif symbol == 'D':
            membership_functions[symbol] = 'leapDown'
            membership_definitions.append('DEFINEDESC leapDown AS (-2.0, -0.5)')
        # elif symbol == '*D':
        #     membership_functions[symbol] = 'extremelyDown'
        #     membership_definitions.append('DEFINEDESC extremelyDown AS (-2, -1)')
        else:
            raise Exception(f'{symbol} not accepted.')

    # Add membership functions and conditions for melodic contours
    for idx, symbol in enumerate(melodic_contours):
        if symbol != 'X' and symbol != 'x':
            add_membership_function(symbol)
            conditions.append(f'n{idx}.interval IS {membership_functions[symbol]}')

    # Add membership functions and conditions for rhythmic contours
    for idx, symbol in enumerate(rhythmic_contours):
        if symbol != 'X' and symbol != 'x':
            add_membership_function(symbol)
            conditions.append(f'n{idx}.duration_ratio IS {membership_functions[symbol]}')

    # Build the MATCH clause
    num_intervals = len(melodic_contours)
    events_chain = ''.join(f'(e{i}:Event)-[n{i}:NEXT]->' for i in range(num_intervals)) + f'(e{num_intervals}:Event)'
    fact_nodes = [f'(e{i})--(f{i}:Fact)' for i in range(num_intervals + 1)]

    match_clause = 'MATCH\n'

    if incipit_only:
        match_clause += " (v:Voice)-[:timeSeries]->(e0:Event),\n"
    
    if collection is not None:
        match_clause += " (tp:TopRhythmic{{collection:'{}'}})-[:RHYTHMIC]->(m:Measure),\n (m)-[:HAS]->(e0:Event),\n".format(collection)

    match_clause += events_chain + ',\n ' + ',\n '.join(fact_nodes)

    # Build the WHERE clause
    where_clause = ''
    if conditions:
        where_clause = 'WHERE \n ' + ' AND\n '.join(conditions)

    # Build the RETURN clause
    return_clause = 'RETURN e0.source AS source, e0.start AS start'

    # Combine all parts into the final query
    query = '\n'.join(membership_definitions) + '\n' + match_clause
    if where_clause:
        query += '\n' + where_clause
    query += '\n' + return_clause

    return move_attribute_values_to_where_clause(query)

def get_first_k_notes_of_each_score(k, source, driver):
    '''
    In: an integer, a driver for the DB
    Out: a crisp query returning the sequences of k first notes for each score in the DB

    Initialize the MATCH and WHERE clauses
    '''

    match_clause = "MATCH\n"
    event_chain = []
    fact_chain = []
    
    for i in range(1, k + 1):
        event_chain.append(f"(e{i}:Event)")
        fact_chain.append(f"(e{i})--(f{i}:Fact)")

    match_clause += "-[:NEXT]->".join(event_chain) + ",\n " + ",\n ".join(fact_chain)
    
    # Add the WHERE clause
    where_clause = f"\nWHERE\n e1.start = 0 AND e1.source = \"{source}\""
    
    # Initialize the RETURN clause
    return_clause = "\nRETURN\n"
    return_fields = []
    
    for i in range(1, k + 1):
        return_fields.append(f"f{i}.class AS pitch_{i}, f{i}.octave AS octave_{i}, f{i}.dur AS dur_{i}, f{i}.duration AS duration_{i}, f{i}.dots AS dots_{i}")
    
    return_fields.append("e1.source AS source")
    
    return_clause += ",\n".join(return_fields)
    
    # Combine all clauses into the final query
    query = match_clause + where_clause + return_clause
    
    # Run the query
    results = run_query(driver, query)

    # Process the results
    sequences = []
    
    for record in results:
        sequence = []
        for i in range(1, k + 1):
            pitch = record[f"pitch_{i}"]
            octave = record[f"octave_{i}"]
            dur = record[f"dur_{i}"]
            duration = record[f"duration_{i}"]
            dots = record[f"dots_{i}"]
            note = Note(pitch, octave, dur, dots)
            sequence.append(note)
        sequence = [note.to_list() for note in sequence]
        sequences.append(sequence)
    
    return sequences[0]

def generate_mp3_from_source_and_time_interval(driver, source, start_time, end_time, bpm=60):
    notes = get_notes_from_source_and_time_interval(driver, source, start_time, end_time)
    file_name = f"{source}_{start_time}_{end_time}.mp3"
    generate_mp3(notes, file_name, bpm)

def get_notes_from_source_and_time_interval(driver, source, start_time, end_time):
    '''
    In: driver for DB, a source to identify one score, a starting and ending time
    Out: a list of notes
    '''

    query = f"""
    MATCH (e:Event)-[:IS]->(f:Fact)
    WHERE e.start >= {start_time} AND e.end <= {end_time} AND e.source = '{source}'
    RETURN f.class AS class, f.octave AS octave, e.dur AS dur, e.dots as dots, e.start as start, e.end as end
    ORDER BY e.start
    """  

    results = run_query(driver, query)
    notes = [Note(record['class'], record['octave'], record['dur'], record['dots'], None, record['start'], record['end']) for record in results]

    return notes

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

    - notes : the array of notes, following the format given in `extract_notes_from_query` ;

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

    - notes_dict : a dictionary of nodes with their attributes, as returned by `extract_notes_from_query`.

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

    - notes_dict : a dictionary of nodes with their attributes, as returned by `extract_notes_from_query`.

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

def execute_cypher_dumps(directory_path: str, uri: str, user: str, password: str, verbose: bool = False):
    '''
    Executes all .cypher dump files in the specified directory one by one.

    - directory_path : path to the directory containing .cypher files;
    - uri            : Neo4j database URI (e.g., "bolt://localhost:7687");
    - user           : database username;
    - password       : database password;
    - verbose        : if True, prints execution logs.
    '''

    # Check if the directory exists
    if not os.path.isdir(directory_path):
        raise ValueError(f"The directory '{directory_path}' does not exist.")

    # List all .cypher or .cql files in the directory, sorted for consistency
    cypher_files = sorted([f for f in os.listdir(directory_path) if f.endswith('.cypher') or f.endswith('.cql')])

    if not cypher_files:
        print("No .cypher files found in the directory.")
        return

    # Connect to the Neo4j database
    driver = connect_to_neo4j(uri, user, password)

    # Execute each Cypher dump file
    for cypher_file in cypher_files:
        file_path = os.path.join(directory_path, cypher_file)

        try:
            with open(file_path, 'r') as file:
                cypher_query = file.read()
            print(f'Executing {cypher_file}')
            # Execute the Cypher query using run_query
            results = run_query(driver, cypher_query)

            if verbose:
                print(f'Successfully executed: {cypher_file}')
        except Exception as e:
            print(f'Error executing {cypher_file}: {e}')

    print("All Cypher dump files have been executed successfully.")

def check_notes_input_format(notes_input: str) -> list[list[tuple[str|None, int|None] | int|float|None]]:
    '''
    Ensure that `notes_input` is in the correct format (see below for a description of the format).
    If not, raise an argparse.ArgumentTypeError.

    In:
        - notes_input: the user input (a string, not a list).

    Out:
        - a list of (char, int, int)  if the format is right ;
        - argparse.ArgumentTypeError  otherwise.

    Description for the format of `notes` :
        `notes` should be a list of `note`s.
        A `note` is a list of the following format : `[(class_1, octave_1), ..., (class_n, octave_n), duration, dots (optional)]`

        For example : `[[('c', 5), 4, 0], [('b', 4), 8, 1], [('b', 4), 8], [('a', 4), ('d', 5), 16, 2]]`.

        duration is in the following format: 1 for whole, 2 for half, ...
        dots is an optional integer representing the number of dots.
    '''

    #---Init (functions to test each part)
    def check_class(class_: str|None) -> bool:
        '''Return True iff `class_` is in correct format.'''

        return (
            class_ == None
            or (
                isinstance(class_, str)
                and (
                    len(class_) == 1 or
                    (len(class_) == 2 and class_[1] in '#sbf')
                )
                and
                class_[0] in 'abcdefgr'
            )
        )

    def check_octave(octave: int|None) -> bool:
        '''Return True iff `octave` is in correct format.'''

        return isinstance(octave, (int, type(None)))

    def check_duration(duration: int|float|None) -> bool:
        '''Return True iff `duration` is in correct format.'''

        return isinstance(duration, (int, float, type(None)))

    def check_dots(dots: int|None) -> bool:
        '''Return True iff `dots` is in correct format.'''

        return isinstance(dots, (int, type(None))) and (dots is None or dots >= 0)

    format_notes = "Notes format: list of [(class, octave), duration, dots]: [[(class, octave), ..., duration, dots], ...]. E.g `[[(\'c\', 5), 4, 0], [(\'b\', 4), 8, 1], [(\'b\', 4), 8], [(\'a\', 4), (\'d\', 5), 16, 2]]`. It is possible to use \"None\" to ignore a criteria. Dots are optinal, with default value of 0."

    #---Convert string to list
    notes_input = notes_input.replace("\\", "")
    notes = literal_eval(notes_input)

    #---Check
    for i, note_or_chord in enumerate(notes):
        #-Check type of the current note/chord (e.g [('c', 5), 8])
        if type(note_or_chord) != list:
            raise argparse.ArgumentTypeError(f'error with note {i}: should be a a list, but "{note_or_chord}", of type {type(note_or_chord)} found !\n' + format_notes)

        #-Check the length of the current note/chord (e.g [('c', 5), 8])
        if len(note_or_chord) < 2:
            raise argparse.ArgumentTypeError(f'error with note {i}: there should be at least two elements in the list, for example `[(\'c\', 5), 4]`, but "{note_or_chord}", with length {len(note_or_chord)} found !\n' + format_notes)

        #-Check the duration
        duration = note_or_chord[1]
        if not check_duration(duration):
            raise argparse.ArgumentTypeError(f'error with note {i}: "{note_or_chord}": "{duration}" (duration) is not a float (or None)\n' + format_notes)

        #-Check the dots (if provided)
        if len(note_or_chord) > 2:
            dots = note_or_chord[-1]
            if not check_dots(dots):
                raise argparse.ArgumentTypeError(f'error with note {i}: "{note_or_chord}": "{dots}" (dots) is not a non-negative integer or None\n' + format_notes)
        else:
            dots = 0  # Default to 0 if dots are not provided

        #-Check each note
        for j, note in enumerate(note_or_chord[:-2]):
            #-Check type of note tuple
            if type(note) != tuple:
                raise argparse.ArgumentTypeError(f'error with note {i}, element {j}: should be a tuple (e.g `(\'c\', 5)`), but "{note}", of type {type(note)} found !\n' + format_notes)

            #-Check length of note tuple
            if len(note) != 2:
                raise argparse.ArgumentTypeError(f'error with note {i}, element {j}: note tuple should have 2 elements (class, octave), but {len(note_or_chord)} found !\n' + format_notes)

            #-Check note class
            if not check_class(note[0]):
                raise argparse.ArgumentTypeError(f'error with note {i}, element {j}: "{note}": "{note[0]}" is not a note class.\n' + format_notes)

            #-Check note octave
            if not check_octave(note[1]):
                raise argparse.ArgumentTypeError(f'error with note {i}, element {j}: "{note}": "{note[1]}" (octave) is not an int, or a float, or None.\n' + format_notes)

    return notes

def check_contour_input_format(contour: str) -> dict:
    pattern = r'^(([*UDRudX]*)(-)([XLSMls]*))$'
    if not re.match(pattern, contour):
        raise argparse.ArgumentTypeError("When using `-C`, NOTES must be a string containing a rhythmic sequence ('L', 'M', 'l', 'S', 's', 'X') "
                            "and a melodic contour sequence ('*U', 'U', 'u', 'R', 'd', 'D', '*D', 'X'), separated by '-'. Example: 'URdU*-LMl'.")

    # Split the input into rhythmic and melodic components
    melodic_part, rhythmic_part = contour.split('-')

    # Convert into lists of individual symbols
    rhythmic_contours = list(rhythmic_part)
    melodic_contours = []

    # Process melodic contour sequence while handling '*U' and '*D' properly
    i = 0
    while i < len(melodic_part):
        if melodic_part[i] == '*':  
            if i + 1 < len(melodic_part) and melodic_part[i + 1] in "UD":
                melodic_contours.append(melodic_part[i]+melodic_part[i+1])
                i += 2
            else:
                raise argparse.ArgumentTypeError(f"Invalid contour element: '{melodic_part[i:]}' (Expected '*U' or '*D').")
        else:
            melodic_contours.append(melodic_part[i])
            i += 1

    # Ensure both lists have the same length
    if len(rhythmic_contours) != len(melodic_contours):
        raise argparse.ArgumentTypeError("Both rhythmic and melodic contours must have the same length. Example: 'URd*U-LMl'.")

    # Store contour as structured data
    ret = {
        'rhythmic': rhythmic_contours,
        'melodic': melodic_contours
    }

    return ret

if __name__ == "__main__":
    # Set up a driver just to clear the cache
    uri = "bolt://localhost:7687"  # Default URI for a local Neo4j instance
    user = "neo4j"                 # Default username
    password = "12345678"          # Replace with your actual password
