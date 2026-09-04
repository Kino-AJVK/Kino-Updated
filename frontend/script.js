// ═══════════════════════════════════════════════════════
//  Kino — Netflix-Themed Movie Recommendation UI
// ═══════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    // ─── DOM Elements ───
    const searchBtn = document.getElementById('search-btn');
    const moodInput = document.getElementById('mood-input');
    const moodChips = document.querySelectorAll('.mood-chip');
    const navbar = document.getElementById('navbar');
    const navLinks = document.querySelectorAll('.nav-links a[data-target]');
    const homeLink = document.querySelector('.nav-links a[data-target="#top"]');

    navLinks.forEach(link => {
        link.addEventListener('click', (event) => {
            event.preventDefault();
            scrollTo(link.dataset.target);
            document.querySelectorAll('.nav-links a').forEach(item => item.classList.remove('active'));
            link.classList.add('active');
        });
    });

    const logoLink = document.querySelector('.logo');
    if (logoLink) {
        logoLink.addEventListener('click', (event) => {
            event.preventDefault();
            scrollToTop();
            document.querySelectorAll('.nav-links a').forEach(item => item.classList.remove('active'));
            if (homeLink) homeLink.classList.add('active');
        });
    }

    // ─── Initialize App ───
    loadHero();
    loadTrending();
    loadGenres();
    loadGenreRow('Action', 'action-track');
    loadGenreRow('Drama', 'drama-track');
    loadGenreRow('Comedy', 'comedy-track');
    loadGenreRow('Sci-Fi', 'scifi-track');
    renderFavorites();

    // ─── Navbar scroll effect ───
    window.addEventListener('scroll', () => {
        navbar.classList.toggle('scrolled', window.scrollY > 50);
    });

    // ─── Search handlers ───
    searchBtn.addEventListener('click', () => searchByMood());
    moodInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') searchByMood();
    });

    // ─── Mood chip click ───
    moodChips.forEach(chip => {
        chip.addEventListener('click', () => {
            const mood = chip.dataset.mood;
            moodInput.value = mood;
            searchByMood();
        });
    });
});


// ═══════════════════════════════════════════════════════
//  FAVORITES
// ═══════════════════════════════════════════════════════

window.movieCache = window.movieCache || {};

function getFavorites() {
    try {
        const favs = localStorage.getItem('kino_favorites');
        return favs ? JSON.parse(favs) : [];
    } catch (e) {
        return [];
    }
}

function saveFavorites(favs) {
    localStorage.setItem('kino_favorites', JSON.stringify(favs));
}

function toggleFavorite(event, movieId) {
    event.stopPropagation();

    let favs = getFavorites();
    const isFav = favs.some(f => f.MovieID === movieId);

    if (isFav) {
        favs = favs.filter(f => f.MovieID !== movieId);
    } else {
        const movie = window.movieCache[movieId];
        if (movie) favs.push(movie);
    }

    saveFavorites(favs);

    const newIsFav = !isFav;

    if (newIsFav) {
        const navFav = document.querySelector('.nav-links a[data-target="#favorites"]');
        if (navFav) {
            navFav.classList.remove('nav-anim-pop');
            void navFav.offsetWidth; // trigger reflow
            navFav.classList.add('nav-anim-pop');
            navFav.addEventListener('animationend', () => navFav.classList.remove('nav-anim-pop'), { once: true });
        }
    }

    document.querySelectorAll(`.favorite-btn[data-id="${movieId}"]`).forEach(btn => {
        // Reset animations
        btn.classList.remove('anim-pop', 'anim-unpop');
        void btn.offsetWidth; // trigger reflow

        let iconSpan = btn.querySelector('.star-icon');
        if (!iconSpan) {
            btn.innerHTML = `<span class="star-icon"></span>`;
            iconSpan = btn.querySelector('.star-icon');
        }

        if (newIsFav) {
            btn.classList.add('active', 'anim-pop');
            iconSpan.textContent = '★';
        } else {
            btn.classList.remove('active');
            btn.classList.add('anim-unpop');
            iconSpan.textContent = '☆';
        }

        btn.addEventListener('animationend', () => {
            btn.classList.remove('anim-pop', 'anim-unpop');
        }, { once: true });
    });

    // Dynamically add/remove from Favorites grid instead of re-rendering everything
    const section = document.getElementById('favorites');
    const grid = document.getElementById('favorites-grid');
    if (section && grid) {
        if (newIsFav) {
            // Remove empty state if present
            const emptyState = grid.querySelector('.empty-state');
            if (emptyState) emptyState.remove();

            section.style.display = 'block';
            const movie = window.movieCache[movieId];
            if (movie) {
                const newCard = createMovieCard(movie, 0);
                newCard.classList.remove('fade-in');
                newCard.classList.add('fav-card-enter');
                newCard.style.animationDelay = '0s';
                grid.appendChild(newCard);
            }
        } else {
            // Find and remove the card from the favorites grid
            const btnInGrid = grid.querySelector(`.favorite-btn[data-id="${movieId}"]`);
            if (btnInGrid) {
                const cardToRemove = btnInGrid.closest('.movie-card');
                if (cardToRemove) {
                    cardToRemove.classList.add('fav-card-exit');
                    setTimeout(() => {
                        cardToRemove.remove();
                        if (grid.querySelectorAll('.movie-card').length === 0) {
                            grid.innerHTML = `
                                <div class="empty-state" style="grid-column: 1 / -1;">
                                    <div class="icon">⭐</div>
                                    <h3>No favorites yet</h3>
                                    <p>Save movies you love by clicking the star.</p>
                                </div>`;
                        }
                    }, 350);
                }
            }
        }
    }
}

