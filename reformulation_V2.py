from find_nearby_pitches import find_frequency_bounds
from find_duration_range import find_duration_range_decimal, find_duration_range_multiplicative_factor
from extract_notes_from_query import extract_notes_from_query, extract_fuzzy_parameters
from utils import calculate_pitch_interval

import re

# This version uses float values for pitch (Fact.frequency) and duration (Event.duration)
# ALPHA parameter is not taken into account
def reformulate_cypher_query(query):
    _, _, _, _, allow_transposition = extract_fuzzy_parameters(query)

    if allow_transposition:
        return reformulate_with_transposition(query)
    else:
        return reformulate_without_transposition(query)


def reformulate_without_transposition(query):
    # Extract the parameters from the augmented query
    pitch_distance, duration_factor, duration_gap, alpha, allow_transposition = extract_fuzzy_parameters(query)
    
    # Extract notes using the new function
    notes = extract_notes_from_query(query)
    
    # Compute the possible notes and duration ranges for each note
    where_clauses = []
    return_clauses = []
    # Small epsilon value for floating-point imprecision
    epsilon = 0.01
    for idx, (note, octave, duration) in enumerate(notes):
        # Prepare the frequency conditions
        min_frequency, max_frequency = find_frequency_bounds(note, octave, pitch_distance)
        frequency_condition = f"f{idx}.frequency >= {min_frequency - epsilon} AND f{idx}.frequency <= {max_frequency + epsilon}"
    
        #Prepare the duration conditions
        if duration_factor != 1:
            min_duration, max_duration = find_duration_range_multiplicative_factor(duration, duration_factor)
            duration_condition = f"e{idx}.duration >= {min_duration} AND e{idx}.duration <= {max_duration}"
        else:
            duration = find_duration_range_multiplicative_factor(duration, duration_factor)[0]
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
        # To give a higher bound to the number of intermediate notes, we suppose the shortest possible note has a duration of 0.125
        max_intermediate_nodes = max(int(duration_gap / 0.125), 1)
        event_path = f"-[:NEXT*1..{max_intermediate_nodes + 1}]->".join([f"(e{idx}:Event)" for idx in range(len(notes))]) + ','
    else:
        event_path = f"-[]->".join([f"(e{idx}:Event)" for idx in range(len(notes))]) + ','  
    simplified_connections = ','.join([f"\n (e{idx})-[]->(f{idx}:Fact)" for idx in range(len(notes))])
    match_clause = 'MATCH \n' + event_path + simplified_connections

    # Construct the RETURN clause
    return_clause = 'RETURN' + ', '.join(return_clauses) + f', \ne0.source AS source, e0.start AS start, e{len(notes) - 1}.end AS end'
    
    # Construct the final query
    new_query = match_clause + '\n' + where_clause + '\n' + return_clause
    return new_query

