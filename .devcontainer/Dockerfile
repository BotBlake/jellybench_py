# Basis-Image mit Python 3.11
FROM mcr.microsoft.com/devcontainers/python:3.11

# Installiere System-Tools
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Installiere pipx
RUN python3 -m pip install --no-cache-dir pipx \
    && python3 -m pipx ensurepath

# Setze Benutzer-Umgebung
ENV PATH="/root/.local/bin:$PATH"

# Arbeitsverzeichnis
WORKDIR /workspace