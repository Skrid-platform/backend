import re
from find_nearby_pitches import find_frequency_bounds, find_nearby_pitches
from extract_notes_from_query import extract_notes_from_query_dict, extract_fuzzy_parameters, extract_match_clause, extract_where_clause, extract_attributes_with_membership_functions, extract_membership_function_support_intervals
from find_duration_range import find_duration_range_decimal, find_duration_range_multiplicative_factor_asym, find_duration_range_multiplicative_factor_sym
from utils import calculate_intervals_dict
from degree_computation import convert_note_to_sharp
from refactor import move_attribute_values_to_where_clause, refactor_variable_names

def make_duration_condition(duration_factor, duration, node_name):
    if duration == None:
        return ''

    if duration_factor != 1:
        min_duration, max_duration = find_duration_range_multiplicative_factor_sym(duration, duration_factor)
        res = f"{node_name}.dur >= {min_duration} AND {node_name}.dur <= {max_duration}"
    else:
        duration = find_duration_range_multiplicative_factor_sym(duration, 1.0)[0]
        res = f"{node_name}.dur = {duration}"
    return res

def make_interval_condition(interval, duration_gap, pitch_distance, idx):
    if duration_gap > 0:
        if pitch_distance > 0:
            interval_condition = f'{interval - pitch_distance} <= totalInterval_{idx} AND totalInterval_{idx} <= {interval + pitch_distance}'
        else:
            interval_condition = f'totalInterval_{idx} = {interval}'
    else:
        # Construct interval conditions for direct connections
        if pitch_distance > 0:
            interval_condition = f'{interval - pitch_distance} <= n{idx}.interval AND n{idx}.interval <= {interval + pitch_distance}'
        else:
            interval_condition = f'n{idx}.interval = {interval}'
    return interval_condition

def split_note_accidental(note):
    """
    Splits a note string into its base note and accidental.

    Parameters:
        note (str): The note string (e.g., 'c', 'c#', 'db').

    Returns:
        tuple: A tuple containing the base note and accidental.
    """
    match = re.match(r'^([a-gA-G])([s#]?)$', note)
    if match:
        base_note = match.group(1).lower()
        accidental = match.group(2)
        if accidental == '':
            accidental = None
        else:
            # Sharps are notated with s here (can be # or s in find_nearby_pitches)
            accidental = 's'
        return base_note, accidental
    else:
        raise ValueError(f"Invalid note name: {note}")

def make_pitch_condition(pitch_distance, pitch, octave, name):
    """
    Creates a pitch condition for a given note, handling accidentals properly.

    Parameters:
        pitch_distance (float): The pitch distance tolerance.
        pitch (str): The pitch class.
        octave (int): The octave number.
        name (str): The variable name of the note in the query.

    Returns:
        str: The pitch condition as a string.
    """
    if pitch is None:
        if octave is None:
            pitch_condition = ''
        else:
            pitch_condition = f"{name}.octave = {octave}"
    else:
        if pitch_distance == 0 or pitch == 'r':
            if pitch == 'r':
                pitch_condition = f"{name}.class = 'r'"
            else:
                # Split pitch into base note and accidental
                base_note, accidental = split_note_accidental(pitch)
                pitch_condition = f"{name}.class = '{base_note}'"
                if accidental:
                    # Add condition for accidental, including accid and accid_ges
                    pitch_condition += f" AND ({name}.accid = '{accidental}' OR {name}.accid_ges = '{accidental}')"
                else:
                    # No accidental, so accid is NULL or empty
                    pitch_condition += f" AND NOT EXISTS({name}.accid) AND NOT EXISTS({name}.accid)"
                if octave is not None:
                    pitch_condition += f" AND {name}.octave = {octave}"
        else:
            o = 4 if octave is None else octave  # Default octave if not specified
            near_pitches = find_nearby_pitches(pitch, o, pitch_distance)
            print(near_pitches)

            pitch_condition = '('
            for n, o_ in near_pitches:
                base_note, accidental = split_note_accidental(n)
                base_condition = f"{name}.class = '{base_note}'"
                if accidental:
                    base_condition += f" AND ({name}.accid = '{accidental}' OR {name}.accid_ges = '{accidental}')"
                else:
                    base_condition += f" AND NOT EXISTS({name}.accid) AND NOT EXISTS({name}.accid)"
                if octave is None:
                    pitch_condition += f"\n  ({base_condition}) OR "
                else:
                    pitch_condition += f"\n  ({base_condition} AND {name}.octave = {o_}) OR "
            # Remove the trailing ' OR ' and close the parentheses
            pitch_condition = pitch_condition.rstrip(' OR ') + '\n)'
    return pitch_condition

def make_sequencing_condition(duration_gap, name_1, name_2):
    sequencing_condition = f"{name_1}.end >= {name_2}.start - {duration_gap}"
    return sequencing_condition

