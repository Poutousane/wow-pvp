import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import time
from datetime import datetime, timedelta

# Configuration de la page Streamlit
st.set_page_config(
    page_title="WoW PVP Stats Tracker",
    page_icon="⚔️",
    layout="wide"
)

# Titre et description de l'application
st.title("⚔️ World of Warcraft PVP Stats Tracker")
st.markdown("Recherchez les statistiques PVP d'un joueur sur World of Warcraft Retail (The War Within)")

# Récupération sécurisée des identifiants de l'API Blizzard
try:
    # Méthode préférée : utiliser st.secrets
    client_id = st.secrets["blizzard_api"]["client_id"]
    client_secret = st.secrets["blizzard_api"]["client_secret"]
except Exception as e:
    st.error("⚠️ Configuration API manquante. Veuillez configurer les secrets Blizzard API.")
    st.stop()


# Fonction pour obtenir un token d'accès
@st.cache_data(ttl=3600)  # Cache le token pendant 1 heure
def get_access_token():
    token_url = "https://oauth.battle.net/token"
    data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret
    }

    try:
        response = requests.post(token_url, data=data)
        if response.status_code == 200:
            return response.json()['access_token']
        else:
            st.error(f"Erreur d'authentification: {response.status_code}")
            st.error(response.text)
            return None
    except Exception as e:
        st.error(f"Erreur de connexion à l'API Blizzard: {str(e)}")
        return None


# Fonction pour obtenir les données PVP
def get_wow_pvp_data(character_name, realm, region="eu"):
    """Fonction qui récupère les données PVP d'un personnage via l'API Blizzard"""
    try:
        with st.spinner(f"Recherche de {character_name} sur {realm}..."):
            # Obtenir un token d'accès
            access_token = get_access_token()
            if not access_token:
                return None

            # Normaliser le nom du serveur et du personnage
            realm_slug = realm.lower().replace("'", "").replace(" ", "-")
            character_slug = character_name.lower()

            # URL de base pour l'API
            base_url = f"https://{region}.api.blizzard.com/profile/wow/character/{realm_slug}/{character_slug}"
            headers = {"Authorization": f"Bearer {access_token}"}

            # 1. Obtenir les informations du personnage
            char_url = f"{base_url}?namespace=profile-{region}&locale=fr_FR"
            char_response = requests.get(char_url, headers=headers)

            if char_response.status_code != 200:
                st.error(f"Personnage non trouvé: {char_response.status_code}")
                return None

            char_data = char_response.json()

            # 2. Obtenir les données PVP
            pvp_url = f"{base_url}/pvp-summary?namespace=profile-{region}&locale=fr_FR"
            pvp_response = requests.get(pvp_url, headers=headers)

            if pvp_response.status_code != 200:
                st.warning("Données PVP non disponibles")
                pvp_data = {}
            else:
                pvp_data = pvp_response.json()

            # 3. Structurer les données
            result = {
                "character": {
                    "name": char_data.get("name", character_name),
                    "realm": char_data.get("realm", {}).get("name", realm),
                    "level": char_data.get("level", 0),
                    "class": char_data.get("character_class", {}).get("name", "Inconnu"),
                    "race": char_data.get("race", {}).get("name", "Inconnu"),
                    "faction": char_data.get("faction", {}).get("name", "Inconnu"),
                    "thumbnail": char_data.get("media", {}).get("avatar_url", "")
                },
                "honor_level": pvp_data.get("honor_level", 0),
                "honor_this_season": pvp_data.get("honor", 0)
            }

            # Traiter les données des brackets PVP
            arena_2v2 = None
            arena_3v3 = None
            rbg = None

            # Parcourir les brackets disponibles
            for bracket in pvp_data.get("brackets", []):
                bracket_type = bracket.get("type", {}).get("type", "")

                # Extraire les statistiques
                season_stats = bracket.get("season_match_statistics", {})
                weekly_stats = bracket.get("weekly_match_statistics", {})

                bracket_data = {
                    "rating": bracket.get("rating", 0),
                    "season_played": season_stats.get("played", 0),
                    "season_won": season_stats.get("won", 0),
                    "season_lost": season_stats.get("lost", 0),
                    "weekly_played": weekly_stats.get("played", 0),
                    "weekly_won": weekly_stats.get("won", 0),
                    "weekly_lost": weekly_stats.get("lost", 0),
                }

                if bracket_type == "ARENA_2v2":
                    arena_2v2 = bracket_data
                elif bracket_type == "ARENA_3v3":
                    arena_3v3 = bracket_data
                elif bracket_type == "BATTLEGROUNDS":
                    rbg = bracket_data

            # Si les données ne sont pas trouvées, utiliser des valeurs par défaut
            default_data = {
                "rating": 0,
                "season_played": 0,
                "season_won": 0,
                "season_lost": 0,
                "weekly_played": 0,
                "weekly_won": 0,
                "weekly_lost": 0,
            }

            result["arena_2v2"] = arena_2v2 if arena_2v2 else default_data
            result["arena_3v3"] = arena_3v3 if arena_3v3 else default_data
            result["battlegrounds"] = rbg if rbg else default_data

            # Calculer les pourcentages de victoire
            for bracket_name in ["arena_2v2", "arena_3v3", "battlegrounds"]:
                bracket = result[bracket_name]

                # Pourcentage de victoire saisonnier
                season_played = bracket["season_played"]
                if season_played > 0:
                    bracket["season_winrate"] = round((bracket["season_won"] / season_played) * 100, 1)
                else:
                    bracket["season_winrate"] = 0

                # Pourcentage de victoire hebdomadaire
                weekly_played = bracket["weekly_played"]
                if weekly_played > 0:
                    bracket["weekly_winrate"] = round((bracket["weekly_won"] / weekly_played) * 100, 1)
                else:
                    bracket["weekly_winrate"] = 0

            return result

    except Exception as e:
        st.error(f"Erreur lors de la récupération des données: {str(e)}")
        return None


