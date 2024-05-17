from find_nearby_pitches import find_frequency_bounds
from find_duration_range import find_duration_range_decimal
from extract_notes_from_query import extract_notes_from_query

import re

# This version uses float values for pitch (Fact.frequency) and duration (Fact.duration)
# ALPHA parameter is not taken into account

def reformulate_cypher_query(query):

    # Extracting the parameters from the augmented query
    pitch_distance = int(re.search(r'TOLERANT pitch=(\d+)', query).group(1))
    duration_distance = float(re.search(r'duration=(\d+\.\d+|\d+)', query).group(1))
    duration_gap = float(re.search(r'gap=(\d+\.\d+|\d+)', query).group(1))
    alpha = float(re.search(r'ALPHA (\d+\.\d+)', query).group(1))
    
    # Extract notes
    notes = extract_notes_from_query(query)
    
    # Compute the possible notes and duration ranges for each note
    where_clauses = []
    for idx, (note, octave, duration) in enumerate(notes, start=1):
        min_frequency, max_frequency = find_frequency_bounds(note, octave, pitch_distance)
        min_duration, max_duration = find_duration_range_decimal(duration, duration_distance)
        
        # Prepare the frequency and duration conditions
        frequency_condition = f"f{idx}.frequency >= {min_frequency} AND f{idx}.frequency <= {max_frequency}"
        duration_condition = f"f{idx}.duration >= {min_duration} AND f{idx}.duration <= {max_duration}"
        
        where_clauses.append(f"{frequency_condition} AND {duration_condition}")
    
    # Constructing the new WHERE clause
    where_clause = 'WHERE\n' + ' AND\n'.join(where_clauses)

    # Adding the sequencing constraints to the WHERE clause
    sequencing_condition = ' AND '.join([f"e{idx}.end >= e{idx+1}.start - {duration_gap}" for idx in range(1, len(notes))])
    where_clause = where_clause + ' AND \n' + sequencing_condition
    
    # Reconstruct the MATCH clause by removing parameters and simplifying node connection syntax
    event_path = '-[*]->'.join([f"(e{idx}:Event)" for idx in range(1, len(notes) + 1)]) + ','
    simplified_connections = ','.join([f"\n (e{idx})-[]->(f{idx}:Fact)" for idx in range(1, len(notes) + 1)])
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