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
from src.core.refactor import move_attribute_values_to_where_clause
from src.representation.chord import Chord
from src.representation.pitch import Pitch
from src.representation.duration import Duration

def create_query_from_list_of_notes(
    notes: list[Chord],
    pitch_distance: float,
    duration_factor: float,
    duration_gap: float,
    alpha: float,
    allow_transposition: bool,
    allow_homothety: bool,
    incipit_only: bool,
    collection: str | None = None
):
    '''
    Create a fuzzy query.

    In :
        - notes                      : the note array ;
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
    '''

    match_clause = 'MATCH\n'
    if allow_transposition:
        match_clause += ' ALLOW_TRANSPOSITION\n'
    if allow_homothety:
        match_clause += ' ALLOW_HOMOTHETY\n'

    match_clause += f' TOLERANT pitch={pitch_distance}, duration={duration_factor}, gap={duration_gap}\n ALPHA {alpha}\n'

    if incipit_only:
        match_clause += ' (v:Voice)-[:timeSeries]->(e0:Event),\n'
    
    if collection is not None:
        match_clause += f" (tp:TopRhythmic{{collection:'{collection}'}})-[:RHYTHMIC]->(m:Measure),\n (m)-[:HAS]->(e0:Event),\n"
    
    events = []
    facts = []
    where_clause_accids = []
    fact_nb = 0
    for i, note_or_chord in enumerate(notes):
        # if len(note_or_chord) > 2:
        #     note = Note(note_or_chord[0][0], note_or_chord[0][1], note_or_chord[1], note_or_chord[2])
        # else:
        #     note = Note(note_or_chord[0][0], note_or_chord[0][1], note_or_chord[1])


        event_properties = []
        if note_or_chord.dur.to_int() is not None:
            event_properties.append(f'dur: {note_or_chord.dur.to_int()}')

        if note_or_chord.dots != None:
            event_properties.append(f'dots: {note_or_chord.dots}')

        properties_str_event = ', '.join(event_properties)
        event = f'(e{i}:Event{{{properties_str_event}}})'

        for pitch in note_or_chord.pitches:
            fact_properties = []

            if pitch.class_ is not None:
                fact_properties.append(f"class:'{pitch.class_}'")

            if pitch.octave is not None:
                fact_properties.append(f'octave:{pitch.octave}')

            if pitch_distance == 0 and pitch.accid is not None:
                accid = pitch.accid.replace('#', 's')
                where_clause_accids.append(f"(f{fact_nb}.accid = '{accid}' OR f{fact_nb}.accid_ges = '{accid}')")

            # Join all defined properties
            properties_str = ', '.join(fact_properties)

            # Construct the full Fact pattern
            fact = f"(e{i})--(f{fact_nb}:Fact{{{properties_str}}})"

            facts.append(fact)
            fact_nb += 1

        events.append(event)
    
    match_clause += " " + "".join(f"{events[i]}-[n{i}:NEXT]->" for i in range(len(events)-1)) + events[-1] + ",\n " + ",\n ".join(facts)

    where_clause = '\nWHERE ' + ' AND '.join(where_clause_accids) + '\n'
    
    return_clause = "\nRETURN e0.source AS source, e0.start AS start"

    query = match_clause + where_clause + return_clause
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

def get_first_k_notes_of_each_score(k, source, driver) -> list[Chord]:
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
        return_fields.append(f"f{i}.class AS pitch_{i}, f{i}.octave AS octave_{i}, f{i}.accid AS accid_{i}, f{i}.accid_ges AS accid_ges_{i}, f{i}.dur AS dur_{i}, f{i}.duration AS duration_{i}, f{i}.dots AS dots_{i}")
    
    return_fields.append("e1.source AS source")
    
    return_clause += ",\n".join(return_fields)
    
    # Combine all clauses into the final query
    query = match_clause + where_clause + return_clause
    
    # Run the query
    results = run_query(driver, query)

    # Process the results
    sequences: list[list[Chord]] = []
    
    for record in results:
        sequence: list[Chord] = []

        for i in range(1, k + 1):
            pitch = record[f"pitch_{i}"]
            octave = record[f"octave_{i}"]
            dur = record[f"dur_{i}"]
            duration = record[f"duration_{i}"]
            dots = record[f"dots_{i}"]

            accid = record[f'accid_{i}']
            if accid == None:
                accid = record[f'accid_ges_{i}']

            note = Chord([Pitch((pitch, octave, accid))], Duration(dur), dots)

            sequence.append(note)

        sequences.append(sequence)
    
    return sequences[0] #TODO: why calculate all the list, if we only return the first element ?

def check_notes_input_format(notes_input: str) -> list[Chord]:
    '''
    Ensure that `notes_input` is in the correct format (see below for a description of the format).
    If not, raise an argparse.ArgumentTypeError.

    In:
        - notes_input: the user input (a string, not a list).

    Out:
        - a list of `Chord`s if the format is right ;
        - argparse.ArgumentTypeError  otherwise.

    Description for the format of `notes` :
        `notes` should be a list of chords.
        A chord is a tuple of the following format: `([note1, note2, ...], duration, dots)`
        A note is in the following format: `class[accidental]/octave` (`accidental` is optional), e.g `c/5` or `c#/5`
        `duration` is in the following format: 1 for whole, 2 for half, 4 for quarter, 8 for eighten, ...

        For example: `[(['c#/5'], 4, 0), (['b/4'], 8, 1), (['b/4'], 8, 0), (['a/4', 'd/5'], 16, 2)]`
    '''

    format_notes = "Notes format: list of ([notes], duration, dots): [([note1, ...], duration, dots)]. E.g `[(['c#/5'], 4, 0), (['b/4'], 8, 1), (['b/4'], 8, 0), (['a/4', 'd/5'], 16, 2)]`. It is possible to use \"None\" to ignore a criteria."

    #---Convert string to list
    notes_input = notes_input.replace("\\", "")
    notes = literal_eval(notes_input)

    ret = []

    #---Check
    for i, note_or_chord in enumerate(notes):
        #-Check type of the current note/chord (e.g [('c', 5), 8])
        if type(note_or_chord) != tuple:
            raise argparse.ArgumentTypeError(f'error with note {i}: should be a tuple, but "{note_or_chord}", of type {type(note_or_chord)} found !\n' + format_notes)

        #-Check the length of the current note/chord (e.g [('c', 5), 8])
        if len(note_or_chord) != 3:
            raise argparse.ArgumentTypeError(f'error with note {i}: there should be three elements in the tuple, for example `([\'c#/5\'], 8, 0)`, but "{note_or_chord}", with length {len(note_or_chord)} found !\n' + format_notes)

        #-Check the duration
        try:
            duration = Duration(note_or_chord[1])
        except ValueError as err:
            raise argparse.ArgumentTypeError(f'error with note {i}: duration: {err}')

        #-Check each note
        pitches = []
        for j, note in enumerate(note_or_chord[0]):
            p = Pitch(None)
            try:
                p.from_str(note)
                pitches.append(p)

            except ValueError as err:
                raise argparse.ArgumentTypeError(f'error with note {i}, element {j}: pitch: {err}')

        try:
            c = Chord(pitches, duration, note_or_chord[2])
            ret.append(c)

        except ValueError as err:
            raise argparse.ArgumentTypeError(f'error with note {i}: chord: {err}')

    return ret

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

