#!/usr/bin/env python3
"""
Kino — Cross-Platform Executor
================================
A single script that works on macOS, Linux, and Windows to set up,
run the data pipeline, and launch the Kino web application.

Usage:
    python run_kino.py --all        # Full pipeline + web server
    python run_kino.py --serve      # Start web server only
    python run_kino.py --spark      # Run Spark processor only
    python run_kino.py --posters    # Run poster fetcher only
    python run_kino.py --hbase      # Seed HBase only
    python run_kino.py --install    # Install dependencies only
    python run_kino.py --stop       # Show how to stop all services
    python run_kino.py --status     # Check which services are running

Exit:
    Press Ctrl+C at any time to gracefully shut down.
"""

import os
import sys
import platform
import subprocess
import signal
import argparse
import shutil
import time


# ============================================================
# CONSTANTS
# ============================================================

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
VENV_DIR = os.path.join(PROJECT_ROOT, ".venv")
REQUIREMENTS = os.path.join(PROJECT_ROOT, "requirements.txt")

SYSTEM = platform.system()  # "Darwin", "Linux", "Windows"
IS_WINDOWS = SYSTEM == "Windows"
IS_MAC = SYSTEM == "Darwin"
IS_LINUX = SYSTEM == "Linux"

# Colors for terminal output (disabled on Windows CMD)
if IS_WINDOWS:
    # Enable ANSI on Windows 10+
    try:
        os.system("")  # enables ANSI escape codes on Windows
    except Exception:
        pass

BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"
DIM = "\033[2m"


# ============================================================
# UTILITIES
# ============================================================

def banner():
    """Print the Kino startup banner."""
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════════════╗
║          🎬  KINO — Cross-Platform Executor  🎬          ║
║       Big Data Movie Recommendation System               ║
╚══════════════════════════════════════════════════════════╝{RESET}
{DIM}  OS: {SYSTEM} ({platform.machine()})
  Python: {platform.python_version()}
  Project: {PROJECT_ROOT}{RESET}
""")


def info(msg):
    print(f"  {GREEN}✓{RESET} {msg}")


def warn(msg):
    print(f"  {YELLOW}⚠{RESET} {msg}")


def error(msg):
    print(f"  {RED}✗{RESET} {msg}")


def section(title):
    print(f"\n{BOLD}{CYAN}{'─' * 60}{RESET}")
    print(f"  {BOLD}{title}{RESET}")
    print(f"{CYAN}{'─' * 60}{RESET}\n")


def get_python():
    """Get the Python executable path (inside venv if it exists)."""
    if IS_WINDOWS:
        venv_python = os.path.join(VENV_DIR, "Scripts", "python.exe")
    else:
        venv_python = os.path.join(VENV_DIR, "bin", "python3")
        if not os.path.exists(venv_python):
            venv_python = os.path.join(VENV_DIR, "bin", "python")

    if os.path.exists(venv_python):
        return venv_python

    return sys.executable


def get_pip():
    """Get the pip executable path (inside venv if it exists)."""
    if IS_WINDOWS:
        venv_pip = os.path.join(VENV_DIR, "Scripts", "pip.exe")
    else:
        venv_pip = os.path.join(VENV_DIR, "bin", "pip")

    if os.path.exists(venv_pip):
        return venv_pip

    return shutil.which("pip3") or shutil.which("pip") or "pip"


def run(cmd, description=None, check=True, cwd=None):
    """Run a command and stream its output."""
    if description:
        info(f"{description}...")

    if cwd is None:
        cwd = PROJECT_ROOT

    try:
        process = subprocess.run(
            cmd,
            cwd=cwd,
            check=check,
            shell=isinstance(cmd, str),
        )
        return process.returncode == 0
    except subprocess.CalledProcessError as e:
        error(f"Command failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        error(f"Command not found: {cmd[0] if isinstance(cmd, list) else cmd}")
        return False


def check_java():
    """Check if Java is available."""
    java_path = shutil.which("java")
    if java_path:
        try:
            result = subprocess.run(
                ["java", "-version"],
                capture_output=True,
                text=True
            )
            version_line = result.stderr.split("\n")[0] if result.stderr else "unknown"
            info(f"Java found: {version_line}")
            return True
        except Exception:
            pass

    warn("Java not found! Java JDK is required for PySpark.")
    if IS_MAC:
        warn("  Install with: brew install openjdk@17")
    elif IS_LINUX:
        warn("  Install with: sudo apt install openjdk-17-jdk")
    elif IS_WINDOWS:
        warn("  Download from: https://adoptium.net/")
    return False


def check_port(port):
    """Check if a port is in use."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


# ============================================================
# CORE ACTIONS
# ============================================================

