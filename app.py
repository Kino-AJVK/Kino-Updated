from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pandas as pd
import os
import re
import difflib


app = FastAPI(title="Kino — Big Data Movie Recommendations")


# ============================================================
# DATA
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

POSTERS_PATH = os.path.join(DATA_DIR, "movies_with_posters.csv")
RATINGS_PATH = os.path.join(DATA_DIR, "movies_with_ratings.csv")

movies_df = None


# ============================================================
# MOOD → GENRE MAPPING
# ============================================================

MOOD_TO_GENRE = {
    "happy": ["Comedy", "Animation", "Musical"],
    "joy": ["Comedy", "Musical"],
    "laugh": ["Comedy"],
    "funny": ["Comedy"],
    "hilarious": ["Comedy"],
    "smile": ["Comedy", "Animation"],
    "humor": ["Comedy"],

    "sad": ["Drama", "Romance"],
    "cry": ["Drama", "Romance"],
    "emotional": ["Drama"],
    "depressing": ["Drama"],
    "tearjerker": ["Drama", "Romance"],

    "scary": ["Horror", "Thriller"],
    "horror": ["Horror"],
    "fear": ["Horror", "Thriller"],
    "spooky": ["Horror", "Fantasy"],
    "creepy": ["Horror", "Mystery"],
    "terrifying": ["Horror"],

    "excited": ["Action", "Adventure", "Sci-Fi"],
    "action": ["Action", "Adventure"],
    "adrenaline": ["Action", "Thriller"],
    "fight": ["Action"],
    "thrill": ["Action", "Thriller"],
    "explosion": ["Action", "Sci-Fi"],
    "hero": ["Action", "Adventure"],
    "combat": ["Action", "War"],

    "think": ["Documentary", "Mystery", "Sci-Fi"],
    "mind": ["Sci-Fi", "Mystery", "Thriller"],
    "mystery": ["Mystery", "Crime", "Thriller"],
    "crime": ["Crime", "Thriller"],
    "detective": ["Crime", "Mystery"],
    "murder": ["Crime", "Mystery", "Thriller"],

    "love": ["Romance", "Comedy"],
    "romantic": ["Romance"],
    "date": ["Romance", "Comedy"],
    "heart": ["Romance", "Drama"],
    "passion": ["Romance", "Drama"],
    "sweet": ["Romance", "Comedy"],

    "future": ["Sci-Fi"],
    "space": ["Sci-Fi"],
    "alien": ["Sci-Fi"],
    "robot": ["Sci-Fi"],

    "magic": ["Fantasy", "Adventure"],
    "fantasy": ["Fantasy"],
    "dragon": ["Fantasy"],
    "wizard": ["Fantasy"],

    "war": ["War"],
    "soldier": ["War", "Action"],
    "battle": ["War", "Action"],

    "cowboy": ["Western"],
    "western": ["Western"],

    "music": ["Musical"],
    "dance": ["Musical"],

    "family": ["Animation", "Comedy"],
    "kid": ["Animation", "Children"],
    "cartoon": ["Animation"],
    "anime": ["Animation", "Sci-Fi", "Action"],

    "real": ["Documentary"],
    "true": ["Documentary"],
    "learn": ["Documentary"],

    "journey": ["Adventure", "Drama"],
    "explore": ["Adventure", "Sci-Fi"],
    "quest": ["Adventure", "Fantasy"],
    "epic": ["Adventure", "Action", "Drama"],

    "dark": ["Film-Noir", "Crime", "Thriller"],
    "noir": ["Film-Noir", "Crime"],
    "tense": ["Thriller", "Crime"],
    "suspense": ["Thriller", "Mystery"],
}


# ============================================================
# LOAD CSV DATA
# ============================================================