def create_match_clause(query):
    '''
    Create the MATCH clause for the compiled query.

    - query        : the entire query string;
    '''

    _, _, duration_gap, _, allow_transposition, _, _, _ = extract_fuzzy_parameters(query)

    if duration_gap > 0:
        # Proceed to create the MATCH clause as per current code

        #---Extract notes from the query
        notes = extract_notes_from_query_dict(query)

        #---Init
        event_nodes = [node for node, attrs in notes.items() if attrs.get('type') == 'Event']

        nb_events = len(event_nodes)

        # To give a higher bound to the number of intermediate notes, we suppose the shortest possible note has a duration of 0.125
        max_intermediate_nodes = max(int(duration_gap / 0.125), 1)

        if allow_transposition:
            # Create paths with variable length relationships using variable node names
            event_paths = []
            for idx in range(len(event_nodes) - 1):
                path = f'p{idx} = (e{idx}:Event)-[:NEXT*1..{max_intermediate_nodes + 1}]->(e{idx+1})'
                event_paths.append(path)
            event_path = ',\n '.join(event_paths) + ','
        else:
            # Create a simplified path without intervals
            event_path = f'-[:NEXT*1..{max_intermediate_nodes + 1}]->'.join([f'({node}:Event)' for node in event_nodes]) + ','

        #---Extract the rest of the MATCH clause (non-event chain patterns) from the input query
        original_match_clause = extract_match_clause(query)

        # Remove fuzzy parameters definitions (if any)
        # Find the position of the first '(' after MATCH
        match_start = original_match_clause.find('MATCH')
        first_paren = original_match_clause.find('(', match_start)
        if first_paren == -1:
            raise ValueError('No node patterns found in MATCH clause')

        # Extract the body of the MATCH clause
        match_body = original_match_clause[first_paren:].strip()

        # Split the MATCH clause into individual patterns separated by commas
        patterns = [p.strip() for p in re.split(r',\s*\n?', match_body) if p.strip()]
        # Now filter out the event chain patterns
        # Assume event chain patterns involve only event nodes connected via :NEXT relationships

        # Build a set of event node names
        event_node_names = set(event_nodes)

        # Define a function to check if a pattern is part of the event chain
        def is_event_chain_pattern(pattern):
            # Find all nodes in the pattern
            nodes = re.findall(r'\(\s*(\w+)(?::[^\)]*)?\s*\)', pattern)
            # Check if all nodes are event nodes (start with 'e')
            for node in nodes:
                if not node.startswith('e'):
                    return False
            # All nodes are event nodes
            return True

        # Filter out the event chain patterns
        simplified_connections = [
            p for p in patterns if not is_event_chain_pattern(p)
        ]

        # Reconstruct the simplified connections as a string
        simplified_connections_str = ',\n '.join(simplified_connections)

        #---Create MATCH clause
        match_clause = 'MATCH\n ' + event_path
        if simplified_connections_str:
            match_clause += '\n ' + simplified_connections_str

        return match_clause
    else:
        # duration_gap <= 0, so we just extract the MATCH clause from the query
        match_clause = extract_match_clause(query)

        # Remove fuzzy parameters definitions (everything between MATCH and the first '(')
        # Find the position of the first '(' after MATCH
        match_start = match_clause.find('MATCH')
        first_paren = match_clause.find('(', match_start)
        if first_paren == -1:
            raise ValueError('No node patterns found in MATCH clause')
        # Extract the cleaned MATCH clause
        match_clause = 'MATCH\n' + match_clause[first_paren:].lstrip()

        return match_clause

def create_with_clause_interval(nb_events, duration_gap):
    '''
    Create the WITH clause for the compilated query that need intervals (so with `allow_transposition` or `contour`).

    - nb_events    : the number of Events ;
    - duration_gap : the duration gap.
    '''

    with_clause = ""
    if duration_gap > 0:
        # Construct interval conditions for paths with intermediate nodes
        interval_conditions = []

        for idx in range(nb_events - 1): # nb of intervals
            interval_condition = f"reduce(totalInterval = 0, rel IN relationships(p{idx}) | totalInterval + rel.interval) AS totalInterval_{idx}"
            interval_conditions.append(interval_condition)

        # Adding the interval clauses if duration_gap is specified
        variables = ' ' + ', '.join([f"e{idx}" for idx in range(nb_events)]) + ',\n ' + ', '.join([f"f{idx}" for idx in range(nb_events)])
        with_clause = 'WITH\n' + variables + ',\n ' + ',\n '.join(interval_conditions) + ' '

    return with_clause

