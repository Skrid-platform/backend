#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Converts fuzzy queries into cypher ones'''

##-Imports
#---General
import re

#---Project
from src.core.fuzzy_computation import (
    find_frequency_bounds,
    find_nearby_pitches,
    find_duration_range_decimal,
    convert_note_to_sharp,
    split_note_accidental,
    find_duration_range_multiplicative_factor_sym
)
from src.core.extract_notes_from_query import (
    extract_notes_from_query_dict,
    extract_fuzzy_parameters,
    extract_match_clause,
    extract_where_clause,
    extract_attributes_with_membership_functions,
    extract_membership_function_support_intervals
)
from src.core.refactor import move_attribute_values_to_where_clause, refactor_variable_names
from src.core.note_calculations import calculate_intervals_list, calculate_dur_ratios_list

##-Functions
def make_duration_condition(duration_factor, duration, node_name, alpha, dotted):
    if duration == None:
        return ''

    # Before reforumation step, we use 'dur' attribute in the data model and in fuzzy query expression to be coherent
    # 'dur' attribute is given in power of two (1, 2, 4, ...) and does not take dots into account
    # 'duration' attribut is given in fraction (0.125, 0.325, ...) and takes dots into account
    duration = 1.0/duration
    if dotted:
        duration = duration*1.5

    if duration_factor != 1:
        min_duration, max_duration = find_duration_range_multiplicative_factor_sym(duration, duration_factor, alpha)
        res = f"{node_name}.duration >= {min_duration} AND {node_name}.duration <= {max_duration}"
    else:
        res = f"{node_name}.duration = {duration}"
    return res

def make_duration_ratio_condition(duration_ratio, duration_gap, duration_factor, idx, alpha):
    if duration_ratio is None:
        return ''

    if duration_factor < 1:
        duration_factor = 1.0/duration_factor
    
    min_ratio, max_ratio = find_duration_range_multiplicative_factor_sym(duration_ratio, duration_factor, alpha)
    if duration_gap > 0:
        if duration_factor > 1:
            duration_ratio_condition = (
                f"EXISTS(f{idx}.duration) AND EXISTS(f{idx + 1}.duration) AND "
                f"{min_ratio} <= f{idx + 1}.duration / f{idx}.duration AND "
                f"f{idx + 1}.duration / f{idx}.duration <= {max_ratio}"
            )
        else:
            duration_ratio_condition = (
                f"EXISTS(f{idx}.duration) AND EXISTS(f{idx + 1}.duration) AND "
                f"f{idx + 1}.duration / f{idx}.duration = {duration_ratio}"
            )
    else:
        if duration_factor > 1:
            duration_ratio_condition = (
                f"{min_ratio} <= n{idx}.duration_ratio AND n{idx}.duration_ratio <= {max_ratio}"
            )
        else:
            duration_ratio_condition = f"n{idx}.duration_ratio = {duration_ratio}"
    
    return duration_ratio_condition

def make_interval_condition(interval, duration_gap, pitch_distance, idx, alpha):
    if interval == 'NA':
        # No rest involved, but lack information for interval inference
        interval_condition = ''
    elif interval is None:
        if duration_gap > 0:
            interval_condition = f"(NOT EXISTS(f{idx}.halfTonesFromA4) OR NOT EXISTS(f{idx + 1}.halfTonesFromA4))"
        else:
            interval_condition = f"NOT EXISTS(n{idx}.interval)"
    else :
        if duration_gap > 0:
            # Utiliser halfTonesFromA4 pour calculer les intervalles entre deux Fact nodes
            if pitch_distance > 0:
                interval_condition = (
                    f"EXISTS(f{idx + 1}.halfTonesFromA4) AND EXISTS(f{idx}.halfTonesFromA4) AND "
                    f"{interval - pitch_distance * (1 - alpha)} <= "
                    f"toFloat(f{idx + 1}.halfTonesFromA4 - f{idx}.halfTonesFromA4)/2 AND "
                    f"toFloat(f{idx + 1}.halfTonesFromA4 - f{idx}.halfTonesFromA4)/2 <= "
                    f"{interval + pitch_distance * (1 - alpha)}"
                )
            else:
                interval_condition = (
                    f"EXISTS(f{idx + 1}.halfTonesFromA4) AND EXISTS(f{idx}.halfTonesFromA4) AND "
                    f"toFloat(f{idx + 1}.halfTonesFromA4 - f{idx}.halfTonesFromA4)/2 = {interval}"
                )
        else:
            # Construct interval conditions for direct connections
            if pitch_distance > 0:
                interval_condition = (
                    f"{interval - pitch_distance * (1 - alpha)} <= n{idx}.interval AND "
                    f"n{idx}.interval <= {interval + pitch_distance * (1 - alpha)}"
                )
            else:
                interval_condition = f"n{idx}.interval = {interval}"
    return interval_condition

