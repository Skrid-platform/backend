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

if __name__ == "__main__":
    # Set up the driver
    uri = "bolt://localhost:7687"  # Default URI for a local Neo4j instance
    user = "neo4j"                 # Default username
    password = "12345678"          # Replace with your actual password
    driver = connect_to_neo4j(uri, user, password)

    generate_mp3_from_source_and_time_interval(driver, "10258_Les_matelots_du_port_St_Jacques.mei", 1.0, 1.875 + 0.125)

    driver.close()
