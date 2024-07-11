from neo4j_connection import connect_to_neo4j, run_query
from generate_audio import generate_mp3
from note import Note

def create_query_from_list_of_notes(notes, pitch_distance, duration_factor, duration_gap, alpha, allow_transposition):
    # In : a list of notes (as class, octave, duration triples), gaps and alpha parameters
    # Out : a fuzzy query searching for the notes with the parameters
    if allow_transposition:
        match_clause = "MATCH\n ALLOW_TRANSPOSITION\n TOLERANT pitch={}, duration={}, gap={}\n ALPHA {}\n".format(
            pitch_distance, duration_factor, duration_gap, alpha)
    else:
        match_clause = "MATCH\n TOLERANT pitch={}, duration={}, gap={}\n ALPHA {}\n".format(
            pitch_distance, duration_factor, duration_gap, alpha)

    events = []
    facts = []
    
    for i, (class_, octave, duration) in enumerate(notes, start=1):
        event = "(e{}:Event)".format(i)
        fact = "(e{})--(f{}{{class:'{}', octave:{}, dur:{}}})".format(i, i, class_, octave, duration)
        events.append(event)
        facts.append(fact)
    
    match_clause += " " + "-[:NEXT]->".join(events) + ",\n " + ",\n ".join(facts)
    return_clause = "\nRETURN e1.source AS source, e1.start AS start"
    
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
    # Define pitches and their relative semitone positions from A
    notes = ['a', 'b', 'c', 'd', 'e', 'f', 'g']
    semitones_from_a = [0, 2, 3, 5, 7, 8, 10]  # A to G, cumulative semitone distance
    
    # Create a mapping from note to its index and semitone offset
    note_to_semitone = {note: semitones for note, semitones in zip(notes, semitones_from_a)}
    
    # Find the base semitone position for the given pitch and octave
    if pitch == 'a' or pitch == 'b' :
        base_semitone = note_to_semitone[pitch] + (octave * 12) + 21
    else :
        base_semitone = note_to_semitone[pitch] + ((octave - 1) * 12) + 21
    
    return base_semitone / 2.0

def calculate_pitch_interval(note1, octave1, note2, octave2):
    return calculate_base_stone(note2, octave2) - calculate_base_stone(note1, octave1)

if __name__ == "__main__":
    # Set up the driver
    uri = "bolt://localhost:7687"  # Default URI for a local Neo4j instance
    user = "neo4j"                 # Default username
    password = "12345678"          # Replace with your actual password
    driver = connect_to_neo4j(uri, user, password)

    generate_mp3_from_source_and_time_interval(driver, "10258_Les_matelots_du_port_St_Jacques.mei", 1.0, 1.875 + 0.125)

    driver.close()