# Fonction pour créer un diagramme circulaire des victoires/défaites
def create_win_loss_chart(won, lost, title):
    if won + lost == 0:
        return None

    df = pd.DataFrame({
        'Résultat': ['Victoires', 'Défaites'],
        'Matchs': [won, lost]
    })

    fig = px.pie(
        df,
        values='Matchs',
        names='Résultat',
        color='Résultat',
        color_discrete_map={'Victoires': 'green', 'Défaites': 'red'},
        title=title
    )
    fig.update_traces(textinfo='percent+value')
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=0, xanchor="center", x=0.5)
    )

    return fig


# Interface de recherche
with st.container():
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        character_name = st.text_input("Nom du personnage", value="", placeholder="Entrez le nom du personnage")

    with col2:
        realm = st.text_input("Serveur", value="", placeholder="Entrez le nom du serveur")

    with col3:
        region = st.selectbox("Région", options=["eu", "us", "kr", "tw"], index=0)
        search_button = st.button("Rechercher", type="primary", use_container_width=True)


# Fonction pour afficher les informations du personnage
def display_character_info(data):
    char_info = data["character"]

    # Section héro avec l'avatar et les informations de base
    col1, col2 = st.columns([1, 3])

    with col1:
        thumbnail = char_info.get("thumbnail", "")
        if thumbnail:
            st.image(thumbnail, width=100)
        else:
            st.image("https://render.worldofwarcraft.com/eu/icons/56/inv_misc_questionmark.jpg", width=100)

    with col2:
        st.subheader(f"{char_info['name']}")
        st.write(f"**Niveau:** {char_info['level']}")
        st.write(f"**Classe:** {char_info['class']}")
        st.write(f"**Race:** {char_info['race']}")
        st.write(f"**Faction:** {char_info['faction']}")
        st.write(f"**Serveur:** {char_info['realm']}")

    # Informations PVP supplémentaires
    st.write(f"**Niveau d'honneur:** {data['honor_level']}")

    # Tableau récapitulatif des ratings
    ratings_data = {
        "Bracket": ["Arena 2v2", "Arena 3v3", "Champ de bataille coté"],
        "Rating": [
            data["arena_2v2"]["rating"],
            data["arena_3v3"]["rating"],
            data["battlegrounds"]["rating"]
        ]
    }
    ratings_df = pd.DataFrame(ratings_data)

    # Affichage des ratings sur une même ligne
    st.subheader("Ratings")
    cols = st.columns(3)
    for i, bracket in enumerate(["Arena 2v2", "Arena 3v3", "Champ de bataille coté"]):
        with cols[i]:
            rating = ratings_df.loc[ratings_df["Bracket"] == bracket, "Rating"].values[0]
            st.metric(bracket, rating)

    # Onglets pour les différents types de PVP
    tab1, tab2, tab3 = st.tabs(["Arena 2v2", "Arena 3v3", "Champ de bataille coté"])

    with tab1:
        display_bracket_stats(data["arena_2v2"], "Arena 2v2")

    with tab2:
        display_bracket_stats(data["arena_3v3"], "Arena 3v3")

    with tab3:
        display_bracket_stats(data["battlegrounds"], "Champ de bataille coté")


# Fonction pour afficher les statistiques d'un bracket
def display_bracket_stats(bracket_data, bracket_name):
    # Diviser en deux colonnes: statistiques de saison et hebdomadaires
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Statistiques de saison")

        # Métriques
        season_played = bracket_data["season_played"]
        season_won = bracket_data["season_won"]
        season_lost = bracket_data["season_lost"]
        season_winrate = bracket_data["season_winrate"]

        # Affichage des statistiques
        st.metric("Matchs joués", season_played)
        st.metric("Victoires", season_won)
        st.metric("Défaites", season_lost)
        st.metric("Pourcentage de victoire", f"{season_winrate}%")

        # Diagramme
        if season_played > 0:
            fig = create_win_loss_chart(
                season_won,
                season_lost,
                f"Ratio de victoires en {bracket_name} (Saison)"
            )
            if fig:
                st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Statistiques hebdomadaires")

        # Métriques
        weekly_played = bracket_data["weekly_played"]
        weekly_won = bracket_data["weekly_won"]
        weekly_lost = bracket_data["weekly_lost"]
        weekly_winrate = bracket_data["weekly_winrate"]

        # Affichage des statistiques
        st.metric("Matchs joués", weekly_played)
        st.metric("Victoires", weekly_won)
        st.metric("Défaites", weekly_lost)
        st.metric("Pourcentage de victoire", f"{weekly_winrate}%")

        # Diagramme
        if weekly_played > 0:
            fig = create_win_loss_chart(
                weekly_won,
                weekly_lost,
                f"Ratio de victoires en {bracket_name} (Hebdomadaire)"
            )
            if fig:
                st.plotly_chart(fig, use_container_width=True)


# Recherche et affichage des résultats
if search_button and character_name and realm:
    # Mise en cache des résultats pour éviter les requêtes répétées
    @st.cache_data(ttl=300)  # Cache pour 5 minutes
    def cached_search(name, realm, region):
        return get_wow_pvp_data(name, realm, region)


    pvp_data = cached_search(character_name, realm, region)

    if pvp_data:
        display_character_info(pvp_data)
    else:
        st.error(
            "Impossible de trouver les données PVP pour ce personnage. Vérifiez que le nom et le serveur sont corrects.")

# Pied de page
st.markdown("---")
st.markdown("Développé avec ❤️ pour la communauté WoW. Cette application n'est pas affiliée à Blizzard Entertainment.")
