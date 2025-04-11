from flask import Flask, request, jsonify
from ast import literal_eval
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
                data.get('collections')
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
                data.get('collections')
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
        uri = data.get('uri')
        user = data.get('user')
        password = data.get('password')

        driver = connect_to_neo4j(uri, user, password)
        crispQuery = reformulate_fuzzy_query(fuzzyQuery)

        result = run_query(driver, crispQuery)
        output_format = data.get('text', 'json')
        print(output_format)

        if output_format == 'text':
            output = process_results_to_text(result, fuzzyQuery)
        else:
            output = process_results_to_json(result, fuzzyQuery)

        return jsonify({'result': output})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)