"""
Mobile APK entry point: Flask backend + WhatsApp server + Android WebView.
"""
import os, sys, time, threading, subprocess, logging, shutil

logging.basicConfig(level=logging.INFO, format='[APP] %(message)s')
log = logging.getLogger('App')

# ── Paths ──
IS_ANDROID = 'ANDROID_PRIVATE' in os.environ
APK_DIR = os.environ.get('ANDROID_PRIVATE') or os.path.dirname(os.path.abspath(__file__))
DATA_DIR = APK_DIR
if IS_ANDROID:
    DATA_DIR = os.path.join(os.environ.get('EXTERNAL_STORAGE') or APK_DIR, 'PrintingApp')
    os.makedirs(DATA_DIR, exist_ok=True)

os.environ['FLASK_PORT'] = '5000'
os.environ['WA_SERVER'] = 'http://127.0.0.1:3000'

# ── Database: copy template to writable location ──
db_src = os.path.join(APK_DIR, 'printing_app.db')
db_dst = os.path.join(DATA_DIR, 'printing_app.db')
if IS_ANDROID:
    if not os.path.exists(db_dst) and os.path.exists(db_src):
        shutil.copy2(db_src, db_dst)
        log.info(f'DB copied: {db_src} -> {db_dst}')
else:
    db_dst = db_src if os.path.exists(db_src) else db_dst
os.environ['DATABASE_PATH'] = db_dst
log.info(f'DB: {os.environ["DATABASE_PATH"]}')

# ── Flask (import AFTER DB path is set) ──
sys.path.insert(0, APK_DIR)
try:
    from web_app.app import app as flask_app
    log.info('Flask app loaded from web_app')
except ImportError:
    sys.path.insert(0, os.path.join(APK_DIR, 'web_app'))
    from app import flask_app
    log.info('Flask app loaded fallback')

flask_ready = threading.Event()

def start_flask():
    flask_ready.set()
    log.info('Flask starting on 127.0.0.1:5000')
    flask_app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)

# ── WhatsApp server ──
whatsapp_proc = None
whatsapp_ready = threading.Event()

