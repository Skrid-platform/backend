#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
