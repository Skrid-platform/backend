from flask import Flask, request, jsonify
from ast import literal_eval
import os
from reformulation_V3 import reformulate_fuzzy_query
from neo4j_connection import connect_to_neo4j, run_query
from process_results import (
    process_results_to_text,
    process_results_to_mp3,
    process_results_to_json,
    process_crisp_results_to_json
)
from utils import (
    create_query_from_list_of_notes,
    create_query_from_contour,
    check_contour_input_format
)

uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "1234678")

app = Flask(__name__)

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

        driver = connect_to_neo4j(uri, user, password)
        crispQuery = reformulate_fuzzy_query(fuzzyQuery)

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

        driver = connect_to_neo4j(uri, user, password)
        result = run_query(driver, query)

        # Convert Neo4j Record objects to dictionaries
        results_as_dicts = [record.data() for record in result]
        return jsonify({'results': results_as_dicts})

    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)