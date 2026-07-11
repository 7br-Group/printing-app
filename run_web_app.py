import os, sys, subprocess, atexit, threading, socket

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    _parent = os.path.dirname(BASE_DIR)
    if os.path.exists(os.path.join(_parent, 'printing_app.db')):
        BASE_DIR = _parent
    MEIPASS = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    MEIPASS = BASE_DIR

WA_PORT = 3000
APP_PORT = 5000
WA_SERVER_DIR = os.path.join(MEIPASS, 'whatsapp_server')
wa_process = None

os.environ.setdefault('WA_SERVER', f'http://localhost:{WA_PORT}')
os.environ.setdefault('DATABASE_PATH', os.path.join(BASE_DIR, 'printing_app.db'))
os.environ['WWEBJS_AUTH_PATH'] = os.path.join(BASE_DIR, '.wwebjs_auth')

sys.path.insert(0, MEIPASS)
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, 'web_app'))
os.environ['APP_ROOT'] = os.path.join(MEIPASS, 'web_app')


def start_whatsapp():
    global wa_process
    node_exe = os.path.join(WA_SERVER_DIR, 'node.exe')
    server_js = os.path.join(WA_SERVER_DIR, 'server.js')
    if not os.path.exists(node_exe) or not os.path.exists(server_js):
        return
    try:
        wa_process = subprocess.Popen(
            [node_exe, server_js],
            cwd=WA_SERVER_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        wa_process = None


def stop_whatsapp():
    global wa_process
    if wa_process is None:
        return
    try:
        wa_process.terminate()
        wa_process.wait(timeout=5)
    except Exception:
        try:
            wa_process.kill()
        except Exception:
            pass
    wa_process = None


atexit.register(stop_whatsapp)


def find_free_port(start=5000):
    port = start
    while port < 5100:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
        port += 1
    return start


from web_app.app import app


def start_flask():
    port = int(os.environ.get('PORT', find_free_port(APP_PORT)))
    os.environ['APP_PORT'] = str(port)
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    start_whatsapp()

    # Start Flask in a background thread
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    # Wait for Flask to be ready
    import time, urllib.request
    port = int(os.environ.get('APP_PORT', APP_PORT))
    for _ in range(30):
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/')
            break
        except Exception:
            time.sleep(0.5)

    # Open native window with pywebview
    import webview
    window = webview.create_window(
        title='نظام الإدارة',
        url=f'http://127.0.0.1:{port}',
        width=1200,
        height=800,
        resizable=True,
        fullscreen=False,
        confirm_close=False,
    )
    webview.start(gui=None, debug=False, http_server=False)
