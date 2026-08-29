import os
import sys
import time
import threading


def _apply_windows_identity():
    if os.name != "nt":
        return

    try:
        import ctypes
        from ctypes import wintypes

        shell32 = ctypes.windll.shell32
        user32 = ctypes.windll.user32

        # Give Windows a stable application identity instead of inheriting Python's.
        try:
            shell32.SetCurrentProcessExplicitAppUserModelID("LR360Viewer.App")
        except Exception:
            pass

        root = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        icon_path = os.path.join(root, "LR360Viewer.ico")
        if not os.path.exists(icon_path):
            return

        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1

        user32.LoadImageW.argtypes = [
            wintypes.HINSTANCE,
            wintypes.LPCWSTR,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        user32.LoadImageW.restype = wintypes.HANDLE
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.FindWindowW.restype = wintypes.HWND
        user32.SendMessageW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        # ctypes.wintypes has no LRESULT alias in standard Python.
        user32.SendMessageW.restype = ctypes.c_ssize_t

        big_icon = user32.LoadImageW(
            None, icon_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE
        )
        small_icon = user32.LoadImageW(
            None, icon_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE
        )

        # pywebview creates the HWND after Python startup, so wait for it.
        for _ in range(400):
            hwnd = user32.FindWindowW(None, "LR 360 Viewer")
            if hwnd:
                if big_icon:
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, big_icon)
                if small_icon:
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, small_icon)
                return
            time.sleep(0.05)
    except Exception:
        pass


if os.name == "nt":
    threading.Thread(target=_apply_windows_identity, daemon=True).start()
