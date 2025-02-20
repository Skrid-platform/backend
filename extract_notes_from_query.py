import re
import numpy as np

def extract_notes_from_query_dict(query: str) -> dict:
    '''
    Extract nodes and their attributes from a given query, including node types.

    Input:
        - query: The fuzzy query.

    Output:
        - Dictionary with node names as keys, each containing a dictionary of attributes including 'type'.

    Example Output:
        {
            'e0': {'type': 'Event'},
            'e1': {'type': 'Event'},
            'e2': {'type': 'Event'},
            'f0': {'type': 'Fact', 'class': 'c', 'octave': 5, 'dur': 1},
            'f1': {'type': 'Fact', 'class': 'd', 'octave': 5, 'dur': 1},
            'f2': {'type': 'Fact', 'class': 'e', 'octave': 5, 'dur': 2},
            't0': {'type': 'NEXT', 'interval': 1},
            't1': {'type': 'NEXT'},
            ...
        }
    '''

    # Initialize the node_attributes dictionary
    node_attributes = {}

    # Extract the MATCH clause
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

    # Extract all patterns (nodes and relationships) in the MATCH clause
    pattern_regex = re.compile(r'(\(|\[)([^\(\)\[\]]+)(\)|\])')
    matches = pattern_regex.findall(match_clause)
    for open_bracket, content, close_bracket in matches:
        # Determine if it's a node or relationship based on brackets
        is_node = open_bracket == '(' and close_bracket == ')'
        is_relationship = open_bracket == '[' and close_bracket == ']'

        # Parse the content to extract variable and type
        parts = content.split(':', 1)
        variable = parts[0].strip()
        node_type = parts[1].strip() if len(parts) > 1 else None

        if variable not in node_attributes:
            node_attributes[variable] = {}

        if node_type:
            node_attributes[variable]['type'] = node_type

    # Extract attributes from the WHERE clause
    where_match = re.search(r'\bWHERE\b', rest_of_query, flags=re.IGNORECASE)
    if where_match:
        where_start = where_match.end()
        # Find any clauses after WHERE
        rest_clause_match = re.search(pattern_clause, rest_of_query[where_start:], flags=re.IGNORECASE)
        if rest_clause_match:
            rest_clause_start = where_start + rest_clause_match.start()
            where_clause = rest_of_query[where_start:rest_clause_start].strip()
            rest_after_where = rest_of_query[rest_clause_start:].strip()
        else:
            where_clause = rest_of_query[where_start:].strip()
            rest_after_where = ''
    else:
        where_clause = ''
        rest_after_where = ''

    # Replace line breaks with spaces in the WHERE clause
    where_clause = where_clause.replace('\n', ' ')

    # Split the WHERE clause into individual conditions using 'AND' or 'OR' as separators
    condition_regex = re.compile(r'\bAND\b|\bOR\b', flags=re.IGNORECASE)
    conditions = condition_regex.split(where_clause)

    # Process each condition to extract variable names, attributes, and values
    for condition in conditions:
        condition = condition.strip()
        # Match patterns like variable.attribute operator value
        attr_regex = re.compile(r'(\w+)\.(\w+)\s*(=|!=|<|>|<=|>=|IS|IS NOT)\s*(.+)', flags=re.IGNORECASE)
        match = attr_regex.match(condition)
        if match:
            var, attr, operator, value = match.groups()
            var = var.strip()
            attr = attr.strip()
            operator = operator.strip().upper()
            value = value.strip()

            # Remove surrounding parentheses from value if present
            if value.startswith('(') and value.endswith(')'):
                value = value[1:-1].strip()

            # Remove quotes from value if present
            if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
                value = value[1:-1]
            elif operator == 'IS' or operator == 'IS NOT':
                # For 'IS' or 'IS NOT' operators, keep the value as is (e.g., 'NULL')
                value = value.upper()
            else:
                # Try to convert value to int or float
                try:
                    if '.' in value:
                        value = float(value)
                    else:
                        value = int(value)
                except ValueError:
                    pass  # Keep value as string if it cannot be converted

            if value == "None":
                value = None

            # Only keep (value, attribute) pairs when its an equality in the original query
            if operator == '=':
                # Add the attribute to the node_attributes dictionary
                if var in node_attributes:
                    node_attributes[var][attr] = value
                else:
                    # Variable not found in the MATCH clause; add it anyway with unknown type
                    node_attributes[var] = {attr: value}
        else:
            # Condition not matching the expected pattern; you may handle other patterns here
            pass

    return node_attributes

