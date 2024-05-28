def note_distance_in_tones(note1, octave1, note2, octave2):
    # Define the semitone distance from C for each note
    semitones_from_c = {
        'c': 0, 'c#': 1, 'd': 2, 'd#': 3, 'e': 4, 'f': 5, 'f#': 6, 
        'g': 7, 'g#': 8, 'a': 9, 'a#': 10, 'b': 11
    }
    
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
    return max(1 - (note_distance_in_tones(note1, octave1, note2, octave2)/(pitch_gap + pitch_gap*0.1)), 0)

def duration_degree(duration1, duration2, duration_gap):
    if duration_gap == 0:
        return 1.0
    
    # Calculate the absolute difference between the two durations
    duration_difference = abs(duration1 - duration2)
    
    # Calculate the degree based on the duration gap
    degree = max(1 - (duration_difference / (duration_gap + duration_gap*0.1)), 0)
    
    return degree

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

if __name__ == "__main__":
    # # Test Example
    # note1 = 'c'
    # octave1 = 4
    # note2 = 'd'
    # octave2 = 4
    # pitch_gap = 1.5

    # degree = pitch_degree(note1, octave1, note2, octave2, pitch_gap)
    # print(f"The pitch degree between {note1}{octave1} and {note2}{octave2} is {degree}.")

    # # Test Example
    # duration1 = 0.5  # Half note
    # duration2 = 0.375  # Three-eighths note
    # duration_gap = 0.25  # Allowed gap as a fraction of a whole note

    # degree = duration_degree(duration1, duration2, duration_gap)
    # print(f"Duration Degree between {duration1} and {duration2} with a gap of {duration_gap} is {degree}")

    # Test Example
    end_time1 = 1.0  # End time of the first note (whole note)
    start_time2 = 1.125  # Start time of the second note (slightly after the first note)
    max_gap = 0.25  # Allowed gap as a fraction of a whole note

    degree = sequencing_degree(end_time1, start_time2, max_gap)
    print(f"Sequencing Degree between end time {end_time1} and start time {start_time2} with a gap of {max_gap} is {degree}")