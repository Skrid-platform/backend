import librosa
import numpy as np
import argparse

from note import Note
from utils import create_query_from_list_of_notes

def frequency_to_note(freq):
    """Convert a frequency to the closest musical note (pitch, octave)."""
    if np.isnan(freq):
        return None, None  # Silence or unvoiced region
    
    note_str = librosa.hz_to_note(freq, octave=True)
    pitch, octave = note_str[:-1], int(note_str[-1])
    return pitch.lower(), octave

def determine_note_durations(f0, sr):
    """Determine rhythmic duration from sample counts."""
    note_durations = []
    note_values = [1, 2, 4, 8, 16, 32]  # Whole, half, quarter, eighth, sixteenth, thirty-second
    note_time_ratios = np.array([1.0 / val for val in note_values])
    
    # Count consecutive samples per note
    durations = []
    prev_pitch, prev_octave = None, None
    start_idx = None

    for i, freq in enumerate(f0):
        pitch, octave = frequency_to_note(freq)
        
        if pitch is None:  # Silence or unvoiced region
            if prev_pitch is not None:
                duration_samples = i - start_idx
                durations.append(duration_samples)
                prev_pitch, prev_octave, start_idx = None, None, None
        else:
            if prev_pitch is None:  # Start of a new note
                start_idx = i
            elif (pitch, octave) != (prev_pitch, prev_octave):  # Note change
                duration_samples = i - start_idx
                durations.append(duration_samples)
                start_idx = i  # New note starts
                
            prev_pitch, prev_octave = pitch, octave

    # Handle last note if it extends to the end
    if prev_pitch is not None:
        duration_samples = len(f0) - start_idx
        durations.append(duration_samples)

    # Infer the basic unit (sixteenth note duration in samples)
    min_duration = min(durations)  # Smallest detected note duration
    sixteenth_note_samples = min_duration  # Assume the shortest detected note is a sixteenth note

    # Convert each duration to a rhythmic value
    for dur_samples in durations:
        dur_whole_note = dur_samples / (sixteenth_note_samples * 16)  # Convert to whole note units
        closest_dur = note_values[np.argmin(np.abs(note_time_ratios - dur_whole_note))]
        note_durations.append(closest_dur)

    return note_durations, sixteenth_note_samples * 16  # Return beat length in samples

def extract_notes(path, sr=16000, fmin=65, fmax=300):
    """Convert WAV audio to a sequence of Note objects with proper rhythmic values."""
    audio, sr = librosa.load(path, sr=sr)
    f0, _, _ = librosa.pyin(audio, sr=sr, fmin=fmin, fmax=fmax, n_thresholds=30)

    # Get durations and reference beat length
    note_durations, beat_samples = determine_note_durations(f0, sr)

    notes = []
    prev_pitch, prev_octave = None, None
    start_idx = None
    cumulative_duration = 0.0  # Start time in whole notes
    note_index = 0

    for i, freq in enumerate(f0):
        pitch, octave = frequency_to_note(freq)

        if pitch is None:  # Silence or unvoiced part
            if prev_pitch is not None:
                duration = note_durations[note_index]  # Get computed rhythmic value
                notes.append(Note(prev_pitch, prev_octave, duration, start=cumulative_duration))
                cumulative_duration += 1.0 / duration  # Move start time forward
                note_index += 1
                prev_pitch, prev_octave, start_idx = None, None, None
        else:
            if prev_pitch is None:
                start_idx = i
            elif (pitch, octave) != (prev_pitch, prev_octave):
                duration = note_durations[note_index]
                notes.append(Note(prev_pitch, prev_octave, duration, start=cumulative_duration))
                cumulative_duration += 1.0 / duration
                start_idx = i
                note_index += 1

            prev_pitch, prev_octave = pitch, octave

    # Handle last note if it extends to the end
    if prev_pitch is not None and note_index < len(note_durations):
        duration = note_durations[note_index]
        notes.append(Note(prev_pitch, prev_octave, duration, start=cumulative_duration))

    return notes

def create_query_from_audio(audio_path, pitch_distance, duration_factor, duration_gap, alpha, allow_transposition, contour_match, collection=None, sr=16000, fmin=65, fmax=300):
    """
    Create a fuzzy query directly from an audio file.
    
    In:
        - audio_path (str)          : Path to the audio file.
        - pitch_distance (float)     : The `pitch distance` (fuzzy param).
        - duration_factor (float)    : The `duration factor` (fuzzy param).
        - duration_gap (float)       : The `duration gap` (fuzzy param).
        - alpha (float)              : The `alpha` param.
        - allow_transposition (bool) : The `allow_transposition` param.
        - contour_match (bool)       : The `contour_match` param.
        - collection (str | None)    : The collection filter.
        - sr (int)                   : Sampling rate for audio processing.
        - fmin (float)               : Minimum frequency for pitch detection.
        - fmax (float)               : Maximum frequency for pitch detection.
    
    Out:
        - A fuzzy query searching for the extracted notes.
    """
    # Extract notes from the audio file
    notes = extract_notes(audio_path, sr=sr, fmin=fmin, fmax=fmax)
    
    # Convert notes to query format
    notes_list = [[(note.pitch, note.octave), note.dur] for note in notes]
    
    # Generate the query
    query = create_query_from_list_of_notes(
        notes_list,
        pitch_distance,
        duration_factor,
        duration_gap,
        alpha,
        allow_transposition,
        contour_match,
        collection
    )
    
    return query

def main():
    parser = argparse.ArgumentParser(description="Generate a fuzzy query from an audio file.")
    parser.add_argument("-p", "--pitch_distance", type=float, required=True, help="Pitch distance (fuzzy param)")
    parser.add_argument("-f", "--duration_factor", type=float, required=True, help="Duration factor (fuzzy param)")
    parser.add_argument("-g", "--duration_gap", type=float, required=True, help="Duration gap (fuzzy param)")
    parser.add_argument("-a", "--alpha", type=float, required=True, help="Alpha parameter")
    parser.add_argument("-t", "--allow_transposition", action="store_true", help="Allow transposition")
    parser.add_argument("-C", "--contour_match", action="store_true", help="Enable contour match")
    parser.add_argument("-c", "--collection", type=str, default=None, help="Collection filter")
    
    args = parser.parse_args()
    
    query = create_query_from_audio(
        "./uploads/audio.wav",
        args.pitch_distance,
        args.duration_factor,
        args.duration_gap,
        args.alpha,
        args.allow_transposition,
        args.contour_match,
        args.collection
    )
    
    print(query)

if __name__ == "__main__":
    main()

# if __name__ == "__main__":
#     # Example usage
#     path = "10361_Belle_nous_irons_dans_tes_verts_prs.mei_0_1_1.0.wav"
#     notes = extract_notes(path)
#     print([note.to_list() for note in notes])