@app.on_event("startup")
async def load_data():
    global movies_df

    print("\n" + "=" * 60)
    print("             KINO DATA LOADER")
    print("=" * 60)

    # --------------------------------------------------------
    # IMPORTANT:
    # CSV is now the PRIMARY SOURCE OF TRUTH.
    #
    # HBase is intentionally NOT loaded here because an older
    # HBase dataset could contain old/missing poster URLs and
    # override the updated CSV.
    # --------------------------------------------------------

    try:
        if os.path.exists(POSTERS_PATH):

            print(f"Loading movie dataset:")
            print(f"  {POSTERS_PATH}")

            movies_df = pd.read_csv(
                POSTERS_PATH,
                low_memory=False
            )

            # Ensure The Godfather poster is available
            # (MovieID 858)
            godfather_mask = movies_df["MovieID"] == 858
            if godfather_mask.any():
                movies_df.loc[godfather_mask, "poster_url"] = (
                    "https://image.tmdb.org/t/p/w500/3bhkrj58Vtu7enYsRolD1fZdja1.jpg"
                )

            print(f"Loaded {len(movies_df):,} movies from movies_with_posters.csv")

        elif os.path.exists(RATINGS_PATH):

            print("movies_with_posters.csv not found.")
            print("Falling back to movies_with_ratings.csv")

            movies_df = pd.read_csv(
                RATINGS_PATH,
                low_memory=False
            )

            print(f"Loaded {len(movies_df):,} movies from ratings CSV")

        else:

            print("ERROR: No movie CSV file found.")
            print(f"Expected:")
            print(f"  {POSTERS_PATH}")

            movies_df = None
            return

        # ----------------------------------------------------
        # REQUIRED COLUMNS
        # ----------------------------------------------------

        if "MovieID" not in movies_df.columns:
            raise ValueError("MovieID column is missing from CSV")

        if "Title" not in movies_df.columns:
            raise ValueError("Title column is missing from CSV")

        if "Genres" not in movies_df.columns:
            movies_df["Genres"] = ""

        if "AvgRating" not in movies_df.columns:
            movies_df["AvgRating"] = 0

        if "NumRatings" not in movies_df.columns:
            movies_df["NumRatings"] = 0

        if "WeightedRating" not in movies_df.columns:
            movies_df["WeightedRating"] = movies_df["AvgRating"]

        if "poster_url" not in movies_df.columns:
            movies_df["poster_url"] = ""

        if "backdrop_url" not in movies_df.columns:
            movies_df["backdrop_url"] = ""

        if "overview" not in movies_df.columns:
            movies_df["overview"] = ""

        # ----------------------------------------------------
        # CLEAN DATA TYPES
        # ----------------------------------------------------

        movies_df["MovieID"] = pd.to_numeric(
            movies_df["MovieID"],
            errors="coerce"
        )

        movies_df["AvgRating"] = pd.to_numeric(
            movies_df["AvgRating"],
            errors="coerce"
        ).fillna(0)

        movies_df["NumRatings"] = pd.to_numeric(
            movies_df["NumRatings"],
            errors="coerce"
        ).fillna(0)

        movies_df["WeightedRating"] = pd.to_numeric(
            movies_df["WeightedRating"],
            errors="coerce"
        ).fillna(0)

        movies_df["MovieID"] = movies_df["MovieID"].fillna(0).astype(int)
        movies_df["NumRatings"] = movies_df["NumRatings"].astype(int)

        # ----------------------------------------------------
        # CLEAN OPTIONAL TEXT FIELDS
        # ----------------------------------------------------

        movies_df["Title"] = movies_df["Title"].fillna("").astype(str)
        movies_df["Genres"] = movies_df["Genres"].fillna("").astype(str)

        movies_df["poster_url"] = (
            movies_df["poster_url"]
            .fillna("")
            .astype(str)
            .replace("nan", "")
        )

        movies_df["backdrop_url"] = (
            movies_df["backdrop_url"]
            .fillna("")
            .astype(str)
            .replace("nan", "")
        )

        movies_df["overview"] = (
            movies_df["overview"]
            .fillna("")
            .astype(str)
            .replace("nan", "")
        )

        # ----------------------------------------------------
        # PRE-COMPUTE SEARCH FIELDS
        # ----------------------------------------------------

        print("Pre-computing normalized titles for search...")

        def clean_title(title):
            match = re.match(
                r"(.+?)\s*\((\d{4})\)\s*$",
                str(title)
            )

            if match:
                return match.group(1).strip()

            return str(title).strip()

        movies_df["clean_title"] = movies_df["Title"].apply(
            clean_title
        )

        movies_df["norm_title"] = movies_df["clean_title"].apply(
            lambda x: re.sub(
                r"\s+",
                " ",
                re.sub(
                    r"[^a-z0-9\s]",
                    " ",
                    str(x).lower()
                )
            ).strip()
        )

        movies_df["norm_title_no_spaces"] = (
            movies_df["norm_title"]
            .str.replace(" ", "", regex=False)
        )

        # ----------------------------------------------------
        # POSTER STATISTICS
        # ----------------------------------------------------

        poster_mask = (
            movies_df["poster_url"]
            .str.strip()
            .str.startswith("http", na=False)
        )

        poster_count = int(poster_mask.sum())
        missing_count = len(movies_df) - poster_count

        print()
        print("DATASET STATUS")
        print("-" * 60)
        print(f"Total movies:             {len(movies_df):,}")
        print(f"Movies with posters:      {poster_count:,}")
        print(f"Movies without posters:   {missing_count:,}")

        # ----------------------------------------------------
        # SPECIFIC GODFATHER CHECK
        # ----------------------------------------------------

        godfather = movies_df[
            movies_df["MovieID"] == 858
        ]

        if not godfather.empty:

            godfather_row = godfather.iloc[0]

            print()
            print("GODFATHER CHECK")
            print("-" * 60)
            print(f"Title:       {godfather_row['Title']}")
            print(f"MovieID:     {godfather_row['MovieID']}")
            print(f"Poster URL:  {godfather_row['poster_url']}")

            if str(godfather_row["poster_url"]).startswith("http"):
                print("STATUS:      POSTER FOUND")
            else:
                print("STATUS:      POSTER MISSING")

        else:
            print()
            print("GODFATHER CHECK")
            print("-" * 60)
            print("The Godfather (MovieID 858) was not found.")

        print()
        print("=" * 60)
        print("KINO DATA LOADING COMPLETE")
        print("=" * 60)
        print()

    except Exception as ex:

        movies_df = None

        print()
        print("=" * 60)
        print("ERROR LOADING MOVIE DATA")
        print("=" * 60)
        print(str(ex))
        print("=" * 60)
        print()


