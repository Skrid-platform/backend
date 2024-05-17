import re

def extract_notes_from_query(query):
    # Regex to find note details within the query
    note_pattern = re.compile(r"\(f\d+\{class:'(\w+)',octave:(\d+), dur:(\d+)\}\)")
    # Extract all matches
    matches = note_pattern.findall(query)
    # Convert extracted values into a list of tuples (class, octave, duration)
    notes = [(match[0].lower(), int(match[1]), int(match[2])) for match in matches]
    return notes