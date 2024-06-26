from find_nearby_pitches import find_frequency_bounds
from find_duration_range import find_duration_range_decimal, find_duration_range_multiplicative_factor
from extract_notes_from_query import extract_notes_from_query, extract_fuzzy_parameters
from utils import calculate_pitch_interval

import re

def reformulate_cypher_query(query):
    _, _, _, _, allow_transposition, _ = extract_fuzzy_parameters(query)

    if allow_transposition:
        return reformulate_with_transposition(query)
    else:
        return reformulate_without_transposition(query)

def make_duration_condition(duration_factor, duration, idx, fixed):
    if duration_factor != 1 and not fixed:
        min_duration, max_duration = find_duration_range_multiplicative_factor(duration, duration_factor)
        res = f"e{idx}.duration >= {min_duration} AND e{idx}.duration <= {max_duration}"
    else:
        duration = find_duration_range_multiplicative_factor(duration, 1.0)[0]
        res = f"e{idx}.duration = {duration}"
    return res

def make_sequencing_condition(duration_gap, idx):

    sequencing_condition = f"e{idx}.end >= e{idx+1}.start - {duration_gap}"
    return sequencing_condition

def reformulate_without_transposition(query):
    # Extract the parameters from the augmented query
    pitch_distance, duration_factor, duration_gap, alpha, allow_transposition, fixed_notes = extract_fuzzy_parameters(query)
    
    # Extract notes using the new function
    notes = extract_notes_from_query(query)

    # Construct the MATCH clause
    if duration_gap > 0:
        # To give a higher bound to the number of intermediate notes, we suppose the shortest possible note has a duration of 0.125
        max_intermediate_nodes = max(int(duration_gap / 0.125), 1)
        event_path = f"-[:NEXT*1..{max_intermediate_nodes + 1}]->".join([f"(e{idx}:Event)" for idx in range(len(notes))]) + ','
    else:
        event_path = f"-[]->".join([f"(e{idx}:Event)" for idx in range(len(notes))]) + ','  
    simplified_connections = ','.join([f"\n (e{idx})-[]->(f{idx}:Fact)" for idx in range(len(notes))])
    match_clause = 'MATCH \n' + event_path + simplified_connections

    # Construct the WHERE clause
    where_clauses = []
    sequencing_conditions = []
    # Small epsilon value for floating-point imprecision
    epsilon = 0.01
    for idx, (note, octave, duration) in enumerate(notes):
        # Prepare the frequency conditions
        if not fixed_notes[idx]:
            min_frequency, max_frequency = find_frequency_bounds(note, octave, pitch_distance)
        else:
            min_frequency, max_frequency = find_frequency_bounds(note, octave, 0)
        frequency_condition = f"f{idx}.frequency >= {round(min_frequency - epsilon, 2)} AND f{idx}.frequency <= {round(max_frequency + epsilon, 2)}"
    
        #Prepare the duration conditions
        duration_condition = make_duration_condition(duration_factor, duration, idx, fixed_notes[idx])

        # Adding sequencing conditions
        if idx < len(notes) - 1 and duration_gap > 0:
            sequencing_condition = make_sequencing_condition(duration_gap, idx)
            sequencing_conditions.append(sequencing_condition)

        where_clauses.append(f"{frequency_condition} AND {duration_condition}")
    
    # Assemble frequency, duration and sequencing conditions
    where_clause = 'WHERE\n' + ' AND\n'.join(where_clauses)
    if sequencing_conditions:
        sequencing_conditions = ' AND '.join(sequencing_conditions)
        where_clause = where_clause + ' AND \n' + sequencing_conditions

    return_clauses = []
    for idx in range(len(notes)):
        # Prepare return clauses with specified names
        return_clauses.extend([
            f"\nf{idx}.class AS pitch_{idx}",
            f"f{idx}.octave AS octave_{idx}",
            f"e{idx}.duration AS duration_{idx}",
            f"e{idx}.start AS start_{idx}",
            f"e{idx}.end AS end_{idx}",
            f"e{idx}.id AS id_{idx}"
        ])
    # Construct the RETURN clause
    return_clause = 'RETURN' + ', '.join(return_clauses) + f', \ne0.source AS source, e0.start AS start, e{len(notes) - 1}.end AS end'
    
    # Construct the final query
    new_query = match_clause + '\n' + where_clause + '\n' + return_clause
    return new_query

