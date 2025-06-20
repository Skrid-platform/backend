import re

from src.core.extract_notes_from_query import extract_match_clause, extract_where_clause, extract_return_clause

def combine_polyphonic_queries(queries):
    """
    Combines multiple crisp queries into a polyphonic query where each pattern appears in a different voice,
    and all patterns are simultaneous.

    Parameters:
        queries (list of str): List of crisp Cypher queries to be combined.

    Returns:
        str: A combined polyphonic Cypher query.
    """
    combined_query_parts = []
    with_clauses = []
    return_clauses = []
    propagating_with_clause_values = []

    for idx, query in enumerate(queries):
        # Extract parts of the query
        match_clause = extract_match_clause(query)
        where_clause = extract_where_clause(query)
        return_clause = extract_return_clause(query)

        # Find the first event in the event chain
        first_event_match = re.search(r'\((e\d+):Event\)', match_clause)
        if not first_event_match:
            raise ValueError(f"No event node found in the query at index {idx}.")
        first_event = first_event_match.group(1)

        # Modify the MATCH clause to include measure
        if idx == 0:
            # For the first query, add measure and extract voice and start time
            match_clause += f',\n    (m:Measure)-[:HAS]->({first_event})'
        else:
            # For subsequent queries, start from the same measure and ensure different voices and simultaneous start
            match_clause = f'MATCH\n    (m)-[:HAS]->({first_event}),' + match_clause[len('MATCH'):]
            where_clause += '\n    AND ' + ' AND '.join([f'e0.voice_nb <> voice_nb_{i+1}' for i in range(idx)]) + f'\n    AND {first_event}.start = start'

        # Append modified query parts
        combined_query_parts.append(f'{match_clause}\n{where_clause}')

        # Extract variables from the return clause
        return_vars = re.findall(r'\b([\w\.]+) AS (\w+)', return_clause)
        return_var_clauses = [f"{original} AS {alias}_{idx+1}" for original, alias in return_vars]

        # Build WITH clause for passing variables
        if idx == 0:
            with_clause = f'WITH {", ".join(return_var_clauses)}, {first_event}.voice_nb AS voice_nb_{idx+1}, m, {first_event}.start AS start'
            
        else:
            with_clause = f'WITH {", ".join(propagating_with_clause_values + return_var_clauses)}, {first_event}.voice_nb AS voice_nb_{idx+1}, m, start'
        
        # Update values that will be propagated
        propagating_with_clause_values.extend([f'{alias}_{idx+1}' for original, alias in return_vars] + [f'voice_nb_{idx+1}'])

        with_clauses.append(with_clause)

        # Adjust return clauses to include suffixed variable names
        return_clauses.extend([f'{alias}_{idx+1}' for _, alias in return_vars])

    # Combine all query parts
    combined_query = ''
    for i in range(len(queries)):
        combined_query += f'{combined_query_parts[i]}\n{with_clauses[i]}\n'

    combined_return_clause = 'RETURN ' + ', '.join(return_clauses)

    # Final assembly
    combined_query += f'{combined_return_clause}'

    return combined_query


if __name__ == "__main__":
    q1 = """MATCH
(e0:Event)-[n0:NEXT]->(e1:Event)-[n1:NEXT]->(e2:Event)-[n2:NEXT]->(e3:Event)-[n3:NEXT]->(e4:Event),
 (e0)--(f0:Fact),
 (e1)--(f1:Fact),
 (e2)--(f2:Fact),
 (e3)--(f3:Fact),
 (e4)--(f4:Fact)
WHERE
f0.duration = 0.25 AND
f0.class = 'f' AND NOT EXISTS(f0.accid) AND f0.octave = 4 AND
f1.duration = 0.125 AND
f1.class = 'g' AND NOT EXISTS(f1.accid) AND f1.octave = 4 AND
f2.duration = 0.125 AND
f2.class = 'f' AND NOT EXISTS(f2.accid) AND f2.octave = 4 AND
f3.duration = 0.25 AND
f3.class = 'e' AND NOT EXISTS(f3.accid) AND f3.octave = 4 AND
f4.duration = 0.25 AND
f4.class = 'f' AND NOT EXISTS(f4.accid) AND f4.octave = 4
RETURN
e0.duration AS duration_0, e0.dots AS dots_0, e0.start AS start_0, e0.end AS end_0, e0.id AS id_0, 
e1.duration AS duration_1, e1.dots AS dots_1, e1.start AS start_1, e1.end AS end_1, e1.id AS id_1, 
e2.duration AS duration_2, e2.dots AS dots_2, e2.start AS start_2, e2.end AS end_2, e2.id AS id_2, 
e3.duration AS duration_3, e3.dots AS dots_3, e3.start AS start_3, e3.end AS end_3, e3.id AS id_3, 
e4.duration AS duration_4, e4.dots AS dots_4, e4.start AS start_4, e4.end AS end_4, e4.id AS id_4, 
f0.octave AS octave_0, f0.class AS pitch_0, 
f1.octave AS octave_1, f1.class AS pitch_1, 
f2.octave AS octave_2, f2.class AS pitch_2, 
f3.octave AS octave_3, f3.class AS pitch_3, 
f4.octave AS octave_4, f4.class AS pitch_4, 
e0.source AS source, e0.start AS start, e4.end AS end"""

    q2 = """MATCH
(e0:Event)-[n0:NEXT]->(e1:Event)-[n1:NEXT]->(e2:Event)-[n2:NEXT]->(e3:Event),
 (e0)--(f0:Fact),
 (e1)--(f1:Fact),
 (e2)--(f2:Fact),
 (e3)--(f3:Fact)
WHERE
f0.duration = 0.25 AND
f0.class = 'c' AND NOT EXISTS(f0.accid) AND f0.octave = 4 AND
f1.duration = 0.25 AND
f1.class = 'c' AND NOT EXISTS(f1.accid) AND f1.octave = 4 AND
f2.duration = 0.25 AND
f2.class = 'c' AND NOT EXISTS(f2.accid) AND f2.octave = 4 AND
f3.duration = 0.25 AND
f3.class = 'c' AND NOT EXISTS(f3.accid) AND f3.octave = 4
RETURN
e0.duration AS duration_0, e0.dots AS dots_0, e0.start AS start_0, e0.end AS end_0, e0.id AS id_0, 
e1.duration AS duration_1, e1.dots AS dots_1, e1.start AS start_1, e1.end AS end_1, e1.id AS id_1, 
e2.duration AS duration_2, e2.dots AS dots_2, e2.start AS start_2, e2.end AS end_2, e2.id AS id_2, 
e3.duration AS duration_3, e3.dots AS dots_3, e3.start AS start_3, e3.end AS end_3, e3.id AS id_3, 
f0.octave AS octave_0, f0.class AS pitch_0, 
f1.octave AS octave_1, f1.class AS pitch_1, 
f2.octave AS octave_2, f2.class AS pitch_2, 
f3.octave AS octave_3, f3.class AS pitch_3, 
e0.source AS source, e0.start AS start, e3.end AS end"""

    q = combine_polyphonic_queries([q1, q2])
    print(q)
