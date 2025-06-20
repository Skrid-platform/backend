#!/usr/bin/env python3
# -*- coding: utf-8 -*-

##-Imports
#---General
import os
import subprocess
import time
import csv
import numpy as np
import glob
import random
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import ast

#---Project
from src.db.neo4j_connection import connect_to_neo4j, run_query
from src.utils import calculate_pitch_interval, create_query_from_contour

class PerformanceLogger:
    _instance = None
    log_file = "performance_log.csv"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PerformanceLogger, cls).__new__(cls)
            cls._instance._segments = {}
            cls._instance._load_log_file()
        return cls._instance

    @classmethod
    def _load_log_file(cls):
        """Charge les entrées existantes du fichier CSV dans le dictionnaire avec ';' comme séparateur."""
        if os.path.exists(cls.log_file):
            with open(cls.log_file, mode="r") as file:
                reader = csv.DictReader(file, delimiter=";")
                for row in reader:
                    name = row["name"]
                    start_time = float(row["start"]) if row["start"] else None
                    end_time = float(row["end"]) if row["end"] else None
                    cls._instance._segments[name] = [start_time, end_time]

    @classmethod
    def _generate_unique_name(cls, base_name):
        """Génère un nom unique avec un suffixe '_i' si nécessaire."""
        count = 0
        name = f"{base_name}_{count}"
        while name in cls._instance._segments:
            name = f"{base_name}_{count}"
            count += 1
        return name
    
    @classmethod
    def _get_unique_name(cls, base_name):
        """Retourne le dernier nom unique créé pour `base_name`."""
        count = 0
        name = f"{base_name}_{count}"
        latest_name = name

        if name not in cls._instance._segments:
             raise ValueError(f"Le segment '{latest_name}' n'existe pas.")

        # Parcours des noms possibles pour trouver le plus grand suffixe existant
        while name in cls._instance._segments:
            latest_name = name
            count += 1
            name = f"{base_name}_{count}"
        
        if cls._instance._segments[latest_name][1] is not None:
            raise ValueError(f"Le segment '{latest_name}' a déjà une date de fin.")

        return latest_name

    def start(self, segment_name):
        unique_name = self._generate_unique_name(segment_name)
        self._segments[unique_name] = [time.time(), None]

    def end(self, segment_name):
        unique_name = self._get_unique_name(segment_name)
        self._segments[unique_name][1] = time.time()

    def save(self):
        """Enregistre les données dans le fichier CSV avec ';' comme séparateur."""
        with open(self.log_file, mode="w", newline="") as file:
            writer = csv.writer(file, delimiter=";")

            # Ajout de l'en-tête
            writer.writerow(["name", "start", "end", "duration"])

            # Écriture des données
            for name, times in self._segments.items():
                start, end = times
                duration = end - start if start is not None and end is not None else None
                # Utilise une chaîne vide pour None, suivant les conventions CSV
                writer.writerow([
                    name,
                    start if start is not None else "",
                    end if end is not None else "",
                    duration if duration is not None else ""
                ])

def process_and_plot(csv_file):
    total_times = []
    execution_times = []

    # Lecture du fichier CSV avec DictReader
    with open(csv_file, "r") as file:
        reader = csv.DictReader(file, delimiter=";")
        rows = list(reader)  # Charger toutes les lignes dans une liste
        
        # Extraction des temps à partir des colonnes `duration`
        for i in range(0, len(rows), 2):  # Lignes impaires pour total
            total_times.append(float(rows[i]["duration"]))
            execution_times.append(float(rows[i + 1]["duration"]))  # Lignes paires pour exécution

    # Calcul des différences
    differences = [total - execution for total, execution in zip(total_times, execution_times)]

    # Création du premier graphique : deux distributions
    plt.figure(figsize=(8, 6))
    plt.boxplot([total_times, execution_times], tick_labels=["Query reformulation, execution and result ranking", "Only query execution"], whis=[0,95])
    plt.ylabel("Time (seconds)")
    plt.savefig("boxplot_distributions.pdf")
    plt.close()

    # Création d'un fichier PDF
    with PdfPages("grouped_boxplots_time_differences.pdf") as pdf:
        # Configuration de la figure avec deux sous-graphiques
        fig, axes = plt.subplots(1, 2, figsize=(12, 6))

        # Premier graphique : toutes les différences
        axes[0].boxplot(differences, tick_labels=["Differences"], whis=[0,95])
        # axes[0].set_title("Time differences (all)")
        axes[0].set_ylabel("Time (seconds)")

        # Deuxième graphique : différences sans les 5 plus grandes
        differences.sort()
        filtered_differences = differences[:-5]
        axes[1].boxplot(filtered_differences, tick_labels=["Differences without 5 most extrem outliers"], whis=[0,95])
        # axes[1].set_title("Time differences (without outliers)")
        axes[1].set_ylabel("Time (seconds)")

        # Ajuster l'espacement entre les sous-graphiques
        fig.tight_layout()

        # Sauvegarder la figure dans le PDF
        pdf.savefig()
        plt.close()

    print("Figures saved as PDFs.")