def extract_fuzzy_parameters(query):
    '''
    Extract parameters from a fuzzy query using regular expressions.

    In :
        - query : the *fuzzy* query ;

    Out :
        pitch_distance(float), duration_factor(float), duration_gap(float), alpha(float), allow_transposition(bool), contour(bool), fixed_notes(bool[]), collection(str | None)
    '''

    # Extracting the parameters from the augmented query
    pitch_distance_re = re.search(r'TOLERANT pitch=(\d+\.\d+|\d+)', query)
    duration_factor_re = re.search(r'duration=(\d+\.\d+|\d+)', query)
    duration_gap_re = re.search(r'gap=(\d+\.\d+|\d+)', query)
    alpha_re = re.search(r'ALPHA (\d+\.\d+)', query)

    pitch_distance = 0.0 if pitch_distance_re == None else float(pitch_distance_re.group(1))
    duration_factor = 1.0 if duration_factor_re == None else float(duration_factor_re.group(1))
    duration_gap = 0.0 if duration_gap_re == None else float(duration_gap_re.group(1))
    alpha = 0.0 if alpha_re == None else float(alpha_re.group(1))

    # Check for the ALLOW_TRANSPOSITION keyword
    allow_transposition = bool(re.search(r'ALLOW_TRANSPOSITION', query))
    contour = True if extract_fuzzy_membership_functions(query) else False

    # Check for collection
    collection_re = re.search(r"tp\.collection\s*=\s*'(.*?)'", query)
    collection = collection_re.group(1) if collection_re else None

    # Extract fixed notes information
    note_pattern = r"\{class:'(\w+|None)', octave:(\d+|None), dur:(\d+\.\d+|\d+|None)\}\)( FIXED)?"
    matches = re.findall(note_pattern, query)
    fixed_notes = [bool(fixed) for _, _, _, fixed in matches]

    return pitch_distance, duration_factor, duration_gap, alpha, allow_transposition, contour, fixed_notes, collection

def extract_fuzzy_membership_functions(query):
    '''
    Extract fuzzy membership function definitions from a fuzzy query using regular expressions.

    In:
        - query: the *fuzzy* query;

    Out:
        A dictionary where the keys are fuzzy term names (str) and the values are Python functions (corresponding to membership functions).
    '''
    
    # Dictionary to store the fuzzy membership functions
    membership_functions = {}

    # Regular expression patterns to detect fuzzy term definitions
    define_trap_re = r'DEFINETRAP (\w+) AS \((-?\d+\.\d+|-?\d+),\s*(-?\d+\.\d+|-?\d+),\s*(-?\d+\.\d+|-?\d+),\s*(-?\d+\.\d+|-?\d+)\)'
    define_asc_re = r'DEFINEASC (\w+) AS \((-?\d+\.\d+|-?\d+),\s*(-?\d+\.\d+|-?\d+)\)'
    define_desc_re = r'DEFINEDESC (\w+) AS \((-?\d+\.\d+|-?\d+),\s*(-?\d+\.\d+|-?\d+)\)'

    # Extract trapezoidal membership functions
    for match in re.findall(define_trap_re, query):
        name, a_minus, a, b, b_plus = match
        membership_functions[name] = create_trapezoidal_function(float(a_minus), float(a), float(b), float(b_plus))

    # Extract ascending membership functions (linear)
    for match in re.findall(define_asc_re, query):
        name, gamma, delta = match
        membership_functions[name] = create_ascending_function(float(gamma), float(delta))

    # Extract descending membership functions (linear)
    for match in re.findall(define_desc_re, query):
        name, gamma, delta = match
        membership_functions[name] = create_descending_function(float(gamma), float(delta))

    return membership_functions