def do_install():
    """Create virtual environment and install dependencies."""
    section("Installing Dependencies")

    # Create venv if it doesn't exist
    if not os.path.exists(VENV_DIR):
        info("Creating virtual environment...")
        run([sys.executable, "-m", "venv", VENV_DIR])
        info(f"Virtual environment created at {VENV_DIR}")
    else:
        info("Virtual environment already exists")

    # Install requirements
    pip = get_pip()
    info("Installing Python packages...")
    run([pip, "install", "-r", REQUIREMENTS])
    info("All dependencies installed!")


def do_spark():
    """Run the Spark data processor."""
    section("Running PySpark Data Processor")

    # Check prerequisites
    if not check_java():
        error("Cannot run Spark without Java. Please install Java JDK first.")
        return False

    rating_csv = os.path.join(PROJECT_ROOT, "rating.csv")
    movie_csv = os.path.join(PROJECT_ROOT, "movie.csv")

    if not os.path.exists(rating_csv):
        error(f"rating.csv not found at {rating_csv}")
        warn("Download the MovieLens 20M dataset from:")
        warn("  https://grouplens.org/datasets/movielens/20m/")
        warn("Place rating.csv in the project root directory.")
        return False

    if not os.path.exists(movie_csv):
        error(f"movie.csv not found at {movie_csv}")
        return False

    python = get_python()
    spark_script = os.path.join(PROJECT_ROOT, "spark", "spark_processor.py")

    info(f"Processing 20M ratings with PySpark...")
    info(f"This may take 2–5 minutes depending on your hardware.\n")

    return run([python, spark_script], check=False)


def do_posters():
    """Run the TMDb poster fetcher."""
    section("Fetching Movie Posters from TMDb")

    ratings_csv = os.path.join(DATA_DIR, "movies_with_ratings.csv")
    link_csv = os.path.join(PROJECT_ROOT, "link.csv")

    if not os.path.exists(ratings_csv):
        error(f"movies_with_ratings.csv not found.")
        warn("Run the Spark processor first: python run_kino.py --spark")
        return False

    if not os.path.exists(link_csv):
        error(f"link.csv not found at {link_csv}")
        warn("Download the MovieLens 20M dataset and place link.csv in the project root.")
        return False

    # Check for .env file
    env_file = os.path.join(PROJECT_ROOT, ".env")
    if not os.path.exists(env_file):
        warn(".env file not found. Creating a template...")
        warn("You need a TMDb API key. Get one free at:")
        warn("  https://www.themoviedb.org/settings/api")
        error("Cannot fetch posters without a TMDb API key.")
        return False

    python = get_python()
    script = os.path.join(PROJECT_ROOT, "scripts", "fetch_posters.py")

    info("Fetching posters using 30 concurrent threads...")
    info("This may take 5–15 minutes depending on your internet speed.\n")

    return run([python, script], check=False)


def do_hbase():
    """Seed the HBase database."""
    section("Seeding HBase Database")

    posters_csv = os.path.join(DATA_DIR, "movies_with_posters.csv")
    if not os.path.exists(posters_csv):
        error("movies_with_posters.csv not found.")
        warn("Run the full pipeline first: python run_kino.py --all")
        return False

    if not check_port(9090):
        warn("HBase Thrift Server does not appear to be running on port 9090.")
        warn("Start HBase first:")
        if IS_MAC:
            warn("  start-hbase.sh && hbase thrift start -p 9090 &")
        elif IS_LINUX:
            warn("  ./bin/start-hbase.sh && ./bin/hbase thrift start -p 9090 &")
        elif IS_WINDOWS:
            warn("  docker run -d --name hbase-kino -p 9090:9090 harisekhon/hbase")
        error("Skipping HBase seeding.")
        return False

    python = get_python()
    script = os.path.join(PROJECT_ROOT, "scripts", "setup_hbase.py")

    info("Creating HBase table and seeding data...\n")
    return run([python, script], check=False)


def do_serve():
    """Launch the FastAPI web server."""
    section("Starting Kino Web Server")

    posters_csv = os.path.join(DATA_DIR, "movies_with_posters.csv")
    ratings_csv = os.path.join(DATA_DIR, "movies_with_ratings.csv")

    if not os.path.exists(posters_csv) and not os.path.exists(ratings_csv):
        error("No data files found!")
        warn("You need at least one of:")
        warn(f"  {posters_csv}")
        warn(f"  {ratings_csv}")
        warn("Run the pipeline first: python run_kino.py --all")
        return False

    if check_port(8000):
        warn("Port 8000 is already in use!")
        warn("Stop the existing process or use a different port.")
        return False

    python = get_python()
    app_script = os.path.join(PROJECT_ROOT, "app.py")

    info(f"Launching FastAPI server on http://localhost:8000")
    info(f"Press Ctrl+C to stop the server.\n")

    print(f"{DIM}{'─' * 60}{RESET}\n")

    try:
        process = subprocess.Popen(
            [python, app_script],
            cwd=PROJECT_ROOT,
        )
        process.wait()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Shutting down Kino server...{RESET}")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        info("Server stopped.")
        return True

    return True


