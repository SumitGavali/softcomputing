"""
run_local.py
============
Unified Local Development Runner for Soft Computing EV Range Intelligence.
Launches both the FastAPI Backend and the Vite Frontend in a single terminal.

Features:
- Live, color-coded unified streaming logs ([BACKEND] in Cyan, [FRONTEND] in Emerald).
- Clean Ctrl+C shutdown: kills all child processes and process trees without leaving orphan ports.
- Excluded from Git tracking via .gitignore.

Usage:
  py -3.11 run_local.py
"""

import os
import sys
import subprocess
import threading
import time
import re
import signal
import socket

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Detect interactive terminal vs piped output
IS_TTY = sys.stdout.isatty()
ANSI_ESCAPE_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')

# ANSI Terminal Styling (enabled in interactive terminals, empty in non-TTY to avoid broken characters)
CYAN = "\033[96m" if IS_TTY else ""
GREEN = "\033[92m" if IS_TTY else ""
YELLOW = "\033[93m" if IS_TTY else ""
MAGENTA = "\033[95m" if IS_TTY else ""
RED = "\033[91m" if IS_TTY else ""
BOLD = "\033[1m" if IS_TTY else ""
RESET = "\033[0m" if IS_TTY else ""

# Enable ANSI colors on Windows PowerShell / CMD
if sys.platform == "win32" and IS_TTY:
    os.system("")

_HERE = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(_HERE, "module3", "frontend")
BACKEND_SCRIPT = os.path.join(_HERE, "module3", "run_module3.py")


def print_banner():
    sep = "=" * 74
    print(f"\n{BOLD}{CYAN}{sep}{RESET}")
    print(f"{BOLD}{CYAN}      RANGE INTELLIGENCE -- UNIFIED LOCAL DEVELOPMENT RUNNER       {RESET}")
    print(f"{BOLD}{CYAN}{sep}{RESET}")
    print(f"  {BOLD}* Frontend Dashboard :{RESET} {GREEN}http://localhost:3000{RESET}")
    print(f"  {BOLD}* FastAPI Backend API:{RESET} {GREEN}http://localhost:8000{RESET}")
    print(f"  {BOLD}* Map Provider Engine:{RESET} {GREEN}OpenStreetMap (Standard & Dark Cartography via Leaflet){RESET}")
    print(f"{CYAN}{sep}{RESET}")
    if IS_TTY:
        print(f"  {YELLOW}Press [Ctrl + C] in this terminal to stop both servers cleanly.{RESET}\n")
    else:
        print("  [TIP] To run in the interactive IDE Terminal with live Ctrl+C cancellation:")
        print("        Open the Terminal tab in your IDE (Ctrl + `) and type: .\\run.bat\n")


def stream_output(pipe, prefix, color):
    """Streams stdout/stderr line by line with clean formatting."""
    try:
        for line in iter(pipe.readline, ""):
            if line:
                cleaned = line.rstrip()
                # Replace CLI unicode symbols that may break on non-UTF8 Windows terminals
                cleaned = (
                    cleaned.replace("➜", "->")
                    .replace("✔", "[OK]")
                    .replace("ℹ", "[i]")
                    .replace("⚠", "[!]")
                    .replace("âžœ", "->")
                )
                if not IS_TTY:
                    cleaned = ANSI_ESCAPE_RE.sub("", cleaned)
                print(f"{color}[{prefix}]{RESET} {cleaned}", flush=True)
    except (ValueError, IOError):
        pass


def kill_process_tree(proc):
    """Kills process and all its children on Windows/Unix."""
    if not proc:
        return
    pid = proc.pid
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass


def main():
    print_banner()

    # Determine Python executable
    py_exec = sys.executable or "python"

    # 1. Start FastAPI Backend Process
    backend_cmd = [py_exec, "-u", BACKEND_SCRIPT, "--api", "--port", "8000"]
    print(f"{YELLOW}[RUNNER]{RESET} Starting FastAPI backend on port 8000...")
    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=_HERE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    backend_thread = threading.Thread(
        target=stream_output,
        args=(backend_proc.stdout, "BACKEND", CYAN),
        daemon=True,
    )
    backend_thread.start()

    # 2. Wait for FastAPI to finish loading ML models & bind port 8000
    print(f"{YELLOW}[RUNNER]{RESET} Waiting for backend to initialize and bind port 8000...")
    start_wait = time.time()
    backend_ready = False
    while time.time() - start_wait < 15:
        try:
            with socket.create_connection(("127.0.0.1", 8000), timeout=0.5):
                backend_ready = True
                break
        except (OSError, ConnectionRefusedError):
            time.sleep(0.3)

    if backend_ready:
        print(f"{GREEN}[RUNNER]{RESET} FastAPI backend is live on port 8000. Launching Vite frontend...\n")
    else:
        print(f"{YELLOW}[RUNNER]{RESET} Backend initialization in progress; starting Vite frontend...\n")

    # 3. Start Vite Frontend Process
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    node_modules_dir = os.path.join(FRONTEND_DIR, "node_modules")
    if not os.path.isdir(node_modules_dir):
        print(f"{YELLOW}[RUNNER]{RESET} Fresh clone detected: installing frontend packages (npm install)...")
        try:
            subprocess.run([npm_cmd, "install"], cwd=FRONTEND_DIR, check=True)
            print(f"{GREEN}[RUNNER]{RESET} Frontend packages installed successfully.\n")
        except Exception as e:
            print(f"{RED}[RUNNER] Failed to run npm install: {e}{RESET}")

    frontend_cmd = [npm_cmd, "run", "dev"]
    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=FRONTEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    frontend_thread = threading.Thread(
        target=stream_output,
        args=(frontend_proc.stdout, "FRONTEND", GREEN),
        daemon=True,
    )
    frontend_thread.start()

    # 3. Monitor and wait for Ctrl+C
    try:
        while True:
            # Check if any process exited unexpectedly
            if backend_proc.poll() is not None:
                print(f"\n{RED}[RUNNER] Backend process exited unexpectedly with code {backend_proc.returncode}{RESET}")
                break
            if frontend_proc.poll() is not None:
                print(f"\n{RED}[RUNNER] Frontend process exited unexpectedly with code {frontend_proc.returncode}{RESET}")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}[RUNNER] Received Ctrl+C -- gracefully shutting down all servers...{RESET}")
    finally:
        print(f"{YELLOW}[RUNNER] Terminating FastAPI backend (PID {backend_proc.pid})...{RESET}")
        kill_process_tree(backend_proc)
        print(f"{YELLOW}[RUNNER] Terminating Vite frontend (PID {frontend_proc.pid})...{RESET}")
        kill_process_tree(frontend_proc)
        print(f"{GREEN}[RUNNER] All servers successfully stopped. Goodbye!{RESET}\n")


if __name__ == "__main__":
    main()