# ============================================================
# MOOD SEARCH
# ============================================================

def map_mood_to_genres(query: str):

    query = str(query).lower()

    genres = set()

    for keyword, genre_list in MOOD_TO_GENRE.items():

        if re.search(
            r"\b" + re.escape(keyword) + r"\b",
            query
        ):
            genres.update(genre_list)

    return list(genres)


# ============================================================
# TITLE / YEAR
# ============================================================

def parse_title_year(title: str):

    match = re.match(
        r"(.+?)\s*\((\d{4})\)\s*$",
        str(title)
    )

    if match:
        return (
            match.group(1).strip(),
            match.group(2)
        )

    return str(title), ""


# ============================================================
# FUZZY MOVIE SEARCH
# ============================================================

def score_movie(norm_title, norm_q, query_tokens):

    if not norm_title or not norm_q:
        return 0

    # Exact match
    if norm_q == norm_title:
        return 100

    # Exact match ignoring spaces
    norm_title_no_spaces = norm_title.replace(" ", "")
    norm_q_no_spaces = norm_q.replace(" ", "")

    if norm_q_no_spaces == norm_title_no_spaces:
        return 95

    # Starts with query
    if (
        len(norm_q_no_spaces) >= 3
        and norm_title_no_spaces.startswith(norm_q_no_spaces)
    ):
        return 90

    if (
        len(norm_q) >= 3
        and norm_title.startswith(norm_q)
    ):
        return 90

    # --------------------------------------------------------
    # Token matching
    # --------------------------------------------------------

    matched_tokens = 0

    title_tokens = norm_title.split()

    for q_tok in query_tokens:

        if any(
            t_tok == q_tok
            or t_tok.startswith(q_tok)
            or (
                len(q_tok) >= 4
                and q_tok in t_tok
            )
            for t_tok in title_tokens
        ):
            matched_tokens += 1

    if (
        matched_tokens == len(query_tokens)
        and len(query_tokens) > 0
    ):
        return 85

    elif matched_tokens > 0:

        return 40 + (
            matched_tokens /
            len(query_tokens) *
            20
        )

    # --------------------------------------------------------
    # Fuzzy typo matching
    # --------------------------------------------------------

    if len(norm_q) > 3:

        sim = difflib.SequenceMatcher(
            None,
            norm_q,
            norm_title
        ).ratio()

        if sim > 0.75:
            return 60 + (sim * 20)

        sim_no_spaces = difflib.SequenceMatcher(
            None,
            norm_q_no_spaces,
            norm_title_no_spaces
        ).ratio()

        if sim_no_spaces > 0.75:
            return 60 + (sim_no_spaces * 20)

    return 0