def make_pitch_condition(pitch_distance: float, pitch: str | None, octave: int | None, name: str, alpha: float):
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
                pitch_condition = f"{name}.type = 'rest'"
            else:
                # Split pitch into base note and accidental
                base_note, accidental = split_note_accidental(pitch)
                pitch_condition = f"{name}.class = '{base_note}'"
                if accidental:
                    # Add condition for accidental, including accid and accid_ges
                    pitch_condition += f" AND ({name}.accid = '{accidental}' OR {name}.accid_ges = '{accidental}')" #TODO: if accidental is a sharp, do we also need to add a condition with the equivalent as a flat ?
                else:
                    # No accidental, so accid is NULL or empty
                    pitch_condition += f" AND NOT EXISTS({name}.accid) AND NOT EXISTS({name}.accid_ges)"
                if octave is not None:
                    pitch_condition += f" AND {name}.octave = {octave}"
        else:
            o = 4 if octave is None else octave  # Default octave if not specified
            near_pitches = find_nearby_pitches(pitch, o, pitch_distance)

            # pitch_condition = '('
            # for n, o_ in near_pitches:
            #     base_note, accidental = split_note_accidental(n)
            #     base_condition = f"{name}.class = '{base_note}'"
            #     if accidental:
            #         base_condition += f" AND ({name}.accid = '{accidental}' OR {name}.accid_ges = '{accidental}')"
            #     else:
            #         base_condition += f" AND NOT EXISTS({name}.accid) AND NOT EXISTS({name}.accid)"
            #     if octave is None:
            #         pitch_condition += f"\n  ({base_condition}) OR "
            #     else:
            #         pitch_condition += f"\n  ({base_condition} AND {name}.octave = {o_}) OR "
            # # Remove the trailing ' OR ' and close the parentheses
            # pitch_condition = pitch_condition.rstrip(' OR ') + '\n)'

            low_freq_bound, high_freq_bound = find_frequency_bounds(pitch, o, pitch_distance, alpha)
            pitch_condition = f"{low_freq_bound} <= {name}.frequency AND {name}.frequency <= {high_freq_bound}"
            
    return pitch_condition

def make_sequencing_condition(duration_gap, name_1, name_2, alpha):
    sequencing_condition = f"{name_1}.end >= {name_2}.start - {duration_gap * (1 - alpha)}"
    return sequencing_condition

def create_match_clause(query: str, notes: dict[str, dict[str, int | str]]) -> str:
    '''
    Create the MATCH clause for the compiled query.

    In:
        - query: the entire query string;
        - notes: the notes extracted from the query

    Out:
        a string representing the match clause
    '''

    _, _, duration_gap, _, allow_transposition, _ = extract_fuzzy_parameters(query)

    if duration_gap > 0:
        # Proceed to create the MATCH clause as per current code

        #---Init
        event_nodes = [node for node, attrs in notes.items() if attrs.get('type') == 'Event']

        nb_events = len(event_nodes)

        # To give a higher bound to the number of intermediate notes, we suppose the shortest possible note has a duration of 0.0625
        max_intermediate_nodes = max(int(duration_gap / 0.0625), 1)

        # Create a simplified path without intervals
        event_path = f'-[:NEXT*1..{max_intermediate_nodes + 1}]->'.join([f'({node}:Event)' for node in event_nodes])

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

        # Replace the event chain patterns with event_path
        simplified_connections = [
            event_path if is_event_chain_pattern(p) else p for p in patterns
        ]

        # Reconstruct the simplified connections as a string
        simplified_connections_str = ',\n '.join(simplified_connections)

        #---Create MATCH clause
        match_clause = 'MATCH\n ' + simplified_connections_str

        return match_clause
    else:
        # duration_gap = 0
        # Extract the MATCH clause from the query
        match_clause = extract_match_clause(query)

        # Remove fuzzy parameters definitions (everything between MATCH and the first '(')
        # Find the position of the first '(' after MATCH
        match_start = match_clause.find('MATCH')
        first_paren = match_clause.find('(', match_start)
        if first_paren == -1:
            raise ValueError('No node patterns found in MATCH clause')

        # Extract the cleaned MATCH clause
        match_clause_body = match_clause[first_paren:].strip()

        # Additional step: when allow_transposition is True, ensure all [:NEXT] relationships are named
        if allow_transposition:
            # Initialize a relationship index
            rel_index = 0

            # Function to replace unnamed [:NEXT] relationships with named ones
            def replace_unnamed_next(match):
                nonlocal rel_index
                replacement = f'[n{rel_index}:NEXT]'
                rel_index += 1
                return replacement

            # Regular expression to find unnamed relationships of the form [:NEXT]
            pattern = r'\[\s*:NEXT\s*\]'

            # Replace unnamed [:NEXT] relationships with named ones
            match_clause_body = re.sub(pattern, replace_unnamed_next, match_clause_body)

        # Reconstruct the match_clause
        match_clause = 'MATCH\n' + match_clause_body

        return match_clause