def extract_membership_function_support_intervals(query):
    '''
    Extract support intervals of fuzzy membership functions from a fuzzy query using regular expressions.

    Parameters:
        query (str): The fuzzy query string.

    Returns:
        dict: A dictionary where the keys are fuzzy term names (str) and the values are tuples representing the support intervals (min_value, max_value).
            - For ascending functions, `max_value` is `float('inf')`.
            - For descending functions, `min_value` is `float('-inf')`.
    '''
    
    # Dictionary to store the support intervals
    support_intervals = {}

    # Regular expression patterns to detect fuzzy term definitions
    define_trap_re = r'DEFINETRAP (\w+) AS \((-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\)'
    define_asc_re = r'DEFINEASC (\w+) AS \((-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\)'
    define_desc_re = r'DEFINEDESC (\w+) AS \((-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\)'

    # Extract trapezoidal membership function support intervals
    for match in re.findall(define_trap_re, query):
        name, a_minus, a, b, b_plus = match
        a_minus = float(a_minus)
        b_plus = float(b_plus)
        # The support interval is from a_minus to b_plus
        support_interval = (a_minus, b_plus)
        support_intervals[name] = support_interval

    # Extract ascending membership function support intervals
    for match in re.findall(define_asc_re, query):
        name, gamma, delta = match
        gamma = float(gamma)
        # The support interval is from gamma to +infinity
        support_interval = (gamma, float('inf'))
        support_intervals[name] = support_interval

    # Extract descending membership function support intervals
    for match in re.findall(define_desc_re, query):
        name, gamma, delta = match
        delta = float(delta)
        # The support interval is from -infinity to delta
        support_interval = (float('-inf'), delta)
        support_intervals[name] = support_interval

    return support_intervals

# Helper function for trapezoidal membership functions
def create_trapezoidal_function(a_minus, a, b, b_plus):
    '''
    Create a trapezoidal membership function based on the four parameters.

    A trapezoidal function is defined by four points (a_minus, a, b, b_plus), where:
    - The function is 0 for values less than a_minus or greater than b_plus.
    - The function is 1 between a and b.
    - The function linearly increases from 0 to 1 between a_minus and a.
    - The function linearly decreases from 1 to 0 between b and b_plus.
    '''
    def trapezoidal(x):
        if x < a_minus or x > b_plus:
            return 0.0
        elif a_minus <= x < a:
            return (x - a_minus) / (a - a_minus)  # Linearly increase from 0 to 1
        elif a <= x <= b:
            return 1.0  # Plateau at 1
        elif b < x <= b_plus:
            return (b_plus - x) / (b_plus - b)  # Linearly decrease from 1 to 0
        return 0.0
    return trapezoidal

# Helper function for ascending membership functions (linear)
def create_ascending_function(gamma, delta):
    '''
    Create an ascending (increasing) membership function based on the two parameters gamma and delta.

    The function linearly increases from 0 to 1 between gamma and delta.
    '''
    def ascending(x):
        if x < gamma:
            return 0.0
        elif gamma <= x <= delta:
            return (x - gamma) / (delta - gamma)  # Linearly increase from 0 to 1
        return 1.0  # Values above delta are at full membership (1)
    return ascending

# Helper function for descending membership functions (linear)
def create_descending_function(gamma, delta):
    '''
    Create a descending (decreasing) membership function based on the two parameters gamma and delta.

    The function linearly decreases from 1 to 0 between gamma and delta.
    '''
    def descending(x):
        if x < gamma:
            return 1.0  # Values below gamma are at full membership (1)
        elif gamma <= x <= delta:
            return (delta - x) / (delta - gamma)  # Linearly decrease from 1 to 0
        return 0.0  # Values above delta have no membership (0)
    return descending

def extract_match_clause(query):
    """
    Extracts the MATCH clause from the query.

    Parameters:
        query (str): The full query string.

    Returns:
        str: The MATCH clause, including the 'MATCH' keyword.

    Raises:
        ValueError: If no MATCH clause is found in the query.
    """
    # Locate the 'MATCH' keyword
    match_match = re.search(r'\bMATCH\b', query, flags=re.IGNORECASE)
    if not match_match:
        raise ValueError('No MATCH clause found in the query')
    match_start = match_match.start()

    # Find the end of the MATCH clause by looking for the next clause keyword
    clause_keywords = ['WHERE', 'RETURN', 'WITH', 'ORDER BY', 'LIMIT', 'SKIP', 'UNION', 'OPTIONAL MATCH', 'DETACH', 'DELETE', 'SET', 'CREATE']
    pattern_clause = r'\b(' + '|'.join(clause_keywords) + r')\b'
    match_end_match = re.search(pattern_clause, query[match_start + len('MATCH'):], flags=re.IGNORECASE)
    if match_end_match:
        match_end = match_start + len('MATCH') + match_end_match.start()
        match_clause = query[match_start:match_end].strip()
    else:
        # MATCH clause goes until the end of the query
        match_clause = query[match_start:].strip()
    return match_clause

