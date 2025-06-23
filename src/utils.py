#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Definition of functions useful for both API and CLI'''

##-Imports
#---General
import os
import argparse
from ast import literal_eval # safer than eval
import re

#---Project
from src.db.neo4j_connection import run_query
from src.core.note import Note
from src.core.refactor import move_attribute_values_to_where_clause

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
    '''

    # Initialize the MATCH and WHERE clauses
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