def create_where_clause(query: str, notes_dict: dict[str, dict[str, int | str]], allow_transposition: bool, allow_homothety: bool, pitch_distance: float, duration_factor: float, duration_gap: float, alpha: float = 0.0):
    # Step 1: Extract the WHERE clause from the query
    try:
        where_clause = extract_where_clause(query)
        has_where_clause = True
    except ValueError as e:
        # No WHERE clause found
        where_clause = ''
        has_where_clause = False

    # Extract attributes associated with membership functions
    attributes_with_membership_functions = extract_attributes_with_membership_functions(query)

    # Step 2: Remove conditions that specify specific attribute values or membership functions
    if has_where_clause:
        # Remove the 'WHERE' keyword
        where_conditions_str = where_clause[len('WHERE'):].strip()

        # Split conditions using 'AND' or 'OR', keeping the operators
        tokens = re.split(r'(\bAND\b)', where_conditions_str, flags=re.IGNORECASE)
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
                r"\b\w+\.(class|octave|dur|interval|dots)\s*=\s*[^\s]+",
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

        membership_function_names = [membership_function_name for node_name, attribute_name, membership_function_name in attributes_with_membership_functions]

        # Reconstruct the WHERE clause
        if filtered_conditions:
            # Build the conditions string
            conditions = []
            for operator, condition in filtered_conditions:
                # Filter out membership function condition in the where clause
                if isinstance(condition, str) and " IS " in condition:
                    _, y = map(str.strip, condition.split(" IS ", 1))
                    if y not in membership_function_names:
                        conditions.append(condition)
                else:
                    conditions.append(condition)
            preexisting_where_clause = ' AND '.join(conditions)
        else:
            # No conditions left after filtering
            preexisting_where_clause = ''
    else:
        preexisting_where_clause = ''

    # Step 3: Extract notes and make conditions for each note
    where_clauses = []
    if allow_transposition:
        intervals = calculate_intervals_list(notes_dict)
    if allow_homothety:
        dur_ratios = calculate_dur_ratios_list(notes_dict)

    # Extract Fact nodes (notes with durations)
    f_nodes = [node for node, attrs in notes_dict.items() if attrs.get('type') == 'Fact']
    for idx, f_node in enumerate(f_nodes):
        attrs = notes_dict[f_node]
        duration = attrs.get('dur')

        if allow_homothety:
            if idx < len(f_nodes) - 1:
                duration_ratio_condition = make_duration_ratio_condition(dur_ratios[idx], duration_gap, duration_factor, idx, alpha)
                if duration_ratio_condition:
                    where_clauses.append(duration_ratio_condition)
        else:
            duration_condition = make_duration_condition(duration_factor, duration, f_node, alpha, attrs.get('dots'))
            if duration_condition:
                where_clauses.append(duration_condition)
        
        if allow_transposition:
            if idx < len(f_nodes) - 1:
                interval_condition = make_interval_condition(intervals[idx], duration_gap, pitch_distance, idx, alpha)
                if interval_condition:
                    where_clauses.append(interval_condition)
        else:
            pitch_condition = make_pitch_condition(pitch_distance, attrs.get('class'), attrs.get('octave'), f_node, alpha)
            if pitch_condition:
                where_clauses.append(pitch_condition)
        


        if duration_gap > 0:
            if idx < len(f_nodes) - 1:
                sequencing_condition = make_sequencing_condition(duration_gap, f'e{idx}', f'e{idx+1}', alpha)
                if sequencing_condition:
                    where_clauses.append(sequencing_condition)

    # Step 4: makes conditions for membership functions
    # Extract support intervals of the membership functions
    support_intervals = extract_membership_function_support_intervals(query)

    # For each attribute associated with a membership function, add a condition to ensure the attribute is within the support interval
    for node_name, attribute_name, membership_function_name in attributes_with_membership_functions:
        # Get the support interval for the membership function
        min_value, max_value = support_intervals[membership_function_name]

        # Add condition for minimum value if it's greater than negative infinity
        if min_value != float('-inf'):
            where_clauses.append(f"{node_name}.{attribute_name} > {min_value}")

        # Add condition for maximum value if it's less than positive infinity
        if max_value != float('inf'):
            where_clauses.append(f"{node_name}.{attribute_name} < {max_value}")

    if preexisting_where_clause:
        preexisting_where_clause = preexisting_where_clause + ' AND\n'
    where_clause = '\nWHERE\n' + preexisting_where_clause  + ' AND\n'.join(where_clauses)
    return where_clause

