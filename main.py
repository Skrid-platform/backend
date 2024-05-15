import re
from find_nearby_pitches import find_nearby_pitches
from find_duration_range import find_duration_range

def extract_notes_from_query(query):
    # Regex to find note details within the query
    note_pattern = re.compile(r"\(f\d+\{class:'(\w+)',octave:(\d+), dur:(\d+)\}\)")
    # Extract all matches
    matches = note_pattern.findall(query)
    # Convert extracted values into a list of tuples (class, octave, duration)
    notes = [(match[0].lower(), int(match[1]), int(match[2])) for match in matches]
    return notes

def reformulate_cypher_query(query):
    # Extracting the parameters from the augmented query
    pitch_distance = int(re.search(r'TOLERANT pitch=(\d+)', query).group(1))
    duration_distance = int(re.search(r'duration=(\d+)', query).group(1))
    alpha = float(re.search(r'ALPHA (\d+\.\d+)', query).group(1))
    
    # Extract notes using the new function
    notes = extract_notes_from_query(query)
    
    # Compute the possible notes and duration ranges for each note
    where_clauses = []
    for idx, (note, octave, duration) in enumerate(notes, start=1):
        nearby_notes = find_nearby_pitches(note, octave, pitch_distance)
        min_duration, max_duration = find_duration_range(duration, duration_distance)
        
        # Prepare the pitch and octave conditions
        notes_condition = f"[f{idx}.class, f{idx}.octave] IN {nearby_notes}"
        
        # Prepare the duration conditions
        duration_condition = f"f{idx}.dur >= {min_duration} AND f{idx}.dur <= {max_duration}"
        
        where_clauses.append(f"{notes_condition} AND {duration_condition}")
    
    # Constructing the new WHERE clause
    where_clause = 'WHERE\n' + ' AND\n '.join(where_clauses)
    
    # Reconstruct the MATCH clause by removing parameters and simplifying node connection syntax
    event_path = '-[:NEXT]->'.join([f"(e{idx}:Event)" for idx in range(1, len(notes)+1)])+','
    simplified_connections = ','.join([f"\n (e{idx})--(f{idx})" for idx in range(1, len(notes)+1)])
    match_clause = 'MATCH \n' + event_path + simplified_connections

    # Reconstruct the RETURN clause
    return_clause = 'RETURN' + re.search(r'RETURN(.*)', query).group(1)
    
    # Construct the final query
    new_query = match_clause + '\n' + where_clause + '\n' + return_clause
    return new_query

# Example usage:
augmented_query = """
MATCH
 TOLERANT pitch=3, duration=2
 ALPHA 0.4
 (e1:Event)-[:NEXT]->(e2:Event)-[:NEXT]->(e3:Event), 
 (e1)--(f1{class:'E',octave:4, dur:4}),
 (e2)--(f2{class:'A',octave:4, dur:4}),
 (e3)--(f3{class:'E',octave:5, dur:4})
RETURN e1.id, e2.id, e3.id
"""
print(reformulate_cypher_query(augmented_query))
