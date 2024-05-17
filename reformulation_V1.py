from find_nearby_pitches import find_nearby_pitches
from find_duration_range import find_duration_range
from extract_notes_from_query import extract_notes_from_query

import re

# This version tries to stick to the augmented query syntax as much as possible
# Pitches intervals are given through the class and octave of Facts nodes
# Durations intervals are given through the duration of Facts nodes
# ALPHA parameter is not taken into account

def reformulate_cypher_query(query):
    # Extracting the parameters from the augmented query
    pitch_distance = int(re.search(r'TOLERANT pitch=(\d+)', query).group(1))
    duration_distance = float(re.search(r'duration=(\d+\.\d+|\d+)', query).group(1))
    duration_gap = float(re.search(r'gap=(\d+\.\d+|\d+)', query).group(1))
    print(pitch_distance, duration_distance, duration_gap)

    # Extract notes
    notes = extract_notes_from_query(query)
    
    # Compute the possible notes and duration ranges for each note
    where_clauses = []
    for idx, (note, octave, duration) in enumerate(notes, start=1):
        nearby_notes = find_nearby_pitches(note, octave, pitch_distance)
        min_duration, max_duration = find_duration_range(duration, duration_distance)
        
        # Prepare the pitch and octave conditions
        notes_condition = f"[f{idx}.class, f{idx}.octave] IN {nearby_notes}"
        
        # Prepare the duration conditions
        duration_condition = f"f{idx}.dur <= {min_duration} AND f{idx}.dur >= {max_duration}" # Comparisons are inverted because durations are ratios
        
        where_clauses.append(f" {notes_condition} AND {duration_condition}")
    
    # Constructing the new WHERE clause
    where_clause = 'WHERE\n' + ' AND\n'.join(where_clauses)

    # Adding the sequencing constraints to the where clause
    sequencing_condition = ' AND '.join([f"e{idx}.end >= e{idx+1}.start - {duration_gap}" for idx in range(1, len(notes))])
    where_clause = where_clause + ' AND \n ' + sequencing_condition
    
    # Reconstruct the MATCH clause by removing parameters and simplifying node connection syntax
    event_path = '-[*]->'.join([f"(e{idx}:Event)" for idx in range(1, len(notes)+1)])+','
    simplified_connections = ','.join([f"\n (e{idx})-[]->(f{idx}:Fact)" for idx in range(1, len(notes)+1)])
    match_clause = 'MATCH \n' + event_path + simplified_connections

    # Reconstruct the RETURN clause
    return_clause = 'RETURN' + re.search(r'RETURN(.*)', query).group(1)
    
    # Construct the final query
    new_query = match_clause + '\n' + where_clause + '\n' + return_clause
    return new_query


if __name__ == "__main__":
    with open('query.cypher', 'r') as file:
        augmented_query = file.read()
    print(reformulate_cypher_query(augmented_query))
