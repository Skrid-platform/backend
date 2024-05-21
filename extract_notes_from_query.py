import re

def extract_notes_from_query(query):
    # Regex to find note details within the query
    note_pattern = re.compile(r"\(f\d+\{class:'(\w+)',octave:(\d+), dur:(\d+)\}\)")
    # Extract all matches
    matches = note_pattern.findall(query)
    # Convert extracted values into a list of tuples (class, octave, duration)
    notes = [(match[0].lower(), int(match[1]), 1/int(match[2])) for match in matches]
    return notes

def extract_fuzzy_parameters(query):
    # Extracting the parameters from the augmented query
    pitch_distance = int(re.search(r'TOLERANT pitch=(\d+)', query).group(1))
    duration_distance = float(re.search(r'duration=(\d+\.\d+|\d+)', query).group(1))
    duration_gap = float(re.search(r'gap=(\d+\.\d+|\d+)', query).group(1))
    alpha = float(re.search(r'ALPHA (\d+\.\d+)', query).group(1))

    return pitch_distance, duration_distance, duration_gap, alpha