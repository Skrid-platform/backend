from degree_computation import convert_note_to_sharp
from math import ceil, floor, log2

def frequency_to_note(frequency):
    # Notes de référence pour une octave (Do = C)
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    # La fréquence de référence est A4 = 440 Hz
    A4_freq = 440.0
    A4_index = note_names.index('A') + 4 * 12  # Position de A4 dans la gamme

    # Calcul du nombre de demi-tons par rapport à A4
    n = round(12 * log2(frequency / A4_freq))

    # Calcul de la position dans la gamme
    note_index = (A4_index + n) % len(note_names)  # Cycle des notes
    octave = (A4_index + n) // len(note_names)     # Calcul de l'octave

    # Note et octave
    note = note_names[note_index]
    return f"{note}{octave:.0f}"

def find_nearby_pitches_old(pitch, octave, max_distance):
    pitch = convert_note_to_sharp(pitch)

    # Define pitches and their relative semitone positions from C
    # notes = ['c', 'd', 'e', 'f', 'g', 'a', 'b']
    # semitones_from_c = [0, 2, 4, 5, 7, 9, 11]  # C to B, cumulative semitone distance

    notes = ['c', 'c#', 'd', 'd#', 'e', 'f', 'f#', 'g', 'g#', 'a', 'a#', 'b']
    semitones_from_c = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    
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
                result.append((note, octave + oct_shift))
                keep_searching = True  # Continue searching (search space is symmetric)

            # Check lower octaves (only if oct_shift is not zero to avoid double counting the base octave)
            if oct_shift != 0:
                target_semitone_low = note_to_semitone[note] + ((octave - oct_shift) * 12)
                distance_low = abs(target_semitone_low - base_semitone)
                
                if distance_low <= max_distance:
                    result.append((note, octave - oct_shift))
                    keep_searching = True  # Continue searching (search space is symmetric)

        oct_shift += 1  # Increase the octave shift for the next loop iteration

    return result

def find_nearby_pitches(pitch, octave, pitch_distance):
    '''
    Return a list of all the notes in the range `pitch_distance` of the center note (`pitch` / `octave`).

    The distance function is the interval (number of semitones) between notes.

    - pitch          : the base pitch. Format example: 'c', 'cs', 'c#' ;
    - octave         : the octave of the note ;
    - pitch_distance : the maximum distance allowed, in tones.

    Out: a list of all near notes, in the format: `[(pitch, octave), ...]`.
    '''

    # Notes semitone by semitone from c
    notes = ['c', 'c#', 'd', 'd#', 'e', 'f', 'f#', 'g', 'g#', 'a', 'a#', 'b']

    pitch = convert_note_to_sharp(pitch)
    i = notes.index(pitch) # The relative semitone of the center note
    max_semitone_dist = int(2 * pitch_distance)

    res = []

    for semitone in range(i - max_semitone_dist, i + max_semitone_dist + 1):
        p = notes[semitone % len(notes)]
        o = octave + (semitone // len(notes))

        res.append((p, o))

    return res

def find_frequency_bounds(pitch, octave, max_distance, alpha = 0.0):
    """
    Calculates the frequency bounds for a given pitch, octave, and maximum semitone distance.

    Parameters:
        pitch (str): The note name (e.g., 'c', 'c#', 'd', 'd#', ..., 'b').
        octave (int): The octave number.
        max_distance (int): The maximum number of tones away from the base note.
        alpha (float): The alpha threshold (0 ≤ alpha ≤ 1).

    Returns:
        tuple: A tuple containing the minimum and maximum frequencies (in Hz) as integers.
    """
    # Ensure pitch is in sharps
    pitch = convert_note_to_sharp(pitch)

    # Define note to semitone offset mapping from A
    note_to_semitone = {'a': 0, 'a#': 1, 'b': 2, 'c': 3, 'c#': 4, 'd': 5, 'd#': 6, 'e': 7, 'f': 8, 'f#': 9, 'g': 10, 'g#': 11}

    if pitch not in note_to_semitone:
        raise ValueError(f"Invalid pitch name: {pitch}")
        
    # Find the base semitone position for the given pitch and octave
    if pitch in ['a', 'a#', 'b']:
        base_semitone = note_to_semitone[pitch] + (octave * 12) + 21
    else :
        base_semitone = note_to_semitone[pitch] + ((octave - 1) * 12) + 21

    # Adjust max_distance based on alpha
    effective_distance_semitone =  2 * max_distance * (1 - alpha)

    # Compute the semitone bounds where the membership function equals alpha
    lower_bound_semitone = base_semitone - effective_distance_semitone
    upper_bound_semitone = base_semitone + effective_distance_semitone
    
    # Convert semitone bounds to frequencies
    min_frequency = 440 * 2 ** ((lower_bound_semitone - 69) / 12)
    max_frequency = 440 * 2 ** ((upper_bound_semitone - 69) / 12)
    
    return floor(min_frequency), ceil(max_frequency)

if __name__ == "__main__":
    frequencies = [440, 261.63, 329.63, 493.88, 880, 30.87]
    for freq in frequencies:
        print(f"{freq:.2f} Hz -> {frequency_to_note(freq)}")
