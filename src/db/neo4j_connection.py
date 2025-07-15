#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Handles the connection to the Neo4j database'''

##-Imports
from neo4j import GraphDatabase

##-Functions
def connect_to_neo4j(uri, user, password):
    '''Connects to the Neo4j database'''

    driver = GraphDatabase.driver(uri, auth=(user, password))
    return driver

def run_query(driver, query):
    '''Runs a query and fetch all results'''

    with driver.session() as session:
        result = session.run(query)
        # return result.data()
        return list(result)  # Collect all records into a list

def execute_cypher_dumps(directory_path: str, uri: str, user: str, password: str, verbose: bool = False):
    '''
    Executes all .cypher dump files in the specified directory one by one.

    - directory_path : path to the directory containing .cypher files;
    - uri            : Neo4j database URI (e.g., "bolt://localhost:7687");
    - user           : database username;
    - password       : database password;
    - verbose        : if True, prints execution logs.
    '''

    # Check if the directory exists
    if not os.path.isdir(directory_path):
        raise ValueError(f"The directory '{directory_path}' does not exist.")

    # List all .cypher or .cql files in the directory, sorted for consistency
    cypher_files = sorted([f for f in os.listdir(directory_path) if f.endswith('.cypher') or f.endswith('.cql')])

    if not cypher_files:
        print("No .cypher files found in the directory.")
        return

    # Connect to the Neo4j database
    driver = connect_to_neo4j(uri, user, password)

    # Execute each Cypher dump file
    for cypher_file in cypher_files:
        file_path = os.path.join(directory_path, cypher_file)

        try:
            with open(file_path, 'r') as file:
                cypher_query = file.read()
            print(f'Executing {cypher_file}')
            # Execute the Cypher query using run_query
            results = run_query(driver, cypher_query)

            if verbose:
                print(f'Successfully executed: {cypher_file}')
        except Exception as e:
            print(f'Error executing {cypher_file}: {e}')

    print("All Cypher dump files have been executed successfully.")
