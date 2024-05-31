from find_nearby_pitches import find_frequency_bounds
from find_duration_range import find_duration_range_decimal
from extract_notes_from_query import extract_notes_from_query, extract_fuzzy_parameters

import re

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

def calculate_interval(note1, octave1, note2, octave2):
    return calculate_base_stone(note2, octave2) - calculate_base_stone(note1, octave1)

# This version uses float values for pitch (Fact.frequency) and duration (Event.duration)
# ALPHA parameter is not taken into account
def reformulate_cypher_query(query):
    # Extract the parameters from the augmented query
    pitch_distance, duration_distance, duration_gap, alpha, allow_transposition = extract_fuzzy_parameters(query)
    
    # Extract notes using the new function
    notes = extract_notes_from_query(query)
    
    # Compute the possible notes and duration ranges for each note
    where_clauses = []
    return_clauses = []
    for idx, (note, octave, duration) in enumerate(notes):
        # Prepare the frequency conditions
        if pitch_distance > 0:
            min_frequency, max_frequency = find_frequency_bounds(note, octave, pitch_distance)
            frequency_condition = f"f{idx}.frequency >= {min_frequency} AND f{idx}.frequency <= {max_frequency}"
        else:
            frequency = find_frequency_bounds(note, octave, pitch_distance)[0]
            frequency_condition = f"f{idx}.frequency = {frequency}"
    
        #Prepare the duration conditions
        if duration_distance > 0:
            min_duration, max_duration = find_duration_range_decimal(duration, duration_distance)
            duration_condition = f"e{idx}.duration >= {min_duration} AND e{idx}.duration <= {max_duration}"
        else:
            duration = find_duration_range_decimal(duration, duration_distance)[0]
            duration_condition = f"e{idx}.duration = {duration}"
        where_clauses.append(f"{frequency_condition} AND {duration_condition}")
        
        # Prepare return clauses with specified names
        return_clauses.extend([
            f"\nf{idx}.class AS pitch_{idx}",
            f"f{idx}.octave AS octave_{idx}",
            f"e{idx}.duration AS duration_{idx}",
            f"e{idx}.start AS start_{idx}",
            f"e{idx}.end AS end_{idx}"
        ])
    
    # Constructing the new WHERE clause
    where_clause = 'WHERE\n' + ' AND\n'.join(where_clauses)

    # Adding the sequencing constraints to the WHERE clause
    if duration_gap > 0:
        sequencing_condition = ' AND '.join([f"e{idx}.end >= e{idx+1}.start - {duration_gap}" for idx in range(len(notes) - 1)])
        where_clause = where_clause + ' AND \n' + sequencing_condition
    
    if duration_gap > 0:
        max_intermediate_nodes = int(duration_gap / 0.015625)
        event_path = f"-[*0..{max_intermediate_nodes}]->".join([f"(e{idx}:Event)" for idx in range(len(notes))]) + ','
    else:
        event_path = f"-[]->".join([f"(e{idx}:Event)" for idx in range(len(notes))]) + ','  
    simplified_connections = ','.join([f"\n (e{idx})-[]->(f{idx}:Fact)" for idx in range(len(notes))])
    match_clause = 'MATCH \n' + event_path + simplified_connections

    # Construct the RETURN clause
    return_clause = 'RETURN' + ', '.join(return_clauses) + ', \n' + 'e0.source AS source, e0.start AS start'
    
    # Construct the final query
    new_query = match_clause + '\n' + where_clause + '\n' + return_clause
    return new_query

if __name__ == "__main__":
    with open('query.cypher', 'r') as file:
        augmented_query = file.read()
    print(reformulate_cypher_query(augmented_query))