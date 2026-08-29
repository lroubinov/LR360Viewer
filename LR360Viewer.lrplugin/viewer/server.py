import http.server
import json
import os
import re
import socketserver
import sys
import threading
import webbrowser
import urllib.parse
import time
import tempfile
import traceback
import io
from pathlib import Path

IMAGE = Path(sys.argv[1]).resolve()
ARG_SESSION_FILE = None
if len(sys.argv) >= 4 and sys.argv[2] == "--session":
    ARG_SESSION_FILE = Path(sys.argv[3]).resolve()

SOURCE_SIDECAR = Path(str(IMAGE) + ".source")
DYNAMIC_PLUGIN_MODE = ARG_SESSION_FILE is not None
LEGACY_PLUGIN_MODE = not DYNAMIC_PLUGIN_MODE and SOURCE_SIDECAR.exists()
EXTERNAL_BRIDGE_MODE = not DYNAMIC_PLUGIN_MODE and not LEGACY_PLUGIN_MODE
SESSION_FILE = ARG_SESSION_FILE
BRIDGE_REQUEST_FILE = None

if EXTERNAL_BRIDGE_MODE:
    try:
        bridge_root = Path(tempfile.gettempdir()) / "LR360Viewer"
        bridge_root.mkdir(parents=True, exist_ok=True)
        SESSION_FILE = bridge_root / (
            f"external-{os.getpid()}-{time.time_ns()}.state"
        )
        BRIDGE_REQUEST_FILE = bridge_root / "external-bridge.request"
        SESSION_FILE.write_text(
            "\n".join([
                "1", str(IMAGE), str(IMAGE), "external_edit", "0", "", "0"
            ]),
            encoding="utf-8",
        )
        BRIDGE_REQUEST_FILE.write_text(str(SESSION_FILE), encoding="utf-8")
    except Exception:
        SESSION_FILE = None
        BRIDGE_REQUEST_FILE = None

DYNAMIC_SESSION_MODE = DYNAMIC_PLUGIN_MODE or (
    EXTERNAL_BRIDGE_MODE and SESSION_FILE is not None
)
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    ROOT = Path(sys._MEIPASS).resolve()
else:
    ROOT = Path(__file__).parent.resolve()

LOG_PATH = Path(tempfile.gettempdir()) / "LR360Viewer-save.log"

NATIVE_IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}
TIFF_TYPES = {".tif", ".tiff"}
session_state_lock = threading.Lock()
session_state_cache = {
    "revision": 1,
    "sourcePath": str(IMAGE),
    "displayPath": str(IMAGE),
    "displayKind": "source",
    "rendering": False,
    "message": "",
    "connected": DYNAMIC_PLUGIN_MODE or LEGACY_PLUGIN_MODE,
}

def session_aux(suffix):
    if not SESSION_FILE:
        return None
    return Path(str(SESSION_FILE) + suffix)

def read_dynamic_state():
    global session_state_cache
    if not DYNAMIC_SESSION_MODE:
        return dict(session_state_cache)
    try:
        lines = SESSION_FILE.read_text(encoding="utf-8").splitlines()
        if len(lines) < 5:
            raise ValueError("Incomplete Lightroom session state")
        state = {
            "revision": int(lines[0]),
            "sourcePath": lines[1],
            "displayPath": lines[2],
            "displayKind": lines[3] or "source",
            "rendering": lines[4] == "1",
            "message": lines[5] if len(lines) > 5 else "",
            "connected": lines[6] == "1" if len(lines) > 6 else DYNAMIC_PLUGIN_MODE,
        }
        if not state["sourcePath"] or not state["displayPath"]:
            raise ValueError("Missing Lightroom session path")
        with session_state_lock:
            session_state_cache = state
        return dict(state)
    except Exception:
        with session_state_lock:
            return dict(session_state_cache)

