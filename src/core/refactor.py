#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Refactors a fuzzy query to a canonical (standard) version'''

##-Imports
#---General
import re
import csv
from io import StringIO

#---Project
# from src.core.extract_notes_from_query import extract_fuzzy_membership_functions, extract_fuzzy_parameters

##-Functions
def move_attribute_values_to_where_clause(query):
    '''
    Move attribute values to the where clause of the query. Also checks that all nodes and relationships have a type.

    - IN : query        : a fuzzy query where some attribute values may be in the match clause ;
    - OUT : the query where attribute values have been moved
    '''
    # Initialize dictionaries to keep track of variables and their types
    node_variables = {}
    relationship_variables = {}

    # Step 1: Extract the MATCH clause and the rest of the query
    match_match = re.search(r'\bMATCH\b', query, flags=re.IGNORECASE)
    if not match_match:
        raise ValueError('No MATCH clause found in the query')
    match_start = match_match.end()

    # Find the end of the MATCH clause by looking for the next clause keyword
    clause_keywords = ['WHERE', 'RETURN', 'WITH', 'ORDER BY', 'LIMIT', 'SKIP', 'UNION', 'OPTIONAL MATCH']
    pattern_clause = r'\b(' + '|'.join(clause_keywords) + r')\b'
    rest_match = re.search(pattern_clause, query[match_start:], flags=re.IGNORECASE)
    if rest_match:
        rest_start = match_start + rest_match.start()
        match_clause = query[match_start:rest_start].strip()
        rest_of_query = query[rest_start:].strip()
    else:
        match_clause = query[match_start:].strip()
        rest_of_query = ''

    # Step 2: Find all patterns (nodes and relationships) in the MATCH clause
    pattern_regex = re.compile(r'(\(|\[)([^\(\)\[\]]+)(\)|\])')
    matches = []
    for m in pattern_regex.finditer(match_clause):
        matches.append((m.start(), m.end(), m.group(1), m.group(2), m.group(3)))  # start, end, open_bracket, content, close_bracket

    # Process each pattern
    properties_to_add = []
    modified_match_clause = match_clause
    offset = 0  # To adjust positions after replacements

    for start, end, open_bracket, content, close_bracket in matches:
        # Parse the pattern
        variable, element_type, properties = parse_pattern(content)

        # Determine if it's a node or relationship based on brackets
        is_node = open_bracket == '(' and close_bracket == ')'
        is_relationship = open_bracket == '[' and close_bracket == ']'

        if is_node:
            variables = node_variables
            element_name = 'Node'
        elif is_relationship:
            variables = relationship_variables
            element_name = 'Relationship'
        else:
            continue  # Skip if neither node nor relationship

        # Check if the variable has been seen before
        if variable in variables:
            if element_type:
                # Optional: Check if the element_type matches the previously stored type
                if variables[variable] != element_type:
                    # Optional: Raise a warning or error if types don't match
                    pass
            else:
                # Variable is untyped but has been seen before; acceptable
                # element_type = variables[variable]
                pass
        else:
            # First occurrence of the variable
            if element_type is None:
                raise ValueError(f'{element_name} "{variable}" is not typed in the MATCH clause')
            variables[variable] = element_type  # Store the type

        # Reconstruct the pattern without properties
        if element_type:
            new_pattern_content = f'{variable}:{element_type}'
        else:
            new_pattern_content = f'{variable}'

        new_pattern = f'{open_bracket}{new_pattern_content}{close_bracket}'

        # Replace the pattern in the MATCH clause
        real_start = start + offset
        real_end = end + offset
        modified_match_clause = (modified_match_clause[:real_start] +
                                 new_pattern +
                                 modified_match_clause[real_end:])
        # Update offset
        offset += len(new_pattern) - (end - start)

        # Collect properties to add to WHERE clause
        if properties:
            # Parse properties into key-value pairs
            prop_dict = parse_properties(properties)
            for key, value in prop_dict.items():
                # Prepare the condition to add to WHERE clause
                condition = f"{variable}.{key} = {value}"
                properties_to_add.append(condition)

    # Step 3: Process the rest of the query to separate WHERE clause and others
    # We need to find the WHERE clause and any other clauses after it
    where_match = re.search(r'\bWHERE\b', rest_of_query, flags=re.IGNORECASE)
    if where_match:
        where_start = where_match.end()
        # Find any clauses after WHERE
        rest_clause_match = re.search(pattern_clause, rest_of_query[where_start:], flags=re.IGNORECASE)
        if rest_clause_match:
            rest_clause_start = where_start + rest_clause_match.start()
            existing_where_clause = rest_of_query[where_start:rest_clause_start].strip()
            rest_after_where = rest_of_query[rest_clause_start:].strip()
        else:
            existing_where_clause = rest_of_query[where_start:].strip()
            rest_after_where = ''
        # Combine existing WHERE clause with new conditions
        new_conditions = ' AND '.join(properties_to_add)
        if existing_where_clause and new_conditions:
            new_where_clause = f"WHERE\n {existing_where_clause} AND\n {new_conditions}"
        elif existing_where_clause:
            new_where_clause = f"WHERE\n {existing_where_clause}"
        elif new_conditions:
            new_where_clause = f"WHERE\n {new_conditions}"
        else:
            new_where_clause = ""
    else:
        # No existing WHERE clause
        existing_where_clause = ''
        rest_after_where = rest_of_query
        new_conditions = ' AND '.join(properties_to_add)
        new_where_clause = f"WHERE {new_conditions}"

    # Step 4: Reconstruct the query
    # Get the part before MATCH
    prefix = query[:match_match.start()].strip()

    # Reconstruct the query
    new_query = f"{prefix}\nMATCH\n {modified_match_clause}\n{new_where_clause}\n{rest_after_where}"

    return new_query

