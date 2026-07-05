"""
Main entry point for Android APX.
Starts Flask backend + WhatsApp server, then shows WebView with the UI.
"""
import os, sys, time, json, socket, threading, subprocess, logging, shutil

logging.basicConfig(level=logging.INFO, format='[APP] %(message)s')
log = logging.getLogger('App')

# ──────────────────────────────────────────────
# Paths (Android APK vs dev)
# ──────────────────────────────────────────────
IS_ANDROID = 'ANDROID_PRIVATE' in os.environ
if IS_ANDROID:
    APK_DIR = os.environ['ANDROID_PRIVATE']
    ASSETS_DIR = os.path.join(APK_DIR, 'assets')
else:
    APK_DIR = os.path.dirname(os.path.abspath(__file__))

# Writable data directory
DATA_DIR = APK_DIR
if IS_ANDROID:
    DATA_DIR = os.path.join(os.environ.get('EXTERNAL_STORAGE', APK_DIR), 'PrintingApp')
    os.makedirs(DATA_DIR, exist_ok=True)

FLASK_PORT = 5000
os.environ['FLASK_PORT'] = str(FLASK_PORT)
os.environ['WA_SERVER'] = f'http://127.0.0.1:3000'

# ──────────────────────────────────────────────
# Database: copy from APK to writable location
# ──────────────────────────────────────────────
def setup_database():
    src = os.path.join(APK_DIR, 'printing_app.db')
    dst = os.path.join(DATA_DIR, 'printing_app.db')

    if IS_ANDROID and not os.path.exists(dst):
        if os.path.exists(src):
            shutil.copy2(src, dst)
            log.info(f'DB copied: {src} -> {dst}')
        else:
            log.warning('No template DB found, will create new')
    elif not os.path.exists(dst):
        # Dev mode: use original DB
        dst = src

    os.environ['DATABASE_PATH'] = dst
    log.info(f'Database: {os.environ["DATABASE_PATH"]}')
    return dst

# ──────────────────────────────────────────────
# Flask server thread
# ──────────────────────────────────────────────
flask_ready = threading.Event()

def start_flask():
    sys.path.insert(0, APK_DIR)
    try:
        # Try loading from web_app package
        from web_app.app import app
    except ImportError:
        # Fallback: load directly
        sys.path.insert(0, os.path.join(APK_DIR, 'web_app'))
        from app import app

    setup_database()
    flask_ready.set()
    log.info(f'Flask starting on 127.0.0.1:{FLASK_PORT}')
    app.run(host='127.0.0.1', port=FLASK_PORT, debug=False, use_reloader=False)

# ──────────────────────────────────────────────
# WhatsApp server (subprocess)
# ──────────────────────────────────────────────
whatsapp_proc = None
whatsapp_ready = threading.Event()

def start_whatsapp():
    global whatsapp_proc

    server_dir = os.path.join(APK_DIR, 'whatsapp_server')
    server_js = os.path.join(server_dir, 'server.js')

    # 1) Try pre-compiled binary (built with pkg)
    pkg_binary = os.path.join(server_dir, 'whatsapp-server')
    if os.path.exists(pkg_binary):
        try:
            os.chmod(pkg_binary, 0o755)
            env = os.environ.copy()
            env['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', '')
            log.info(f'Starting WhatsApp via pkg binary')
            whatsapp_proc = subprocess.Popen(
                [pkg_binary],
                cwd=server_dir, env=env,
                stdout=open(os.path.join(DATA_DIR, 'whatsapp.log'), 'w'),
                stderr=subprocess.STDOUT,
            )
            time.sleep(4)
            whatsapp_ready.set()
            log.info(f'WhatsApp pkg PID: {whatsapp_proc.pid}')
            return
        except Exception as e:
            log.warning(f'pkg binary failed: {e}')

    # 2) Try system Node.js
    for node_cmd in [os.path.join(APK_DIR, 'node-arm64', 'bin', 'node'), 'node']:
        if not os.path.exists(node_cmd) and node_cmd != 'node':
            continue
        try:
            env = os.environ.copy()
            env['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', '')
            log.info(f'Starting WhatsApp via {node_cmd}')
            whatsapp_proc = subprocess.Popen(
                [node_cmd, server_js] if node_cmd != 'node' else ['node', server_js],
                cwd=server_dir, env=env,
                stdout=open(os.path.join(DATA_DIR, 'whatsapp.log'), 'w'),
                stderr=subprocess.STDOUT,
            )
            time.sleep(4)
            whatsapp_ready.set()
            log.info(f'WhatsApp node PID: {whatsapp_proc.pid}')
            return
        except Exception as e:
            log.warning(f'Node {node_cmd} failed: {e}')

    log.warning('WhatsApp server not available — install nodejs or build pkg binary')
    whatsapp_ready.set()

# ──────────────────────────────────────────────
# WebView (Android native)
# ──────────────────────────────────────────────
def launch_webview():
    """Replace Kivy surface with Android WebView loading localhost:5000"""
    try:
        from jnius import autoclass
        WebView = autoclass('android.webkit.WebView')
        WebViewClient = autoclass('android.webkit.WebViewClient')
        WebSettings = autoclass('android.webkit.WebSettings')
        PythonActivity = autoclass('org.kivy.android.PythonActivity')

        activity = PythonActivity.mActivity
        webview = WebView(activity)

        settings = webview.getSettings()
        settings.setJavaScriptEnabled(True)
        settings.setDomStorageEnabled(True)
        settings.setLoadWithOverviewMode(True)
        settings.setUseWideViewPort(True)
        settings.setCacheMode(WebSettings.LOAD_NO_CACHE)
        settings.setAllowFileAccess(True)
        settings.setAllowContentAccess(True)
        settings.setMixedContentMode(0)  # Always allow

        webview.loadUrl(f'http://127.0.0.1:{FLASK_PORT}')
        activity.setContentView(webview)

        log.info('WebView loaded')
    except Exception as e:
        log.error(f'WebView error: {e}')
        import traceback
        traceback.print_exc()

# ──────────────────────────────────────────────
# Kivy App
# ──────────────────────────────────────────────
from kivy.app import App
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.config import Config
Config.set('kivy', 'log_level', 'warning')
Config.set('kivy', 'window_icon', '')

class PrintingApp(App):
    def build(self):
        self.label = Label(
            text='[size=48]🖨️[/size]\n\n[size=20]نظام إدارة المطبعة[/size]\n\n[size=16]جاري التشغيل...[/size]',
            font_size='16sp',
            halign='center',
            valign='middle',
            markup=True,
        )
        self.label.bind(size=self.label.setter('text_size'))
        self.label.color = (1, 1, 1, 1)
        return self.label

    def on_start(self):
        # Set dark background
        from kivy.core.window import Window
        Window.clearcolor = (0.06, 0.09, 0.16, 1)

        threading.Thread(target=start_flask, daemon=True).start()
        threading.Thread(target=start_whatsapp, daemon=True).start()

        def check_ready(dt):
            if flask_ready.is_set() and whatsapp_ready.is_set():
                Clock.schedule_once(lambda dt: launch_webview(), 0.5)
            else:
                Clock.schedule_once(check_ready, 0.5)

        Clock.schedule_once(check_ready, 1)

    def on_pause(self):
        return True

    def on_resume(self):
        pass

    def on_stop(self):
        global whatsapp_proc
        if whatsapp_proc:
            whatsapp_proc.terminate()
            try: whatsapp_proc.wait(timeout=3)
            except: pass
            whatsapp_proc = None

if __name__ == '__main__':
    PrintingApp().run()