def generate_queries(notes, suffixe):
    for j in np.linspace(1,4,7):
        for i in range(1, len(notes) + 1):
            notes_subset = notes[:i]
            
            formatted_notes = f'"{notes_subset}"'
            
            output_file = f"{suffixe}_{j}_{i}.cypher"
            
            command = f"python3 main_parser.py write -o ./test_queries/{suffixe}/{output_file} -p 0.0 -f {j} -g 0.0 -a 0.0 {formatted_notes}"
            
            print(f"Running command: {command}")
            subprocess.run(command, shell=True)

def generate_random_queries(sequences, num_queries=100):
    queries = []
    output_dir = "./test_queries/random_queries/"
    default_values = {"-p": 0.0, "-f": 1.0, "-g": 0.0}

    # Générer 100 requêtes aléatoires
    for i in range(1, num_queries + 1):
        # Choisir un pattern aléatoire
        pattern = random.choice(sequences)
        
        # Choisir aléatoirement le début et la fin
        start = random.randint(0, 18)
        end = random.randint(start, 19)
        selected_sequence = pattern[start:end+1]  # Slicing pour la séquence choisie
        formatted_sequence = f"\"{selected_sequence}\""
        
        # Choisir les leviers de flexibilité utilisés
        levers = {"-p": default_values["-p"], "-f": default_values["-f"], "-g": default_values["-g"]}
        for lever in levers:
            if random.choice([True, False]):  # Décision aléatoire d'utiliser le levier
                if lever == "-p":
                    levers[lever] = random.choice(np.linspace(0,3,7))
                elif lever == "-f":
                    levers[lever] = random.choice(np.linspace(2.0,8.0,7))
                elif lever == "-g":
                    levers[lever] = random.choice([0.0625, 0.125, 0.25, 0.5])
        
        # Construire le fichier de sortie
        output_file = f"{output_dir}query_{i}.cypher"
        
        # Construire la commande
        command = (
            f"python3 main_parser.py write -o {output_file} -p {levers['-p']} -f {levers['-f']} -g {levers['-g']} -a 0.0 {formatted_sequence}"
        )
        
        print(f"Running command: {command}")
        subprocess.run(command, shell=True)

def generate_length_based_queries(output_dir, sequences, param_name, param_values, max_length, transpose):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    else:
        for file_path in glob.glob(os.path.join(output_dir, "*.cypher")):
            os.remove(file_path)

    # Itérer sur chaque valeur du paramètre
    for param_value in param_values:
        # Itérer sur les longueurs de pattern (de 1 à 20)
        for pattern_length in range(1, max_length + 1):
            # Générer une requête pour chaque séquence
            for seq_index, sequence in enumerate(sequences):
                # Extraire le sous-pattern de la séquence
                pattern = sequence[:pattern_length]
                formatted_pattern = f"\"{pattern}\""

                # Construire le nom du fichier de sortie
                file_name = f"{param_name.strip('-')}_{param_value}_len_{pattern_length}_seq_{seq_index + 1}.cypher"
                output_file = os.path.join(output_dir, file_name)

                # Fixer les autre paramètres
                if param_name == "-p":
                    p_value, f_value, g_value = param_value, 1.0, 0.0
                elif param_name == "-f":
                    p_value, f_value, g_value = 0.0, param_value, 0.0
                else:
                    p_value, f_value, g_value = 0.0, 1.0, param_value

                # Construire la commande
                if not transpose:
                    command = (f"python3 main_parser.py write -o {output_file} -p {p_value} -f {f_value} -g {g_value} -a 0.0 {formatted_pattern}")
                if transpose:
                    command = (f"python3 main_parser.py write -o {output_file} -p {p_value} -f {f_value} -g {g_value} -a 0.0 -t {formatted_pattern}")

                print(f"Running command: {command}")
                subprocess.run(command, shell=True)

    print(f"Queries written to {output_dir}")

