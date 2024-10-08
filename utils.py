from neo4j_connection import connect_to_neo4j, run_query
from generate_audio import generate_mp3
from degree_computation import convert_note_to_sharp
from note import Note

def create_query_from_list_of_notes(notes, pitch_distance, duration_factor, duration_gap, alpha, allow_transposition, contour_match, collections=None):
    '''
    Create a fuzzy query.

    In :
        - notes                      : the note array (see below for the format) ;
        - pitch_distance (float)     : the `pitch distance` (fuzzy param) ;
        - duration_factor (float)    : the `duration factor` (fuzzy param) ;
        - duration_gap (float)       : the `duration gap` (fuzzy param) ;
        - alpha (float)              : the `alpha` param ;
        - allow_transposition (bool) : the `allow_transposition` param ;
        - contour_match (bool)       : the `contour_match` param ;
        - collections (str[] | None) : the collection filter.

    Out :
        a fuzzy query searching for the notes given in parameters.

    Description for the format of `notes` :
        `notes` should be a list of `note`s.
        A `note` is a list of the following format : `[(class_1, octave_1), ..., (class_n, octave_n), duration]`

        For example : `[[('c', 5), 4], [('b', 4), 8], [('b', 4), 8], [('a', 4), ('d', 5), 16]]`.

        duration is in the following format: 1 for whole, 2 for half, ...
        float is allowed for dotted notes (e.g dotted half is 1/(1/2 + 1/4) = 4 / 3).
    '''

    match_clause = 'MATCH\n'
    if allow_transposition:
        match_clause += ' ALLOW_TRANSPOSITION\n'
    if contour_match:
        match_clause += ' CONTOUR\n'

    match_clause += f' TOLERANT pitch={pitch_distance}, duration={duration_factor}, gap={duration_gap}\n ALPHA {alpha}\n'

    if collections != None:
        match_clause += ' COLLECTIONS '
        match_clause += '"' + '" "'.join(collections) + '"\n'

    events = []
    facts = []
    fact_nb = 0
    for i, note_or_chord in enumerate(notes):
        duration = note_or_chord[-1]

        # event = '(e{}:Event{{dur:{}}})'.format(i, duration)
        event = '(e{}:Event)'.format(i)

        for note in note_or_chord[:-1]:
            class_, octave = note
            fact = "(e{})--(f{}{{class:'{}', octave:{}, dur:{}}})".format(i, fact_nb, class_, octave, duration)

            facts.append(fact)
            fact_nb += 1

        events.append(event)
    
    match_clause += " " + "-[:NEXT]->".join(events) + ",\n " + ",\n ".join(facts)
    return_clause = "\nRETURN e0.source AS source, e0.start AS start"
    
    query = match_clause + return_clause
    return query

def create_query_from_contour(contour):
    """
    Constructs a fuzzy contour query based on the provided contour string.

    Parameters:
        contour (str): A string representing a sequence of contour steps.
            Symbols:
                '*D' : extremely down
                'D'  : leap down
                'd'  : step down
                'R'  : repeat
                'u'  : step up
                'U'  : leap up
                '*U' : extremely up

    Returns:
        str: A fuzzy contour query string.
    """
    # Mapping of contour symbols to membership function names and definitions
    membership_functions = {}
    # List to keep track of unique membership functions added to the query
    membership_definitions = []
    # List of interval conditions in the WHERE clause
    interval_conditions = []
    # Counter for event and relationship nodes
    event_nodes = []
    fact_nodes = []

    # Helper function to define membership functions
    def add_membership_function(symbol):
        if symbol in membership_functions:
            return  # Already defined

        a_minus, a, b, b_plus = 0.0, 0.5, 1.0, 1.5
        strong_support_length = abs(b - a)
        desc_length = abs(b_plus - b)
        asc_length = abs(a - a_minus)

        if symbol == 'u':
            # Define stepUp
            membership_functions[symbol] = f'DEFINETRAP stepUp AS ({a_minus}, {a}, {b}, {b_plus})'
            membership_definitions.append(membership_functions[symbol])
        elif symbol == 'U':
            # Define leapUp based on stepUp
            membership_functions[symbol] = f'DEFINETRAP leapUp AS ({b}, {b_plus}, {b_plus + strong_support_length}, {b_plus + strong_support_length + asc_length})'
            membership_definitions.append(membership_functions[symbol])
        elif symbol == '*U':
            # Define extremelyUp based on leapUp
            membership_functions[symbol] = f'DEFINEASC extremelyUp AS ({b_plus + strong_support_length}, {b_plus + strong_support_length + asc_length})'
            membership_definitions.append(membership_functions[symbol])
        elif symbol == 'R':
            # Define repeat based on stepUp
            membership_functions[symbol] = f'DEFINETRAP repeat AS ({-asc_length}, {-a_minus}, {a_minus}, {asc_length})'
            membership_definitions.append(membership_functions[symbol])
        elif symbol == 'd':
            # Define stepDown based on stepUp
            membership_functions[symbol] = f'DEFINETRAP stepDown AS ({-b_plus}, {-b}, {-a}, {-a_minus})'
            membership_definitions.append(membership_functions[symbol])
        elif symbol == 'D':
            # Define leapDown based on stepUp
            membership_functions[symbol] = f'DEFINETRAP leapDown AS ({-b_plus - strong_support_length - asc_length}, {-b_plus - strong_support_length}, {-b_plus}, {-b})'
            membership_definitions.append(membership_functions[symbol])
        elif symbol == '*D':
            # Define extremelyDown based on stepUp
            membership_functions[symbol] = f'DEFINEDESC extremelyDown AS ({-b_plus - strong_support_length - asc_length}, {-b_plus - strong_support_length})'
            membership_definitions.append(membership_functions[symbol])

    # Normalize the contour string into a list of symbols
    # Handle symbols like '*D', '*U'
    i = 0
    symbols = []
    while i < len(contour):
        if contour[i] == '*':
            symbol = contour[i] + contour[i + 1]
            i += 2
        else:
            symbol = contour[i]
            i += 1
        symbols.append(symbol)

    # Build the MATCH and WHERE clauses
    for idx, symbol in enumerate(symbols):
        add_membership_function(symbol)
        event_nodes.append(f'(e{idx}:Event)')
        fact_nodes.append(f'(e{idx})--(f{idx}:Fact)')

        # Determine the membership function name for the interval
        if symbol == 'd':
            mf_name = 'stepDown'
        elif symbol == 'D':
            mf_name = 'leapDown'
        elif symbol == '*D':
            mf_name = 'extremelyDown'
        elif symbol == 'u':
            mf_name = 'stepUp'
        elif symbol == 'U':
            mf_name = 'leapUp'
        elif symbol == '*U':
            mf_name = 'extremelyUp'
        elif symbol == 'R':
            mf_name = 'repeat'
        else:
            raise ValueError(f"Unknown symbol '{symbol}' in contour.")

        interval_conditions.append(f'n{idx}.interval IS {mf_name}')

    # Construct the query parts
    query_parts = []

    # Add membership function definitions
    query_parts.extend(membership_definitions)

    # Build the MATCH clause
    num_intervals = len(interval_conditions)
    events_chain = ''.join(f'(e{i}:Event)-[n{i}:NEXT]->' for i in range(num_intervals)) + f'(e{num_intervals}:Event)'
    match_clause = 'MATCH\n  '+ events_chain + ',\n  ' + ',\n  '.join(fact_nodes)

    # Build the WHERE clause
    where_clause = ''
    if interval_conditions:
        where_clause = 'WHERE\n  ' + ' AND\n  '.join(interval_conditions)

    # Build the RETURN clause
    return_clause = f'RETURN e0.source AS source, e0.start AS start'

    # Combine all parts into the final query
    query = '\n'.join(query_parts) + '\n' + match_clause
    if where_clause:
        query += '\n' + where_clause
    query += '\n' + return_clause

    return query