def parse_pattern(content):
    # Initialize
    variable = None
    element_type = None
    properties = None

    # Check if there is a '{' in content (properties)
    prop_start = content.find('{')
    if prop_start != -1:
        # There are properties
        prop_end = content.find('}', prop_start)
        if prop_end == -1:
            raise ValueError('Unmatched { in pattern')
        properties_str = content[prop_start+1:prop_end].strip()
        content = content[:prop_start].strip()
        properties = properties_str
    else:
        properties = None

    # Now, content is variable_name[:type]
    parts = content.split(':', 1)
    variable = parts[0].strip()
    element_type = parts[1].strip() if len(parts) > 1 else None

    return variable, element_type, properties

def parse_properties(properties_str):
    # Parse properties string into a dictionary
    prop_dict = {}
    # Split on commas, taking care of commas inside quotes
    properties = split_properties(properties_str)
    for prop in properties:
        # Split on ':' or '='
        if ':' in prop:
            key, value = prop.split(':', 1)
        elif '=' in prop:
            key, value = prop.split('=', 1)
        else:
            raise ValueError(f"Invalid property format: {prop}")
        key = key.strip()
        value = value.strip()
        # Add quotes around strings if not already quoted
        if not (value.startswith("'") and value.endswith("'")) and not (value.startswith('"') and value.endswith('"')):
            # Check if value is a number or boolean
            if not re.match(r'^-?\d+(\.\d+)?$', value) and value.lower() not in ('true', 'false', 'null'):
                # Assume it's a string, add quotes
                value = f"'{value}'"
        prop_dict[key] = value
    return prop_dict

def split_properties(properties_str):
    # Split properties string on commas, taking care of commas inside quotes
    f = StringIO(properties_str)
    reader = csv.reader(f, skipinitialspace=True)
    return next(reader)

def refactor_variable_names(query):
    '''
    Changes all occurrences of node's names into a standardized one.

    - query: The input query string.

    Returns the refactored query with standardized variable names.
    '''
    # Initialize dictionaries to keep track of variables and their standardized names
    variable_types = {}  # Original variable name -> type
    standardized_names = {}  # Original variable name -> standardized name
    type_counters = {}  # Type -> counter (starting from 0)

    # Step 1: Extract the MATCH clause and the rest of the query
    match_match = re.search(r'\bMATCH\b', query, flags=re.IGNORECASE)
    if not match_match:
        raise ValueError('No MATCH clause found in the query')
    match_start = match_match.start()

    # Find the end of the MATCH clause by looking for the next clause keyword
    clause_keywords = ['WHERE', 'RETURN', 'WITH', 'ORDER BY', 'LIMIT', 'SKIP', 'UNION', 'OPTIONAL MATCH']
    pattern_clause = r'\b(' + '|'.join(clause_keywords) + r')\b'
    match_end_match = re.search(pattern_clause, query[match_start:], flags=re.IGNORECASE)
    if match_end_match:
        match_end = match_start + match_end_match.start()
        match_clause = query[match_start:match_end].strip()
        rest_of_query = query[match_end:].strip()
    else:
        match_clause = query[match_start:].strip()
        rest_of_query = ''

    # Step 2: Find all patterns (nodes and relationships) in the MATCH clause
    # Use regex to find patterns like (var:type{props}), [var:type{props}]
    pattern_regex = re.compile(r'(\(|\[)(\s*\w+\s*)(:\s*\w+\s*)?(\{[^}]*\}\s*)?(\)|\])')
    # Initialize a list to hold the variable occurrences with their positions
    variable_occurrences = []  # List of tuples: (variable_name, var_type)

    # Process the MATCH clause to find variables and their types
    index = 0
    while index < len(match_clause):
        match = pattern_regex.search(match_clause, index)
        if not match:
            break
        # Extract variable name and type
        var_name = match.group(2).strip()
        type_part = match.group(3)
        var_type = type_part.strip(':').strip() if type_part else None

        # Check if this is the first occurrence
        if var_name not in variable_types:
            if var_type is None:
                raise ValueError(f'Variable "{var_name}" does not have a type specified')
            variable_types[var_name] = var_type

        index = match.end()

    # Now, create standardized names for variables based on their types
    for var_name, var_type in variable_types.items():
        # Initialize counter for this type if not already
        if var_type not in type_counters:
            type_counters[var_type] = 0
        # Create standardized name
        standardized_name = f'{var_type[0].lower()}{type_counters[var_type]}'
        # Increment counter
        type_counters[var_type] += 1
        # Map original variable name to standardized name
        standardized_names[var_name] = standardized_name

    # Now, replace variable names in the query with standardized names
    # We need to ensure that variable names are replaced correctly throughout the query

    # Create a regex pattern to match variable names in the query
    # We need to match variable names when they appear as whole words or before certain characters (like '.', ':', '{', '(', etc.)
    escaped_var_names = [re.escape(var_name) for var_name in variable_types.keys()]
    # Sort variable names by length in descending order to avoid partial replacements
    escaped_var_names.sort(key=len, reverse=True)
    var_pattern = r'(?<!\w)(' + '|'.join(escaped_var_names) + r')(?!\w)'

    # Define a replacement function
    def replace_var(match):
        var_name = match.group(1)
        return standardized_names.get(var_name, var_name)

    # Replace variable names in the entire query
    new_query = re.sub(var_pattern, replace_var, query)

    return new_query

##-Run
if __name__ == "__main__":
    with open('fuzzy_query.cypher', 'r') as file:
        fuzzy_query = file.read()

    fuzzy_query = move_attribute_values_to_where_clause(fuzzy_query)
    fuzzy_query = refactor_variable_names(fuzzy_query)
    print(fuzzy_query)