def generate_queries_v2(test_name, sequences, p_value, f_value, g_value, pattern_length, with_transpose = False):
    output_dir = f"./test_queries/{test_name}/"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Générer une requête pour chaque séquence
    for seq_index, sequence in enumerate(sequences):
        # Extraire le sous-pattern de la séquence
        pattern = sequence[:pattern_length]
        formatted_pattern = f"\"{pattern}\""

        # Construire le nom du fichier de sortie
        file_name = f"{test_name}_{p_value}_{f_value}_{g_value}_len_{pattern_length}_seq_{seq_index + 1}.cypher"
        output_file = os.path.join(output_dir, file_name)

        # Vérifier si le fichier existe déjà et le supprimer si nécessaire
        if os.path.exists(output_file):
            print(f"File {output_file} already exists. Deleting it.")
            os.remove(output_file)

        # Construire la commande
        if with_transpose:
            command = (f"python3 main_parser.py write -o {output_file} -p {p_value} -f {f_value} -g {g_value} -a 0.0 -t {formatted_pattern}")
        else :
            command = (f"python3 main_parser.py write -o {output_file} -p {p_value} -f {f_value} -g {g_value} -a 0.0 {formatted_pattern}")

        print(f"Running command: {command}")
        subprocess.run(command, shell=True)

    print(f"Queries written to {output_dir}")

def execute_queries(dir_path, sequences, param_name, param_values, max_length):
    for param_value in param_values:
        for pattern_length in range(1, max_length + 1):
            for seq_index, sequence in enumerate(sequences):
                query_file = f"{param_name.strip('-')}_{param_value}_len_{pattern_length}_seq_{seq_index + 1}.cypher"
                command = f"python3 main_parser.py send -f -F {dir_path}{query_file}  > /dev/null"
                print(f"Running command: {command}")
                subprocess.run(command, shell=True)

def execute_queries_v2(test_name, sequences, pattern_length, suffix=None):
    dir_path = f"./queries/test_queries/{test_name}/"
    for seq_index, sequence in enumerate(sequences):
        if suffix:
            query_file = f"{test_name}_{suffix}_len_{pattern_length}_seq_{seq_index + 1}.cypher"
        else:
            query_file = f"{test_name}_len_{pattern_length}_seq_{seq_index + 1}.cypher"
        command = f"python3 main_parser.py send -f -F {dir_path}{query_file}  > /dev/null"
        print(f"Running command: {command}")
        subprocess.run(command, shell=True)

def process_and_generate_latex(test_name, param_values, max_length, nb_sequences):
    """
    Génère du code LaTeX pour les temps totaux et les temps d'exécution à partir d'un fichier CSV.
    
    :param test_name: Nom du test utilisé pour les fichiers CSV et LaTeX.
    :param param_values: Liste des valeurs pour le paramètre testé.
    :param max_length: Longueur maximale des séquences.
    :param nb_sequences: Nombre de séquences par test.
    """
    import csv
    import numpy as np

    # Déduire les noms des fichiers
    csv_file = f"./CSV/{test_name}_log.csv"
    file_name = test_name
    label_title = test_name.capitalize()

    # Chargement des données depuis le CSV
    with open(csv_file, "r") as file:
        reader = csv.DictReader(file, delimiter=";")
        rows = list(reader)

    # Initialisation des structures pour les données
    total_times = {param: [[] for _ in range(max_length)] for param in param_values}
    execution_times = {param: [[] for _ in range(max_length)] for param in param_values}

    # Remplissage des données
    for param_idx, param_value in enumerate(param_values):
        for length in range(1, max_length + 1):
            base_idx = (param_idx * max_length + (length - 1)) * nb_sequences * 2
            for seq in range(nb_sequences):
                total_time = float(rows[base_idx + seq * 2]["duration"])  # Temps total
                exec_time = float(rows[base_idx + seq * 2 + 1]["duration"])  # Temps d'exécution
                total_times[param_value][length - 1].append(total_time)
                execution_times[param_value][length - 1].append(total_time - exec_time)

    # Calcul des moyennes
    avg_total_times = {
        param: [np.mean(times) for times in total_times[param]] for param in param_values
    }

    avg_execution_deltas = {
        param: [np.mean(deltas) for deltas in execution_times[param]] for param in param_values
    }

    # Génération du code LaTeX
    def generate_latex_curves(data, labels):
        colors = ["blue", "red", "green", "orange", "purple", "cyan"]
        latex_code = ""
        for idx, (param, values) in enumerate(data.items()):
            latex_code += f"""
        \\addplot[color={{{colors[idx % len(colors)]}}}, mark=*, thick] coordinates {{{" ".join(f"({i + 1}, {value:.4f})" for i, value in enumerate(values))}}};
        \\addlegendentry{{{labels.format(param=param)}}}
        """
        return latex_code

    # Générer les deux figures
    latex_code_total = generate_latex_curves(
        avg_total_times,
        labels=f"{label_title} = {{param}}"
    )

    latex_code_execution = generate_latex_curves(
        avg_execution_deltas,
        labels=f"{label_title} = {{param}}"
    )

    # Écrire le code LaTeX dans des fichiers
    with open(f"./latex/{file_name}.tex", "w") as file:
        file.write(latex_code_total)
    print(f"LaTeX code written to './latex/{file_name}.tex'")

    with open(f"./latex/{file_name}_surplus.tex", "w") as file:
        file.write(latex_code_execution)
    print(f"LaTeX code written to './latex/{file_name}_surplus.tex'")

