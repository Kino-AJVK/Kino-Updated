from pyspark.sql import SparkSession
from pyspark.sql.functions import col, avg, count
import os
import sys

# Setting python paths for PySpark to work seamlessly
os.environ['PYSPARK_PYTHON'] = sys.executable
os.environ['PYSPARK_DRIVER_PYTHON'] = sys.executable

def main():
    """
    PySpark Big Data Processor for MovieLens 20M Dataset.
    
    Reads 20,000,000+ ratings and 27,000+ movies,
    computes per-movie rating statistics using distributed Spark processing,
    and outputs a clean CSV for the API backend.
    """
    print("=" * 60)
    print("  PySpark Big Data Processor — MovieLens 20M")
    print("=" * 60)
    
    print("\n[1/5] Initializing PySpark Session...")
    spark = SparkSession.builder \
        .appName("MovieLens20M_Processor") \
        .master("local[*]") \
        .config("spark.driver.memory", "4g") \
        .config("spark.sql.shuffle.partitions", "8") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("ERROR")
    
    project_root = os.path.dirname(os.path.dirname(__file__))
    
    # ─── Load Ratings (20M rows, ~690MB) ───
    print("\n[2/5] Loading 20,000,000+ ratings...")
    ratings_path = os.path.join(project_root, "rating.csv")
    ratings_df = spark.read.csv(ratings_path, header=True, inferSchema=True)
    ratings_df = ratings_df.withColumnRenamed("userId", "UserID") \
                           .withColumnRenamed("movieId", "MovieID") \
                           .withColumnRenamed("rating", "Rating") \
                           .withColumnRenamed("timestamp", "Timestamp")
    
    total_ratings = ratings_df.count()
    print(f"  ✓ Loaded {total_ratings:,} ratings")
    
    # ─── Aggregate Ratings per Movie ───
    print("\n[3/5] Aggregating ratings per movie (distributed Spark)...")
    movie_stats = ratings_df.groupBy("MovieID").agg(
        avg("Rating").alias("AvgRating"),
        count("Rating").alias("NumRatings")
    ).filter(col("NumRatings") >= 50)
    
    stats_count = movie_stats.count()
    print(f"  ✓ Computed stats for {stats_count:,} movies (filtered: NumRatings >= 50)")
    
    # ─── Load Movies Metadata ───
    print("\n[4/5] Loading movies metadata...")
    movies_path = os.path.join(project_root, "movie.csv")
    movies_df = spark.read.csv(movies_path, header=True, inferSchema=True)
    movies_df = movies_df.withColumnRenamed("movieId", "MovieID") \
                         .withColumnRenamed("title", "Title") \
                         .withColumnRenamed("genres", "Genres")
    
    total_movies = movies_df.count()
    print(f"  ✓ Loaded {total_movies:,} movies")
    
    # ─── Join Datasets ───
    print("\n[5/5] Joining datasets and exporting...")
    final_df = movies_df.join(movie_stats, "MovieID", "inner")
    
    final_pd = final_df.toPandas()
    
    # IMDB Weighted Rating formula
    m = final_pd['NumRatings'].quantile(0.75)
    C = final_pd['AvgRating'].mean()
    final_pd['WeightedRating'] = (
        (final_pd['NumRatings'] / (final_pd['NumRatings'] + m)) * final_pd['AvgRating'] +
        (m / (final_pd['NumRatings'] + m)) * C
    )
    final_pd = final_pd.sort_values('WeightedRating', ascending=False)
    
    out_dir = os.path.join(project_root, "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "movies_with_ratings.csv")
    final_pd.to_csv(out_path, index=False)
    
    print(f"\n{'=' * 60}")
    print(f"  ✓ Total movies after filtering: {len(final_pd):,}")
    print(f"  ✓ Output: {out_path}")
    print(f"  ✓ Top 5 movies:")
    for _, row in final_pd.head(5).iterrows():
        print(f"    {row['Title']} — ★ {row['AvgRating']:.2f} ({int(row['NumRatings'])} ratings)")
    print(f"{'=' * 60}")
    
    spark.stop()

if __name__ == "__main__":
    main()