# ============================================================
# MOVIE → API DICTIONARY
# ============================================================

def movie_to_dict(row):

    title, year = parse_title_year(
        row.get("Title", "")
    )

    poster_url = row.get("poster_url", "")
    backdrop_url = row.get("backdrop_url", "")
    overview = row.get("overview", "")

    # Prevent pandas NaN from reaching frontend
    if pd.isna(poster_url):
        poster_url = ""

    if pd.isna(backdrop_url):
        backdrop_url = ""

    if pd.isna(overview):
        overview = ""

    return {
        "MovieID": int(row["MovieID"]),

        "Title": title,

        "FullTitle": str(
            row.get("Title", "")
        ),

        "Year": year,

        "Genres": str(
            row.get("Genres", "")
        ).split("|"),

        "AvgRating": round(
            float(row.get("AvgRating", 0)),
            2
        ),

        "NumRatings": int(
            row.get("NumRatings", 0)
        ),

        "WeightedRating": round(
            float(
                row.get(
                    "WeightedRating",
                    0
                )
            ),
            2
        ),

        "poster_url": str(poster_url),

        "backdrop_url": str(backdrop_url),

        "overview": str(overview),
    }


# ============================================================
# API — MOVIE / MOOD SEARCH
# ============================================================

@app.get("/api/mood")
async def get_movies_by_mood(
    q: str = "",
    limit: int = 20
):

    if movies_df is None:
        raise HTTPException(
            status_code=503,
            detail="Data not loaded"
        )

    q = str(q).strip()

    # No query → top-rated movies
    if not q:

        top = (
            movies_df
            .sort_values(
                "WeightedRating",
                ascending=False
            )
            .head(limit)
        )

        return [
            movie_to_dict(row)
            for _, row in top.iterrows()
        ]

    # --------------------------------------------------------
    # Mood → genre
    # --------------------------------------------------------

    target_genres = map_mood_to_genres(q)

    # --------------------------------------------------------
    # Normalize search query
    # --------------------------------------------------------

    norm_q = re.sub(
        r"\s+",
        " ",
        re.sub(
            r"[^a-z0-9\s]",
            " ",
            q.lower()
        )
    ).strip()

    query_tokens = norm_q.split()

    # --------------------------------------------------------
    # Fuzzy title scores
    # --------------------------------------------------------

    scores = movies_df["norm_title"].apply(
        lambda x: score_movie(
            x,
            norm_q,
            query_tokens
        )
    )

    # --------------------------------------------------------
    # Add mood/genre relevance
    # --------------------------------------------------------

    if target_genres:

        genre_pattern = "|".join(
            re.escape(g)
            for g in target_genres
        )

        genre_mask = movies_df[
            "Genres"
        ].str.contains(
            genre_pattern,
            case=False,
            na=False,
            regex=True
        )

        final_scores = (
            scores
            + (
                genre_mask.astype(int)
                * 50
            )
        )

    else:

        final_scores = scores

    # --------------------------------------------------------
    # Filter
    # --------------------------------------------------------

    filtered = movies_df[
        final_scores > 0
    ].copy()

    if filtered.empty:
        return []

    filtered["search_score"] = (
        final_scores[
            final_scores > 0
        ]
    )

    # --------------------------------------------------------
    # Sort by relevance, then rating
    # --------------------------------------------------------

    sorted_movies = (
        filtered
        .sort_values(
            [
                "search_score",
                "WeightedRating"
            ],
            ascending=[
                False,
                False
            ]
        )
        .head(limit)
    )

    return [
        movie_to_dict(row)
        for _, row in sorted_movies.iterrows()
    ]


# ============================================================
# API — TRENDING
# ============================================================

@app.get("/api/trending")
async def get_trending(
    limit: int = 20
):

    if movies_df is None:
        raise HTTPException(
            status_code=503,
            detail="Data not loaded"
        )

    top = (
        movies_df
        .sort_values(
            "WeightedRating",
            ascending=False
        )
        .head(limit)
    )

    return [
        movie_to_dict(row)
        for _, row in top.iterrows()
    ]