def generate_histogram_bar(csv_file, output_file, label, bar_color_total="blue", bar_color_execution="red"):
    """
    Génère un bâton d'histogramme LaTeX pour un fichier CSV donné.

    Args:
        csv_file (str): Chemin vers le fichier CSV contenant les données de test.
        label (str): Étiquette de l'axe des abscisses pour ce bâton.
        bar_color_total (str): Couleur de la barre représentant le temps total.
        bar_color_execution (str): Couleur de la barre représentant le temps d'exécution uniquement.

    Returns:
        str: Code LaTeX pour le bâton d'histogramme.
    """
    # Charger les données depuis le CSV
    total_times = []
    execution_times = []

    with open(csv_file, "r") as file:
        reader = csv.DictReader(file, delimiter=";")
        rows = list(reader)

        for i, row in enumerate(rows):
            duration = float(row["duration"])
            if i % 2 == 0:  # Temps total (ligne paire)
                total_times.append(duration)
            else:  # Temps d'exécution uniquement (ligne impaire)
                execution_times.append(duration)

    # Calcul des moyennes
    avg_total_time = np.mean(total_times)
    avg_execution_time = np.mean(execution_times)
    print(output_file, f'{avg_total_time:.2f}', f'{avg_execution_time:.2f}')

    # Générer le code LaTeX pour le bâton
    latex_code = f"""
    \\addplot[ybar, bar width=0.5cm, fill={bar_color_total}] coordinates {{
        ({label}, {avg_total_time:.2f})
    }};
    \\addplot[ybar, bar width=0.3cm, fill={bar_color_execution}] coordinates {{
        ({label}, {avg_execution_time:.2f})
    }};
    """

    # Écrire le code LaTeX dans un fichier
    with open(f"./latex/{output_file}.tex", "w") as file:
        file.write(latex_code)

    print(f"LaTeX code written to './latex/{output_file}.tex")

    return latex_code

def generate_multiple_random_notes(n, num_notes=15, output_file="random_notes.txt"):
    """
    Génère `n` listes de 15 notes à partir de partitions aléatoires et les écrit dans un fichier texte.
    
    Args:
        n (int): Nombre de listes à générer.
        num_notes (int): Nombre exact de notes à garder (par défaut 15).
        output_file (str): Nom du fichier de sortie (par défaut "random_notes.txt").
        
    Returns:
        None
    """
    # Obtenir la liste des partitions avec `list`
    result = subprocess.run(
        ["python3", "main_parser.py", "list"], capture_output=True, text=True
    )
    partitions = result.stdout.strip().splitlines()
    
    if not partitions:
        raise ValueError("No partitions found.")

    generated_notes = []

    for _ in range(n):
        # Choisir une partition aléatoirement
        chosen_partition = random.choice(partitions)

        # Générer un entier aléatoire k entre 1 et 10
        k = random.randint(1, 10)
        num_extra_notes = num_notes + k

        # Obtenir les `num_notes+k` premières notes avec `get`
        result = subprocess.run(
            ["python3", "main_parser.py", "get", chosen_partition, str(num_extra_notes)],
            capture_output=True,
            text=True
        )
        notes = result.stdout.strip()

        # Convertir la chaîne en une liste Python
        try:
            notes_list = ast.literal_eval(notes)
        except (SyntaxError, ValueError):
            raise ValueError("Failed to parse notes from command output.")
        if len(notes_list) < num_extra_notes:
            raise ValueError(f"Partition {chosen_partition} does not have enough notes.")

        # Retirer les k premières notes pour conserver les 15 suivantes
        truncated_notes = notes_list[k:k + num_notes]
        generated_notes.append(truncated_notes)

    # Écrire les résultats dans un fichier texte
    with open(output_file, "w") as f:
        f.write(repr(generated_notes))

    print(f"Generated notes saved to {output_file}")

