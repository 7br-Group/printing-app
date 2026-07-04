import sys, os
import socket

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

# Find the database in multiple locations
db_candidates = [
    os.environ.get('DATABASE_PATH'),
    os.path.join(base_dir, 'printing_app.db'),
    os.path.join(base_dir, 'dist', 'printing_app.db'),
    os.path.join(os.path.dirname(base_dir), 'printing_app.db'),
]
db_path = next((p for p in db_candidates if p and os.path.exists(p)), db_candidates[1])
os.environ['DATABASE_PATH'] = db_path

os.environ['WA_SERVER'] = os.environ.get('WA_SERVER', 'http://localhost:3000')

from web_app.app import app

# Get actual LAN IP
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 80))
    lan_ip = s.getsockname()[0]
    s.close()
except:
    lan_ip = '127.0.0.1'

port = int(os.environ.get('PORT', 5000))
print(f'Server running on:')
print(f'  Local:   http://127.0.0.1:{port}')
print(f'  Network: http://{lan_ip}:{port}')
print(f'  Password: admin')
app.run(host='0.0.0.0', port=port, debug=False)
