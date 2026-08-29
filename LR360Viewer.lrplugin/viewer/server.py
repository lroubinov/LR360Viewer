import http.server
import json
import os
import re
import socketserver
import sys
import os
import threading
import webbrowser
import urllib.parse
import time
import tempfile
import traceback
import io
from pathlib import Path

IMAGE = Path(sys.argv[1]).resolve()
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    ROOT = Path(sys._MEIPASS).resolve()
else:
    ROOT = Path(__file__).parent.resolve()

LOG_PATH = Path(tempfile.gettempdir()) / "LR360Viewer-save.log"

def save_log(msg):
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + "  " + str(msg) + "\n")
    except Exception:
        pass


last_heartbeat = time.monotonic()
ever_connected = False
state_lock = threading.Lock()

def touch():
    global last_heartbeat, ever_connected
    with state_lock:
        last_heartbeat = time.monotonic()
        ever_connected = True

class ReusableTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

class Handler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        touch()
        save_log("POST received: " + self.path)
        try:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/save-perspective":
                self.send_error(404)
                return

            length_text = self.headers.get("Content-Length")
            save_log("Content-Length: " + str(length_text))
            if not length_text:
                raise RuntimeError("Missing Content-Length")
            n = int(length_text)
            if n <= 0:
                raise RuntimeError("Empty JPEG request")

            data = self.rfile.read(n)
            save_log("JPEG bytes received: " + str(len(data)))
            if len(data) != n:
                raise RuntimeError(f"Incomplete JPEG body: expected {n}, got {len(data)}")

            qs = urllib.parse.parse_qs(parsed.query)
            mode = re.sub(r"[^A-Za-z0-9_-]+", "_", qs.get("mode", ["Perspective"])[0])
            ratio = re.sub(r"[^A-Za-z0-9_-]+", "_", qs.get("ratio", ["Original"])[0].replace(":", "x"))
            fov = re.sub(r"[^0-9-]+", "", qs.get("fov", [""])[0])
            roll = re.sub(r"[^0-9-]+", "", qs.get("roll", ["0"])[0])
            size = re.sub(r"[^A-Za-z0-9_-]+", "_", qs.get("size", ["max"])[0])
            quality = re.sub(r"[^0-9]+", "", qs.get("q", ["98"])[0])
            out_format = qs.get("format", ["jpeg"])[0].lower()
            shot = re.sub(r"[^0-9]+", "", qs.get("shot", [""])[0])
            if out_format not in ("jpeg", "tiff"):
                out_format = "jpeg"

            sidecar = Path(str(IMAGE) + ".source")
            save_log("Sidecar: " + str(sidecar))
            if not sidecar.exists():
                raise RuntimeError("Source sidecar does not exist: " + str(sidecar))

            source = sidecar.read_text(encoding="utf-8").strip()
            save_log("Original source: " + source)
            if not source:
                raise RuntimeError("Original Lightroom source path is empty")

            source_path = Path(source)
            folder = source_path.parent
            stem = source_path.stem

            # Smart, readable filename. Default settings are omitted where useful.
            parts = [stem, mode, ratio]
            if fov:
                parts.append(f"FOV{fov}")
            if roll and roll != "0":
                parts.append(f"R{roll}")
            if size and size != "max":
                parts.append(size.upper())
            if quality and quality != "98" and out_format == "jpeg":
                parts.append(f"Q{quality}")
            if shot:
                try:
                    parts.append(f"S{int(shot):02d}")
                except Exception:
                    parts.append("S" + shot)

            smart_stem = "_".join(parts)
            ext = ".tif" if out_format == "tiff" else ".jpg"
            out = folder / f"{smart_stem}{ext}"
            i = 2
            while out.exists():
                out = folder / f"{smart_stem}_{i}{ext}"
                i += 1

            if out_format == "tiff":
                save_log("Converting PNG transport to TIFF: " + str(out))
                try:
                    from PIL import Image
                except Exception as e:
                    raise RuntimeError("TIFF export requires Pillow. Run Install-WebView2.cmd once. " + str(e))
                with Image.open(io.BytesIO(data)) as im:
                    im.convert("RGB").save(out, format="TIFF", compression="tiff_lzw")
                save_log("TIFF write complete")
            else:
                save_log("Writing JPEG: " + str(out))
                out.write_bytes(data)
                save_log("JPEG write complete")

            request_file = Path(str(IMAGE) + ".import")
            wait_started = time.monotonic()
            while request_file.exists() and time.monotonic() - wait_started < 15:
                time.sleep(0.1)
            request_file.write_text(str(out), encoding="utf-8")
            save_log("Import request written: " + str(request_file))

            payload = json.dumps({"ok": True, "path": str(out)}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(payload)
            self.wfile.flush()
            self.close_connection = True
            save_log("HTTP 200 sent successfully")

        except Exception as e:
            save_log("ERROR: " + repr(e))
            save_log(traceback.format_exc())
            msg = str(e).encode("utf-8", errors="replace")
            try:
                self.send_response(500)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(msg)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(msg)
                self.wfile.flush()
                self.close_connection = True
            except Exception as send_err:
                save_log("Could not send error response: " + repr(send_err))

    def do_GET(self):
        if self.path.startswith("/image"):
            try:
                data = IMAGE.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self.send_error(500, str(e))
            return

        if self.path.startswith("/heartbeat"):
            touch()
            self.send_response(204)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return

        if self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        return super().do_GET()

    def log_message(self, fmt, *args):
        # Keep console/log noise low in detached mode.
        pass

os.chdir(ROOT)

with ReusableTCPServer(("127.0.0.1", 0), Handler) as httpd:
    port = httpd.server_address[1]
    url = f"http://127.0.0.1:{port}/viewer.html"

    def watchdog():
        started = time.monotonic()
        while True:
            time.sleep(2)
            with state_lock:
                connected = ever_connected
                idle = time.monotonic() - last_heartbeat
            if not connected:
                if time.monotonic() - started > 45:
                    httpd.shutdown()
                    return
            elif idle > 10:
                httpd.shutdown()
                return

    threading.Thread(target=watchdog, daemon=True).start()
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    try:
        import webview
        save_log("Opening Microsoft Edge WebView2 window")
        webview.create_window(
            "LR 360 Viewer",
            url,
            width=1500,
            height=920,
            min_size=(900, 600),
            background_color="#111111"
        )
        webview.start(gui="edgechromium", debug=False)
    except Exception as e:
        save_log("WebView2 unavailable; browser fallback: " + repr(e))
        try:
            webbrowser.open_new_tab(url)
            while server_thread.is_alive():
                time.sleep(1)
        except Exception:
            pass
    finally:
        try:
            httpd.shutdown()
        except Exception:
            pass