def reformulate_with_transposition(query):
    # Extract the parameters from the augmented query
    pitch_distance, duration_factor, duration_gap, alpha, allow_transposition, fixed_notes = extract_fuzzy_parameters(query)
    
    # Extract notes using the new function
    notes = extract_notes_from_query(query)
    
    # Compute the intervals between consecutive notes
    intervals = []
    for i in range(len(notes) - 1):
        note1, octave1, _ = notes[i]
        note2, octave2, _ = notes[i + 1]
        interval = calculate_pitch_interval(note1, octave1, note2, octave2)
        intervals.append(interval)

    # Construct MATCH clause
    if duration_gap > 0:
        # To give a higher bound to the number of intermediate notes, we suppose the shortest possible note has a duration of 0.125
        max_intermediate_nodes = max(int(duration_gap / 0.125), 1)
        event_path = ',\n'.join([f"p{idx} = (e{idx}:Event)-[:NEXT*1..{max_intermediate_nodes + 1}]->(e{idx+1}:Event)" for idx in range(len(notes) - 1)]) + ','
    else:
        event_path = "".join([f"(e{idx}:Event)-[r{idx}:NEXT]->" for idx in range(len(notes) - 1)]) + f"(e{len(notes) - 1}:Event)"+ ','
    simplified_connections = ','.join([f"\n (e{idx})-[]->(f{idx}:Fact)" for idx in range(len(notes))])
    match_clause = 'MATCH \n' + event_path + simplified_connections

    # Construct WITH clause
    with_clause = ""
    if duration_gap > 0:
        # Construct interval conditions for paths with intermediate nodes
        interval_conditions = []
        for idx in range(len(intervals)):
            interval_condition = f"reduce(totalInterval = 0, rel IN relationships(p{idx}) | totalInterval + rel.interval) AS totalInterval_{idx}"
            interval_conditions.append(interval_condition)
        # Adding the interval clauses if duration_gap is specified
        variables = ', '.join([f"e{idx}" for idx in range(len(notes))]) + ',\n' + ', '.join([f"f{idx}" for idx in range(len(notes))])
        with_clause = 'WITH\n' + variables + ',\n' + ',\n'.join(interval_conditions) + ' '


    # Construct WHERE clause
    where_clauses = []
    for idx, (note, octave, duration) in enumerate(notes):
        #Prepare the duration conditions
        duration_condition = make_duration_condition(duration_factor, duration, idx, fixed_notes[idx])
        if idx < len(notes) - 1:
            if duration_gap > 0:
                if pitch_distance > 0 and not fixed_notes[idx]:
                    interval_condition = f"totalInterval_{idx} <= {intervals[idx]} + {pitch_distance} AND totalInterval_{idx} >= {intervals[idx]} - {pitch_distance}"
                else:
                    interval_condition = f"totalInterval_{idx} = {intervals[idx]}"
            else:
                # Construct interval conditions for direct connections
                if pitch_distance > 0 and not fixed_notes[idx]:
                    interval_condition = f"r{idx}.interval <= {intervals[idx]} + {pitch_distance} AND r{idx}.interval >= {intervals[idx]} - {pitch_distance}"
                else:
                    interval_condition = f"r{idx}.interval = {intervals[idx]}"
            where_clauses.append(duration_condition + " AND " + interval_condition)
        else:
            where_clauses.append(duration_condition)
    where_clause = 'WHERE\n' + ' AND\n'.join(where_clauses)

    # Adding the sequencing constraints to the WHERE clause
    if duration_gap > 0:
        sequencing_conditions = []
        for idx in range(len(notes) - 1):
            sequencing_condition = make_sequencing_condition(duration_gap, idx)
            if sequencing_condition:
                sequencing_conditions.append(sequencing_condition)
        sequencing_conditions = ' AND '.join(sequencing_conditions)
        where_clause = where_clause + ' AND \n' + sequencing_conditions

    # Construct RETURN clause
    return_clauses = []
    for idx, (note, octave, duration) in enumerate(notes):
        # Prepare return clauses with specified names
        return_clauses.extend([
            f"\nf{idx}.class AS pitch_{idx}",
            f"f{idx}.octave AS octave_{idx}",
            f"e{idx}.duration AS duration_{idx}",
            f"e{idx}.start AS start_{idx}",
            f"e{idx}.end AS end_{idx}",
            f"e{idx}.id AS id_{idx}"
        ])
        if idx < len(notes) - 1:
            if duration_gap > 0:
                return_clauses.append(f"totalInterval_{idx} AS interval_{idx}")
            else:
                return_clauses.append(f"r{idx}.interval AS interval_{idx}")
    return_clause = 'RETURN' + ', '.join(return_clauses) + f', \ne0.source AS source, e0.start AS start, e{len(notes) - 1}.end AS end'

    # Assemble the query
    if duration_gap > 0:
        # Add the with clause if duration gap is positive
        new_query = match_clause + '\n' + with_clause + '\n' + where_clause + '\n' + return_clause
    else:
        new_query = match_clause + '\n' + where_clause + '\n' + return_clause

    return new_query

if __name__ == "__main__":
    with open('query.cypher', 'r') as file:
        augmented_query = file.read()
    print(reformulate_cypher_query(augmented_query))
