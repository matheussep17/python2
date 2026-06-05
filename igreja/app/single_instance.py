import socket
import sys


_LOCK_HANDLE = None
_LOCK_SOCKET = None
_MUTEX_NAME = "Local\\MediaSuiteIgrejaSingleInstance"
_FALLBACK_PORT = 54321


def acquire_single_instance_lock() -> bool:
    """Return False when another instance of the app is already running."""
    global _LOCK_HANDLE, _LOCK_SOCKET

    if _LOCK_HANDLE is not None or _LOCK_SOCKET is not None:
        return True

    if sys.platform.startswith("win"):
        return _acquire_windows_mutex()

    return _acquire_socket_lock()


def _acquire_windows_mutex() -> bool:
    global _LOCK_HANDLE

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.CreateMutexW.restype = wintypes.HANDLE

    handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if not handle:
        return True

    if ctypes.get_last_error() == 183:
        kernel32.CloseHandle(handle)
        return False

    _LOCK_HANDLE = handle
    return True


def _acquire_socket_lock() -> bool:
    global _LOCK_SOCKET

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", _FALLBACK_PORT))
    except OSError:
        sock.close()
        return False

    _LOCK_SOCKET = sock
    return True