def create_return_clause(query, notes_dict, duration_gap, intervals, allow_homothety):
    '''
    Create the RETURN clause for the compiled query.

    Parameters:
        - notes_dict   : dictionary of nodes and their attributes, as returned by `extract_notes_from_query`.
        - duration_gap : the duration gap. Used only when `intervals` is True.
        - intervals    : indicates if the return clause is for a query that allows transposition or contour match.
                         If so, it will also add `interval_{idx}` to the clause.
        - allow_homothety : indicates if duration homothety (proportional duration relationships) is allowed.
    
    The function uses the actual names of the nodes in the RETURN clause but keeps the aliases (e.g., `AS pitch_0`) consistent with the indexing for processing.
    '''

    # Extract event nodes and fact nodes from the notes dictionary
    event_nodes = [node_name for node_name, attrs in notes_dict.items() if attrs.get('type') == 'Event']
    fact_nodes = [node_name for node_name, attrs in notes_dict.items() if attrs.get('type') == 'Fact']
    
    return_clauses = []

    # Map events to their corresponding facts based on indices
    for idx, event_node_name in enumerate(event_nodes):
        return_clauses.extend([
            f"\n{event_node_name}.duration AS duration_{idx}",
            f"{event_node_name}.dots AS dots_{idx}",
            f"{event_node_name}.start AS start_{idx}",
            f"{event_node_name}.end AS end_{idx}",
            f"{event_node_name}.id AS id_{idx}"
        ])

        if intervals and idx < len(event_nodes) - 1:
            if duration_gap > 0:
                return_clauses.append(f"toFloat(f{idx + 1}.halfTonesFromA4 - f{idx}.halfTonesFromA4)/2 AS interval_{idx}")
            else:
                return_clauses.append(f"n{idx}.interval AS interval_{idx}")
        
        if allow_homothety and idx < len(event_nodes) - 1:
            if duration_gap > 0:
                return_clauses.append(f"toFloat(f{idx + 1}.duration) / toFloat(f{idx}.duration) AS duration_ratio_{idx}")
            else:
                return_clauses.append(f"n{idx}.duration_ratio AS duration_ratio_{idx}")
    
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
        return_item = f"\n{node_name}.{attribute_name} AS {attribute_name}_{node_name}_{membership_function_name}"
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

    query = move_attribute_values_to_where_clause(query)

    #------Init
    #---Extract the parameters from the augmented query
    pitch_distance, duration_factor, duration_gap, alpha, allow_transposition, allow_homothety = extract_fuzzy_parameters(query)

    #---Extract notes using the new function
    notes = extract_notes_from_query_dict(query)
    
    #------Construct the MATCH clause
    match_clause = create_match_clause(query, notes)

    #------Construct the WHERE clause
    where_clause = create_where_clause(query, notes, allow_transposition, allow_homothety, pitch_distance, duration_factor, duration_gap, alpha)

    #------Construct the return clause
    return_clause = create_return_clause(query, notes, duration_gap, allow_transposition, allow_homothety)
    
    # ------Construct the final query
    # new_query = match_clause + '\n' + with_clause + where_clause + col_clause + '\n' + return_clause
    new_query = match_clause  + where_clause + return_clause
    return new_query.strip('\n')

##-Run
if __name__ == '__main__':
    with open('fuzzy_query.cypher', 'r') as file:
        fuzzy_query = file.read()

    fuzzy_query = move_attribute_values_to_where_clause(fuzzy_query)
    fuzzy_query = refactor_variable_names(fuzzy_query)
    print(reformulate_fuzzy_query(fuzzy_query))
