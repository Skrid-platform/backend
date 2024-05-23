from main import connect_to_neo4j, run_query
from reformulation_V2 import reformulate_cypher_query
from generate_audio import generate_mp3

def create_cypher_query(notes, pitch_distance, duration_distance, duration_gap, alpha):
    match_clause = "MATCH\n TOLERANT pitch={}, duration={}, gap={}\n ALPHA {}\n".format(
        pitch_distance, duration_distance, duration_gap, alpha)
    
    events = []
    facts = []
    
    for i, (cls, octave, duration) in enumerate(notes, start=1):
        event = "(e{}:Event)".format(i)
        fact = "(e{})--(f{}{{class:'{}',octave:{}, dur:{}}})".format(i, i, cls, octave, duration)
        events.append(event)
        facts.append(fact)
    
    match_clause += " " + "-[:NEXT]->".join(events) + ",\n " + ",\n ".join(facts)
    return_clause = "\nRETURN e1.source AS source, e1.start AS start"
    
    query = match_clause + return_clause
    return query

def create_first_k_notes_query(k):
    # Initialize the MATCH and WHERE clauses
    match_clause = "MATCH\n"
    event_chain = []
    fact_chain = []
    
    for i in range(1, k + 1):
        event_chain.append(f"(e{i}:Event)")
        fact_chain.append(f"(e{i})--(f{i}:Fact)")

    match_clause += "-[:NEXT]->".join(event_chain) + ",\n " + ",\n ".join(fact_chain)
    
    # Add the WHERE clause
    where_clause = "\nWHERE\n e1.start = 0"
    
    # Initialize the RETURN clause
    return_clause = "\nRETURN\n"
    return_fields = []
    
    for i in range(1, k + 1):
        return_fields.append(f"f{i}.class AS pitch_{i}, f{i}.octave AS octave_{i}, e{i}.duration AS duration_{i}")
    
    return_fields.append("e1.source AS source")
    
    return_clause += ",\n".join(return_fields)
    
    # Combine all clauses into the final query
    query = match_clause + where_clause + return_clause
    return query

def process_first_k_notes_results(result, k):
    sequences = []
    
    for record in result:
        sequence = []
        for i in range(1, k + 1):
            pitch = record[f"pitch_{i}"]
            octave = record[f"octave_{i}"]
            duration = record[f"duration_{i}"]
            note = (pitch, octave, 1/duration)
            sequence.append(note)
        sequences.append(sequence)
    
    return sequences

def query_and_generate_mp3(driver, source, start_time, end_time, bpm=60):
    query = f"""
    MATCH (e:Event)-[]->(f:Fact)
    WHERE e.start >= {start_time} AND e.end <= {end_time} AND e.source = '{source}'
    RETURN f.class AS class, f.octave AS octave, f.dur AS duration
    ORDER BY e.start
    """

    results = run_query(driver, query)
    notes = [(record['class'], record['octave'], record['duration']) for record in results]

    file_name = f"{source}_{start_time}_{end_time}.mp3"
    generate_mp3(notes, file_name, bpm)

if __name__ == "__main__":
    # Set up the driver
    uri = "bolt://localhost:7687"  # Default URI for a local Neo4j instance
    user = "neo4j"                 # Default username
    password = "12345678"          # Replace with your actual password
    driver = connect_to_neo4j(uri, user, password)

    # k = 10
    # query = create_first_k_notes_query(k)
    # result = run_query(driver, query)
    # incipits = process_first_k_notes_results(result, k)

    # notes = incipits[1]
    # pitch_distance = 1
    # duration_distance = 0.125
    # duration_gap = 0.25
    # alpha = 0.4

    # augmented_query = create_cypher_query(notes, pitch_distance, duration_distance, duration_gap, alpha)
    # print(reformulate_cypher_query(augmented_query))

    # print(notes)
    # generate_mp3(notes)

    query_and_generate_mp3(driver, 'Air_n_78.mei', 5.3125, 6.875 + 0.125, 60)

    driver.close()