def current_state():
    if DYNAMIC_SESSION_MODE:
        state = read_dynamic_state()
        if EXTERNAL_BRIDGE_MODE and not state.get("connected"):
            state.update({
                "revision": "external:" + str(state.get("revision", 1)),
                "sourcePath": str(IMAGE),
                "displayPath": str(IMAGE),
                "displayKind": "external_edit",
                "rendering": False,
                "message": "",
            })
        return state
    if LEGACY_PLUGIN_MODE:
        try:
            source = SOURCE_SIDECAR.read_text(encoding="utf-8").strip()
        except Exception:
            source = ""
        return {
            "revision": 1,
            "sourcePath": source or str(IMAGE),
            "displayPath": str(IMAGE),
            "displayKind": "lightroom_render",
            "rendering": False,
            "message": "",
            "connected": True,
        }
    return dict(session_state_cache)

def plugin_save_mode(state=None):
    state = state or current_state()
    return (
        DYNAMIC_PLUGIN_MODE
        or LEGACY_PLUGIN_MODE
        or (EXTERNAL_BRIDGE_MODE and bool(state.get("connected")))
    )

def current_session_mode(state=None):
    state = state or current_state()
    if EXTERNAL_BRIDGE_MODE and state.get("connected"):
        return "external_live"

    return "plugin" if (DYNAMIC_PLUGIN_MODE or LEGACY_PLUGIN_MODE) else "external_editor"
def preview_info(path):
    path = Path(path)
    if not path.exists():
        return False, None, False, "The selected source file is unavailable."
    suffix = path.suffix.lower()
    if suffix in NATIVE_IMAGE_TYPES:
        return True, NATIVE_IMAGE_TYPES[suffix], False, ""
    if suffix in TIFF_TYPES:
        return True, "image/png", True, ""
    return (
        False,
        None,
        False,
        "This source format cannot be previewed directly. Apply Lightroom Edits to render it.",
    )

def touch_session_alive():
    alive = session_aux(".alive")
    if not alive:
        return
    try:
        alive.write_text(str(time.time()), encoding="ascii")
    except Exception:
        pass

def external_output_format():
    suffix = IMAGE.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        return "jpeg"
    if suffix in (".tif", ".tiff"):
        return "tiff"
    return None

