from neo4j import GraphDatabase
from note import Note
from degree_computation import pitch_degree, duration_degree, sequencing_degree
from reformulation_V2 import reformulate_cypher_query
from extract_notes_from_query import extract_notes_from_query, extract_fuzzy_parameters

# Function to connect to the Neo4j database
def connect_to_neo4j(uri, user, password):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    return driver

# Function to run a query and fetch all results
def run_query(driver, query):
    with driver.session() as session:
        result = session.run(query)
        return list(result)  # Collect all records into a list

# Function to process the query results and convert them to Note instances
def process_results(result, query_notes, pitch_gap, duration_gap, sequencing_gap):
    note_sequences = []
    for record in result:
        note_sequence = []
        for idx in range(1, 4):  # Assuming we have 3 notes in the result
            pitch = record[f"pitch_{idx}"]
            octave = record[f"octave_{idx}"]
            duration = record[f"duration_{idx}"]
            start = record[f"start_{idx}"]
            end = record[f"end_{idx}"]
            note = Note(pitch, octave, duration, start, end)
            note_sequence.append(note)
        note_sequences.append(note_sequence)
    
    # Compute and print degrees
    for seq_idx, note_sequence in enumerate(note_sequences):
        print(f"Sequence {seq_idx + 1}:")
        for idx, note in enumerate(note_sequence):
            query_note = query_notes[idx]
            pitch_deg = pitch_degree(query_note[0], query_note[1], note.pitch, note.octave, pitch_gap)
            duration_deg = duration_degree(query_note[2], note.duration, duration_gap)
            sequencing_deg = 1.0  # Default sequencing degree
            
            if idx > 0:  # Compute sequencing degree for the second and third notes
                prev_note = note_sequence[idx - 1]
                sequencing_deg = sequencing_degree(prev_note.end, note.start, sequencing_gap)
            
            print(f"  Note {idx + 1}: {note}")
            print(f"    Pitch Degree: {pitch_deg}")
            print(f"    Duration Degree: {duration_deg}")
            print(f"    Sequencing Degree: {sequencing_deg}")
        print()  # Add a blank line between sequences

# Main function
def main():
    # Set up the driver
    uri = "bolt://localhost:7687"  # Default URI for a local Neo4j instance
    user = "neo4j"                 # Default username
    password = "12345678"          # Replace with your actual password
    driver = connect_to_neo4j(uri, user, password)

    # Get the query
    with open('query.cypher', 'r') as file:
        augmented_query = file.read()

    # Extract the query notes and fuzzy parameters    
    query_notes = extract_notes_from_query(augmented_query)
    pitch_gap, duration_gap, sequencing_gap, alpha = extract_fuzzy_parameters(augmented_query)

    # compile, run and process the results of the query
    compiled_query = reformulate_cypher_query(augmented_query)
    result = run_query(driver, compiled_query)
    process_results(result, query_notes, pitch_gap, duration_gap, sequencing_gap)

    driver.close()

if __name__ == "__main__":
    main()
