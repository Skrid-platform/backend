#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Defines an API to interface the features'''

##-Imports
#---General
from flask import Flask, request, jsonify
from ast import literal_eval
import os
from random import randint

#---Project
from src.core.reformulation_V3 import reformulate_fuzzy_query
from src.db.neo4j_connection import connect_to_neo4j, run_query
from src.core.process_results import (
    process_results_to_text,
    process_results_to_json,
    process_crisp_results_to_json
)
from src.utils import (
    check_notes_input_format,
    create_query_from_list_of_notes,
    create_query_from_contour,
    check_contour_input_format
)
from src.audio.recording_to_notes import RecordingToNotes


##-Init
uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "1234678")

DEBUG = True
HOST = '0.0.0.0'
PORT = 5000

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024**2 # 16 MB
app.config['UPLOAD_FOLDER'] = 'uploads/'


##-Functions
def does_query_edits_db(query: str):
    '''
    Checks if the query contains some keywords that modify the database.

    Args:
        query: the cypher query
    
    Returns:
        True if `query` would modify the database, False otherwise
    '''

    keywords = ('create', 'delete', 'set', 'remove', 'detach', 'load')
    for k in keywords:
        if k in query.lower():
            print(f'Query contains "{k.upper()}" keyword. Aborting it.')
            return True

    return False


##-Routes
@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({'message': 'pong'})

@app.route('/generate-query', methods=['POST'])
def generate_query():
    '''
    This endpoint makes a fuzzy query from notes, filters and fuzzy parameters.

    Data to post:
    ```
    {
        'notes': str,
        'pitch_distance': float,
        'duration_factor': float,
        'duration_gap': float,
        'alpha': float,
        'allow_transposition': bool,
        'allow_homothety': bool,
        'incipit_only': bool,
        'collection': str
    }
    ```

    Format of `notes`:
        - For a normal search: see the documentation of `check_notes_input_format`. In the shape of ` "[([note1, ...], duration, dots), ...]"`, e.g `[(["c#/5", "d/5"], 4, 0), (['c/5'], 16, 0)]`.
        - For a contour search: check the documentation of `check_contour_input_format` (not written yet ...)

    If some parameters (apart `notes`) are not specified, they will take their default values.
    '''

    data = request.get_json()

    try:
        contour_search = data.get('contour_match', False)

        if contour_search:
            contour = data['notes']
            contour = check_contour_input_format(contour)
            query = create_query_from_contour(
                contour,
                data.get('incipit_only', False),
                data.get('collection')
            )
        else:
            notes = data['notes']

            #---Convert string to list
            notes_chords = check_notes_input_format(notes)

            query = create_query_from_list_of_notes(
                notes_chords,
                float(data.get('pitch_distance', 0.0)),
                float(data.get('duration_factor', 1.0)),
                float(data.get('duration_gap', 0.0)),
                float(data.get('alpha', 0.0)),
                data.get('allow_transposition', False),
                data.get('allow_homothety', False),
                data.get('incipit_only', False),
                data.get('collection')
            )

        return jsonify({'query': query})

    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 400

@app.route('/execute-fuzzy-query', methods=['POST'])
def execute_query():
    '''
    This endpoint sends a fuzzy query, and return the processed results

    If the query contains a keyword editing the database, then it is aborted.

    Data to post:
    ```
    { 'query': str }
    ```

    Returns the results, in the following format: `{ 'results': r }`, where `r` has the following shape:
        ```
        [
            {
                'source': str,
                'number_of_occurrences': int,
                'max_match_degree': int,       (opt)
                'matches': [                   (opt)
                    {
                        'overall_degree': int,
                        'notes': [
                            {
                                'note_deg': int,
                                'pitch_deg': int,
                                'duration_deg': int,
                                'sequencing_deg': int,
                                'id': str
                            },
                            ...
                        ]
                    },
                    ...
                ]
            },
            ...
        ]
        ```
    '''

    data = request.get_json()
    try:
        fuzzyQuery = data['query']
        crispQuery = reformulate_fuzzy_query(fuzzyQuery)

        if does_query_edits_db(crispQuery):
            return jsonify({'error': 'Keyword not allowed in query (edits the database)'}), 400

        driver = connect_to_neo4j(uri, user, password)

        result = run_query(driver, crispQuery)
        output = process_results_to_json(result, fuzzyQuery)

        driver.close()

        return jsonify({'results': output})

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/execute-crisp-query', methods=['POST'])
def execute_crisp_query():
    '''
    This endpoint sends a crisp query to the database.

    If the query contains a keyword editing the database, then it is aborted.

    Data to post:
    ```
    { 'query': str }
    ```

    Returns `{ 'results': r }`, where `r` is a list of json.
    '''

    data = request.get_json()
    try:
        query = data.get('query')

        if does_query_edits_db(query):
            return jsonify({'error': 'Keyword not allowed in query (edits the database)'}), 400

        driver = connect_to_neo4j(uri, user, password)

        result = run_query(driver, query)
        results_as_dicts = [record.data() for record in result] # Convert Neo4j Record objects to dictionaries

        driver.close()

        return jsonify({'results': results_as_dicts})

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/convert-recording', methods=['POST'])
def convert_recording_to_notes():
    '''
    This endpoint converts an audio file to an array of notes (using spotify's `basic-pitch`).

    Data to post: the audio file.

    Returns `{ 'notes': n }` or `{ 'error': str }`, where `n` is in the following format:
    ```
    [
        [[note1_str, ...], duration_str, dots],
        ...
    ]
    ```
    '''

    try:
        #---Get the file and save it
        uploaded_file = request.files['file']

        if uploaded_file.filename == None:
            return jsonify({'error': 'no file given'}), 400

        # Make a file name with a random nonce
        fn_nonce = randint(100000, 9999999)
        get_ext = lambda x: x[len(x) - x.find('.'):] # function that retrieve the file extension from a string
        ext = get_ext(uploaded_file.filename)
        fn = app.config['UPLOAD_FOLDER'] + f'audio_{fn_nonce}.{ext}'
        uploaded_file.save(fn)

        #---Convert it
        C = RecordingToNotes()
        notes = C.get_notes(fn)

        #---Delete the file
        os.remove(fn)

        notes_json = [c.to_array_format(duration_format='str') for c in notes]

        return jsonify({'notes': notes_json})

    except Exception as e:
        return jsonify({'error': str(e)}), 400


##-Run
if __name__ == '__main__':
    from sys import argv

    if len(argv) <= 1:
        print('--------------------------------------')
        print('To launch without the debug mode, run:')
        print(f'    {argv[0]} nodebug')
        print('--------------------------------------')

    else:
        if argv[1].lower() == 'nodebug':
            DEBUG = False

    app.run(debug=DEBUG, host=HOST, port=PORT)