def populate_500_score():

        uri = "bolt://localhost:7687"  # Default URI for a local Neo4j instance
        user = "neo4j"                 # Default username
        password = "12345678"          # Replace with your actual password
        driver = connect_to_neo4j(uri, user, password)

        with open("load_500_scores.cql", "r") as f:
            query = f.read()

        # Run the query
        run_query(driver, query)

def save_csv(test_name):
    """
    Déplace le fichier performance_log.csv vers le dossier CSV avec un nom basé sur le test_name.
    """
    command = f"mv ./performance_log.csv ./CSV/{test_name}_log.csv"
    print(f"Running command: {command}")
    subprocess.run(command, shell=True)

def extract_contour_from_notes(notes):
    """
    Extracts the melodic and rhythmic contour from a sequence of notes.

    Parameters:
        notes (list): A list of notes, where each note is in the format `[('pitch', octave), duration]`.

    Returns:
        tuple: A tuple containing (melodic_contour, rhythmic_contour), both as lists of contour symbols.
    """
    
    def get_melodic_symbol(interval):
        """Maps a pitch interval to a contour symbol."""
        if interval > 2:
            return '*U'
        elif interval > 1:
            return 'U'
        elif interval > 0:
            return 'u'
        elif interval == 0:
            return 'R'
        elif interval < -2:
            return '*D'
        elif interval < -1:
            return 'D'
        else:
            return 'd'

    def get_rhythmic_symbol(ratio):
        """Maps a duration ratio to a contour symbol."""
        if ratio >= 4.0:
            return 'L'
        elif ratio >= 1.5:
            return 'l'
        elif ratio == 1.0:
            return 'M'
        elif ratio <= 0.25:
            return 'S'
        else:
            return 's'

    melodic_contour = []
    rhythmic_contour = []

    for i in range(len(notes) - 1):
        # Extract pitch and octave
        (pitch1, octave1), duration1 = notes[i]
        (pitch2, octave2), duration2 = notes[i + 1]

        # Compute pitch interval
        if pitch1 is None or pitch2 is None:
            melodic_contour.append('X')
        else:
            interval = calculate_pitch_interval(pitch1, octave1, pitch2, octave2)
            melodic_contour.append(get_melodic_symbol(interval))

        # Compute duration ratio
        if duration1 is None or duration2 is None:
            melodic_contour.append('X')
        else:
            ratio = duration1 / duration2
            rhythmic_contour.append(get_rhythmic_symbol(ratio))

    return ''.join(melodic_contour), ''.join(rhythmic_contour)

def generate_contour_queries(test_name, contour_file, with_interval, with_duration_ratio, length):
    output_dir = f"./queries/test_queries/{test_name}/"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Charger les contours depuis le fichier
    with open(contour_file, "r") as file:
        contours = [line.strip() for line in file if line.strip()]

    if not contours:
        raise ValueError("No contours found in the file.")

    # Générer les requêtes pour chaque contour
    for idx, contour in enumerate(contours):      
        melodic_part, rhythmic_part = contour.split("-")

        # Convert into lists of individual symbols
        rhythmic_contours = list(rhythmic_part)
        melodic_contours = []

        # Process melodic contour sequence while handling '*U' and '*D' properly
        i = 0
        while i < len(melodic_part):
            if melodic_part[i] == '*':  
                    melodic_contours.append(melodic_part[i]+melodic_part[i+1])
                    i += 2
            else:
                melodic_contours.append(melodic_part[i])
                i += 1

        # Générer les contours
        new_melodic = melodic_contours[:length] if with_interval else ["X" for _ in range(length)]
        new_rhythmic = rhythmic_contours[:length] if with_duration_ratio else ["X" for _ in range(length)]
        new_contour = f"{new_melodic}-{new_rhythmic}"

        new_contour = {
            'rhythmic': new_rhythmic,
            'melodic': new_melodic
        }

        query = create_query_from_contour(new_contour, False)

        # Déterminer le nom du fichier de sortie
        query_name = f"{test_name}_{with_interval}_{with_duration_ratio}_len_{length}_seq_{idx+1}.cypher"
        output_file = os.path.join(output_dir, query_name)

        # Écrire la requête dans un fichier
        with open(output_file, "w") as f:
                f.write(query + "\n")
                print(f"Generated query {output_file}")


