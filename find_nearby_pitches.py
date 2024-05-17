def find_nearby_pitches(pitch, octave, max_distance):
    # Define pitches and their relative semitone positions from C
    notes = ['c', 'd', 'e', 'f', 'g', 'a', 'b']
    semitones_from_c = [0, 2, 4, 5, 7, 9, 11]  # C to B, cumulative semitone distance

    # notes = ['c', 'c#', 'd', 'd#', 'e', 'f', 'f#', 'g', 'g#', 'a', 'a#', 'b']
    # semitones_from_c = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    
    # Create a mapping from note to its index and semitone offset
    note_to_index = {note: idx for idx, note in enumerate(notes)}
    note_to_semitone = {note: semitones for note, semitones in zip(notes, semitones_from_c)}
    
    # Find the base semitone position for the given pitch and octave
    base_semitone = note_to_semitone[pitch] + (octave * 12)
    
    # Compute nearby notes within the maximum distance
    result = []
    oct_shift = 0
    keep_searching = True

    while keep_searching:
        keep_searching = False  # Assume no more octaves are needed unless we find one within range
        for note in notes:
            # Check higher octaves
            target_semitone_high = note_to_semitone[note] + ((octave + oct_shift) * 12)
            distance_high = abs(target_semitone_high - base_semitone)

            if distance_high <= max_distance:
                result.append([note, octave + oct_shift])
                keep_searching = True  # Continue searching (search space is symmetric)

            # Check lower octaves (only if oct_shift is not zero to avoid double counting the base octave)
            if oct_shift != 0:
                target_semitone_low = note_to_semitone[note] + ((octave - oct_shift) * 12)
                distance_low = abs(target_semitone_low - base_semitone)
                
                if distance_low <= max_distance:
                    result.append([note, octave - oct_shift])
                    keep_searching = True  # Continue searching (search space is symmetric)

        oct_shift += 1  # Increase the octave shift for the next loop iteration

    return result

def find_frequency_bounds(pitch, octave, max_distance):
# Define pitches and their relative semitone positions from A
    notes = ['a', 'b', 'c', 'd', 'e', 'f', 'g']
    semitones_from_a = [0, 2, 3, 5, 7, 8, 10]  # A to G, cumulative semitone distance
    
    # Create a mapping from note to its index and semitone offset
    note_to_semitone = {note: semitones for note, semitones in zip(notes, semitones_from_a)}
    
    # Find the base semitone position for the given pitch and octave
    if pitch == 'c' or pitch == 'd' or pitch == 'e' or pitch == 'f' or pitch == 'g':
        base_semitone = note_to_semitone[pitch] + ((octave + 1) * 12) + 21
    else:
        base_semitone = note_to_semitone[pitch] + (octave * 12) + 21
    
    # Compute the frequency range based on the maximum semitone distance
    lower_bound_semitone = base_semitone - max_distance
    upper_bound_semitone = base_semitone + max_distance
    
    min_frequency = 440 * 2 ** ((lower_bound_semitone - 69) / 12)
    max_frequency = 440 * 2 ** ((upper_bound_semitone - 69) / 12)
    
    return round(min_frequency,2), round(max_frequency,2)

if __name__ == "__main__":
    # Example usage:
    pitch = 'e'
    octave = 5
    max_distance = 3  # Maximum distance in semitones
    print(find_frequency_bounds(pitch, octave, max_distance))
