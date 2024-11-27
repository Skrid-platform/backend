import os
import subprocess
import time
import csv
import numpy as np
import glob
import random
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

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

def generate_length_based_queries(output_dir, sequences, param_name, param_values, max_lenght):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Itérer sur chaque valeur du paramètre
    for param_value in param_values:
        # Itérer sur les longueurs de pattern (de 1 à 20)
        for pattern_length in range(1, max_lenght + 1):
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
                command = (f"python3 main_parser.py write -o {output_file} -p {p_value} -f {f_value} -g {g_value} -a 0.0 {formatted_pattern}")

                print(f"Running command: {command}")
                subprocess.run(command, shell=True)

    print(f"Queries written to {output_dir}")

def execute_queries(dir_path, sequences, param_name, param_values, max_lenght):
    for param_value in param_values:
        for pattern_length in range(1, max_lenght + 1):
            for seq_index, sequence in enumerate(sequences):
                query_file = f"{param_name.strip('-')}_{param_value}_len_{pattern_length}_seq_{seq_index + 1}.cypher"
                command = f"python3 main_parser.py send -f -F {dir_path}{query_file}  > /dev/null"
                print(f"Running command: {command}")
                subprocess.run(command, shell=True)

def process_and_generate_latex(csv_file, nb_sequences, param_values, max_length, file_name):
    # Chargement des données depuis le CSV
    with open(csv_file, "r") as file:
        reader = csv.DictReader(file, delimiter=";")
        rows = list(reader)

    # Initialisation des structures pour les données
    total_times = {param: [[] for _ in range(max_length)] for param in param_values}
    execution_times = {param: [[] for _ in range(max_length)] for param in param_values}

    # Remplissage des données
    num_params = len(param_values)
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
    latex_code = generate_latex_curves(
        avg_total_times,
        labels="Param = {param}"
    )

    # Écrire le code LaTeX dans un fichier
    with open(f"./latex/{file_name}.tex", "w") as file:
        file.write(latex_code)

    print(f"LaTeX code written to './latex/{file_name}.tex")

    latex_code = generate_latex_curves(
        avg_execution_deltas,
        labels="Param = {param}"
    )

    # Écrire le code LaTeX dans un fichier
    with open(f"./latex/{file_name}_surplus.tex", "w") as file:
        file.write(latex_code)
    
    print(f"LaTeX code written to './latex/{file_name}_surplus.tex")