# if __name__ == "__main__":
    # for _ in range(12):
    #     populate_500_score()

    # generate_multiple_random_notes(15, 15)
    # sequences = []
    # with open("random_notes.txt", "r") as f:
    #     sequences = ast.literal_eval(f.read())
        # sequences = [[[(note[0][0], note[0][1]), note[1]] for note in sequence] for sequence in sequences]
    # sequences = sequences[:3]
    # nb_sequences=len(sequences)
    # max_length=15

    # write_queries = False
    # execute_queries = True
    # write_latex = True

    # if os.path.exists("./performance_log.csv"):
    #     print(f"File ./performance_log.csv already exists. Deleting it.")
    #     os.remove("./performance_log.csv")

    # # Tests pour le pitch V2
    # pitch_values = [1.0, 2.0, 3.0]
    # test_name = "pitch"
    # for pitch_value in pitch_values:
    #     for length in range(1, max_length + 1):
    #         if write_queries:
    #             generate_queries_v2(test_name, sequences, pitch_value, 1.0, 0.0, length, False)
    #         if execute_queries:
    #             execute_queries_v2(test_name, sequences, pitch_value, 1.0, 0.0, length)

    # if execute_queries:
    #     save_csv(test_name)
    
    # if write_latex:
    #     try:
    #         process_and_generate_latex(test_name, pitch_values, max_length, nb_sequences)
    #     except Exception as e:
    #         print(f"An error occurred while processing {test_name}: {e}")

    # test_name = "pitch_transp"
    # for pitch_value in pitch_values:
    #     for length in range(1, max_length + 1):
    #         if write_queries:
    #             generate_queries_v2(test_name, sequences, pitch_value, 1.0, 0.0, length, True)
    #         if execute_queries:
    #             execute_queries_v2(test_name, sequences, pitch_value, 1.0, 0.0, length)

    # if execute_queries:
    #     save_csv(test_name)

    # if write_latex:
    #     try:
    #         process_and_generate_latex(test_name, pitch_values, max_length, nb_sequences)
    #     except Exception as e:
    #         print(f"An error occurred while processing {test_name}: {e}")

    # # Tests pour la durée V2
    # duration_values = [2.0, 4.0, 8.0]
    # test_name = "duration"

    # for duration_value in duration_values:
    #     for length in range(1, max_length + 1):
    #         if write_queries:
    #             generate_queries_v2(test_name, sequences, 0.0, duration_value, 0.0, length, False)
    #         if execute_queries:
    #             execute_queries_v2(test_name, sequences, 0.0, duration_value, 0.0, length)

    # if execute_queries:
    #     save_csv(test_name)
    
    # if write_latex:
    #     try:
    #         process_and_generate_latex(test_name, duration_values, max_length, nb_sequences)
    #     except Exception as e:
    #         print(f"An error occurred while processing {test_name}: {e}")


    # test_name = "duration_transp"
    # for duration_value in duration_values:
    #     for length in range(1, max_length + 1):
    #         if write_queries:
    #             generate_queries_v2(test_name, sequences, 0.0, duration_value, 0.0, length, True)
    #         if execute_queries:
    #             execute_queries_v2(test_name, sequences, 0.0, duration_value, 0.0, length)

    # if execute_queries:
    #     save_csv(test_name)

    # if write_latex:
    #     try:
    #         process_and_generate_latex(test_name, duration_values, max_length, nb_sequences)
    #     except Exception as e:
    #         print(f"An error occurred while processing {test_name}: {e}")

    # Tests pour le séquençage V2
    # gap_values = [0.25, 0.125, 0.0625]
    # gap_values = [0.25, 0.125]
    # test_name = "gap"

    # for gap_value in gap_values:
    #     for length in range(1, max_length + 1):
    #         if write_queries:
    #             generate_queries_v2(test_name, sequences, 0.0, 1.0, gap_value, length, False)
    #         if execute_queries:
    #             execute_queries_v2(test_name, sequences, 0.0, 1.0, gap_value, length)

    # if execute_queries:
    #     save_csv(test_name)

    # if write_latex:
    #     try:
    #         process_and_generate_latex(test_name, gap_values, max_length, nb_sequences)
    #     except Exception as e:
    #         print(f"An error occurred while processing {test_name}: {e}")

    # test_name = "gap_transp"
    # for gap_value in gap_values:
    #     for length in range(1, max_length + 1):
    #         if write_queries:
    #             generate_queries_v2(test_name, sequences, 0.0, 1.0, gap_value, length, True)
    #         if execute_queries:
    #             execute_queries_v2(test_name, sequences, 0.0, 1.0, gap_value, length)

    # if execute_queries:
    #     save_csv(test_name)

    # if write_latex:
    #     try:
    #         process_and_generate_latex(test_name, gap_values, max_length, nb_sequences)
    #     except Exception as e:
    #         print(f"An error occurred while processing {test_name}: {e}")

    # # Tests taille de base
    # test_name = f"db_size_6000"
    # if write_queries:
    #     generate_queries_v2("db_size", sequences, 1.0, 2.0, 0.0625, 6, False)
    # if execute_queries:
    #     execute_queries_v2("db_size", sequences, 1.0, 2.0, 0.0625, 6)

    # if execute_queries:
    #     save_csv(test_name)
    
    # if write_latex:
    #     try:
    #         generate_histogram_bar(f"./CSV/{test_name}_log.csv", test_name,"label")
    #     except Exception as e:
    #         print(f"An error occurred while processing {test_name}: {e}")

    # # Tests taille de base avec transposition
    # test_name = f"db_size_6000_t"
    # if write_queries:
    #     generate_queries_v2("db_size_t", sequences, 1.0, 2.0, 0.0625, 6, True)
    # if execute_queries:
    #     execute_queries_v2("db_size_t", sequences, 1.0, 2.0, 0.0625, 6)

    # if execute_queries:
    #     save_csv(test_name)
    
    # if write_latex:
    #     try:
    #         generate_histogram_bar(f"./CSV/{test_name}_log.csv", test_name,"label")
    #     except Exception as e:
    #         print(f"An error occurred while processing {test_name}: {e}")

