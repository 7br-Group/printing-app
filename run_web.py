import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['WA_SERVER'] = 'http://localhost:3000'
os.environ['DATABASE_PATH'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'printing_app.db')
from web_app.app import app
app.run(host='0.0.0.0', port=5000)
