import re

def extract_notes_from_query(query: str) -> list[list[tuple[str|None, int|None] | int|float|None]]:
    '''
    Extract the notes from a given query.

    Input :
        - query : the fuzzy query.

    Ouput :
        notes in the following format :
        `[[(class_1, octave_1), ..., (class_n, octave_n), duration], ...]`

        For example : `[[('c', 5), 4], [('b', 4), 8], [('b', 4), 8], [('a', 4), ('d', 5), 16]]`.

        duration is in the following format: 1 for whole, 2 for half, ...
        float is allowed for dotted notes (e.g dotted half is 1/(1/2 + 1/4) = 4 / 3).
    '''

    #---Regex to find note details within the query
    # note_pattern = re.compile(r"\{class:'(\w+|None)', octave:(\d+|None), dur:(\d+\.\d+|\d+|None)\}\)")
    note_pattern = re.compile(r"\(e(\d+)\)--\(f(\d+)\{class:'(\w+|None)', octave:(\d+|None), dur:(\d+\.\d+|\d+|None)\}\)")

    # Extract all matches
    matches = note_pattern.findall(query)

    #---Convert extracted values into a list of [(class, octave), ..., (class, octave), duration] (for each note / chord)
    notes = []
    current_event_nb = -1 # Will also correspond to len(notes) - 1
    last_duration = None

    for match in matches:
        event_nb, fact_nb, class_, octave, duration = match

        event_nb = int(event_nb)
        fact_nb = int(fact_nb)

        if current_event_nb < event_nb:
            current_event_nb = event_nb
            notes.append([])

            if event_nb > 0: # Adding duration for previous event (note / chord)
                notes[event_nb - 1].append(last_duration)

        if class_ == 'None':
            class_ = None
        else:
            class_ = class_.lower()

        if octave == 'None':
            octave = None
        else:
            octave = int(octave)

        if duration == 'None':
            duration = None
        else:
            duration = 1 / float(duration)

        note = (class_, octave)
        notes[event_nb].append(note)
        last_duration = duration

    # Adding last duration
    if len(notes) > 0:
        notes[-1].append(last_duration)

    return notes

def extract_fuzzy_parameters(query):
    '''
    Extract parameters from a fuzzy query using regular expressions.

    In :
        - query : the *fuzzy* query ;

    Out :
        pitch_distance(float), duration_factor(float), duration_gap(float), alpha(float), allow_transposition(bool), contour(bool), fixed_notes(bool[]), collections(str[] | None)
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
    contour = bool(re.search(r'CONTOUR', query))

    # Check for collections filter
    collections_line_lst = re.compile(r'COLLECTIONS .*\n').findall(query)
    filter_collections = len(collections_line_lst) > 0
    if filter_collections:
        # collections = [s.strip('"') for s in re.compile(r'".+"').findall(collections_line_lst[0])]
        collections = []
        for col in collections_line_lst[0].split('"'):
            if col not in ('', ' ', 'COLLECTIONS ', '\n'):
                collections.append(f'{col}')
    else:
        collections = None

    # Extract fixed notes information
    note_pattern = r"\{class:'(\w+|None)', octave:(\d+|None), dur:(\d+\.\d+|\d+|None)\}\)( FIXED)?"
    matches = re.findall(note_pattern, query)
    fixed_notes = [bool(fixed) for _, _, _, fixed in matches]

    return pitch_distance, duration_factor, duration_gap, alpha, allow_transposition, contour, fixed_notes, collections


if __name__ == "__main__":
    # Get the query
    with open('fuzzy_query.cypher', 'r') as file:
        augmented_query = file.read()
    
    print(extract_fuzzy_parameters(augmented_query))