def create_where_clause(query, allow_transposition, pitch_distance, duration_factor, duration_gap):
    # Step 1: Extract the WHERE clause from the query
    try:
        where_clause = extract_where_clause(query)
        has_where_clause = True
    except ValueError as e:
        # No WHERE clause found
        where_clause = ''
        has_where_clause = False

    # Step 2: Remove conditions that specify specific attribute values
    if has_where_clause:
        # Remove the 'WHERE' keyword
        where_conditions_str = where_clause[len('WHERE'):].strip()

        # Split conditions using 'AND' or 'OR', keeping the operators
        tokens = re.split(r'(\bAND\b|\bOR\b)', where_conditions_str, flags=re.IGNORECASE)

        # Build a list of conditions with their preceding operators
        conditions_with_operators = []
        i = 0
        while i < len(tokens):
            token = tokens[i].strip()
            if i == 0:
                # First condition (no preceding operator)
                condition = token
                conditions_with_operators.append((None, condition))
                i += 1
            else:
                # Operator and condition
                operator = token
                condition = tokens[i + 1].strip() if i + 1 < len(tokens) else ''
                conditions_with_operators.append((operator, condition))
                i += 2

        # List to hold filtered conditions
        filtered_conditions = []
        for idx, (operator, condition) in enumerate(conditions_with_operators):
            # Check if the condition matches the pattern to remove
            match = re.match(
                r'\b\w+\.(class|octave|dur|interval)\s*(=)\s*.+',
                condition,
                re.IGNORECASE
            )
            if match:
                # Condition matches; decide whether to remove adjacent operator
                condition_ends_with_paren = condition.endswith(')')
                is_last_condition = idx == len(conditions_with_operators) - 1

                if not condition_ends_with_paren and not is_last_condition:
                    # Remove next operator (operator of the next condition)
                    if idx + 1 < len(conditions_with_operators):
                        next_operator, next_condition = conditions_with_operators[idx + 1]
                        conditions_with_operators[idx + 1] = (None, next_condition)
                else:
                    # Remove previous operator (current operator)
                    pass  # Operator is already excluded when we skip adding this condition
                # Do not add this condition to filtered_conditions
            else:
                # Condition does not match; keep it
                filtered_conditions.append((operator, condition))

        # Reconstruct the WHERE clause
        if filtered_conditions:
            # Build the conditions string
            conditions_str = ''
            for operator, condition in filtered_conditions:
                if operator:
                    conditions_str += f' {operator} '
                conditions_str += condition
            # Add 'WHERE' keyword
            new_where_clause = 'WHERE\n ' + conditions_str.strip()
        else:
            # No conditions left after filtering
            new_where_clause = ''
    else:
        new_where_clause = ''

    # Step 3: Extract notes and make conditions for each note
    notes_dict = extract_notes_from_query_dict(query)
    where_clauses = []
    if allow_transposition:
        intervals = calculate_intervals_dict(notes_dict)

    # Extract Fact nodes (notes with durations)
    f_nodes = [node for node, attrs in notes_dict.items() if attrs.get('type') == 'Fact']

    for idx, f_node in enumerate(f_nodes):
        attrs = notes_dict[f_node]
        duration = attrs.get('dur')
        if duration is not None:
            duration_condition = make_duration_condition(duration_factor, duration, f_node)
            if duration_condition:
                where_clauses.append(duration_condition)
        
        if allow_transposition:
            if idx < len(f_nodes) - 1:
                interval_condition = make_interval_condition(intervals[idx], duration_gap, pitch_distance, idx)
                if interval_condition:
                    where_clauses.append(interval_condition)
        else:
            duration_condition = make_pitch_condition(pitch_distance, attrs.get('class'), attrs.get('octave'), f_node)
            if duration_condition:
                where_clauses.append(duration_condition)
        
        if duration_gap > 0:
            if idx < len(f_nodes) - 1:
                sequencing_condition = make_sequencing_condition(duration_gap, f'e{idx}', f'e{idx+1}')
                if sequencing_condition:
                    where_clauses.append(sequencing_condition)

    # Step 4: makes conditions for membership functions
    # Extract attributes associated with membership functions
    attributes_with_membership_functions = extract_attributes_with_membership_functions(query)

    # Extract support intervals of the membership functions
    support_intervals = extract_membership_function_support_intervals(query)

    # For each attribute associated with a membership function, add a condition to ensure the attribute is within the support interval
    for node_name, attribute_name, membership_function_name in attributes_with_membership_functions:
        # Get the support interval for the membership function
        min_value, max_value = support_intervals[membership_function_name]

        # Add condition for minimum value if it's greater than negative infinity
        if min_value != float('-inf'):
            where_clauses.append(f"{node_name}.{attribute_name} >= {min_value}")

        # Add condition for maximum value if it's less than positive infinity
        if max_value != float('inf'):
            where_clauses.append(f"{node_name}.{attribute_name} <= {max_value}")

    where_clause = '\nWHERE\n' + ' AND\n'.join(where_clauses)
    return where_clause

