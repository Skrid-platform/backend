from neo4j import GraphDatabase

# Function to connect to the Neo4j database
def connect_to_neo4j(uri, user, password):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    return driver

# Function to run a query and fetch all results
def run_query(driver, query):
    with driver.session() as session:
        result = session.run(query)
        # return result.data()
        return list(result)  # Collect all records into a list
