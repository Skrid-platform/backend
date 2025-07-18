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

2. **Set up a Python virtual environment**

Important: the python version needs to be between `3.8` and `3.11` (both included) for the `basic-pitch` dependency.

Set up a virtual environment:
```bash
# Create the virtual environment
python3 -m venv venv

# Activate it (needs to be ran every time)
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
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
| Command             | Alias | Description                               |
|---------------------|-------|-------------------------------------------|
| `compile`           | `c`   | Compile a fuzzy query into Cypher         |
| `send`              | `s`   | Send a query (crisp or fuzzy)             |
| `write`             | `w`   | Generate a fuzzy query from note input    |
| `recording_convert` | `r`   | Converts a recording to music notes       |
| `get`               | `g`   | Extract the first `k` notes from a piece  |
| `list`              | `l`   | List available song files in the database |

#### Example usage:
```bash
python3 main_parser.py compile -F fuzzy_query.cypher -o crisp_query.cypher
python3 main_parser.py send -F crisp_query.cypher -t result.txt
python3 main_parser.py write "[(['c#/5'], 4, 0), (['b/4'], 8, 1), (['b/4'], 8, 0), (['a/4', 'd/5'], 16, 2)]" -a 0.5 -t
python3 main_parser.py get Air_n_83.mei 5 -o notes
```

---

### 2. 🌐 API (`api.py`)

A Flask-based API that exposes key functionalities for use in front-end applications like SKRID.

#### Available Endpoints:

| Endpoint                 | Method | Description                                      |
|--------------------------|--------|--------------------------------------------------|
| `/ping`                  | GET    | Health check                                     |
| `/collections-names`     | GET    | Retrieve the names of the available collections  |
| `/collection/<col_name>` | GET    | Gets the file names of the collection `col_name` |
| `/generate-query`        | POST   | Generate a fuzzy or contour query                |
| `/compile-query`         | POST   | Compile a fuzzy query into Cypher                |
| `/execute-fuzzy-query`   | POST   | Execute a fuzzy query and return results         |
| `/execute-crisp-query`   | POST   | Execute a crisp Cypher query and return results  |
| `/search-results`        | POST   | Perform a search from melody and parameters      |
| `/convert-recording`     | POST   | Converts a recording to music notes              |

#### Example usage:
```bash
curl -X POST http://localhost:5000/generate-query \
    -H "Content-Type: application/json" \
    -d '{"notes": "[([\"c#/5\"], 4, 0), ([\"b/4\"], 8, 1), ([\"b/4\"], 8, 0), ([\"a/4\", \"d/5\"], 16, 2)]", "alpha": 0.2}'
```

```bash
curl -X POST http://localhost:5000/convert-recording \
    -F file=@relative/path/to/audio.wav
```

> The API is used by the Node.js server powering the SKRID front-end and it can be used directly.

---

## 📁 File Structure
Source modules for parsing, reformulation, database interaction, and query execution are organized into:
| File / folder        | Description                                              |
|----------------------|----------------------------------------------------------|
| `main_parser.py`     | CLI entry point                                          |
| `api.py`             | Flask server                                             |
| `src/core/`          | core logic modules                                       |
| `src/representation/`| classes used for an internal representation of the notes |
| `src/db/`            | connection to the neo4j database                         |
| `src/audio/`         | modules managing audio                                   |

File tree:
```
.
├── src/
│   ├── audio/
│   │   ├── generate_audio.py
│   │   └── recording_to_notes.py
│   ├── core/
│   │   ├── combine_queries.py
│   │   ├── extract_notes_from_query.py
│   │   ├── fuzzy_computation.py
│   │   ├── note_calculations.py
│   │   ├── process_results.py
│   │   ├── refactor.py
│   │   └── reformulation_V3.py
│   ├── db/
│   │   └── neo4j_connection.py
│   ├── representation/
│   │   ├── chord.py
│   │   ├── duration.py
│   │   └── pitch.py
│   └── utils.py
├── tests/
│   └── testing_utilities.py
│
├── uploads/
│
├── api.py
├── main_parser.py
│
├── Dockerfile
├── requirements.txt
│
├── LICENSE.md
├── README.md
└── TODO.md
```

---

## License

This project is distributed under the MIT License.  
See [LICENSE](./LICENSE) for details.  
(Copyright © 2023–2025 IRISA)