def atomic_replace(out, writer):
    temp_out = out.with_name(
        f".{out.name}.lr360viewer-{os.getpid()}-{threading.get_ident()}.tmp"
    )
    try:
        writer(temp_out)
        os.replace(temp_out, out)
    finally:
        try:
            if temp_out.exists():
                temp_out.unlink()
        except Exception:
            pass

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

    touch_session_alive()
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
            if parsed.path == "/request-render":
                state = current_state()
                if not DYNAMIC_SESSION_MODE or not plugin_save_mode(state):
                    self.send_error(
                        409, "Lightroom Live Link is not connected"
                    )
                    return
                request_file = session_aux(".render-request")
                request_file.write_text(str(time.time()), encoding="ascii")
                payload = json.dumps({"ok": True}).encode("utf-8")
                self.send_response(202)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(payload)
                self.close_connection = True
                save_log("Lightroom render requested")
                return

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

            state = current_state()
            save_as_plugin = plugin_save_mode(state)
            if save_as_plugin:
                save_log("Session mode: " + current_session_mode(state))
                client_revision = qs.get("revision", [""])[0]
                if DYNAMIC_SESSION_MODE and client_revision:
                    try:
                        revision_matches = int(client_revision) == int(state["revision"])
                    except (TypeError, ValueError):
                        revision_matches = False
                    if not revision_matches:
                        raise RuntimeError(
                            "The active Lightroom photo changed during export. Try saving again."
                        )
                source = str(state.get("sourcePath", "")).strip()
                if LEGACY_PLUGIN_MODE:
                    save_log("Sidecar: " + str(SOURCE_SIDECAR))
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
            else:
                save_log("Session mode: external_editor")
                out_format = external_output_format()
                if not out_format:
                    raise RuntimeError(
                        "External Editor mode supports JPEG or TIFF files. "
                        "Configure Lightroom External Editing to use JPEG or TIFF."
                    )
                out = IMAGE
                save_log("External Editor target: " + str(out))

            if out_format == "tiff":
                save_log("Converting PNG transport to TIFF: " + str(out))
                try:
                    from PIL import Image
                except Exception as e:
                    raise RuntimeError("TIFF export requires Pillow. Run Install-WebView2.cmd once. " + str(e))
                def write_tiff(target):
                    with Image.open(io.BytesIO(data)) as im:
                        im.convert("RGB").save(
                            target, format="TIFF", compression="tiff_lzw"
                        )
                if save_as_plugin:
                    write_tiff(out)
                else:
                    atomic_replace(out, write_tiff)
                save_log("TIFF write complete")
            else:
                save_log("Writing JPEG: " + str(out))
                if save_as_plugin:
                    out.write_bytes(data)
                else:
                    atomic_replace(out, lambda target: target.write_bytes(data))
                save_log("JPEG write complete")

            if save_as_plugin:
                request_file = (
                    session_aux(".import")
                    if DYNAMIC_SESSION_MODE
                    else Path(str(IMAGE) + ".import")
                )
                wait_started = time.monotonic()
                while request_file.exists() and time.monotonic() - wait_started < 15:
                    time.sleep(0.1)
                request_text = source + "\n" + str(out) if DYNAMIC_SESSION_MODE else str(out)
                request_file.write_text(request_text, encoding="utf-8")
                save_log("Import request written: " + str(request_file))

            payload = json.dumps({
                "ok": True,
                "path": str(out),
                "sessionMode": current_session_mode(state),
            }).encode("utf-8")
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
        if self.path.startswith("/session"):
            touch()
            state = current_state()
            mode = current_session_mode(state)
            save_as_plugin = plugin_save_mode(state)
            display_path = Path(state["displayPath"])
            image_supported, _, _, preview_message = preview_info(display_path)
            input_format = "jpeg" if save_as_plugin else external_output_format()
            message = state.get("message") or preview_message
            payload = json.dumps({
                "mode": mode,
                "inputFormat": input_format,
                "supported": save_as_plugin or input_format is not None,
                "inputName": Path(state["sourcePath"]).name,
                "dynamicSwitching": DYNAMIC_PLUGIN_MODE or mode == "external_live",
                "revision": state["revision"],
                "rendering": state["rendering"],
                "displayKind": state["displayKind"],
                "imageSupported": image_supported,
                "message": message,
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if self.path.startswith("/image"):
            try:
                state = current_state()
                display_path = Path(state["displayPath"])
                supported, content_type, convert_tiff, message = preview_info(display_path)
                if not supported:
                    self.send_error(415, message)
                    return
                if convert_tiff:
                    try:
                        from PIL import Image
                    except Exception as e:
                        raise RuntimeError("TIFF preview requires Pillow. " + str(e))
                    with Image.open(display_path) as im:
                        preview = io.BytesIO()
                        im.convert("RGB").save(preview, format="PNG")
                        data = preview.getvalue()
                else:
                    data = display_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
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

touch_session_alive()
if BRIDGE_REQUEST_FILE and SESSION_FILE:
    BRIDGE_REQUEST_FILE.write_text(str(SESSION_FILE), encoding="utf-8")

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
        alive = session_aux(".alive")
        if alive:
            try:
                if alive.exists():
                    alive.unlink()
            except Exception:
                pass
        if EXTERNAL_BRIDGE_MODE:
            try:
                if (
                    BRIDGE_REQUEST_FILE
                    and BRIDGE_REQUEST_FILE.exists()
                    and BRIDGE_REQUEST_FILE.read_text(encoding="utf-8").strip()
                    == str(SESSION_FILE)
                ):
                    BRIDGE_REQUEST_FILE.unlink()
            except Exception:
                pass
            for bridge_file in (
                session_aux(".render-request"),
                session_aux(".import"),
                SESSION_FILE,
            ):
                try:
                    if bridge_file and bridge_file.exists():
                        bridge_file.unlink()
                except Exception:
                    pass