function renderFavorites() {
    const favs = getFavorites();
    const section = document.getElementById('favorites');
    const grid = document.getElementById('favorites-grid');

    if (!section || !grid) return;

    section.style.display = 'block';
    grid.innerHTML = '';

    if (favs.length === 0) {
        grid.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <div class="icon">⭐</div>
                <h3>No favorites yet</h3>
                <p>Save movies you love by clicking the star.</p>
            </div>`;
        return;
    }

    favs.forEach((m, i) => grid.appendChild(createMovieCard(m, i)));
}

// ═══════════════════════════════════════════════════════
//  API CALLS
// ═══════════════════════════════════════════════════════

async function fetchAPI(endpoint) {
    try {
        const res = await fetch(endpoint);
        if (!res.ok) throw new Error(`API Error: ${res.status}`);
        return await res.json();
    } catch (err) {
        console.error('API Error:', err);
        return null;
    }
}


// ═══════════════════════════════════════════════════════
//  HERO BANNER
// ═══════════════════════════════════════════════════════

async function loadHero() {
    const movie = await fetchAPI('/api/hero');
    if (!movie) return;

    const heroImg = document.getElementById('hero-img');
    const heroTitle = document.getElementById('hero-title');
    const heroRating = document.getElementById('hero-rating');
    const heroYear = document.getElementById('hero-year');
    const heroGenre = document.getElementById('hero-genre');
    const heroOverview = document.getElementById('hero-overview');
    const heroBtn = document.getElementById('hero-details-btn');

    if (movie.backdrop_url) {
        heroImg.src = movie.backdrop_url;
    } else if (movie.poster_url) {
        heroImg.src = movie.poster_url;
    }

    heroTitle.textContent = movie.Title;
    heroRating.textContent = `★ ${movie.AvgRating}`;
    heroYear.textContent = movie.Year;
    heroGenre.textContent = movie.Genres.slice(0, 3).join(' • ');
    heroOverview.textContent = movie.overview || '';
    heroBtn.onclick = () => openModal(movie.MovieID);
}


// ═══════════════════════════════════════════════════════
//  TRENDING
// ═══════════════════════════════════════════════════════

async function loadTrending() {
    const movies = await fetchAPI('/api/trending?limit=20');
    if (!movies) return;
    const track = document.getElementById('trending-track');
    track.innerHTML = '';
    movies.forEach((m, i) => track.appendChild(createMovieCard(m, i)));
}


// ═══════════════════════════════════════════════════════
//  GENRES
// ═══════════════════════════════════════════════════════

async function loadGenres() {
    const genres = await fetchAPI('/api/genres');
    if (!genres) return;

    const container = document.getElementById('genre-filters');
    container.innerHTML = '';

    // Add "All" button
    const allBtn = document.createElement('button');
    allBtn.className = 'genre-btn active';
    allBtn.textContent = 'All';
    allBtn.onclick = () => {
        document.querySelectorAll('.genre-btn').forEach(b => b.classList.remove('active'));
        allBtn.classList.add('active');
        document.getElementById('genre-results').style.display = 'none';
    };
    container.appendChild(allBtn);

    genres.forEach(genre => {
        const btn = document.createElement('button');
        btn.className = 'genre-btn';
        btn.textContent = genre;
        btn.onclick = () => selectGenre(genre, btn);
        container.appendChild(btn);
    });
}

async function selectGenre(genre, btn) {
    document.querySelectorAll('.genre-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    const movies = await fetchAPI(`/api/movies/genre/${encodeURIComponent(genre)}?limit=20`);
    if (!movies) return;

    const section = document.getElementById('genre-results');
    const title = document.getElementById('genre-results-title');
    const track = document.getElementById('genre-results-track');

    title.textContent = `Top ${genre} Movies`;
    track.innerHTML = '';
    movies.forEach((m, i) => track.appendChild(createMovieCard(m, i)));
    section.style.display = 'block';
    scrollTo('#genre-results');
}

async function loadGenreRow(genre, trackId) {
    const movies = await fetchAPI(`/api/movies/genre/${encodeURIComponent(genre)}?limit=20`);
    if (!movies) return;
    const track = document.getElementById(trackId);
    track.innerHTML = '';
    movies.forEach((m, i) => track.appendChild(createMovieCard(m, i)));
}


// ═══════════════════════════════════════════════════════
//  MOOD SEARCH
// ═══════════════════════════════════════════════════════

async function searchByMood() {
    const query = document.getElementById('mood-input').value.trim();
    const section = document.getElementById('mood-results');
    const title = document.getElementById('mood-results-title');
    const grid = document.getElementById('mood-results-grid');

    if (!query) return;

    title.textContent = `Searching for "${query}"...`;
    grid.innerHTML = '<div class="loader"></div>';
    section.style.display = 'block';

    const movies = await fetchAPI(`/api/mood?q=${encodeURIComponent(query)}&limit=24`);

    if (!movies || movies.length === 0) {
        grid.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <div class="icon">🎬</div>
                <h3>No movies found</h3>
                <p>Try different keywords like "happy", "scary", or "space adventure"</p>
            </div>`;
        title.textContent = `No results for "${query}"`;
        return;
    }

    title.textContent = `Movies for "${query}" mood`;
    grid.innerHTML = '';
    movies.forEach((m, i) => grid.appendChild(createMovieCard(m, i)));

    scrollTo('#mood-results');
}


