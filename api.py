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
    process_results_to_mp3,
    process_results_to_json,
    process_crisp_results_to_json
)
from src.utils import (
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
def query_edits_db(query: str):
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
            notes = notes.replace("\\", "")
            notes = literal_eval(notes)
            query = create_query_from_list_of_notes(
                notes,
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
        return jsonify({'error': str(e)}), 400

@app.route('/compile-query', methods=['POST'])
def compile_query():
    data = request.get_json()
    try:
        query = data['query']
        compiled_query = reformulate_fuzzy_query(query)
        return jsonify({'compiled_query': compiled_query})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/execute-fuzzy-query', methods=['POST'])
def execute_query():
    data = request.get_json()
    try:
        fuzzyQuery = data['query']
        crispQuery = reformulate_fuzzy_query(fuzzyQuery)

        if query_edits_db(crispQuery):
            return jsonify({'error': 'Keyword not allowed in query (edits the database)'}), 400

        driver = connect_to_neo4j(uri, user, password)

        result = run_query(driver, crispQuery)
        
        output = process_results_to_json(result, fuzzyQuery)

        return jsonify({'result': output})

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/execute-crisp-query', methods=['POST'])
def execute_crisp_query():
    data = request.get_json()
    try:
        query = data.get('query')

        if query_edits_db(query):
            return jsonify({'error': 'Keyword not allowed in query (edits the database)'}), 400

        driver = connect_to_neo4j(uri, user, password)
        result = run_query(driver, query)

        # Convert Neo4j Record objects to dictionaries
        results_as_dicts = [record.data() for record in result]
        return jsonify({'results': results_as_dicts})

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/convert-recording', methods=['POST'])
def convert_recording_to_notes():
    try:
        #---Get the file and save it
        uploaded_file = request.files['file']

        if uploaded_file.filename == None:
            return jsonify({'error': 'no file given'}), 400

        fn_nonce = randint(100000, 9999999)
        get_ext = lambda x: x[len(x) - x.find('.'):]
        ext = get_ext(uploaded_file.filename)
        fn = app.config['UPLOAD_FOLDER'] + f'audio_{fn_nonce}.{ext}'
        uploaded_file.save(fn)

        #---Convert it
        C = RecordingToNotes()
        notes = C.get_notes(fn)

        #---Delete the file
        os.remove(fn)

        return jsonify({'notes': notes})

    except Exception as e:
        return jsonify({'error': str(e)}), 400


##-Run
if __name__ == '__main__':
    app.run(debug=DEBUG, host=HOST, port=PORT)
