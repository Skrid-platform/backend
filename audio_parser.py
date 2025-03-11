import librosa
import numpy as np
import argparse
import scipy.signal
import re

from note import Note
from utils import create_query_from_list_of_notes

def smooth_f0(f0, window_size=3):
    """Apply median filtering to remove frequency outliers."""
    smoothed_f0 = scipy.signal.medfilt(f0, kernel_size=window_size)
    smoothed_f0 = [freq if freq > 0.0 else None for freq in smoothed_f0]
    return smoothed_f0

def average_aggregate_f0(f0, samples_per_sec=100, target_samples_per_sec=20):
    """Reduce the number of samples in f0 by averaging over aggregation groups."""
    aggregation_size = samples_per_sec // target_samples_per_sec  # Determine group size
    num_groups = len(f0) // aggregation_size
    
    aggregated_f0 = [np.nanmean(f0[i * aggregation_size: (i + 1) * aggregation_size]) for i in range(num_groups)]
    
    return np.array(aggregated_f0)

def frequency_to_note(freq):
    """Convert frequency to a musical note with cents deviation using regex."""
    if freq is None:
        return None, None, None  # Silence or unvoiced region
    
    note_str = librosa.hz_to_note(freq, cents=True)
    
    match = re.match(r"([A-Ga-g#♯♭]+)(-?\d+)([+-]?\d+)?", note_str)
    
    if match:
        pitch = match.group(1)  # Extract pitch name
        octave = int(match.group(2))  # Extract octave
        cents = int(match.group(3)) if match.group(3) else 0  # Extract cents deviation (default 0)
        return pitch, octave, cents

    return None, None, None  # Fallback in case of unexpected format


def map_frequencies_to_pitches(f0, cents_threshold=50):
    """Convert frequencies to sticky pitches, tracking sequence lengths."""
    pitches = []
    sequence_lengths = []
    prev_pitch, prev_octave, prev_cents = None, None, None
    count = 0

    print([frequency_to_note(freq) for freq in f0], len(f0))
    for freq in f0:
        pitch, octave, cents = frequency_to_note(freq)

        if prev_pitch is not None:
            # Check if transitioning from a note to its sharp variant
            if prev_pitch + "#" == pitch and prev_cents is not None and cents is not None:
                if prev_cents > cents_threshold and cents < -cents_threshold:
                    # Treat it as the same note (sticky behavior)
                    count += 1
                    continue

        # If new pitch is detected, store the previous one
        if pitch == prev_pitch:
            count += 1
        else:
            if prev_pitch is not None:
                pitches.append((prev_pitch, prev_octave))
                sequence_lengths.append(count)
            prev_pitch, prev_octave, prev_cents = pitch, octave, cents
            count = 1

    # Store last note
    if prev_pitch is not None:
        pitches.append((prev_pitch, prev_octave))
        sequence_lengths.append(count)

    return pitches, sequence_lengths

def assign_durations(sequence_lengths):
    """Compute relative durations and assign closest musical note fractions."""
    max_length = max(sequence_lengths)
    relative_durations = [length / max_length for length in sequence_lengths]
    
    # Define eligible musical durations (including dotted notes)
    eligible_durations = {1, 1/2, 1/4, 1/8, 1/16, 3/4, 3/8, 3/16}
    
    # Assign nearest eligible fraction
    durations = [min(eligible_durations, key=lambda x: abs(x - dur)) for dur in relative_durations]
    return durations

def extract_notes(path, sr=16000, fmin=65, fmax=900):
    """Convert WAV audio to a sequence of Note objects with proper rhythmic values."""
    audio, sr = librosa.load(path, sr=sr)
    f0, _, _ = librosa.pyin(audio, sr=sr, fmin=fmin, fmax=fmax, n_thresholds=30)
    f0 = smooth_f0(f0)
    f0 = average_aggregate_f0(f0)
    print(f0, len(f0),'f0')
    pitches, sequence_lengths = map_frequencies_to_pitches(f0)
    durations = assign_durations(sequence_lengths)
    
    notes = []
    cumulative_duration = 0.0  # Start time in whole notes
    
    for (pitch, octave), duration in zip(pitches, durations):
        if pitch is not None:
            notes.append(Note(pitch, octave, duration, start=cumulative_duration))
            cumulative_duration += duration
    
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
        # "../uploads/audio.wav",
        "./uploads/audio.wav",
        # "./10361_Belle_nous_irons_dans_tes_verts_prs.mei_0_1_1.0.wav",
        # "./SolSiRe.wav",
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
    # main()
    # # Example usage
    # path = "SolSiRe.wav"
    # notes = extract_notes(path)
    # print([note.to_list() for note in notes])

    res = extract_notes("./audio/input/10361_Belle_nous_irons_dans_tes_verts_prs.mei_0_1_1.0.mp3", sr=48000)
    print(res, len(res))