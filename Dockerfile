FROM nikolaik/python-nodejs:python3.12-nodejs22

WORKDIR /app

# Copy Python requirements
COPY requirements-desktop.txt web_app/requirements.txt ./
RUN pip install --no-cache-dir -r requirements-desktop.txt 2>/dev/null || true
RUN pip install --no-cache-dir flask requests gunicorn

# Copy Node.js server
COPY whatsapp_server/package.json ./whatsapp_server/
RUN cd whatsapp_server && npm install

# Copy everything
COPY . .

# Expose port
EXPOSE 10000

# Start both services
CMD cd whatsapp_server && node server.js --port 3000 & cd /app && gunicorn web_app.app:app --bind 0.0.0.0:${PORT:-10000} --workers 2 --timeout 120
