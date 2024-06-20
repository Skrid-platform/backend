import os
import shutil

from extract_notes_from_query import extract_notes_from_query, extract_fuzzy_parameters
from note import Note
from degree_computation import pitch_degree, duration_degree, sequencing_degree, aggregate_note_degrees, aggregate_sequence_degrees, aggregate_degrees, pitch_degree_with_intervals, duration_degree_with_multiplicative_factor
from generate_audio import generate_mp3
from utils import get_notes_from_source_and_time_interval, calculate_pitch_interval

def min_aggregation(*degrees):
    return min(degrees)

def average_aggregation(*degrees):
    return sum(degrees) / len(degrees)

def almost_all(degree):
    high_bound, low_bound = 0.5, 0.8
    if degree > high_bound:
        return 1.0
    elif degree < low_bound:
        return 0.0
    else:
        return (degree - low_bound) / (high_bound - low_bound)

def almost_all_aggregation(*degrees):
    average = sum(degrees) / len(degrees)
    return almost_all(average)


def almost_all_aggregation_yager(*degrees):
    # Sort the degrees in ascending order and get distinct values
    sorted_degrees = sorted(set(degrees))

    # Initialize the result
    max_min_alpha_degree = 0

    # Iterate over all distinct alpha cuts
    for alpha in sorted_degrees:
        # Compute the alpha cut
        A_alpha = [degree for degree in degrees if degree >= alpha]
        # Calculate the degree of the alpha cut
        A_alpha_degree = almost_all(len(A_alpha) / len(sorted_degrees))
        print(f"alpha = {alpha}, A_alpha = {A_alpha}, degree = {A_alpha_degree} for mean = {len(A_alpha) / len(degrees)}")
        # Calculate min
        min_alpha_degree = min(alpha, A_alpha_degree)
        # Update the maximum of these minimum values
        max_min_alpha_degree = max(max_min_alpha_degree, min_alpha_degree)

    return max_min_alpha_degree

def get_ordered_results(result, query):
    # Extract the query notes and fuzzy parameters    
    query_notes = extract_notes_from_query(query)
    pitch_gap, duration_factor, sequencing_gap, alpha, allow_transpose, fixed_notes = extract_fuzzy_parameters(query)

    note_sequences = []
    for record in result:
        note_sequence = []
        for idx in range(len(query_notes)):
            pitch = record[f"pitch_{idx}"]
            octave = record[f"octave_{idx}"]
            duration = record[f"duration_{idx}"]
            start = record[f"start_{idx}"]
            end = record[f"end_{idx}"]
            note = Note(pitch, octave, duration, start, end)
            note_sequence.append(note)
        note_sequences.append((note_sequence, record['source'], record['start'], record['end']))

    sequence_details = []

    for seq_idx, (note_sequence, source, start, end) in enumerate(note_sequences):
        note_degrees = []
        note_details = []  # Buffer to store note details before writing
        for idx, note in enumerate(note_sequence):
            query_note = query_notes[idx]
            pitch_deg = pitch_degree(query_note[0], query_note[1], note.pitch, note.octave, pitch_gap)
            duration_deg = duration_degree_with_multiplicative_factor(query_note[2], note.duration, duration_factor)
            sequencing_deg = 1.0  # Default sequencing degree
            
            if idx > 0:  # Compute sequencing degree for the second and third notes
                prev_note = note_sequence[idx - 1]
                sequencing_deg = sequencing_degree(prev_note.end, note.start, sequencing_gap)
            
            relevant_note_degrees = [degree for degree, gap in [(pitch_deg, pitch_gap), (duration_deg, duration_factor), (sequencing_deg, sequencing_gap)] if gap > 0]

            if len(relevant_note_degrees) > 0:
                note_deg = aggregate_degrees(min_aggregation, relevant_note_degrees)
            else :
                note_deg = 1.0
            note_degrees.append(note_deg)
            
            note_detail = (note, pitch_deg, duration_deg, sequencing_deg, note_deg)
            note_details.append(note_detail)
        
        sequence_degree = aggregate_degrees(average_aggregation, note_degrees)
        
        if sequence_degree >= alpha:  # Apply alpha cut
            sequence_details.append((source, start, end, sequence_degree, note_details))
    
    # Sort the sequences by their overall degree in descending order
    sequence_details.sort(key=lambda x: x[3], reverse=True)

    return sequence_details

