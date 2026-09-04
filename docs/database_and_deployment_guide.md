# Kino — System Deployment & NoSQL Database Guide

> **This document details the configuration, deployment commands (across macOS, Linux, and Windows), database architecture, and minimum hardware/software specifications for the Kino Movie Recommendation System.**

---

## 1. Minimum System Requirements

To run the PySpark pipeline and HBase cluster locally, your system must meet these specifications:

### Hardware Requirements
* **CPU:** Dual-core 64-bit Intel/AMD or Apple Silicon (M1/M2/M3)
* **RAM:** Minimum 8 GB (16 GB recommended to run Hadoop, HBase, and PySpark concurrently)
* **Storage:** Minimum 5 GB free disk space (to store the raw 20M dataset, Spark logs, and HBase tables)

### Software Prerequisites
* **Operating System:** macOS (High Sierra or later), Linux (Ubuntu 20.04+ recommended), or Windows 10/11
* **Java SDK:** Java JDK 8, 11, or 17 (Required by Hadoop & HBase; OpenJDK 17 is recommended)
* **Python:** Version 3.8 to 3.11 (Python 3.9 is recommended)

---

## 2. Multi-OS Execution Guide

Below are the step-by-step commands to install, configure, and launch the entire Kino platform.

### Step 2.1: Virtual Environment Setup

#### 🍎 macOS & 🐧 Linux
```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install Python requirements
pip install -r requirements.txt
```

#### 🪟 Windows
```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\Activate.ps1

# Install Python requirements
pip install -r requirements.txt
```

---

### Step 2.2: Install and Start HBase

#### 🍎 macOS (via Homebrew)
```bash
# Install HBase via Homebrew
brew install hbase

# Start Zookeeper and HBase services
start-hbase.sh

# Wait for HBase to fully initialize, then start the Thrift daemon
sleep 5 && hbase thrift start -p 9090 &
```

#### 🐧 Linux (Manual Tarball Installation)
```bash
# Download HBase 2.6.x (stable)
wget https://downloads.apache.org/hbase/2.6.6/hbase-2.6.6-bin.tar.gz
tar -xzvf hbase-2.6.6-bin.tar.gz
cd hbase-2.6.6

# Start HBase master & region servers
./bin/start-hbase.sh

# Wait for HBase to fully initialize, then start Thrift daemon
sleep 5 && ./bin/hbase thrift start -p 9090 &
```

#### 🪟 Windows (via WSL2 / Docker - Recommended)
HBase does not run natively on Windows command prompt without complex Cygwin configurations. It is highly recommended to run it in Windows Subsystem for Linux (WSL2) or Docker:
```bash
# Run HBase in Docker
docker run -d --name hbase-kino -p 9090:9090 -p 16010:16010 harisekhon/hbase

# Zookeeper, HBase Master, and Thrift Server are automatically started.
```

---

### Step 2.3: Data Pipeline execution

Once your environment is set up and HBase is running, execute the pipeline:

```bash
# 1. Run the PySpark Aggregator (Aggregates 20M ratings)
python spark/spark_processor.py

# 2. Enrich movies with TMDb Posters (needs TMDB_API_KEY inside .env)
python scripts/fetch_posters.py

# 3. Create HBase tables and seed the database
python scripts/setup_hbase.py
```

---

### Step 2.4: Launch Web Application
```bash
python app.py
```
Open your browser to **http://localhost:8000** to explore the active application!

---

## 3. NoSQL Database Architecture in Detail

Kino utilizes **Apache HBase** as its production-serving datastore. Unlike relational databases (SQL) or document stores (MongoDB), HBase is a columnar-family NoSQL database running natively on top of the Hadoop Distributed File System (HDFS).

### 3.1 Column-Family Schema Design

HBase groups data into column families (CFs), which are stored together on disk in separate HFiles. The table `kino_movies` is structured with three specialized column families:

```
Table: kino_movies
┌────────────────────────────────────────────────────────────┐
│ Row Key: 000318 (MovieID zero-padded to 6 digits)          │
├─────────────────┬───────────────────┬──────────────────────┤
│ CF: info        │ CF: stats         │ CF: links            │
├─────────────────┼───────────────────┼──────────────────────┤
│ info:title      │ stats:avg_rating  │ links:poster_url     │
│ info:genres     │ stats:num_ratings │ links:backdrop_url   │
│                 │ stats:weighted    │ links:overview       │
└─────────────────┴───────────────────┴──────────────────────┘
```

1. **`info` Family:** Stores immutable metadata (`title`, `genres`). Since these values do not change frequently, they are grouped together.
2. **`stats` Family:** Stores numerical calculations and metrics (`avg_rating`, `num_ratings`, `weighted_rating`) computed by our Spark job.
3. **`links` Family:** Stores the dynamically resolved assets fetched from the external TMDb API (`poster_url`, `backdrop_url`, `overview`).

### 3.2 Row-Key Strategy (Zero-Padding)

HBase stores rows lexicographically (alphabetically) by row key. If we used standard integers as row keys (e.g. `1`, `2`, `10`, `11`, `100`), HBase would sort them as:
`1, 10, 100, 11, 2, 20...`

To maintain correct numerical ordering and enable efficient row scans, Kino **zero-pads MovieIDs to a 6-digit string** (e.g. MovieID `318` becomes row key `000318`, MovieID `1` becomes `000001`).

### 3.3 Thrift Server Connection & Batch Scans

FastAPI connects to HBase Thrift server using the `happybase` client library. To avoid performance degradation:
* **Batch Fetching:** Running standard `scan()` queries on 10,000+ items sequentially creates massive overhead. Kino uses `table.scan(batch_size=1000)` which groups database transfer calls into batch blocks, speeding up API retrieval from seconds down to milliseconds.
* **Fault-Tolerant Fallback:** In the event that Zookeeper or the HBase cluster goes offline, the system is designed with a fallback interface that automatically redirects API reads to local cache CSV backups (`data/movies_with_posters.csv`), ensuring 100% application uptime.
