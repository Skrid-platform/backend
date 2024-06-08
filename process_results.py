import os
import shutil

from extract_notes_from_query import extract_notes_from_query, extract_fuzzy_parameters
from note import Note
from degree_computation import pitch_degree, duration_degree, sequencing_degree, aggregate_note_degrees, aggregate_sequence_degrees, aggregate_degrees
from generate_audio import generate_mp3
from utils import get_notes_from_source_and_time_interval

def min_aggregation(*degrees):
    return min(degrees)

def average_aggregation(*degrees):
    return sum(degrees) / len(degrees)

def get_ordered_results(result, query):
 # Extract the query notes and fuzzy parameters    
    query_notes = extract_notes_from_query(query)
    pitch_gap, duration_gap, sequencing_gap, alpha, allow_transpose = extract_fuzzy_parameters(query)

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
            duration_deg = duration_degree(query_note[2], note.duration, duration_gap)
            sequencing_deg = 1.0  # Default sequencing degree
            
            if idx > 0:  # Compute sequencing degree for the second and third notes
                prev_note = note_sequence[idx - 1]
                sequencing_deg = sequencing_degree(prev_note.end, note.start, sequencing_gap)
            
            relevant_note_degrees = [degree for degree, gap in [(pitch_deg, pitch_gap), (duration_deg, duration_gap), (sequencing_deg, sequencing_gap)] if gap > 0]

            if len(relevant_note_degrees) > 0:
                note_deg = aggregate_degrees(average_aggregation, relevant_note_degrees)
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

def process_results_to_text(result, query):
    sequence_details = get_ordered_results(result, query)

    with open("results.txt", "w") as file:  # Open in write mode to clear the file
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