# ============================================================
# API — GENRES
# ============================================================

@app.get("/api/genres")
async def get_genres():

    if movies_df is None:
        raise HTTPException(
            status_code=503,
            detail="Data not loaded"
        )

    all_genres = set()

    for genres_str in movies_df[
        "Genres"
    ].dropna():

        for genre in str(
            genres_str
        ).split("|"):

            genre = genre.strip()

            if genre:
                all_genres.add(genre)

    all_genres.discard(
        "(no genres listed)"
    )

    return sorted(
        list(all_genres)
    )


# ============================================================
# API — MOVIES BY GENRE
# ============================================================

@app.get("/api/movies/genre/{genre}")
async def get_movies_by_genre(
    genre: str,
    limit: int = 20
):

    if movies_df is None:
        raise HTTPException(
            status_code=503,
            detail="Data not loaded"
        )

    genre = str(genre).strip()

    filtered = movies_df[
        movies_df["Genres"].str.contains(
            re.escape(genre),
            case=False,
            na=False,
            regex=True
        )
    ]

    sorted_movies = (
        filtered
        .sort_values(
            "WeightedRating",
            ascending=False
        )
        .head(limit)
    )

    return [
        movie_to_dict(row)
        for _, row in sorted_movies.iterrows()
    ]


# ============================================================
# API — MOVIE DETAILS
# ============================================================

@app.get("/api/movies/{movie_id}")
async def get_movie_detail(
    movie_id: int
):

    if movies_df is None:
        raise HTTPException(
            status_code=503,
            detail="Data not loaded"
        )

    movie = movies_df[
        movies_df["MovieID"] == movie_id
    ]

    if movie.empty:
        raise HTTPException(
            status_code=404,
            detail="Movie not found"
        )

    row = movie.iloc[0]

    detail = movie_to_dict(row)
    detail["poster_url"] = str(row["poster_url"])

    # --------------------------------------------------------
    # Similar movies
    # --------------------------------------------------------

    movie_genres = str(
        row["Genres"]
    ).split("|")

    if movie_genres:

        valid_genres = [
            g.strip()
            for g in movie_genres[:2]
            if g.strip()
        ]

        if valid_genres:

            genre_pattern = "|".join(
                re.escape(g)
                for g in valid_genres
            )

            similar = movies_df[
                (
                    movies_df["Genres"]
                    .str.contains(
                        genre_pattern,
                        case=False,
                        na=False,
                        regex=True
                    )
                )
                &
                (
                    movies_df["MovieID"]
                    != movie_id
                )
            ]

            similar = (
                similar
                .sort_values(
                    "WeightedRating",
                    ascending=False
                )
                .head(12)
            )

            detail["similar"] = [
                movie_to_dict(r)
                for _, r in similar.iterrows()
            ]

    return detail


# ============================================================
# API — HERO MOVIE
# ============================================================

@app.get("/api/hero")
async def get_hero_movie():

    if movies_df is None:
        raise HTTPException(
            status_code=503,
            detail="Data not loaded"
        )

    # Prefer movies with backdrop
    candidates = movies_df[
        movies_df[
            "backdrop_url"
        ]
        .astype(str)
        .str.startswith(
            "http"
        )
    ]

    if candidates.empty:
        candidates = movies_df

    top = (
        candidates
        .sort_values(
            "WeightedRating",
            ascending=False
        )
        .head(20)
    )

    # Random hero from top 20
    hero = top.sample(
        1
    ).iloc[0]

    return movie_to_dict(hero)


# ============================================================
# FRONTEND
# ============================================================

FRONTEND_DIR = os.path.join(
    BASE_DIR,
    "frontend"
)


@app.get("/")
async def serve_index():

    index_path = os.path.join(
        FRONTEND_DIR,
        "index.html"
    )

    if not os.path.exists(index_path):

        raise HTTPException(
            status_code=404,
            detail="frontend/index.html not found"
        )

    return FileResponse(
        index_path
    )


# ============================================================
# STATIC FILES
# ============================================================

if os.path.exists(FRONTEND_DIR):

    app.mount(
        "/static",
        StaticFiles(
            directory=FRONTEND_DIR
        ),
        name="static"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )