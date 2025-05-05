import pickle
import streamlit as st
import requests
import pandas as pd
from io import BytesIO
from fpdf import FPDF
import os
import tempfile
from PIL import Image
from dotenv import load_dotenv

# Load API key from .env file
load_dotenv()
API_KEY = os.getenv("TMDB_API_KEY")

# ------------------ API Helpers ------------------ #

def fetch_movie_details(movie_id):
    try:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={API_KEY}&language=en-US&append_to_response=credits"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        poster = f"https://image.tmdb.org/t/p/w500/{data['poster_path']}" if data.get('poster_path') else "https://via.placeholder.com/500x750?text=No+Image"
        genres = ", ".join([genre['name'] for genre in data.get('genres', [])])
        rating = data.get('vote_average', 'N/A')
        cast_list = [cast['name'] for cast in data.get('credits', {}).get('cast', [])][:5]
        cast = ", ".join(cast_list)

        return poster, genres, rating, cast
    except Exception as e:
        print(f"Error fetching details: {e}")
        return "https://via.placeholder.com/500x750?text=Error", "N/A", "N/A", "N/A"

def fetch_trailer(movie_id):
    try:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={API_KEY}&language=en-US"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        for video in data.get('results', []):
            if video['type'] == 'Trailer' and video['site'] == 'YouTube':
                return f"https://www.youtube.com/watch?v={video['key']}"
        return "https://youtube.com"
    except:
        return "https://youtube.com"

# ------------------ Recommendation Logic ------------------ #

def recommend(movie, num_results=10):
    index = movies[movies['title'] == movie].index[0]
    distances = sorted(list(enumerate(similarity[index])), reverse=True, key=lambda x: x[1])

    recommendations = []

    for i in distances[1:num_results + 1]:
        movie_id = movies.iloc[i[0]].movie_id
        title = movies.iloc[i[0]].title
        poster, genres, rating, cast = fetch_movie_details(movie_id)
        trailer = fetch_trailer(movie_id)

        recommendations.append({
            "Title": title,
            "Poster": poster,
            "Genres": genres,
            "Rating": rating,
            "Cast": cast,
            "Trailer": trailer
        })

    return recommendations

def filter_movies_by_criteria(genre='', cast='', min_rating=0.0, num_results=10):
    matched = []
    for i in range(len(movies)):
        movie_id = movies.iloc[i].movie_id
        title = movies.iloc[i].title
        poster, genres, rating, cast_list = fetch_movie_details(movie_id)
        trailer = fetch_trailer(movie_id)

        if genre.lower() in genres.lower() and cast.lower() in cast_list.lower():
            try:
                if float(rating) >= min_rating:
                    matched.append({
                        "Title": title,
                        "Poster": poster,
                        "Genres": genres,
                        "Rating": rating,
                        "Cast": cast_list,
                        "Trailer": trailer
                    })
                    if len(matched) >= num_results:
                        break
            except:
                continue

    return matched

# ------------------ PDF Export ------------------ #

def create_pdf(recommendations):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Movie Recommendations", ln=True, align='C')
    pdf.ln(10)

    for movie in recommendations:
        try:
            response = requests.get(movie['Poster'], stream=True)
            if response.status_code == 200:
                temp_img = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                with open(temp_img.name, 'wb') as f:
                    f.write(response.content)

                img = Image.open(temp_img.name)
                img = img.resize((80, 120))
                img.save(temp_img.name)

                pdf.image(temp_img.name, x=10, y=pdf.get_y(), w=40)
                os.unlink(temp_img.name)

        except Exception as e:
            print(f"Failed to load image: {e}")

        pdf.set_xy(55, pdf.get_y())
        pdf.multi_cell(0, 10, txt=(
            f"Title: {movie['Title']}\n"
            f"Genres: {movie['Genres']}\n"
            f"Rating: {movie['Rating']}\n"
            f"Cast: {movie['Cast']}\n"
            f"Trailer: {movie['Trailer']}"
        ))
        pdf.ln(10)

    return pdf.output(dest='S').encode('latin-1')

# ------------------ Streamlit UI ------------------ #

st.set_page_config(page_title="🎬 Movie Recommender", layout="wide")
st.header('🎥 Movie Recommendation System')

movies = pickle.load(open('movie_list.pkl', 'rb'))
similarity = pickle.load(open('similarity.pkl', 'rb'))

movie_list = movies['title'].values
num_results = st.sidebar.slider("Number of Recommendations", 1, 20, 5)

st.sidebar.markdown("---")
st.sidebar.subheader("🔎 Search by Genre/Cast/Rating")

genre_filter = st.sidebar.text_input("🎭 Genre contains:")
cast_filter = st.sidebar.text_input("👥 Cast contains:")
min_rating = st.sidebar.slider("⭐ Minimum Rating", 0.0, 10.0, 0.0, step=0.1)

filtered_results = []

if genre_filter or cast_filter or min_rating > 0:
    filtered_results = filter_movies_by_criteria(genre_filter, cast_filter, min_rating, num_results)
    if filtered_results:
        st.subheader("🔍 Filtered Results")
        cols = st.columns(min(len(filtered_results), 5))
        for i, movie in enumerate(filtered_results):
            with cols[i % 5]:
                st.image(movie['Poster'])
                st.markdown(f"**{movie['Title']}**")
                st.markdown(f"🎭 **Genres:** {movie['Genres']}")
                st.markdown(f"⭐ **Rating:** {movie['Rating']}")
                st.markdown(f"👥 **Cast:** {movie['Cast']}")
                st.markdown(f"[🎬 Trailer]({movie['Trailer']})", unsafe_allow_html=True)

        pdf_data = create_pdf(filtered_results)
        st.download_button("⬇️ Download Filtered Results as PDF", data=pdf_data, file_name="filtered_recommendations.pdf", mime='application/pdf')
    else:
        st.warning("No movies matched your filters.")

st.markdown("---")
selected_movie = st.selectbox("🎞️ Or select a movie to get similar recommendations", movie_list)
if st.button('🎯 Show Recommendations'):
    results = recommend(selected_movie, num_results)
    st.subheader("🎬 Recommended Movies")
    cols = st.columns(min(len(results), 5))
    for i, movie in enumerate(results):
        with cols[i % 5]:
            st.image(movie['Poster'])
            st.markdown(f"**{movie['Title']}**")
            st.markdown(f"🎭 **Genres:** {movie['Genres']}")
            st.markdown(f"⭐ **Rating:** {movie['Rating']}")
            st.markdown(f"👥 **Cast:** {movie['Cast']}")
            st.markdown(f"[🎬 Trailer]({movie['Trailer']})", unsafe_allow_html=True)

    pdf_data = create_pdf(results)
    st.download_button("⬇️ Download Recommendations as PDF", data=pdf_data, file_name="movie_recommendations.pdf", mime='application/pdf')