def create_return_clause(query, notes_dict, duration_gap=0., intervals=False):
    '''
    Create the RETURN clause for the compiled query.

    Parameters:
        - notes_dict   : dictionary of nodes and their attributes, as returned by `extract_notes_from_query`.
        - duration_gap : the duration gap. Used only when `intervals` is True.
        - intervals    : indicates if the return clause is for a query that allows transposition or contour match.
                         If so, it will also add `interval_{idx}` to the clause.

    The function uses the actual names of the nodes in the RETURN clause but keeps the aliases (e.g., `AS pitch_0`) consistent with the indexing for processing.
    '''

    # Extract event nodes and fact nodes from the notes dictionary
    event_nodes = [node_name for node_name, attrs in notes_dict.items() if attrs.get('type') == 'Event']
    fact_nodes = [node_name for node_name, attrs in notes_dict.items() if attrs.get('type') == 'Fact']

    return_clauses = []

    # Map events to their corresponding facts based on indices
    # Assuming that for each event, there is at least one corresponding fact
    for idx, event_node_name in enumerate(event_nodes):
        return_clauses.extend([
            f"\n{event_node_name}.duration AS duration_{idx}",
            f"{event_node_name}.start AS start_{idx}",
            f"{event_node_name}.end AS end_{idx}",
            f"{event_node_name}.id AS id_{idx}"
        ])

        if intervals and idx < len(event_nodes) - 1:
            if duration_gap > 0:
                return_clauses.append(f"totalInterval_{idx} AS interval_{idx}")
            else:
                # Assuming relationships are named based on indices
                return_clauses.append(f"n{idx}.interval AS interval_{idx}")

    for idx, fact_node_name in enumerate(fact_nodes):
        return_clauses.extend([
            f"\n{fact_node_name}.octave AS octave_{idx}",
            f"{fact_node_name}.class AS pitch_{idx}"
        ])

    # Add source, start, and end from the first and last events
    first_event_node_name = event_nodes[0]
    last_event_node_name = event_nodes[-1]
    return_clauses.extend([
        f"\n{first_event_node_name}.source AS source",
        f"{first_event_node_name}.start AS start",
        f"{last_event_node_name}.end AS end"
    ])

    # Extract attributes associated with membership functions
    attributes_with_membership_functions = extract_attributes_with_membership_functions(query)

    # Collect existing return items to prevent duplicates
    existing_return_items = set(return_clauses)

    # For each attribute, add it to the return clause with appropriate alias
    for node_name, attribute_name, membership_function_name in attributes_with_membership_functions:
        # Construct the return clause item
        return_item = f"\n{node_name}.{attribute_name} AS {attribute_name}_{node_name}_{membership_function_name}"
        # Check if the item is already in the return_clauses
        if return_item not in existing_return_items:
            return_clauses.append(return_item)
            existing_return_items.add(return_item)

    return_clause = '\nRETURN' + ', '.join(return_clauses)

    return return_clause

def reformulate_fuzzy_query(query):
    '''
    Converts a fuzzy query to a cypher one.

    - query : the fuzzy query.
    '''

    #------Init
    #---Extract the parameters from the augmented query
    pitch_distance, duration_factor, duration_gap, alpha, allow_transposition, contour_match, fixed_notes, collections = extract_fuzzy_parameters(query)

    #---Extract notes using the new function
    notes = extract_notes_from_query_dict(query)

    nb_events = len([note_name for note_name, note in notes.items() if note['type'] == 'Event'])
    nb_facts = len([note_name for note_name, note in notes.items() if note['type'] == 'Fact'])
    
    #------Construct the MATCH clause
    match_clause = create_match_clause(query)

    #------Construct WITH clause
    if allow_transposition:
        with_clause = create_with_clause_interval(nb_events, duration_gap)
    else:
        with_clause = ''

    #------Construct the WHERE clause
    where_clause = create_where_clause(query, allow_transposition, pitch_distance, duration_factor, duration_gap)

    # #------Construct the collection filter
    # col_clause = create_collection_clause(collections, nb_events, nb_facts, duration_gap, allow_transposition or contour_match)

    #------Construct the return clause
    return_clause = create_return_clause(query, notes, duration_gap, allow_transposition)
    
    # ------Construct the final query
    # new_query = match_clause + '\n' + with_clause + where_clause + col_clause + '\n' + return_clause
    new_query = match_clause + with_clause + where_clause + return_clause
    return new_query.strip('\n')

if __name__ == '__main__':
    with open('fuzzy_query.cypher', 'r') as file:
        fuzzy_query = file.read()
    fuzzy_query = move_attribute_values_to_where_clause(fuzzy_query)
    fuzzy_query = refactor_variable_names(fuzzy_query)
    print(reformulate_fuzzy_query(fuzzy_query))
