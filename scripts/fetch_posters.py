"""
TMDb Movie Poster Fetcher
=========================
Enriches movies_with_ratings.csv with poster URLs from TMDb API.
Uses link.csv to map MovieLens MovieIDs → TMDb IDs.

Usage:
    1. Create .env file with: TMDB_API_KEY=your_key_here
    2. Run: python scripts/fetch_posters.py
"""

import pandas as pd
import requests
import os
import time
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"
POSTER_SIZE = "w500"
BACKDROP_SIZE = "original"
MAX_WORKERS = 30  # Adjust thread count for higher speed (TMDb does not restrict rate limits severely anymore)


def fetch_movie_details(tmdb_id, api_key):
    """Fetch movie details from TMDb API."""
    url = f"{TMDB_BASE_URL}/movie/{int(tmdb_id)}"
    params = {"api_key": api_key, "language": "en-US"}
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                "poster_path": data.get("poster_path", ""),
                "backdrop_path": data.get("backdrop_path", ""),
                "overview": data.get("overview", ""),
            }
        elif response.status_code == 429:
            # Respect rate limit retry-after header if present, or sleep and retry
            retry_after = int(response.headers.get("Retry-After", 2))
            time.sleep(retry_after)
            return fetch_movie_details(tmdb_id, api_key)
        return None
    except requests.exceptions.RequestException:
        return None


def main():
    if not TMDB_API_KEY:
        print("ERROR: No TMDb API key found!")
        print("Create a .env file in the project root with:")
        print("  TMDB_API_KEY=your_api_key_here")
        print("\nGet a free key at: https://www.themoviedb.org/settings/api")
        return
    
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data"
    
    # Load movies with ratings
    movies_path = data_dir / "movies_with_ratings.csv"
    if not movies_path.exists():
        print(f"ERROR: {movies_path} not found. Run spark_processor.py first.")
        return
    
    movies_df = pd.read_csv(movies_path)
    print(f"Loaded {len(movies_df)} movies")
    
    # Load link.csv for MovieLens → TMDb mapping
    link_path = project_root / "link.csv"
    if not link_path.exists():
        print(f"ERROR: {link_path} not found.")
        return
    
    links_df = pd.read_csv(link_path)
    links_df.columns = links_df.columns.str.strip().str.replace('"', '')
    links_df = links_df.rename(columns={"movieId": "MovieID", "tmdbId": "tmdb_id", "imdbId": "imdb_id"})
    
    merged = movies_df.merge(links_df[["MovieID", "tmdb_id", "imdb_id"]], on="MovieID", how="left")
    has_tmdb = merged["tmdb_id"].notna().sum()
    print(f"Movies with TMDb IDs: {has_tmdb}/{len(merged)} ({100*has_tmdb/len(merged):.1f}%)")
    
    # Load cache
    cache_path = data_dir / "poster_cache.json"
    cache = {}
    if cache_path.exists():
        try:
            with open(cache_path, "r") as f:
                cache = json.load(f)
            print(f"Loaded {len(cache)} cached entries")
        except Exception:
            print("Could not read poster_cache.json, starting fresh.")
            cache = {}
    
    # Setup thread-safe resources
    cache_lock = Lock()
    results = {}
    
    # Separate what needs to be fetched from what is cached
    to_fetch = []
    for idx, row in merged.iterrows():
        tmdb_id = row.get("tmdb_id")
        if pd.isna(tmdb_id):
            results[idx] = {"poster_url": "", "backdrop_url": "", "overview": ""}
            continue
            
        tmdb_id_str = str(int(tmdb_id))
        
        # Check cache
        if tmdb_id_str in cache:
            results[idx] = cache[tmdb_id_str]
        else:
            to_fetch.append((idx, tmdb_id))
            
    print(f"Cached hits: {len(merged) - len(to_fetch) - merged['tmdb_id'].isna().sum()}")
    print(f"Pending to fetch: {len(to_fetch)}")
    
    # Fetch using ThreadPoolExecutor
    if to_fetch:
        print(f"\nFetching posters for {len(to_fetch)} movies concurrently using {MAX_WORKERS} threads...\n")
        start_time = time.time()
        completed_count = 0
        
        def worker(item):
            index, tmdb_id = item
            details = fetch_movie_details(tmdb_id, TMDB_API_KEY)
            return index, tmdb_id, details

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_movie = {executor.submit(worker, item): item for item in to_fetch}
            
            for future in as_completed(future_to_movie):
                index, tmdb_id, details = future.result()
                tmdb_id_str = str(int(tmdb_id))
                
                if details and details["poster_path"]:
                    poster_url = f"{TMDB_IMAGE_BASE}/{POSTER_SIZE}{details['poster_path']}"
                    backdrop_url = f"{TMDB_IMAGE_BASE}/{BACKDROP_SIZE}{details['backdrop_path']}" if details["backdrop_path"] else ""
                    overview = details.get("overview", "")
                    
                    movie_data = {
                        "poster_url": poster_url,
                        "backdrop_url": backdrop_url,
                        "overview": overview
                    }
                else:
                    movie_data = {"poster_url": "", "backdrop_url": "", "overview": ""}
                
                results[index] = movie_data
                
                # Write to shared cache in a thread-safe way
                with cache_lock:
                    if details and details["poster_path"]:
                        cache[tmdb_id_str] = movie_data
                
                completed_count += 1
                if completed_count % 100 == 0 or completed_count == len(to_fetch):
                    elapsed = time.time() - start_time
                    rate = completed_count / elapsed if elapsed > 0 else 0
                    remaining = (len(to_fetch) - completed_count) / rate if rate > 0 else 0
                    print(f"  Progress: {completed_count}/{len(to_fetch)} ({100*completed_count/len(to_fetch):.1f}%) "
                          f"— {rate:.1f} req/s — ~{remaining:.0f}s remaining")
    
        # Save cache
        with cache_lock:
            with open(cache_path, "w") as f:
                json.dump(cache, f)
            print(f"\nCache saved ({len(cache)} entries)")
            
    # Build final poster, backdrop, overview columns based on merged indexes
    poster_urls = []
    backdrop_urls = []
    overviews = []
    
    for idx in range(len(merged)):
        data = results.get(idx, {"poster_url": "", "backdrop_url": "", "overview": ""})
        poster_urls.append(data.get("poster_url", ""))
        backdrop_urls.append(data.get("backdrop_url", ""))
        overviews.append(data.get("overview", ""))
        
    merged["poster_url"] = poster_urls
    merged["backdrop_url"] = backdrop_urls
    merged["overview"] = overviews
    
    out_path = data_dir / "movies_with_posters.csv"
    merged.to_csv(out_path, index=False)
    
    has_posters = merged["poster_url"].astype(bool).sum()
    print(f"\n{'=' * 60}")
    print(f"  ✓ Done! Movies with posters: {has_posters}/{len(merged)} ({100*has_posters/len(merged):.1f}%)")
    print(f"  ✓ Saved to: {out_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