def get_first_k_notes_of_each_score(k, source, driver):
    # In : an integer, a driver for the DB
    # Out : a crisp query returning the sequences of k first notes for each score in the DB

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
        return_fields.append(f"f{i}.class AS pitch_{i}, f{i}.octave AS octave_{i}, e{i}.duration AS duration_{i}")
    
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
            duration = record[f"duration_{i}"]
            note = (pitch, octave, 1/duration)
            sequence.append(note)
        sequences.append(sequence)
    
    return sequences[0]

def generate_mp3_from_source_and_time_interval(driver, source, start_time, end_time, bpm=60):
    notes = get_notes_from_source_and_time_interval(driver, source, start_time, end_time)
    file_name = f"{source}_{start_time}_{end_time}.mp3"
    generate_mp3(notes, file_name, bpm)

def get_notes_from_source_and_time_interval(driver, source, start_time, end_time):
    # In : driver for DB, a source to identify one score, a starting and ending time
    # Out : a list of notes (in class, octave, duration triples)

    query = f"""
    MATCH (e:Event)-[]->(f:Fact)
    WHERE e.start >= {start_time} AND e.end <= {end_time} AND e.source = '{source}'
    RETURN f.class AS class, f.octave AS octave, e.duration AS duration, e.start as start, e.end as end
    ORDER BY e.start
    """  

    results = run_query(driver, query)
    notes = [Note(record['class'], record['octave'], record['duration'], record['start'], record['end']) for record in results]

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

def calculate_intervals_dict(notes_dict: dict) -> list[float]:
    '''
    Compute the list of intervals between consecutive notes.

    - notes_dict : a dictionary of nodes with their attributes, as returned by `extract_notes_from_query`.

    Output: a list of intervals between consecutive notes.
    '''
    # Extract Fact nodes (notes) from the dictionary
    fact_nodes = {node_name: attrs for node_name, attrs in notes_dict.items() if attrs.get('type') == 'Fact'}

    # Initialize a list to hold pitches
    pitches = []


    for node_name, attrs in fact_nodes.items():
        
        note_class = attrs.get('class')
        octave = attrs.get('octave')
        if note_class is not None and octave is not None:
            pitches.append([note_class, octave])
        else:
            # If note class or octave is missing, append None
            pitches.append(None)

    # Compute intervals between consecutive pitches
    intervals = []
    for i in range(len(pitches) - 1):

        if None in (pitches[i][0], pitches[i][1], pitches[i+1][0], pitches[i+1][1]):
            interval = None
        else:
            interval = calculate_pitch_interval(pitches[i][0], pitches[i][1], pitches[i+1][0], pitches[i+1][1])

        intervals.append(interval)

    return intervals

if __name__ == "__main__":
    contour = 'URRUdD'
    query = create_query_from_contour(contour)
    print(query)
