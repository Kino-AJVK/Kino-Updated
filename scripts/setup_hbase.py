"""
HBase Database Setup & Data Seeder
==================================
Creates the required HBase tables and seeds them with data from
data/movies_with_posters.csv.

Prerequisites:
    1. HBase must be installed and running.
    2. The HBase Thrift Server must be running:
       $ hbase thrift start -p 9090
    3. Install happybase:
       $ pip install happybase

Usage:
    python scripts/setup_hbase.py
"""

import pandas as pd
import happybase
import sys
import os

HBASE_HOST = os.getenv("HBASE_HOST", "localhost")
HBASE_PORT = int(os.getenv("HBASE_PORT", 9090))
TABLE_NAME = "kino_movies"


def main():
    print("=" * 60)
    print("  HBase Setup & Seeder — Kino Movie Recommendation System")
    print("=" * 60)
    
    # 1. Load the processed dataset
    data_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "movies_with_posters.csv")
    if not os.path.exists(data_path):
        print(f"ERROR: {data_path} not found.")
        print("Please run spark/spark_processor.py and scripts/fetch_posters.py first.")
        sys.exit(1)
        
    df = pd.read_csv(data_path)
    print(f"✓ Loaded {len(df)} movies from {data_path}")
    
    # 2. Connect to HBase
    print(f"Connecting to HBase Thrift Server at {HBASE_HOST}:{HBASE_PORT}...")
    try:
        connection = happybase.Connection(host=HBASE_HOST, port=HBASE_PORT)
        # Force connection opening to test it
        connection.tables()
        print("✓ Connected to HBase successfully!")
    except Exception as e:
        print(f"ERROR: Could not connect to HBase Thrift Server: {e}")
        print("\nMake sure HBase is running and the Thrift server is started:")
        print("  $ hbase thrift start -p 9090")
        sys.exit(1)
        
    # 3. Create table
    tables = [t.decode("utf-8") for t in connection.tables()]
    if TABLE_NAME in tables:
        print(f"Table '{TABLE_NAME}' already exists. Recreating to perform a clean seed...")
        try:
            connection.disable_table(TABLE_NAME)
            connection.delete_table(TABLE_NAME)
            print(f"✓ Deleted existing table '{TABLE_NAME}'")
        except Exception as e:
            print(f"Warning during delete: {e}")
            
    print(f"Creating table '{TABLE_NAME}' with column families 'info', 'stats', 'links'...")
    connection.create_table(
        TABLE_NAME,
        {
            "info": dict(max_versions=1),   # For title, genres
            "stats": dict(max_versions=1),  # For ratings, metrics
            "links": dict(max_versions=1),  # For poster/backdrop URLs & synopses
        }
    )
    print(f"✓ Table '{TABLE_NAME}' created successfully.")
    
    # 4. Seed data
    print("Seeding HBase table...")
    table = connection.table(TABLE_NAME)
    
    # Use batch for highly efficient bulk writing
    batch = table.batch()
    batch_size = 100
    written = 0
    
    for idx, row in df.iterrows():
        movie_id = row.get("MovieID")
        if pd.isna(movie_id):
            continue
            
        # Zero-pad MovieID to ensure correct alphabetical/lexicographical sorting in HBase scans
        row_key = f"{int(movie_id):06d}"
        
        # Build column family mappings
        data = {
            b"info:title": str(row.get("Title", "")).encode("utf-8"),
            b"info:genres": str(row.get("Genres", "")).encode("utf-8"),
            
            b"stats:avg_rating": str(row.get("AvgRating", 0.0)).encode("utf-8"),
            b"stats:num_ratings": str(row.get("NumRatings", 0)).encode("utf-8"),
            b"stats:weighted_rating": str(row.get("WeightedRating", 0.0)).encode("utf-8"),
            
            b"links:poster_url": str(row.get("poster_url", "")).encode("utf-8"),
            b"links:backdrop_url": str(row.get("backdrop_url", "")).encode("utf-8"),
            b"links:overview": str(row.get("overview", "")).encode("utf-8"),
        }
        
        batch.put(row_key, data)
        written += 1
        
        if written % batch_size == 0:
            batch.send()
            batch = table.batch()
            print(f"  Processed {written}/{len(df)} movies...")
            
    # Send remaining rows
    batch.send()
    print(f"✓ Successfully seeded {written} movies into table '{TABLE_NAME}'!")
    connection.close()


if __name__ == "__main__":
    main()
