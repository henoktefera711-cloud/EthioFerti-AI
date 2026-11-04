import os
import sys
import threading
import time

_server = None
_server_thread = None

def start_server(runtime_path):
    global _server, _server_thread

    if _server_thread and _server_thread.is_alive():
        return True

    runtime_path = os.path.abspath(runtime_path)
    os.chdir(runtime_path)

    if runtime_path not in sys.path:
        sys.path.insert(0, runtime_path)

    import uvicorn
    from app.main import app

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="warning",
        access_log=False
    )

    _server = uvicorn.Server(config)

    def run():
        _server.run()

    _server_thread = threading.Thread(target=run, daemon=True)
    _server_thread.start()

    for _ in range(50):
        if _server.started:
            return True
        time.sleep(0.2)

    raise RuntimeError("Local Python server did not start")

def stop_server():
    global _server
    if _server:
        _server.should_exit = True