if __name__ == "__main__":
    sequences = [
        [
            [('b', 4), 8], [('c', 5), 8], [('d', 5), 8], [('d', 5), 8], [('d', 5), 8], 
            [('e', 5), 8], [('d', 5), 4], [('b', 4), 8], [('b', 4), 16], [('c', 5), 16], 
            [('d', 5), 8], [('d', 5), 8], [('d', 5), 8], [('e', 5), 8], [('d', 5), 4], 
            [('b', 4), 8], [('b', 4), 16], [('c', 5), 16], [('d', 5), 8], [('d', 5), 8]
        ],
        [
            [('c', 5), 2.6666666666666665], [('c', 5), 8.0], [('d', 5), 8.0], [('f', 5), 8.0], 
            [('e', 5), 2.6666666666666665], [('d', 5), 8.0], [('c', 5), 4.0], [('a', 4), 8.0], 
            [('a', 4), 8.0], [('a', 4), 8.0], [('e', 5), 8.0], [('e', 5), 8.0], [('d', 5), 8.0], 
            [('c', 5), 2.6666666666666665], [('c', 5), 8.0], [('d', 5), 8.0], [('f', 5), 8.0], 
            [('e', 5), 2.6666666666666665], [('d', 5), 8.0], [('c', 5), 8.0]
        ],
        [
            [('a', 4), 4.0], [('a', 4), 8.0], [('c', 5), 2.6666666666666665], [('c', 5), 2.6666666666666665], 
            [('b', 4), 2.6666666666666665], [('c', 5), 4.0], [('b', 4), 8.0], [('a', 4), 4.0], 
            [('b', 4), 8.0], [('c', 5), 4.0], [('b', 4), 8.0], [('a', 4), 4.0], [('g', 4), 8.0], 
            [('a', 4), 4.0], [('a', 4), 8.0], [('c', 5), 2.6666666666666665], [('c', 5), 2.6666666666666665], 
            [('b', 4), 4.0], [('b', 4), 8.0], [('a', 4), 4.0]
        ],
        [
            [('b', 4), 8.0], [('c', 5), 8.0], [('d', 5), 8.0], [('d', 5), 8.0], [('c', 5), 8.0], 
            [('b', 4), 8.0], [('a', 4), 8.0], [('b', 4), 8.0], [('c', 5), 8.0], [('b', 4), 4.0], 
            [('g', 4), 8.0], [('b', 4), 8.0], [('c', 5), 8.0], [('d', 5), 8.0], [('d', 5), 8.0], 
            [('c', 5), 8.0], [('b', 4), 8.0], [('a', 4), 8.0], [('g', 4), 8.0], [('a', 4), 8.0]
        ],
        [
            [('a', 4), 4.0], [('b', 4), 8.0], [('b', 4), 4.0], [('a', 4), 8.0], [('a', 4), 2.6666666666666665], 
            [('g', 4), 4.0], [('b', 4), 8.0], [('a', 4), 4.0], [('g', 4), 8.0], [('f', 4), 4.0], 
            [('g', 4), 8.0], [('a', 4), 2.6666666666666665], [('g', 4), 8.0], [('a', 4), 8.0], 
            [('b', 4), 8.0], [('b', 4), 4.0], [('a', 4), 8.0], [('a', 4), 8.0], [('g', 4), 8.0], [('a', 4), 8.0]
        ],
        [
            [('a', 4), 5.333333333333333], [('b', 4), 16.0], [('c', 5), 8.0], [('c', 5), 8.0], 
            [('b', 4), 8.0], [('a', 4), 8.0], [('a', 4), 8.0], [('g', 4), 8.0], [('a', 4), 5.333333333333333], 
            [('b', 4), 16.0], [('c', 5), 8.0], [('c', 5), 8.0], [('b', 4), 8.0], [('b', 4), 8.0], 
            [('a', 4), 4.0], [('c', 5), 5.333333333333333], [('c', 5), 16.0], [('c', 5), 8.0], [('e', 5), 8.0], [('d', 5), 8.0]
        ],
        [
            [('d', 5), 4.0], [('d', 5), 8.0], [('e', 5), 8.0], [('c', 5), 4.0], [('d', 5), 8.0], 
            [('e', 5), 8.0], [('f', 5), 8.0], [('e', 5), 8.0], [('d', 5), 4.0], [('e', 5), 2.6666666666666665], 
            [('b', 4), 16.0], [('c', 5), 16.0], [('d', 5), 4.0], [('d', 5), 8.0], [('e', 5), 8.0], 
            [('c', 5), 4.0], [('d', 5), 8.0], [('e', 5), 8.0], [('e', 5), 8.0], [('a', 4), 8.0]
        ],
        [
            [('a', 4), 8.0], [('b', 4), 8.0], [('c', 5), 8.0], [('b', 4), 8.0], [('c', 5), 8.0], 
            [('d', 5), 8.0], [('c', 5), 8.0], [('b', 4), 4.0], [('r', None), 8.0], [('a', 4), 8.0], 
            [('b', 4), 8.0], [('c', 5), 8.0], [('b', 4), 8.0], [('c', 5), 8.0], [('d', 5), 8.0], 
            [('c', 5), 8.0], [('b', 4), 4.0], [('r', None), 8.0], [('e', 4), 8.0], [('a', 4), 8.0]
        ],
        [
            [('e', 5), 8.0], [('e', 5), 8.0], [('e', 5), 8.0], [('c', 5), 4.0], [('c', 5), 8.0], 
            [('d', 5), 8.0], [('d', 5), 8.0], [('d', 5), 8.0], [('e', 5), 4.0], [('d', 5), 8.0], 
            [('e', 5), 8.0], [('e', 5), 8.0], [('c', 5), 8.0], [('c', 5), 8.0], [('d', 5), 8.0], 
            [('d', 5), 8.0], [('e', 5), 4.0], [('e', 5), 8.0], [('e', 5), 8.0], [('c', 5), 5.333333333333333]
        ],
        [
            [('c', 5), 8.0], [('b', 4), 8.0], [('a', 4), 8.0], [('b', 4), 8.0], [('c', 5), 8.0], 
            [('c', 5), 8.0], [('d', 5), 8.0], [('e', 5), 8.0], [('d', 5), 8.0], [('e', 5), 8.0], 
            [('c', 5), 8.0], [('a', 4), 4.0], [('g', 4), 8.0], [('g', 4), 8.0], [('c', 5), 8.0], 
            [('b', 4), 8.0], [('a', 4), 8.0], [('b', 4), 8.0], [('c', 5), 4.0], [('c', 5), 8.0]
        ]
    ]

    nb_sequences=len(sequences)
    max_length=15

    # # Tests pour le pitch
    # param_values=[0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    # param_name = "-p"
    # dir_path = f"./test_queries/{param_name}_flex/"

    # generate_length_based_queries(dir_path, sequences, param_name, param_values, max_length)

    # execute_queries(dir_path, sequences, param_name, param_values, max_length)

    # command = f"mv ./performance_log.csv ./CSV/{param_name}_log.csv"
    # print(f"Running command: {command}")
    # subprocess.run(command, shell=True)

    # process_and_generate_latex(f"./CSV/{param_name}_log.csv", nb_sequences, param_values, max_length, param_name)

    # # Tests pour le duration
    # param_values=[2.0, 4.0, 8.0]
    # param_name = "-f"
    # dir_path = f"./test_queries/{param_name}_flex/"

    # generate_length_based_queries(dir_path, sequences, param_name, param_values, max_length)

    # execute_queries(dir_path, sequences, param_name, param_values, max_length)

    # command = f"mv ./performance_log.csv ./CSV/{param_name}_log.csv"
    # print(f"Running command: {command}")
    # subprocess.run(command, shell=True)

    # process_and_generate_latex(f"./CSV/{param_name}_log.csv", nb_sequences, param_values, max_length, param_name)

    # Tests pour le gap
    param_values=[0.5]
    param_name = "-g"
    dir_path = f"./test_queries/{param_name}_flex/"

    # generate_length_based_queries(dir_path, sequences, param_name, param_values, max_length)

    execute_queries(dir_path, sequences, param_name, param_values, max_length)

    command = f"mv ./performance_log.csv ./CSV/{param_name}_2_log.csv"
    print(f"Running command: {command}")
    subprocess.run(command, shell=True)

    process_and_generate_latex(f"./CSV/{param_name}_2_log.csv", nb_sequences, param_values, max_length, param_name)