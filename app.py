import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import time
from datetime import datetime, timedelta



    response = requests.post(token_url, data=data)
    if response.status_code == 200:
        return response.json()['access_token']
    else:
        st.error(f"Erreur d'authentification: {response.status_code}")
        st.error(response.text)
        return None


# Fonction pour obtenir les données PVP avec l'API réelle
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
            brackets = pvp_data.get("pvp_brackets", {})

            # Arena 2v2
            arena_2v2 = next((b for b in pvp_data.get("brackets", []) if b.get("id") == "ARENA_2v2"), {})
            result["arena_2v2"] = {
                "rating": arena_2v2.get("rating", 0),
                "season_played": arena_2v2.get("season_match_statistics", {}).get("played", 0),
                "season_won": arena_2v2.get("season_match_statistics", {}).get("won", 0),
                "season_lost": arena_2v2.get("season_match_statistics", {}).get("lost", 0),
                "weekly_played": arena_2v2.get("weekly_match_statistics", {}).get("played", 0),
                "weekly_won": arena_2v2.get("weekly_match_statistics", {}).get("won", 0),
                "weekly_lost": arena_2v2.get("weekly_match_statistics", {}).get("lost", 0),
            }

            # Arena 3v3
            arena_3v3 = next((b for b in pvp_data.get("brackets", []) if b.get("id") == "ARENA_3v3"), {})
            result["arena_3v3"] = {
                "rating": arena_3v3.get("rating", 0),
                "season_played": arena_3v3.get("season_match_statistics", {}).get("played", 0),
                "season_won": arena_3v3.get("season_match_statistics", {}).get("won", 0),
                "season_lost": arena_3v3.get("season_match_statistics", {}).get("lost", 0),
                "weekly_played": arena_3v3.get("weekly_match_statistics", {}).get("played", 0),
                "weekly_won": arena_3v3.get("weekly_match_statistics", {}).get("won", 0),
                "weekly_lost": arena_3v3.get("weekly_match_statistics", {}).get("lost", 0),
            }

            # RBG
            rbg = next((b for b in pvp_data.get("brackets", []) if b.get("id") == "BATTLEGROUNDS"), {})
            result["battlegrounds"] = {
                "rating": rbg.get("rating", 0),
                "season_played": rbg.get("season_match_statistics", {}).get("played", 0),
                "season_won": rbg.get("season_match_statistics", {}).get("won", 0),
                "season_lost": rbg.get("season_match_statistics", {}).get("lost", 0),
                "weekly_played": rbg.get("weekly_match_statistics", {}).get("played", 0),
                "weekly_won": rbg.get("weekly_match_statistics", {}).get("won", 0),
                "weekly_lost": rbg.get("weekly_match_statistics", {}).get("lost", 0),
            }

            return result

    except Exception as e:
        st.error(f"Erreur lors de la récupération des données: {str(e)}")
        return None