def reformulate_with_transposition(query):
    # Extract the parameters from the augmented query
    pitch_distance, duration_factor, duration_gap, alpha, allow_transposition = extract_fuzzy_parameters(query)
    
    # Extract notes using the new function
    notes = extract_notes_from_query(query)
    print(notes)
    
    # Compute the intervals between consecutive notes
    intervals = []
    for i in range(len(notes) - 1):
        note1, octave1, _ = notes[i]
        note2, octave2, _ = notes[i + 1]
        interval = calculate_pitch_interval(note1, octave1, note2, octave2)
        intervals.append(interval)
    
    where_clauses = []
    return_clauses = []
    interval_clauses = []
    
    # Small epsilon value for floating-point imprecision
    epsilon = 0.01
    
    for idx, (note, octave, duration) in enumerate(notes):
        #Prepare the duration conditions
        if duration_factor != 1:
            min_duration, max_duration = find_duration_range_multiplicative_factor(duration, duration_factor)
            duration_condition = f"e{idx}.duration >= {min_duration} AND e{idx}.duration <= {max_duration}"
        else:
            duration = find_duration_range_multiplicative_factor(duration, duration_factor)[0]
            duration_condition = f"e{idx}.duration = {duration}"
        where_clauses.append(duration_condition)
        
        # Prepare return clauses with specified names
        return_clauses.extend([
            f"\nf{idx}.class AS pitch_{idx}",
            f"f{idx}.octave AS octave_{idx}",
            f"e{idx}.duration AS duration_{idx}",
            f"e{idx}.start AS start_{idx}",
            f"e{idx}.end AS end_{idx}"
        ])
        if idx < len(notes) - 1:
            if duration_gap > 0:
                return_clauses.extend([
                    f"totalInterval_{idx} AS interval_{idx}"
                ])
            else:
                return_clauses.extend([
                    f"r{idx}.interval AS interval_{idx}"
                ])

    # Handle duration_gap
    if duration_gap > 0:
        # To give a higher bound to the number of intermediate notes, we suppose the shortest possible note has a duration of 0.125
        max_intermediate_nodes = max(int(duration_gap / 0.125), 1)
        event_path = ',\n'.join([f"p{idx} = (e{idx}:Event)-[:NEXT*1..{max_intermediate_nodes + 1}]->(e{idx+1}:Event)" for idx in range(len(notes) - 1)]) + ','
        
        # Construct interval conditions for paths with intermediate nodes
        for idx in range(len(intervals)):
            interval_clause = f"reduce(totalInterval = 0, rel IN relationships(p{idx}) | totalInterval + rel.interval) AS totalInterval_{idx}"
            interval_clauses.append(interval_clause)
            if pitch_distance > 0:
                where_clauses.append(f"totalInterval_{idx} <= {intervals[idx]} + {pitch_distance} AND totalInterval_{idx} >= {intervals[idx]} - {pitch_distance}")
            else:
                where_clauses.append(f"totalInterval_{idx} = {intervals[idx]}")
        
    else:
        event_path = "".join([f"(e{idx}:Event)-[r{idx}:NEXT]->" for idx in range(len(notes) - 1)]) + f"(e{len(notes) - 1}:Event)"+ ','

        # Construct interval conditions for direct connections
        for idx in range(len(intervals)):
            if pitch_distance > 0:
                where_clauses.append(f"r{idx}.interval <= {intervals[idx]} + {pitch_distance} AND r{idx}.interval >= {intervals[idx]} - {pitch_distance}")
            else:
                where_clauses.append(f"r{idx}.interval = {intervals[idx]}")
    
    simplified_connections = ','.join([f"\n (e{idx})-[]->(f{idx}:Fact)" for idx in range(len(notes))])
    match_clause = 'MATCH \n' + event_path + simplified_connections

    # Constructing the new WHERE clause
    where_clause = 'WHERE\n' + ' AND\n'.join(where_clauses)

    # Adding the sequencing constraints to the WHERE clause
    if duration_gap > 0:
        sequencing_condition = ' AND '.join([f"e{idx}.end >= e{idx+1}.start - {duration_gap}" for idx in range(len(notes) - 1)])
        where_clause = where_clause + ' AND \n' + sequencing_condition

    # Construct the RETURN clause
    return_clause = 'RETURN' + ', '.join(return_clauses) + f', \ne0.source AS source, e0.start AS start, e{len(notes) - 1}.end AS end'
    
    if duration_gap > 0:
        # Adding the interval clauses if duration_gap is specified
        variables = ', '.join([f"e{idx}" for idx in range(len(notes))]) + ',\n' + ', '.join([f"f{idx}" for idx in range(len(notes))])
        interval_with_clause = 'WITH\n' + variables + ',\n' + ',\n'.join(interval_clauses) + ' '
        new_query = match_clause + '\n' + interval_with_clause + '\n' + where_clause + '\n' + return_clause
    else:
        new_query = match_clause + '\n' + where_clause + '\n' + return_clause

    return new_query

if __name__ == "__main__":
    with open('query.cypher', 'r') as file:
        augmented_query = file.read()
    print(reformulate_cypher_query(augmented_query))