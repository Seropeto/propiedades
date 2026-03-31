FROM python:3.11-slim

# Instalar Node.js, Chromium y dependencias del sistema
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    chromium \
    chromium-driver \
    fonts-liberation \
    fonts-dejavu-core \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2t64 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

# Instalar dependencias Python
COPY listapro/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar dependencias Node.js para Remotion
COPY listapro/video/package.json ./video/
RUN cd video && npm install

# Copiar código de la aplicación
COPY listapro/ .

# Crear directorios persistentes
RUN mkdir -p uploads generated

# Variables de entorno para Chromium (usado por Remotion)
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true

# Puerto de la aplicación
EXPOSE 8000

# Comando de inicio
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