if __name__ == "__main__":
    sequences = []
    contour_file="./tests/contours.txt"
    with open(contour_file, "r") as file:
        sequences = [line.strip() for line in file if line.strip()]
    nb_sequences=len(sequences)
    max_length=14

    # sequences = sequences[:3]
    # nb_sequences=3
    # max_length=4

    write_queries = True
    execute_queries = True
    write_latex = True

    if os.path.exists("./performance_log.csv") and execute_queries:
        print(f"File ./performance_log.csv already exists. Deleting it.")
        os.remove("./performance_log.csv")

    # ====================================================================== #
    # Tests longueurs contour (tous)
    chosen_attributes = [(True, True), (True, False), (False, True)]
    test_name = "contour_2"
    for with_interval, with_dur_ratio in chosen_attributes:
        for length in range(1, max_length + 1):
            if write_queries:
                generate_contour_queries(test_name, contour_file, with_interval, with_dur_ratio, length)
            if execute_queries:
                execute_queries_v2(test_name, sequences, length, f"{with_interval}_{with_dur_ratio}")

    if execute_queries:
        save_csv(test_name)
    
    if write_latex:
        try:
            process_and_generate_latex(test_name, chosen_attributes, max_length, nb_sequences)
        except Exception as e:
            print(f"An error occurred while processing {test_name}: {e}")

    # # ====================================================================== #
    # # Tests taille de base
    # test_name = f"contour_db_size_2000"
    # if write_queries:
    #     generate_contour_queries("contour_db_size", contour_file, True, True, 6)
    # if execute_queries:
    #     execute_queries_v2("contour_db_size", sequences, 6, "True_True")

    # if execute_queries:
    #     save_csv(test_name)
    
    # if write_latex:
    #     try:
    #         generate_histogram_bar(f"./CSV/{test_name}_log.csv", test_name,"label")
    #     except Exception as e:
    #         print(f"An error occurred while processing {test_name}: {e}")