def get_ordered_results_with_transpose(result, query):
    # Extract the query notes and fuzzy parameters    
    query_notes = extract_notes_from_query(query)
    pitch_gap, duration_factor, sequencing_gap, alpha, allow_transpose, fixed_notes = extract_fuzzy_parameters(query)

    # Compute the intervals between consecutive notes
    intervals = []
    for i in range(len(query_notes) - 1):
        note1, octave1, _ = query_notes[i]
        note2, octave2, _ = query_notes[i + 1]
        interval = calculate_pitch_interval(note1, octave1, note2, octave2)
        intervals.append(interval)

    note_sequences = []
    for record in result:
        note_sequence = []
        for idx in range(len(query_notes)):
            pitch = record[f"pitch_{idx}"]
            octave = record[f"octave_{idx}"]
            duration = record[f"duration_{idx}"]
            start = record[f"start_{idx}"]
            end = record[f"end_{idx}"]
            note = Note(pitch, octave, duration, start, end)
            if idx == 0:
                interval = None
            else:
                interval = record[f"interval_{idx - 1}"]
            note_sequence.append((note, interval))
        note_sequences.append((note_sequence, record['source'], record['start'], record['end']))

    sequence_details = []

    for seq_idx, (note_sequence, source, start, end) in enumerate(note_sequences):
        note_degrees = []
        note_details = []  # Buffer to store note details before writing
        for idx, (note, interval) in enumerate(note_sequence):
            query_note = query_notes[idx]
            if idx == 0:
                # When considering transposition, the first note always has its pitch degree equal to 1.0
                pitch_deg = 1.0
            else:
                pitch_deg = pitch_degree_with_intervals(intervals[idx - 1], interval, pitch_gap)
            duration_deg = duration_degree_with_multiplicative_factor(query_note[2], note.duration, duration_factor)
            sequencing_deg = 1.0  # Default sequencing degree
            
            if idx > 0:  # Compute sequencing degree for the second and third notes
                prev_note = note_sequence[idx - 1][0]
                sequencing_deg = sequencing_degree(prev_note.end, note.start, sequencing_gap)
            
            relevant_note_degrees = [degree for degree, gap in [(pitch_deg, pitch_gap), (duration_deg, duration_factor), (sequencing_deg, sequencing_gap)] if gap > 0]

            if len(relevant_note_degrees) > 0:
                note_deg = aggregate_degrees(min_aggregation, relevant_note_degrees)
            else :
                note_deg = 1.0
            note_degrees.append(note_deg)
            
            note_detail = (note, pitch_deg, duration_deg, sequencing_deg, note_deg)
            note_details.append(note_detail)
        
        sequence_degree = aggregate_degrees(average_aggregation, note_degrees)
        
        if sequence_degree >= alpha:  # Apply alpha cut
            sequence_details.append((source, start, end, sequence_degree, note_details))
    
    # Sort the sequences by their overall degree in descending order
    sequence_details.sort(key=lambda x: x[3], reverse=True)

    return sequence_details

def process_results_to_text(result, query, fn='results.txt'):
    _, _, _, _, allow_transpose, _ = extract_fuzzy_parameters(query)

    if allow_transpose:
        sequence_details = get_ordered_results_with_transpose(result, query)
    else:
        sequence_details = get_ordered_results(result, query)

    with open(fn, "w") as file:  # Open in write mode to clear the file
        for source, start, end, sequence_degree, note_details in sequence_details:
            file.write(f"Source: {source}, Start: {start}, End: {end}, Overall Degree: {sequence_degree}\n")
            for idx, (note, pitch_deg, duration_deg, sequencing_deg, note_deg) in enumerate(note_details):
                file.write(f"  Note {idx + 1}: {note}\n")
                file.write(f"    Pitch Degree: {pitch_deg}\n")
                file.write(f"    Duration Degree: {duration_deg}\n")
                file.write(f"    Sequencing Degree: {sequencing_deg}\n")
                file.write(f"    Aggregated Note Degree: {note_deg}\n")
            file.write("\n")  # Add a blank line between sequences


def process_results_to_mp3(result, query, max_files, driver):
    _, _, _, _, allow_transpose, _ = extract_fuzzy_parameters(query)

    if allow_transpose:
        sequence_details = get_ordered_results_with_transpose(result, query)
    else:
        sequence_details = get_ordered_results(result, query)

    if len(sequence_details) > max_files:
        # Limit the number of files to generate
        sequence_details = sequence_details[:max_files]

    # Clear previous results in audio directory
    audio_dir = os.path.join(os.getcwd(), "audio")
    if os.path.exists(audio_dir):
        shutil.rmtree(audio_dir)
    os.makedirs(audio_dir)

    # Generate MP3 files
    for idx, (source, start, end, sequence_degree, note_details) in enumerate(sequence_details):
        notes = get_notes_from_source_and_time_interval(driver, source, start, end)
        file_name = f"{source}_{start}_{end}_{round(sequence_degree, 2)}.mp3"
        generate_mp3(notes, file_name, bpm=60)

if __name__ == "__main__":
    # Example usage
    degrees = [0.7, 0.3, 1, 0.3, 0.7, 0.3]
    result = almost_all_aggregation_yager(*degrees)
    print(result)