def extract_where_clause(query):
    """
    Extracts the WHERE clause from the query.

    Parameters:
        query (str): The full query string.

    Returns:
        str: The WHERE clause, including the 'WHERE' keyword.

    Raises:
        ValueError: If no WHERE clause is found in the query.
    """
    # Locate the 'WHERE' keyword
    where_match = re.search(r'\bWHERE\b', query, flags=re.IGNORECASE)
    if not where_match:
        raise ValueError('No WHERE clause found in the query')
    where_start = where_match.start()

    # Find the end of the WHERE clause by looking for the next clause keyword
    clause_keywords = ['RETURN', 'WITH', 'ORDER BY', 'LIMIT', 'SKIP', 'UNION', 'OPTIONAL MATCH', 'DETACH', 'DELETE', 'SET', 'CREATE']
    pattern_clause = r'\b(' + '|'.join(clause_keywords) + r')\b'
    where_end_match = re.search(pattern_clause, query[where_start + len('WHERE'):], flags=re.IGNORECASE)
    if where_end_match:
        where_end = where_start + len('WHERE') + where_end_match.start()
        where_clause = query[where_start:where_end].strip()
    else:
        # WHERE clause goes until the end of the query
        where_clause = query[where_start:].strip()
    return where_clause

def extract_return_clause(query):
    """
    Extracts the RETURN clause from the query.

    Parameters:
        query (str): The full query string.

    Returns:
        str: The RETURN clause, including the 'RETURN' keyword.

    Raises:
        ValueError: If no RETURN clause is found in the query.
    """
    # Locate the 'RETURN' keyword
    return_match = re.search(r'\bRETURN\b', query, flags=re.IGNORECASE)
    if not return_match:
        raise ValueError('No RETURN clause found in the query')
    return_start = return_match.start()

    # Find the end of the RETURN clause by looking for the next clause keyword
    clause_keywords = ['LIMIT', 'SKIP', 'ORDER BY', 'UNION', 'DETACH', 'DELETE', 'SET', 'CREATE']
    pattern_clause = r'\b(' + '|'.join(clause_keywords) + r')\b'
    return_end_match = re.search(pattern_clause, query[return_start + len('RETURN'):], flags=re.IGNORECASE)
    if return_end_match:
        return_end = return_start + len('RETURN') + return_end_match.start()
        return_clause = query[return_start:return_end].strip()
    else:
        # RETURN clause goes until the end of the query
        return_clause = query[return_start:].strip()
    return return_clause

def extract_attributes_with_membership_functions(query):
    """
    Extracts attributes that are associated with membership functions in the query.

    Parameters:
        query (str): The fuzzy query string.

    Returns:
        List of lists: Each list contains (node_name, attribute_name, membership_function_name).
    """

    membership_functions_names = extract_fuzzy_membership_functions(query)
    membership_functions_names = list(membership_functions_names.keys())

    pattern = re.compile(r'\(?\s*(\w+)\.(\w+)\s*\)?\s+IS\s+(\w+)', re.IGNORECASE)

    matches = []

    for node_name, attribute_name, is_object in pattern.findall(query):
        if is_object in membership_functions_names:
            matches.append([node_name, attribute_name, is_object])

    return matches

if __name__ == "__main__":
    query = """DEFINEASC leapUp AS (1.0,1.5)
    DEFINEDESC slow AS (2.0,3.0)
    DEFINETRAP medium AS (1.0,2.0,3.0,4.0)
    MATCH
    ALLOW_TRANSPOSITION
    TOLERANT pitch=0.0, duration=1.0, gap=0.0
    ALPHA 0.5
    (e0:Event)-[t0:NEXT]->(e1:Event)-[t1:NEXT]->(e2:Event),
    (e0)--(f0:Fact),
    (e1)--(f1:Fact),
    (e2)--(f2:Fact)
    WHERE t0.interval is leapUp AND f0.class = 'c' AND f1.class = 'd' AND f2.class = 'e' AND e0.name IS NULL
    RETURN e0.source AS source, e0.start AS start"""

    print(extract_match_clause(query))