def do_status():
    """Check which services are currently running."""
    section("Service Status")

    services = [
        ("FastAPI Web Server", 8000),
        ("HBase Thrift Server", 9090),
        ("HBase Master UI", 16010),
        ("Zookeeper", 2181),
    ]

    for name, port in services:
        if check_port(port):
            info(f"{name} — {GREEN}RUNNING{RESET} (port {port})")
        else:
            print(f"  {DIM}○ {name} — not running (port {port}){RESET}")

    # Check data files
    print()
    data_files = [
        ("movies_with_posters.csv", os.path.join(DATA_DIR, "movies_with_posters.csv")),
        ("movies_with_ratings.csv", os.path.join(DATA_DIR, "movies_with_ratings.csv")),
        ("rating.csv (raw)", os.path.join(PROJECT_ROOT, "rating.csv")),
        ("movie.csv (raw)", os.path.join(PROJECT_ROOT, "movie.csv")),
        ("link.csv (raw)", os.path.join(PROJECT_ROOT, "link.csv")),
        (".env (API key)", os.path.join(PROJECT_ROOT, ".env")),
    ]

    print(f"  {BOLD}Data Files:{RESET}")
    for name, path in data_files:
        if os.path.exists(path):
            size_mb = os.path.getsize(path) / (1024 * 1024)
            info(f"{name} — {GREEN}found{RESET} ({size_mb:.1f} MB)")
        else:
            print(f"  {DIM}○ {name} — not found{RESET}")


def do_stop_info():
    """Print instructions on how to stop all services."""
    section("How to Stop Everything")

    print(f"""
  {BOLD}1. Stop the Web Server:{RESET}
     Press Ctrl+C in the terminal running the server.

  {BOLD}2. Stop HBase Thrift Server:{RESET}""")

    if IS_WINDOWS:
        print(f"""     docker stop hbase-kino
     docker rm hbase-kino""")
    else:
        print(f"""     # Find the process:
     lsof -i :9090
     # Kill it:
     kill <PID>""")

    print(f"""
  {BOLD}3. Stop HBase:{RESET}""")

    if IS_WINDOWS:
        print(f"     (Handled by Docker — see step 2)")
    elif IS_MAC:
        print(f"     stop-hbase.sh")
    else:
        print(f"     ./bin/stop-hbase.sh")

    print(f"""
  {BOLD}4. Deactivate Virtual Environment:{RESET}
     deactivate

  {BOLD}5. Verify all stopped:{RESET}""")

    if IS_WINDOWS:
        print(f"     netstat -ano | findstr :8000")
        print(f"     netstat -ano | findstr :9090")
    else:
        print(f"     lsof -i :8000   # Should return nothing")
        print(f"     lsof -i :9090   # Should return nothing")

    print()


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Kino — Cross-Platform Executor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_kino.py --all          Run full pipeline + web server
  python run_kino.py --serve        Start web server only (data must exist)
  python run_kino.py --spark        Run Spark processor only
  python run_kino.py --posters      Run poster fetcher only
  python run_kino.py --hbase        Seed HBase only
  python run_kino.py --install      Install dependencies only
  python run_kino.py --status       Check service status
  python run_kino.py --stop         Show shutdown instructions

Press Ctrl+C at any time to exit gracefully.
        """
    )

    parser.add_argument("--all", action="store_true",
                        help="Run full pipeline (install + spark + posters + hbase + serve)")
    parser.add_argument("--serve", action="store_true",
                        help="Start the web server only")
    parser.add_argument("--spark", action="store_true",
                        help="Run the PySpark data processor")
    parser.add_argument("--posters", action="store_true",
                        help="Run the TMDb poster fetcher")
    parser.add_argument("--hbase", action="store_true",
                        help="Seed the HBase database")
    parser.add_argument("--install", action="store_true",
                        help="Install dependencies only")
    parser.add_argument("--status", action="store_true",
                        help="Check which services are running")
    parser.add_argument("--stop", action="store_true",
                        help="Show shutdown instructions")

    args = parser.parse_args()

    # If no args, show help
    if not any(vars(args).values()):
        banner()
        parser.print_help()
        print()
        return

    banner()

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print(f"\n\n{YELLOW}Interrupted! Shutting down...{RESET}")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Execute requested actions
    if args.status:
        do_status()
        return

    if args.stop:
        do_stop_info()
        return

    if args.install or args.all:
        do_install()

    if args.spark or args.all:
        do_spark()

    if args.posters or args.all:
        do_posters()

    if args.hbase or args.all:
        do_hbase()

    if args.serve or args.all:
        do_serve()

    if not (args.serve or args.all):
        print(f"\n{GREEN}{BOLD}Done!{RESET}\n")


if __name__ == "__main__":
    main()
