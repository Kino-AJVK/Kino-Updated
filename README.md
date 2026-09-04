# 🎬 Kino — Big Data Movie Recommendation System

> **A portfolio-ready Big Data movie recommendation engine powered by PySpark, FastAPI, and a Netflix-inspired dark aesthetic UI. Built on the MovieLens 20M dataset.**

---

## 🚀 Key Features

* **🍿 Netflix-Inspired Dark Theme:** Beautiful user interface with poster grids, fluid hover cards, responsive navigation, glassmorphism overlays, and star ratings.
* **⚡ PySpark Data Aggregation:** Distributed processing of **20,000,000+ ratings** to clean, aggregate, and calculate statistics (average rating, rating count, IMDB weighted rating) for 27,000+ movies.
* **🎭 Mood & Keyword NLP Search:** Enter search descriptions like *"I want something scary"*, *"feel like laughing"*, or *"space adventure"* to map user emotions to movie genres.
* **🎬 TMDb API Poster Fetching:** Real-time data integration mapping MovieLens IDs to TMDb IDs via parallel thread pooling for fast poster fetching.
* **🔍 Movie Detail Modals:** Click on any card to view release details, average ratings, a short movie synopsis, and a carousel of dynamically calculated similar movies.
* **🗄️ HBase NoSQL Integration:** Native Hadoop column-family database support. Served data is fetched dynamically from an HBase table (`kino_movies`) via the `happybase` thrift library with standard local CSV backup mode.

---

## 📁 Folder Structure

Your repository should contain these folders and files:

```
kino/
├── app.py                      # FastAPI application backend
├── requirements.txt            # Python dependencies
├── .gitignore                  # Excludes large files (20M ratings) and API keys
├── .env.example                # Template for environment configuration
│
├── data/
│   └── movies_with_posters.csv # The final enriched dataset containing poster URLs
│
├── docs/                       # Project documentation & guides
│   ├── database_and_deployment_guide.md # Multi-OS HBase installation steps
│   └── hbase_usage_guide.md             # HBase schema design & viva sheet
│
├── frontend/                   # UI files
│   ├── index.html              # Netflix theme landing & homepage
│   ├── styles.css              # Custom styling & hover animations
│   └── script.js               # Modal controls, search, and carousel logic
│
├── spark/
│   └── spark_processor.py      # PySpark script to aggregate 20M ratings
│
└── scripts/
    ├── fetch_posters.py        # TMDb poster & backdrop fetcher (Multithreaded)
    └── setup_hbase.py          # HBase table creator and seeder script
```

---

## 🛠️ Installation & Setup

Follow these steps to run the project locally:

### 1. Clone & Set Up Environment
```bash
# Navigate to project directory
cd archive\ 2

# Create a virtual environment and activate it
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure TMDb API Key
1. Create a free account at [themoviedb.org](https://www.themoviedb.org/).
2. Request an API key in your account settings under **API**.
3. Create a `.env` file in the root folder and add your key:
   ```env
   TMDB_API_KEY=your_actual_api_key_here
   ```

### 3. Run the Big Data Pipeline & Seed HBase NoSQL
1. Start your local Hadoop / HBase services.
2. Start the HBase Thrift Server (FastAPI communicates via Thrift on port `9090`):
   ```bash
   hbase thrift start -p 9090
   ```
3. Run the pipeline and seed the database:
   ```bash
   # Step A: Run PySpark processor to aggregate the 20M dataset
   python spark/spark_processor.py

   # Step B: Run the multithreaded fetcher to download poster URLs
   python scripts/fetch_posters.py

   # Step C: Setup HBase tables and seed data
   python scripts/setup_hbase.py
   ```

### 4. Launch the Web Application
Make sure the HBase Thrift Server is running, then start the web server:
```bash
python app.py
```
Open **[http://localhost:8000](http://localhost:8000)** in your web browser. 

*Note: If HBase is not running, the application will print a warning and automatically fall back to local `data/movies_with_posters.csv` to ensure standard functionality.*

---

## 📊 System Architecture & Data Flow

```
[Raw MovieLens CSVs (20M ratings)] 
              │
              ▼ (PySpark Read)
    [PySpark Processing] ───► Calculates weighted ratings & statistics
              │
              ▼ (Pandas Export)
    [movies_with_ratings.csv] 
              │
              ▼ (scripts/fetch_posters.py using TMDb API mapping)
    [movies_with_posters.csv] 
              │
              ▼ (scripts/setup_hbase.py)
      [HBase NoSQL DB] ───► Column families: info, stats, links
              │
              ▼ (FastAPI Load via happybase)
    [In-Memory DataFrames] ───► Served instantly via API endpoints
              │
              ▼ (REST JSON)
    [Kino Netflix-themed SPA UI] ───► Dynamic rendering in browser
```

---

## 🎓 Academic Highlights for University Evaluation

* **Big Data Scale:** Processes raw dataset containing **20 million user ratings** (`rating.csv` ~690MB) and **27,000 movies** using Apache Spark.
* **Distributed Computing:** Uses PySpark DataFrames to perform group-by operations, aggregations, and joins.
* **Weighted Rating System:** Implements the **IMDB Weighted Rating formula** to handle rating bias (filtering out movies with high ratings but very low vote counts):
  $$\text{Weighted Rating} = \left(\frac{v}{v+m}\cdot R\right) + \left(\frac{m}{v+m}\cdot C\right)$$
  *(Where $v$ = vote count, $m$ = threshold votes, $R$ = average rating, $C$ = global mean)*
* **Concurrency:** Implements Python `ThreadPoolExecutor` for asynchronous I/O calls to speed up TMDb API queries from several hours down to minutes.
* **NoSQL Column-Family Database Design:** Integrates Apache HBase to serve movie data. Designed 3 distinct column families (`info` for metadata, `stats` for ratings metrics, and `links` for posters and overviews) to demonstrate distributed columnar store schema design.
* **Dual Serving Mode:** Implement a fault-tolerant system architecture where the API automatically drops back to localized JSON/CSV datasets if HBase clusters/Thrift networks are unavailable, preserving system uptime.
