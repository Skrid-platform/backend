# 🎼 Symbolic Music Query Engine

This project provides a flexible engine for querying symbolic music corpora using **fuzzy**, **contour-based**, and **polyphonic** patterns. It's built around a **Neo4j graph database**, and exposes both a **command-line interface (CLI)** and an **API**.

---

## ✨ Features

- **Flexible melody matching** with fuzzy tolerance on pitch, rhythm, and timing.
- **Contour-based queries** using fuzzy logic capabilities.
- **Support for polyphony** by combining multiple independent voice queries.
- **Efficient database execution** using Neo4j and Cypher query translation.

---

## 🚀 Getting Started

### 1. Clone the repository
```bash
git clone https://gitlab.inria.fr/skrid/backend.git
cd backend
```

### 2. Dependencies

1. **Set up the database**

**Important:** This codebase assumes a **Neo4j 4.2.1.X** database running a specific symbolic music data model. Data ingestion (from MEI (and other well-known sheet music format) to graph format) is handled in a separate repository:
👉 [SKRID Data Ingestion](https://gitlab.inria.fr/skrid/data-ingestion)

(more infos to be added)

2. Setup on macOS (skip if not on macOS)

**Set up a Python virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r dependencies.txt
```

4. **Run the Flask API locally**
```bash
python3 api.py
```

---

## 🧪 Entry Points

### 1. 👤 Command-Line Interface (`main_parser.py`)

This is the CLI interface for compiling, sending, and generating queries.

```bash
usage: main_parser.py [-h] [-U URI] [-u USER] [-p PASSWORD]
                      {compile,c,send,s,write,w,get,g,list,l} ...
```

#### Subcommands:
| Command      | Alias | Description                               |
|--------------|-------|-------------------------------------------|
| `compile`    | `c`   | Compile a fuzzy query into Cypher         |
| `send`       | `s`   | Send a query (crisp or fuzzy)             |
| `write`      | `w`   | Generate a fuzzy query from note input    |
| `get`        | `g`   | Extract the first `k` notes from a piece  |
| `list`       | `l`   | List available song files in the database |

#### Example usage:
```bash
python3 main_parser.py compile -F fuzzy_query.cypher -o crisp_query.cypher
python3 main_parser.py send -F crisp_query.cypher -t result.txt
python3 main_parser.py write "[[('c', 5), 1, 1], [('d', 5), None]]" -a 0.5 -t
python3 main_parser.py get Air_n_83.mei 5 -o notes
```

---

### 2. 🌐 API (`api.py`)

A Flask-based API that exposes key functionalities for use in front-end applications like SKRID.

#### Available Endpoints:

| Endpoint                   | Method | Description                                 |
|----------------------------|--------|---------------------------------------------|
| `/ping`                   | GET    | Health check                                |
| `/generate-query`         | POST   | Generate a fuzzy or contour query           |
| `/compile-query`          | POST   | Compile a fuzzy query into Cypher           |
| `/execute-fuzzy-query`    | POST   | Execute a fuzzy query and return results    |
| `/execute-crisp-query`    | POST   | Execute a crisp Cypher query and return results |

#### Example usage:
```bash
curl -X POST http://localhost:5000/generate-query \
    -H "Content-Type: application/json" \
    -d '{"notes": "[[(\"c\", 5), 4], [(\"d\", 5), 4]]", "alpha": 0.2}'
```

> The API is used by the Node.js server powering the SKRID front-end and it can be used directly.

---

## 📁 File Structure

Source modules for parsing, reformulation, database interaction, and query execution are organized into:
- `main_parser.py`: CLI entry point.
- `api.py`: Flask server.
- `reformulation_V3.py`, `neo4j_connection.py`, `process_results.py`, `utils.py`: Core logic modules.

A formal breakdown will be added once the refactor is complete.

---

## License

This project is distributed under the MIT License.  
See [LICENSE](./LICENSE) for details.  
(Copyright © 2023–2025 IRISA)