// ═══════════════════════════════════════════════════════
//  MOVIE CARD COMPONENT
// ═══════════════════════════════════════════════════════

function createMovieCard(movie, index) {
    window.movieCache[movie.MovieID] = movie;

    const card = document.createElement('div');
    card.className = 'movie-card fade-in';
    card.style.animationDelay = `${index * 0.04}s`;
    card.onclick = () => openModal(movie.MovieID);

    const posterURL = movie.poster_url ? String(movie.poster_url).trim() : '';

    const posterHTML = posterURL
        ? `<img class="poster-img" src="${posterURL}" alt="${movie.Title}" loading="lazy">`
        : `<div class="poster-placeholder">🎬</div>`;

    const genreTags = (movie.Genres || []).slice(0, 3)
        .map(g => `<span class="card-genre-tag">${g}</span>`).join('');

    const isFav = getFavorites().some(f => f.MovieID === movie.MovieID);
    const favBtnHTML = `<button class="favorite-btn ${isFav ? 'active' : ''}" data-id="${movie.MovieID}" onclick="toggleFavorite(event, ${movie.MovieID})"><span class="star-icon">${isFav ? '★' : '☆'}</span></button>`;

    card.innerHTML = `
        <div class="poster-wrap">
            ${posterHTML}
            ${favBtnHTML}
            <div class="rating-badge">★ ${movie.AvgRating}</div>
            <div class="card-overlay">
                <div class="card-title">${movie.Title}</div>
                <div class="card-meta">
                    <span class="card-rating">★ ${movie.AvgRating}</span>
                    <span class="card-year">${movie.Year || ''}</span>
                </div>
                <div class="card-genres">${genreTags}</div>
            </div>
        </div>
    `;

    return card;
}


