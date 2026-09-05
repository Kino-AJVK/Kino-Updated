# 🎬 Kino — Complete Execution Guide

> **Everything you need to start, run, understand, and shut down the Kino Big Data Movie Recommendation System.**

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Quick Start (Any OS)](#2-quick-start-any-os)
3. [Step-by-Step Manual Execution](#3-step-by-step-manual-execution)
4. [Cross-Platform Executor Script](#4-cross-platform-executor-script)
5. [What Is Actually Happening — The Big Data Pipeline Explained](#5-what-is-actually-happening--the-big-data-pipeline-explained)
6. [Data Sources — Where Does the Data Come From?](#6-data-sources--where-does-the-data-come-from)
7. [What Apache Spark Does and How](#7-what-apache-spark-does-and-how)
8. [What Is Stored in HBase and Why](#8-what-is-stored-in-hbase-and-why)
9. [How to Shut Everything Down](#9-how-to-shut-everything-down)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

| Requirement      | Details                                                              |
|------------------|----------------------------------------------------------------------|
| **Java JDK**     | JDK 8, 11, or 17 (OpenJDK 17 recommended). Required by Spark & HBase |
| **Python**       | 3.8 – 3.11 (3.9 recommended)                                         |
| **Apache Spark** | Bundled via `pyspark` pip package (no separate install needed)         |
| **Apache HBase** | Required only if you want the NoSQL serving layer (optional — the app works without it) |
| **TMDb API Key** | Free key from [themoviedb.org](https://www.themoviedb.org/settings/api) — needed to fetch movie posters |
| **RAM**          | 8 GB minimum, 16 GB recommended                                      |
| **Disk Space**   | ~5 GB free (for the 690 MB ratings file, Spark temp files, etc.)      |

### Verify Java

```bash
java -version
```

If not installed:
- **macOS:** `brew install openjdk@17`
- **Linux (Ubuntu/Debian):** `sudo apt install openjdk-17-jdk`
- **Windows:** Download from [adoptium.net](https://adoptium.net/) and add to PATH

### Verify Python

```bash
python3 --version   # macOS/Linux
python --version    # Windows
```

---

## 2. Quick Start (Any OS)

If you just want to **see the web app running** (without HBase), this is the fastest path:

```bash
# 1. Create & activate virtual environment
python3 -m venv .venv              # macOS/Linux
# python -m venv .venv             # Windows

source .venv/bin/activate           # macOS/Linux
# .venv\Scripts\activate            # Windows CMD
# .venv\Scripts\Activate.ps1        # Windows PowerShell

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the web server (uses the pre-built data/movies_with_posters.csv)
python app.py

# 4. Open in browser
# → http://localhost:8000
```

> **Note:** The repository already includes `data/movies_with_posters.csv` (the fully processed dataset with poster URLs). You only need to run the Spark pipeline and poster fetcher if you want to **regenerate** the data from scratch.

---

## 3. Step-by-Step Manual Execution

### Step 1 — Environment Setup

#### macOS / Linux
```bash
cd /path/to/Kino-Updated-main
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### Windows (CMD)
```cmd
cd C:\path\to\Kino-Updated-main
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

#### Windows (PowerShell)
```powershell
cd C:\path\to\Kino-Updated-main
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Step 2 — Configure TMDb API Key

Create a `.env` file in the project root:

```env
TMDB_API_KEY=your_actual_api_key_here
```

Get a free key at: https://www.themoviedb.org/settings/api

### Step 3 — Download the Raw Dataset

Download the **MovieLens 20M** dataset from https://grouplens.org/datasets/movielens/20m/

You need these two files placed **in the project root** (not in `data/`):

| File          | Size    | Contents                                    |
|---------------|---------|---------------------------------------------|
| `rating.csv`  | ~690 MB | 20,000,000+ individual user–movie ratings   |
| `movie.csv`   | ~1.3 MB | 27,000+ movie titles with genres            |
| `link.csv`    | ~700 KB | MovieLens ID → TMDb ID / IMDb ID mappings   |

### Step 4 — Run the Spark Data Pipeline

```bash
python spark/spark_processor.py
```

**What this does:** Reads 20M ratings, aggregates per-movie statistics, computes IMDB weighted ratings, outputs `data/movies_with_ratings.csv`.

### Step 5 — Fetch Movie Posters from TMDb

```bash
python scripts/fetch_posters.py
```

**What this does:** Maps MovieLens IDs to TMDb IDs (via `link.csv`), calls the TMDb API in parallel (30 threads), downloads poster URLs, backdrop URLs, and plot overviews. Outputs `data/movies_with_posters.csv`.

### Step 6 — (Optional) Set Up HBase

```bash
# Start HBase (macOS)
start-hbase.sh
hbase thrift start -p 9090 &

# Start HBase (Linux)
./bin/start-hbase.sh
./bin/hbase thrift start -p 9090 &

# Start HBase (Windows — use Docker)
docker run -d --name hbase-kino -p 9090:9090 -p 16010:16010 harisekhon/hbase

# Seed the database
python scripts/setup_hbase.py
```

### Step 7 — Launch the Web App

```bash
python app.py
```

Open **http://localhost:8000** in your browser.

---

## 4. Cross-Platform Executor Script

### Can we make a single executor that works on any OS?

**Yes.** Since the entire project is Python-based, we can use a Python launcher script that works identically on macOS, Linux, and Windows. Python's `os`, `sys`, `subprocess`, and `platform` modules abstract away OS differences.

A cross-platform executor script `run_kino.py` has been created in the project root (see below). It:

- Detects your OS automatically
- Creates a virtual environment if one doesn't exist
- Installs dependencies
- Runs any/all pipeline steps
- Launches the web server
- Provides a clean shutdown option

#### Usage

```bash
# Run everything (full pipeline + web server)
python run_kino.py --all

# Just start the web server (if data already exists)
python run_kino.py --serve

# Run only the Spark pipeline
python run_kino.py --spark

# Run only the poster fetcher
python run_kino.py --posters

# Seed HBase only
python run_kino.py --hbase

# Install dependencies only
python run_kino.py --install
```

#### How to Exit

Press **`Ctrl + C`** in the terminal. The script catches the signal and shuts down the Uvicorn server cleanly.

---

## 5. What Is Actually Happening — The Big Data Pipeline Explained

The Kino project is a **4-stage Big Data pipeline** that transforms 20 million raw user ratings into a fully functional, Netflix-themed movie recommendation web app.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        THE KINO DATA PIPELINE                           │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  STAGE 1: SPARK PROCESSING                                               │
│  ┌─────────────┐    ┌──────────────────┐    ┌────────────────────────┐   │
│  │ rating.csv   │───►│ PySpark Engine   │───►│ movies_with_ratings   │   │
│  │ (690 MB)     │    │ (20M rows)       │    │ .csv                  │   │
│  │ movie.csv    │───►│ GroupBy, Agg,    │    │ (MovieID, Title,      │   │
│  │ (1.3 MB)     │    │ Join, Filter     │    │  Genres, AvgRating,   │   │
│  └─────────────┘    └──────────────────┘    │  NumRatings,          │   │
│                                              │  WeightedRating)      │   │
│                                              └──────────┬─────────────┘   │
│  STAGE 2: POSTER ENRICHMENT                             │                │
│  ┌─────────────┐    ┌──────────────────┐    ┌──────────▼─────────────┐   │
│  │ link.csv     │───►│ TMDb API         │───►│ movies_with_posters   │   │
│  │ (ID mapping) │    │ (30 threads)     │    │ .csv                  │   │
│  └─────────────┘    └──────────────────┘    │ (+ poster_url,        │   │
│                                              │   backdrop_url,       │   │
│                                              │   overview, tmdb_id)  │   │
│                                              └──────────┬─────────────┘   │
│  STAGE 3: DATABASE SEEDING (Optional)                   │                │
│  ┌──────────────────────────────────────────────────────▼─────────────┐   │
│  │ HBase Table: kino_movies                                           │   │
│  │ ┌──────────┐  ┌──────────────┐  ┌─────────────────────────────┐   │   │
│  │ │ CF: info │  │ CF: stats    │  │ CF: links                   │   │   │
│  │ │ title    │  │ avg_rating   │  │ poster_url, backdrop_url,   │   │   │
│  │ │ genres   │  │ num_ratings  │  │ overview                    │   │   │
│  │ │          │  │ weighted_rat │  │                             │   │   │
│  │ └──────────┘  └──────────────┘  └─────────────────────────────┘   │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  STAGE 4: WEB APPLICATION                                                │
│  ┌──────────────┐    ┌──────────────┐    ┌────────────────────────────┐  │
│  │ FastAPI      │───►│ REST JSON    │───►│ Netflix-themed SPA UI     │  │
│  │ (app.py)     │    │ API          │    │ (HTML/CSS/JS)             │  │
│  │ Port 8000    │    │ /api/mood    │    │ Mood search, posters,     │  │
│  │              │    │ /api/trending│    │ detail modals, carousels  │  │
│  └──────────────┘    └──────────────┘    └────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Data Sources — Where Does the Data Come From?

### Primary Source: MovieLens 20M Dataset

| File         | Source | Rows         | Columns                              | Purpose                          |
|--------------|--------|--------------|--------------------------------------|----------------------------------|
| `rating.csv` | [GroupLens Research](https://grouplens.org/datasets/movielens/20m/) | **20,000,263** | `userId, movieId, rating, timestamp` | Raw user-to-movie star ratings (0.5–5.0 scale) |
| `movie.csv`  | Same source | **27,278**     | `movieId, title, genres`             | Movie titles with pipe-separated genre tags |
| `link.csv`   | Same source | **27,278**     | `movieId, imdbId, tmdbId`            | Cross-reference IDs to IMDb and TMDb |

**MovieLens** is a research dataset published by the **GroupLens lab** at the University of Minnesota. The 20M version contains ratings collected between January 1995 and March 2015.

### Secondary Source: TMDb API

| Data Retrieved   | Source | How                                               |
|------------------|--------|---------------------------------------------------|
| `poster_url`     | [TMDb](https://www.themoviedb.org/) | `GET /movie/{tmdb_id}` → `poster_path`            |
| `backdrop_url`   | TMDb   | `GET /movie/{tmdb_id}` → `backdrop_path`           |
| `overview`       | TMDb   | `GET /movie/{tmdb_id}` → `overview` (plot summary) |

The `fetch_posters.py` script uses `link.csv` to translate MovieLens IDs → TMDb IDs, then calls the TMDb REST API using 30 concurrent threads via Python's `ThreadPoolExecutor`.

### Generated / Processed Files

| File                         | Generated By            | Contents                                                 |
|------------------------------|-------------------------|----------------------------------------------------------|
| `data/movies_with_ratings.csv` | `spark_processor.py`   | Movies with computed AvgRating, NumRatings, WeightedRating |
| `data/movies_with_posters.csv` | `fetch_posters.py`     | Above + poster_url, backdrop_url, overview, tmdb_id       |
| `data/poster_cache.json`      | `fetch_posters.py`     | Cache of TMDb API responses (avoids re-fetching)          |

---

## 7. What Apache Spark Does and How

### Why Spark?

The `rating.csv` file is **690 MB** with **20 million rows**. Processing this with plain Python/Pandas would:
- Take several minutes and consume 4–8 GB of RAM
- Not demonstrate distributed computing

**Apache Spark (PySpark)** is a distributed data processing engine designed for exactly this kind of workload. Even in local mode (`local[*]`), Spark uses all your CPU cores in parallel.

### What `spark_processor.py` Does — Step by Step

```
┌──────────────────────────────────────────────────────────────────┐
│  Step 1: Initialize SparkSession                                 │
│  ─────────────────────────────────                               │
│  Creates a Spark application named "MovieLens20M_Processor"      │
│  running in local mode with 4 GB driver memory.                  │
│  This starts a mini Spark cluster on your machine.               │
├──────────────────────────────────────────────────────────────────┤
│  Step 2: Read rating.csv (20M rows)                              │
│  ──────────────────────────────────                              │
│  Spark reads the CSV in parallel across multiple partitions.     │
│  Columns: userId, movieId, rating, timestamp                     │
│  Spark does NOT load this into RAM all at once — it partitions   │
│  the data and processes chunks in parallel.                      │
├──────────────────────────────────────────────────────────────────┤
│  Step 3: GroupBy + Aggregate                                     │
│  ────────────────────────                                        │
│  ratings_df.groupBy("MovieID").agg(                              │
│      avg("Rating")   → AvgRating,                                │
│      count("Rating") → NumRatings                                │
│  ).filter(NumRatings >= 50)                                      │
│                                                                  │
│  This is the core Big Data operation:                             │
│  • Groups all 20M ratings by MovieID                              │
│  • Computes the average rating per movie                          │
│  • Counts how many users rated each movie                         │
│  • Filters out movies with < 50 ratings (noise reduction)         │
│                                                                  │
│  Spark distributes this across all CPU cores using a              │
│  shuffle operation (data is re-partitioned by MovieID).           │
├──────────────────────────────────────────────────────────────────┤
│  Step 4: Read movie.csv (27K rows)                               │
│  ──────────────────────────────                                  │
│  Loads the movie metadata (Title, Genres) into a Spark DataFrame.│
├──────────────────────────────────────────────────────────────────┤
│  Step 5: JOIN + IMDB Weighted Rating                             │
│  ─────────────────────────────────                               │
│  • INNER JOIN movies with their computed stats                    │
│  • Converts to Pandas for the weighted rating formula:            │
│                                                                  │
│     WeightedRating = (v/(v+m)) × R + (m/(v+m)) × C              │
│                                                                  │
│     v = number of ratings for this movie                          │
│     m = 75th percentile of rating counts (threshold)              │
│     R = average rating for this movie                             │
│     C = global mean rating across all movies                      │
│                                                                  │
│  This is the IMDB formula. It prevents movies with very few       │
│  but all-perfect ratings from ranking above well-known films.     │
│  Example: A movie with 3 ratings of 5.0 won't outrank            │
│  The Shawshank Redemption with 63,000+ ratings of 4.45.          │
├──────────────────────────────────────────────────────────────────┤
│  Step 6: Export to CSV                                           │
│  ─────────────────────                                           │
│  Saves the result as data/movies_with_ratings.csv                │
│  Columns: MovieID, Title, Genres, AvgRating, NumRatings,         │
│           WeightedRating                                          │
│  Typically ~6,000–8,000 movies survive the filter.               │
├──────────────────────────────────────────────────────────────────┤
│  Step 7: Stop Spark                                              │
│  ──────────────────                                              │
│  Calls spark.stop() to release all resources.                    │
└──────────────────────────────────────────────────────────────────┘
```

### Key Spark Concepts Used

| Concept               | How It's Used                                                              |
|-----------------------|----------------------------------------------------------------------------|
| **SparkSession**      | Entry point to all Spark functionality                                     |
| **DataFrame API**     | Structured, column-oriented data processing (like SQL tables)              |
| **Lazy Evaluation**   | Spark doesn't execute until an action (like `.count()`) is called          |
| **Partitioning**      | Data is split across CPU cores; `local[*]` uses all available cores        |
| **Shuffle**           | During `groupBy`, data is redistributed so all ratings for a movie land on the same partition |
| **Driver Memory**     | Set to 4 GB to handle the 690 MB dataset                                  |

---

## 8. What Is Stored in HBase and Why

### The HBase Table: `kino_movies`

HBase is a **column-family NoSQL database** that runs on top of HDFS (Hadoop Distributed File System). Unlike SQL databases that store data in fixed rows and columns, HBase groups columns into **families** that are stored together on disk.

### Schema

```
Table: kino_movies
Row Key: Zero-padded MovieID (e.g., "000318" for MovieID 318)

┌──────────────────────────────────────────────────────────────────────────┐
│                        Column Families (CFs)                             │
├───────────────────┬───────────────────────┬──────────────────────────────┤
│    CF: info       │    CF: stats          │    CF: links                 │
├───────────────────┼───────────────────────┼──────────────────────────────┤
│ info:title        │ stats:avg_rating      │ links:poster_url             │
│ "Shawshank        │ "4.447"               │ "https://image.tmdb.org/..."  │
│  Redemption,      │                       │                              │
│  The (1994)"      │ stats:num_ratings     │ links:backdrop_url           │
│                   │ "63366"               │ "https://image.tmdb.org/..."  │
│ info:genres       │                       │                              │
│ "Crime|Drama"     │ stats:weighted_rating │ links:overview               │
│                   │ "4.4225"              │ "Imprisoned in the 1940s..." │
└───────────────────┴───────────────────────┴──────────────────────────────┘
```

### Why Three Separate Column Families?

| Column Family | What's Stored | Why It's Separate |
|---------------|---------------|-------------------|
| **`info`**    | `title`, `genres` | **Immutable metadata** — never changes. Grouping together means HBase can read just this family without touching stats or links. |
| **`stats`**   | `avg_rating`, `num_ratings`, `weighted_rating` | **Computed metrics** — generated by the Spark pipeline. If you re-run Spark with new ratings, only this family needs updating. |
| **`links`**   | `poster_url`, `backdrop_url`, `overview` | **External API data** — fetched from TMDb. These are the most volatile (posters can change). Separating them means you can refresh links without touching stats or metadata. |

### Why Zero-Padded Row Keys?

HBase sorts rows **lexicographically** (alphabetically), not numerically:

```
Without padding:  1 → 10 → 100 → 11 → 2 → 20 → 3  (WRONG!)
With padding:     000001 → 000002 → 000003 → 000010 → 000011 → 000020 → 000100  (CORRECT!)
```

MovieID `318` becomes row key `"000318"` to maintain correct sort order in HBase scans.

### Why HBase and Not MySQL/PostgreSQL?

| Reason | Explanation |
|--------|-------------|
| **Hadoop Ecosystem Integration** | HBase runs natively on HDFS. In a production Big Data environment, the Spark output could write directly to HBase without exporting to CSV first. |
| **Horizontal Scalability** | HBase can scale to billions of rows across hundreds of machines. SQL databases require complex sharding. |
| **Column-Family Design** | Perfect for this use case — different data categories (metadata vs. stats vs. media links) change at different rates. |
| **Sparse Data Handling** | If a movie doesn't have a poster or overview, HBase simply doesn't store that column — no wasted space. SQL would store NULLs. |
| **Academic Demonstration** | Demonstrates proficiency with the Hadoop/NoSQL stack, a core requirement for Big Data coursework. |

### How the App Uses HBase (Dual-Mode)

```
                    ┌──── Is HBase running? ────┐
                    │                            │
                  YES                           NO
                    │                            │
        ┌───────────▼───────────┐   ┌───────────▼───────────┐
        │ Connect via Thrift    │   │ Load from CSV file     │
        │ (happybase library)   │   │ data/movies_with_      │
        │ Port 9090             │   │ posters.csv            │
        │                       │   │                        │
        │ Batch scan with       │   │ pd.read_csv()          │
        │ batch_size=1000       │   │                        │
        └───────────┬───────────┘   └───────────┬───────────┘
                    │                            │
                    └──────────┬─────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  In-Memory Pandas   │
                    │  DataFrame          │
                    │  (serves all API    │
                    │   requests)         │
                    └─────────────────────┘
```

The app **always works** — HBase is optional. If the Thrift connection fails, it gracefully falls back to the CSV.

---

## 9. How to Shut Everything Down

### Stopping the Web Server

Press **`Ctrl + C`** in the terminal where `python app.py` is running.

```
^C
INFO:     Shutting down
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
```

### Stopping HBase (if running)

#### macOS / Linux

```bash
# Stop the Thrift server (find its PID)
# Method 1: If you started it in the background with &
jobs          # lists background jobs
kill %1       # kill job number 1

# Method 2: Find by port
lsof -i :9090                    # find the PID
kill <PID>                       # kill it

# Stop HBase and Zookeeper
stop-hbase.sh                    # macOS (brew install)
# OR
./bin/stop-hbase.sh              # Linux (tarball install)
```

#### Windows (Docker)

```bash
docker stop hbase-kino
docker rm hbase-kino             # optional: remove the container
```

### Deactivating the Virtual Environment

```bash
deactivate                       # works on all OS
```

### Complete Shutdown Checklist

```
✅ 1. Ctrl+C to stop the FastAPI server (python app.py)
✅ 2. Kill the HBase Thrift server (port 9090)
✅ 3. Stop HBase master + region servers (stop-hbase.sh)
✅ 4. Deactivate the Python virtual environment (deactivate)
✅ 5. (Optional) Stop Docker containers if using Docker for HBase
```

### Verifying Everything Is Stopped

```bash
# Check if anything is still listening on the project ports
lsof -i :8000    # FastAPI — should return nothing
lsof -i :9090    # HBase Thrift — should return nothing
lsof -i :16010   # HBase Master UI — should return nothing
lsof -i :2181    # Zookeeper — should return nothing
```

On Windows:
```powershell
netstat -ano | findstr :8000
netstat -ano | findstr :9090
```

---

## 10. Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: No module named 'pyspark'` | Run `pip install -r requirements.txt` inside the activated virtual environment |
| `JAVA_HOME is not set` | Install Java JDK and set `JAVA_HOME` environment variable |
| `rating.csv not found` | Download the MovieLens 20M dataset and place `rating.csv` in the project root |
| `Could not connect to HBase Thrift Server` | Either start HBase + Thrift, or just skip it — the app works without HBase |
| `TMDB_API_KEY not found` | Create a `.env` file in the project root with `TMDB_API_KEY=your_key` |
| `Port 8000 already in use` | Kill the existing process: `lsof -i :8000` then `kill <PID>` |
| Posters not showing | Run `python scripts/fetch_posters.py` to fetch poster URLs from TMDb |
| Spark running slowly | Ensure Java is installed and `JAVA_HOME` is set. Close other heavy apps to free RAM. |

---

*Last updated: September 2026*
