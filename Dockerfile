# Utiliser une image officielle de Python
FROM python:3.10-slim

# Définir le répertoire de travail
WORKDIR /app

# Copier les dépendances
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code source
COPY . .

# Exposer le port (si ton API écoute sur 5000 par exemple)
EXPOSE 5000

# Lancer l'API
CMD ["python3", "-u", "api.py"]