// ═══════════════════════════════════════════════════════
//  MOVIE DETAIL MODAL
// ═══════════════════════════════════════════════════════

async function openModal(movieId) {
    const movie = await fetchAPI(`/api/movies/${movieId}`);
    if (!movie) return;

    const backdrop = document.getElementById('modal-backdrop');
    document.getElementById('modal-title').textContent = movie.Title;
    document.getElementById('modal-rating').textContent = `★ ${movie.AvgRating}`;
    document.getElementById('modal-votes').textContent = `(${movie.NumRatings.toLocaleString()} ratings)`;
    document.getElementById('modal-year').textContent = movie.Year;

    // Backdrop image
    const modalImg = document.getElementById('modal-img');
    if (movie.backdrop_url) {
        modalImg.src = movie.backdrop_url;
        modalImg.style.display = 'block';
    } else if (movie.poster_url) {
        modalImg.src = movie.poster_url;
        modalImg.style.display = 'block';
    } else {
        modalImg.style.display = 'none';
    }

    // Genres
    const genresContainer = document.getElementById('modal-genres');
    genresContainer.innerHTML = (movie.Genres || [])
        .map(g => `<span class="modal-genre-tag">${g}</span>`).join('');

    // Overview
    document.getElementById('modal-overview').textContent = movie.overview || 'No overview available.';

    // Similar movies
    const similarTrack = document.getElementById('modal-similar');
    similarTrack.innerHTML = '';
    if (movie.similar && movie.similar.length > 0) {
        movie.similar.forEach((m, i) => similarTrack.appendChild(createMovieCard(m, i)));
    } else {
        similarTrack.innerHTML = '<p style="color: var(--text-muted); font-size: 0.85rem;">No similar movies found</p>';
    }

    backdrop.classList.add('visible');
    document.body.style.overflow = 'hidden';
}

function closeModal(event) {
    if (event.target === document.getElementById('modal-backdrop')) {
        closeModalForce();
    }
}

function closeModalForce() {
    document.getElementById('modal-backdrop').classList.remove('visible');
    document.body.style.overflow = '';
}

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModalForce();
});


// ═══════════════════════════════════════════════════════
//  CAROUSEL SCROLL
// ═══════════════════════════════════════════════════════

function scrollCarousel(trackId, direction) {
    const track = document.getElementById(trackId);
    const scrollAmount = track.clientWidth * 0.75;
    track.scrollBy({ left: direction * scrollAmount, behavior: 'smooth' });
}


// ═══════════════════════════════════════════════════════
//  NAVIGATION HELPERS
// ═══════════════════════════════════════════════════════

function toggleSearch() {
    const searchBox = document.getElementById('nav-search');
    searchBox.classList.toggle('open');
    if (searchBox.classList.contains('open')) {
        document.getElementById('nav-search-input').focus();
    }
}

function navSearch() {
    const query = document.getElementById('nav-search-input').value.trim();
    if (query) {
        document.getElementById('mood-input').value = query;
        searchByMood();
        document.getElementById('nav-search').classList.remove('open');
    }
}

function scrollToTop() {
    window.scroll({ top: 0, behavior: 'smooth' });
}

// Generic scroll-to helper
function scrollTo(selector) {
    if (selector === '#top' || selector === 'body') {
        window.scroll({ top: 0, behavior: 'smooth' });
        return;
    }

    const el = document.querySelector(selector);
    if (el) {
        const navbar = document.getElementById('navbar');
        const navbarHeight = navbar ? navbar.offsetHeight : 0;
        const smallSpacing = 20;

        const elementPosition = el.getBoundingClientRect().top + window.scrollY;
        const offsetPosition = elementPosition - navbarHeight - smallSpacing;

        window.scroll({
            top: offsetPosition,
            behavior: 'smooth'
        });
    }
}
