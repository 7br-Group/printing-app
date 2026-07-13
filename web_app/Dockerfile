FROM nikolaik/python-nodejs:python3.12-nodejs22

WORKDIR /app

# Copy Python requirements
COPY requirements-desktop.txt .
RUN pip install --no-cache-dir -r requirements-desktop.txt 2>/dev/null || true
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Node.js requirements
COPY whatsapp_server/package.json ./whatsapp_server/
RUN cd whatsapp_server && npm install

# Copy app code
COPY . .

# Expose ports
EXPOSE 5000 3000

# Start both servers
CMD python web_app/app.py & node whatsapp_server/server.js
