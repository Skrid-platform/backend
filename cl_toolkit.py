import sys
import os

from neo4j_connection import connect_to_neo4j, run_query
from reformulation_V2 import reformulate_fuzzy_query
from process_results import process_results_to_text, process_results_to_mp3
from utils import get_first_k_notes_of_each_score, create_query_from_list_of_notes

# Function to display the menu
def display_menu():
    print("Command Line Toolkit:")
    print("1. Write a fuzzy pattern query")
    print("2. Compile the fuzzy query")
    print("3. Get the result of a query")
    print("4. Get the first k notes of a specified song")
    print("h. Help")
    print("e. Exit")

# Function to handle writing a fuzzy pattern query
def write_fuzzy_pattern_query():
    notes_input = input("Enter the list of notes (as triples e.g., [(c, 5, 1), (d, 5, 4)]): ")
    notes = eval(notes_input)  # Convert string input to list of tuples
    pitch_distance = float(input("Enter pitch distance (default 0.0): ") or "0.0")
    duration_factor = float(input("Enter duration factor (default 1.0): ") or "1.0")
    duration_gap = float(input("Enter duration gap (default 0.0): ") or "0.0")
    
    allow_transposition_input = input("Allow transposition? (y/n): ") or "n"
    allow_transposition = allow_transposition_input.lower() == 'y'
    
    alpha = float(input("Enter alpha (default 0.0): ") or "0.0")
    
    query = create_query_from_list_of_notes(notes, pitch_distance, duration_factor, duration_gap, alpha, allow_transposition, False)
    print(query)
    save_option = input("Do you want to save the query to fuzzy_query.cypher? (y/n, default y): ") or "y"
    if save_option.lower() == 'y':
        with open("fuzzy_query.cypher", "w") as file:
            file.write(query)

# Function to handle compiling the fuzzy query
def compile_fuzzy_query():
    with open("fuzzy_query.cypher", "r") as file:
        query = file.read()
    print("Compiling")
    print(query)
    print("Compiled query:")
    compiled_query = reformulate_fuzzy_query(query)
    print(compiled_query)
    save_option = (input("Do you want to save the compiled query to crisp_query.cypher? (y/n): ") or "y")
    if save_option.lower() == 'y':
        with open("crisp_query.cypher", "w") as file:
            file.write(compiled_query)

# Function to get the result of a query
def get_query_result(driver):
    with open("fuzzy_query.cypher", "r") as file:
            fuzzy_query = file.read()
    crisp_query = reformulate_fuzzy_query(fuzzy_query)
    print("Query to be executed:")
    print(crisp_query)
    confirm = (input("Do you want to proceed? (y/n): ") or "y")
    if confirm.lower() == 'y':
        result = run_query(driver, crisp_query)
        output_format = (input("Do you want the results in text (t) or as MP3 files (m)? ") or "t")
        if output_format.lower() == 't':
            process_results_to_text(result, fuzzy_query)
        elif output_format.lower() == 'm':
            maxfiles = int(input("How many files to save? "))
            process_results_to_mp3(result, fuzzy_query, maxfiles, driver)

# Function to get the first k notes of a specified song
def get_first_k_notes_of_song(driver):
    print("Available songs:")
    available_songs = list_available_songs(driver)
    for song in available_songs:
        print(song)
    source = input("Enter the name of the song: ")
    k = int(input("Enter the number of wanted first notes: "))
    # Assuming we have the driver and session setup
    result = get_first_k_notes_of_each_score(k, source, driver)
    print(f"Here is the first {k} notes of {source} :")
    print(result)

    save_option = (input("Do you want to save a fuzzy query searching for this pattern ? (y/n): ") or "y")
    if save_option.lower() == 'y':
        pitch_distance = float(input("Enter pitch distance (default 0.0): ") or "0.0")
        duration_factor = float(input("Enter duration factor (default 1.0): ") or "1.0")
        duration_gap = float(input("Enter duration gap (default 0.0): ") or "0.0")
            
        allow_transposition_input = input("Allow transposition? (y/n): ") or "n"
        allow_transposition = allow_transposition_input.lower() == 'y'

        alpha = float(input("Enter alpha (default 0.0): ") or "0.0")
        query = create_query_from_list_of_notes(result, pitch_distance, duration_factor, duration_gap, alpha, allow_transposition, False)
        print(query)
        with open("fuzzy_query.cypher", "w") as file:
            file.write(query)

def list_available_songs(driver):
    query = "MATCH (s:Score) RETURN DISTINCT s.source AS source"
    result = run_query(driver, query)
    return [record["source"] for record in result]

# Main function to run the command-line toolkit
def main():
    # Set up the driver
    uri = "bolt://localhost:7687"  # Default URI for a local Neo4j instance
    user = "neo4j"                 # Default username
    password = "12345678"          # Replace with your actual password
    driver = connect_to_neo4j(uri, user, password)

    stop = False
    while stop == False:
        display_menu()
        choice = input("Enter your choice: ")
        if choice == '1':
            write_fuzzy_pattern_query()
        elif choice == '2':
            compile_fuzzy_query()
        elif choice == '3':
            get_query_result(driver)
        elif choice == '4':
            get_first_k_notes_of_song(driver)
        elif choice.lower() == 'h':
            display_menu()
        elif choice.lower() == 'e':
            print("Exiting.")
            stop = True
        else:
            print("Invalid choice. Please enter a valid number.")
    driver.close()

if __name__ == "__main__":
    main()