def start_whatsapp():
    global whatsapp_proc
    server_dir = os.path.join(APK_DIR, 'whatsapp_server')
    server_js = os.path.join(server_dir, 'server.js')

    # 1) pkg binary
    for binary in [
        os.path.join(server_dir, 'whatsapp-server'),
        os.path.join(server_dir, 'whatsapp-server-arm64'),
    ]:
        if os.path.exists(binary):
            try:
                os.chmod(binary, 0o755)
                env = os.environ.copy()
                log.info(f'Starting WhatsApp via {binary}')
                whatsapp_proc = subprocess.Popen(
                    [binary], cwd=server_dir, env=env,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                time.sleep(4)
                if whatsapp_proc.poll() is None:
                    whatsapp_ready.set()
                    log.info(f'WhatsApp started PID {whatsapp_proc.pid}')
                    return
                log.warning('pkg binary exited immediately')
            except Exception as e:
                log.warning(f'pkg binary failed: {e}')

    # 2) system node
    for node_cmd in [os.path.join(APK_DIR, 'node-arm64', 'bin', 'node'), 'node']:
        if node_cmd != 'node' and not os.path.exists(node_cmd):
            continue
        try:
            env = os.environ.copy()
            log.info(f'Starting WhatsApp via {node_cmd}')
            cmd = [node_cmd, server_js] if node_cmd != 'node' else ['node', server_js]
            whatsapp_proc = subprocess.Popen(
                cmd, cwd=server_dir, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            time.sleep(4)
            if whatsapp_proc.poll() is None:
                whatsapp_ready.set()
                log.info(f'WhatsApp started PID {whatsapp_proc.pid}')
                return
            log.warning(f'{node_cmd} exited immediately')
        except Exception as e:
            log.warning(f'{node_cmd} failed: {e}')

    log.warning('WhatsApp server not available — skipped')
    whatsapp_ready.set()

def whatsapp_watchdog():
    """Auto-restart WhatsApp if crashed."""
    global whatsapp_proc
    while whatsapp_proc is not None:
        time.sleep(10)
        if whatsapp_proc.poll() is not None:
            log.warning(f'WhatsApp crashed (code {whatsapp_proc.returncode}), restarting...')
            start_whatsapp()

# ── Android WebView ──
def launch_webview():
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
        settings.setMixedContentMode(0)

        # Back button support
        webview.setOnKeyListener(lambda v, keyCode, event: None)
        from jnius import PythonJavaClass, java_method
        class BackHandler(PythonJavaClass):
            __javainterfaces__ = ['android/view/View$OnKeyListener']
            @java_method('(Landroid/view/View;ILandroid/view/KeyEvent;)Z')
            def onKey(self, v, keyCode, event):
                if keyCode == 4 and event.getAction() == 0:  # KEYCODE_BACK
                    if webview.canGoBack():
                        webview.goBack()
                        return True
                    activity.finish()
                    return True
                return False
        webview.setOnKeyListener(BackHandler())

        # Error page
        class AppWebViewClient(WebViewClient):
            @java_method('(Landroid/webkit/WebView;Ljava/lang/String;Landroid/graphics/Bitmap;)V')
            def onPageStarted(self, view, url, favicon):
                pass
            @java_method('(Landroid/webkit/WebView;Ljava/lang/String;Landroid/graphics/Bitmap;)V')
            def onPageFinished(self, view, url):
                pass
            @java_method('(Landroid/webkit/WebView;ILjava/lang/String;Ljava/lang/String;)V')
            def onReceivedError(self, view, errorCode, desc, url):
                error_html = (
                    '<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8">'
                    '<meta name="viewport" content="width=device-width,initial-scale=1">'
                    '<style>body{font-family:sans-serif;display:flex;align-items:center;justify-content:center;'
                    'min-height:100vh;background:#0f172a;color:#fff;margin:0;padding:20px;text-align:center}'
                    'h1{font-size:1.4rem;margin-bottom:1rem}p{color:#94a3b8;line-height:1.8}</style>'
                    '</head><body><div>'
                    '<h1>⚠️ الخادم لم يبدأ بعد</h1>'
                    '<p>جاري تشغيل الخادم المحلي. تأكد من منح التطبيق صلاحية الإنترنت.<br>'
                    'إذا استمرت المشكلة، أعد تشغيل التطبيق.</p>'
                    '<button onclick="location.reload()" style="padding:12px 24px;background:#3b82f6;'
                    'color:#fff;border:none;border-radius:8px;font-size:16px">إعادة المحاولة</button>'
                    '</div></body></html>'
                )
                view.loadDataWithBaseURL(None, error_html, 'text/html', 'UTF-8', None)

        webview.setWebViewClient(AppWebViewClient())
        webview.loadUrl('http://127.0.0.1:5000')
        activity.setContentView(webview)
        log.info('WebView loaded')
    except Exception as e:
        log.error(f'WebView error: {e}')
        import traceback
        traceback.print_exc()

# ── Kivy App ──
from kivy.app import App
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.config import Config
Config.set('kivy', 'log_level', 'warning')

class PrintingApp(App):
    def build(self):
        self.label = Label(
            text='[size=48]🖨️[/size]\n\n[size=20]نظام إدارة المطبعة[/size]\n\n[size=16]جاري التشغيل...[/size]',
            font_size='16sp', halign='center', valign='middle', markup=True,
        )
        self.label.bind(size=self.label.setter('text_size'))
        self.label.color = (1, 1, 1, 1)
        return self.label

    def on_start(self):
        from kivy.core.window import Window
        Window.clearcolor = (0.06, 0.09, 0.16, 1)

        threading.Thread(target=start_flask, daemon=True).start()
        threading.Thread(target=start_whatsapp, daemon=True).start()
        if os.path.exists(os.path.join(APK_DIR, 'whatsapp_server', 'server.js')):
            threading.Thread(target=whatsapp_watchdog, daemon=True).start()

        start_time = time.time()
        launched = [False]

        def check(dt):
            if not flask_ready.is_set():
                Clock.schedule_once(check, 0.5)
                return
            if launched[0]:
                return
            launched[0] = True
            # Small delay then launch WebView
            Clock.schedule_once(lambda dt: launch_webview(), 0.5)

        def timeout(dt):
            if not launched[0]:
                launched[0] = True
                log.warning('Flask timeout, launching WebView anyway')
                launch_webview()

        Clock.schedule_once(check, 0.5)
        Clock.schedule_once(timeout, 15)

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
