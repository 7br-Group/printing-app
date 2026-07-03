#!/bin/bash
# Start both WhatsApp Node.js server and Flask web app

# Start WhatsApp server in background
cd whatsapp_server
node server.js &
NODE_PID=$!
cd ..

# Set WhatsApp server URL for Flask
export WA_SERVER=http://localhost:3000

# Start Flask web app
cd web_app
gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --workers 2 --timeout 120 &
FLASK_PID=$!

# Handle shutdown
trap "kill $NODE_PID $FLASK_PID 2>/dev/null" EXIT

wait
