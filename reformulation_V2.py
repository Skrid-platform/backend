from find_nearby_pitches import find_frequency_bounds, find_nearby_pitches
from find_duration_range import find_duration_range_decimal, find_duration_range_multiplicative_factor
from extract_notes_from_query import extract_notes_from_query, extract_fuzzy_parameters
from utils import calculate_pitch_interval

import re

def reformulate_cypher_query(query):
    return reformulate_fuzzy_query(query) #TODO: remove one of the two functions.

def make_duration_condition(duration_factor, duration, idx, fixed):
    if duration == None:
        return ''

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


def create_match_clause(nb_notes, duration_gap, transpose=False):
    '''
    Create the MATCH clause for the compilated query.

    - nb_notes     : the number of notes ;
    - duration_gap : the duration gap ;
    - transpose    : indicate if transposition is allowed.
    '''

    if duration_gap > 0:
        # To give a higher bound to the number of intermediate notes, we suppose the shortest possible note has a duration of 0.125
        max_intermediate_nodes = max(int(duration_gap / 0.125), 1)

        if transpose:
            event_path = ',\n '.join([f"p{idx} = (e{idx}:Event)-[:NEXT*1..{max_intermediate_nodes + 1}]->(e{idx+1}:Event)" for idx in range(nb_notes - 1)]) + ','
        else:
            event_path = f"-[:NEXT*1..{max_intermediate_nodes + 1}]->".join([f"(e{idx}:Event)" for idx in range(nb_notes)]) + ','

    else:
        if transpose:
            event_path = "".join([f"(e{idx}:Event)-[r{idx}:NEXT]->" for idx in range(nb_notes - 1)]) + f"(e{nb_notes - 1}:Event)"+ ','
        else:
            event_path = f"-[]->".join([f"(e{idx}:Event)" for idx in range(nb_notes)]) + ','  

    simplified_connections = ','.join([f"\n (e{idx})-[]->(f{idx}:Fact)" for idx in range(nb_notes)])
    match_clause = 'MATCH \n ' + event_path + simplified_connections

    return match_clause

def create_with_clause_allow_transposition(nb_notes, duration_gap):
    '''
    Create the WITH clause for the compilated query (only with allow_transposition).

    - nb_notes     : the number of notes ;
    - duration_gap : the duration gap.
    '''

    with_clause = ""
    if duration_gap > 0:
        # Construct interval conditions for paths with intermediate nodes
        interval_conditions = []

        for idx in range(nb_notes - 1): # nb of intervals
            interval_condition = f"reduce(totalInterval = 0, rel IN relationships(p{idx}) | totalInterval + rel.interval) AS totalInterval_{idx}"
            interval_conditions.append(interval_condition)

        # Adding the interval clauses if duration_gap is specified
        variables = ', '.join([f"e{idx}" for idx in range(nb_notes)]) + ',\n' + ', '.join([f"f{idx}" for idx in range(nb_notes)])
        with_clause = 'WITH\n' + variables + ',\n' + ',\n'.join(interval_conditions) + ' '

    return with_clause + '\n'

