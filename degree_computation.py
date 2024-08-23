def convert_note_to_sharp(note):
    '''
    Convert a note to its equivalent in sharp (if it is a flat).
    If the note has no accidental, it is not modified.

    - note : a string of length 1 or 2 representing a musical note class (no octave).
             Sharp can be represented either with 's' or '#'.
             Flat can be represented either with 'f' of 'b'.

    Output: `note` with sharp represented as '#', or `note` unchanged if there was no accidental.
    '''

    notes = 'abcdefg'

    note = note.replace('s', '#')
    if len(note) == 2 and note[1] in ('f', 'b'):
        note = notes[(notes.index(note[0]) - 1) % len(notes)] + '#' # Convert flat to sharp

    return note

def note_distance_in_tones(note1, octave1, note2, octave2):
    '''Calculate the distance (in tones) between two notes.'''

    if note1 == None or note2 == None: # If one note is None, it means that the note is unspecified, so only check for octave distance
        if octave1 == None or octave2 == None:
            return 0

        else:
            return 12 * abs(octave2 - octave1) / 2

    #---Define the semitone distance from C for each note
    semitones_from_c = {
        'c': 0, 'c#': 1, 'd': 2, 'd#': 3, 'e': 4, 'f': 5, 'f#': 6, 
        'g': 7, 'g#': 8, 'a': 9, 'a#': 10, 'b': 11
    }

    #---Replace 's' with '#' and convert flat to sharp
    note1 = convert_note_to_sharp(note1)
    note2 = convert_note_to_sharp(note2)

    #---Manages when octave is None
    if octave1 == None and octave2 == None: # In this case, return the distance between notes as if it was in the same octave.
        octave1 = 4
        octave2 = 4

    # If one octave in None, set it to the other (so that the distance will be )
    elif octave1 == None:
        octave1 = octave2
    elif octave2 == None:
        octave2 = octave1
    
    #---Calculate the distances
    # Calculate the semitone position for each note
    semitone1 = semitones_from_c[note1] + (octave1 * 12)
    semitone2 = semitones_from_c[note2] + (octave2 * 12)
    
    # Calculate the absolute distance in semitones
    distance_in_semitones = abs(semitone2 - semitone1)
    
    # Convert semitones to tones (1 tone = 2 semitones)
    distance_in_tones = distance_in_semitones / 2
    
    return distance_in_tones

def pitch_degree(note1, octave1, note2, octave2, pitch_gap):
    if pitch_gap == 0:
        return 1.0

    #TODO: Why not just `pitch_gap` but ` + pitch_gap / 10` ?
    # Maybe this is to avoid to have 0% for a match at the edge ?
    d = 1 - (note_distance_in_tones(note1, octave1, note2, octave2) / (pitch_gap + pitch_gap*0.1))
    return max(d, 0)

def pitch_degree_with_intervals(interval1, interval2, pitch_gap):
    if pitch_gap == 0 or interval1 == None or interval2 == None:
        return 1.0

    d = 1 - (abs(interval1 - interval2) / (pitch_gap + pitch_gap*0.1))
    return max(d, 0)
  

def duration_degree(duration1, duration2, max_duration_distance):
    if max_duration_distance == 0:
        return 1.0
    # Calculate the absolute difference between the two durations
    duration_difference = abs(duration1 - duration2)
    
    # Calculate the degree based on the duration gap
    degree = max(1 - (duration_difference / (max_duration_distance + max_duration_distance*0.1)), 0)
    
    return degree

def duration_degree_with_multiplicative_factor(expected_duration, duration, factor):
    if factor == 1.0 or expected_duration is None:
        return 1.0

    lower_bound = expected_duration / factor
    upper_bound = expected_duration * factor

    # If the duration is outside the acceptable range, return 0
    if duration < lower_bound or duration > upper_bound:
        return 0.0

    # Linear interpolation when duration is less than or equal to expected_duration
    if duration <= expected_duration:
        return (duration - lower_bound) / (expected_duration - lower_bound)

    # Linear interpolation when duration is greater than expected_duration
    return (upper_bound - duration) / (upper_bound - expected_duration)

def sequencing_degree(end_time1, start_time2, max_gap):
    if max_gap == 0:
        return 1.0
    
    # Calculate the gap between the end time of the first note and the start time of the second note
    time_gap = start_time2 - end_time1
    
    # Calculate the degree based on the maximum allowed gap
    degree = max(1 - (time_gap / (max_gap + max_gap*0.1)), 0)
    
    return degree

def aggregate_note_degrees(aggregation_fn, pitch_degree, duration_degree, sequencing_degree):
    return aggregation_fn(pitch_degree, duration_degree, sequencing_degree)

def aggregate_sequence_degrees(aggregation_fn, degree_list):
    return aggregation_fn(*degree_list)

def aggregate_degrees(aggregation_fn, degree_list):
    return aggregation_fn(*degree_list)

if __name__ == "__main__":
    print(duration_degree_with_multiplicative_factor(0.25, 0.125, 0.5))