def create_where_clause_without_transposition(notes, fixed_notes, pitch_distance, duration_factor, duration_gap):
    '''
    Create the WHERE clause to match `notes`.
    Does not allow transposition.

    - notes           : the array of notes triples (pitch, octave, duration) ;
    - fixed_notes     : the array indicating if notes are fixed ;
    - pitch_distance  : the pitch distance ;
    - duration_factor : the duration factor ;
    - duration_gap    : the duration gap.
    '''

    where_clauses = []
    sequencing_conditions = []

    for idx, (note, octave, duration) in enumerate(notes):
        #---Making note condition (class + octave)
        if note == None:
            if octave == None:
                note_condition = ''
            else:
                note_condition = f'f{idx}.octave = {octave}'

        else:
            if fixed_notes[idx] or pitch_distance == 0:
                note_condition = f'f{idx}.class = "{note[0]}"'

                if len(note) > 1 and note[1] in ('#', 's'): # sharp
                    note_condition += f' AND (f{idx}.accid = "s" OR f{idx}.accid_ges = "s")' # f.accid : accidental on the note. f.accid_ges : accidental on the clef.

                elif len(note) > 1 and note[1] in ('b', 'f'): # flat
                    note_condition += f' AND (f{idx}.accid = "f" OR f{idx}.accid_ges = "f")' # f.accid : accidental on the note. f.accid_ges : accidental on the clef.

                if octave != None:
                    note_condition += f' AND f{idx}.octave = {octave}'

            else:
                o = 4 if octave is None else octave # If octave is None, use 4 to get near notes classes
                near_notes = find_nearby_pitches(note, o, pitch_distance)

                note_condition = '('
                for n, o_ in near_notes:
                    base_condition = f'f{idx}.class = "{n[0]}"'

                    if len(n) > 1 and n[1] in ('#', 's'): # sharp
                        base_condition += f' AND (f{idx}.accid = "s" OR f{idx}.accid_ges = "s")' # f.accid : accidental on the note. f.accid_ges : accidental on the clef.

                    elif len(n) > 1 and n[1] in ('b', 'f'): # flat
                        base_condition += f' AND (f{idx}.accid = "f" OR f{idx}.accid_ges = "f")' # f.accid : accidental on the note. f.accid_ges : accidental on the clef.

                    if octave == None:
                        note_condition += f'\n  ({base_condition}) OR '
                    else:
                        note_condition += f'\n  ({base_condition} AND f{idx}.octave = {o_}) OR '

                note_condition = note_condition[:-len(' OR ')] + '\n )' # Remove trailing ' AND '

        #---Making the duration condition
        duration_condition = make_duration_condition(duration_factor, duration, idx, fixed_notes[idx])

        # Adding sequencing conditions
        if idx < len(notes) - 1 and duration_gap > 0:
            sequencing_condition = make_sequencing_condition(duration_gap, idx)
            sequencing_conditions.append(sequencing_condition)

        if note_condition == '' or duration_condition == '':
            where_clause_i = note_condition + duration_condition # if only one is '', the concatenation of both is equal to the one which is not ''.
        else:
            where_clause_i = note_condition + ' AND ' + duration_condition

        where_clauses.append(' ' + where_clause_i)
    
    #---Assemble frequency, duration and sequencing conditions
    where_clause = 'WHERE\n' + ' AND\n'.join(where_clauses)
    if sequencing_conditions:
        sequencing_conditions = ' AND '.join(sequencing_conditions)
        where_clause = where_clause + ' AND \n ' + sequencing_conditions

    return where_clause

def create_where_clause_with_transposition(notes, fixed_notes, pitch_distance, duration_factor, duration_gap):
    '''
    Create the WHERE clause to match `notes`.
    Allows transposition.

    - notes           : the array of notes triples (pitch, octave, duration) ;
    - fixed_notes     : the array indicating if notes are fixed ;
    - pitch_distance  : the pitch distance ;
    - duration_factor : the duration factor ;
    - duration_gap    : the duration gap.
    '''

    #---Compute the intervals between consecutive notes
    intervals = []
    for i in range(len(notes) - 1):
        note1, octave1, _ = notes[i]
        note2, octave2, _ = notes[i + 1]

        if None in (note1, octave1, note2, octave2):
            interval = None
        else:
            interval = calculate_pitch_interval(note1, octave1, note2, octave2)

        intervals.append(interval)

    where_clauses = []

    for idx, (note, octave, duration) in enumerate(notes):
        duration_condition = make_duration_condition(duration_factor, duration, idx, fixed_notes[idx])

        if idx == len(notes) - 1 or intervals[idx] == None: # only duration condition for the last step or if no interval given
            if duration_condition != '':
                where_clauses.append(duration_condition)

        else: # duration condition + interval condition
            if duration_gap > 0:
                if pitch_distance > 0 and not fixed_notes[idx]:
                    interval_condition = f"{intervals[idx] - pitch_distance} <= totalInterval_{idx} AND totalInterval_{idx} <= {intervals[idx] + pitch_distance}"
                else:
                    interval_condition = f"totalInterval_{idx} = {intervals[idx]}"

            else:
                # Construct interval conditions for direct connections
                if pitch_distance > 0 and not fixed_notes[idx]:
                    interval_condition = f"{intervals[idx] - pitch_distance} <= r{idx}.interval AND r{idx}.interval <= {intervals[idx] + pitch_distance}"
                else:
                    interval_condition = f"r{idx}.interval = {intervals[idx]}"
                    # if intervals[idx] > 0:
                    #     interval_condition = f"r{idx}.interval > 0"
                    # elif intervals[idx] == 0:
                    #     interval_condition = f"r{idx}.interval = 0"
                    # else:
                    #     interval_condition = f"r{idx}.interval < 0"

            if duration_condition != '':
                where_clauses.append(duration_condition + " AND " + interval_condition)
            else:
                where_clauses.append(interval_condition)

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

    return where_clause

def create_collection_clause(collections, nb_notes):
    '''
    Create the clause that will filter the given collections.

    - collections : the array of collection strings ;
    - nb_notes    : the number of notes.
    '''

    if collections == None or len(collections) == 0:
        col_clause = ''

    else:
        col_clause = '\nWITH'

        as_col_clause = ''
        for k in range(nb_notes):
            as_col_clause += f'e{k} as e{k}, f{k} as f{k}, '

        as_col_clause = as_col_clause[:-2] # Remove trailing ', '

        col_clause += '\n ' + as_col_clause
        col_clause += '\nCALL {\n WITH e1\n MATCH (e1)<-[:timeSeries|VOICE|NEXT*]-(s:Score)\n RETURN s\n LIMIT 1\n}'
        col_clause += '\nWITH\n s as s, ' + as_col_clause

        col_clause += '\nWHERE'
        for col in collections:
            col_clause += f'\n s.collection CONTAINS "{col}" OR'

        col_clause = col_clause[:-3] # Remove trailing ' OR'.

    return col_clause

def create_return_clause(nb_notes, duration_gap=0., transpose=False):
    '''
    Create the return clause.

    - nb_notes     : the number of notes in the search melody ;
    - duration_gap : the duration gap. Used only when transpose is True ;
    - transpose    : indicate if the return clause is for a query that allows transposition or not. If so, it will also add `interval_{idx}` to the clause.
    '''

    return_clauses = []
    for idx in range(nb_notes):
        # Prepare return clauses with specified names
        return_clauses.extend([
            f"\n f{idx}.class AS pitch_{idx}",
            f"f{idx}.octave AS octave_{idx}",
            f"e{idx}.duration AS duration_{idx}",
            f"e{idx}.start AS start_{idx}",
            f"e{idx}.end AS end_{idx}",
            f"e{idx}.id AS id_{idx}"
        ])

        if transpose and idx < nb_notes - 1:
            if duration_gap > 0:
                return_clauses.append(f"totalInterval_{idx} AS interval_{idx}")
            else:
                return_clauses.append(f"r{idx}.interval AS interval_{idx}")

    return_clause = 'RETURN' + ', '.join(return_clauses) + f', \n e0.source AS source, e0.start AS start, e{nb_notes - 1}.end AS end'

    return return_clause


def reformulate_fuzzy_query(query):
    '''
    Converts a fuzzy query to a cypher one.

    - query : the fuzzy query.
    '''

    #------Init
    #---Extract the parameters from the augmented query
    pitch_distance, duration_factor, duration_gap, alpha, allow_transposition, fixed_notes, collections = extract_fuzzy_parameters(query)

    #---Extract notes using the new function
    notes = extract_notes_from_query(query)
    
    #------Construct the MATCH clause
    match_clause = create_match_clause(len(notes), duration_gap, allow_transposition)

    #------Construct WITH clause
    if allow_transposition:
        with_clause = create_with_clause_allow_transposition(len(notes), duration_gap)
    else:
        with_clause = ''

    #------Construct the WHERE clause
    if allow_transposition:
        where_clause = create_where_clause_with_transposition(notes, fixed_notes, pitch_distance, duration_factor, duration_gap)
    else:
        where_clause = create_where_clause_without_transposition(notes, fixed_notes, pitch_distance, duration_factor, duration_gap)

    #------Construct the collection filter
    col_clause = create_collection_clause(collections, len(notes))

    #------Construct the return clause
    return_clause = create_return_clause(len(notes), duration_gap, allow_transposition)
    
    #------Construct the final query
    new_query = match_clause + '\n' + with_clause + where_clause + col_clause + '\n' + return_clause
    return new_query


if __name__ == "__main__":
    with open('query.cypher', 'r') as file:
        augmented_query = file.read()
    print(reformulate_fuzzy_query(augmented_query))
