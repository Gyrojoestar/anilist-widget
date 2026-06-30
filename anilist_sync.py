import requests

ANILIST_USERNAME = "Gyrojostar"

GRAPHQL_QUERY = """
query ($username: String) {
  User(name: $username) {
    name
    avatar { large }
    favourites { anime(perPage: 1) { nodes { title { romaji } } } }
    statistics {
      anime { count minutesWatched meanScore }
      manga { count }
    }
  }
  recentAnime: MediaListCollection(userName: $username, type: ANIME, status: CURRENT, sort: [UPDATED_TIME_DESC]) {
    lists { entries { progress media { title { romaji } episodes } } }
  }
  recentManga: MediaListCollection(userName: $username, type: MANGA, status: CURRENT, sort: [UPDATED_TIME_DESC]) {
    lists { entries { progress media { title { romaji } chapters } } }
  }
}
"""


def fetch_anilist_data():
    url = "https://graphql.anilist.co"
    variables = {"username": ANILIST_USERNAME}

    try:
        response = requests.post(url, json={"query": GRAPHQL_QUERY, "variables": variables})
        response.raise_for_status()
        data = response.json()["data"]

        user = data["User"]
        anime_stats = user["statistics"]["anime"]
        manga_stats = user["statistics"]["manga"]

        anime_lists = data["recentAnime"]["lists"]
        if anime_lists and anime_lists[0]["entries"]:
            entry = anime_lists[0]["entries"][0]
            recent_anime = f"{entry['media']['title']['romaji']} ({entry['progress']}/{entry['media']['episodes'] or '?'})"
        else:
            recent_anime = "None"

        manga_lists = data["recentManga"]["lists"]
        if manga_lists and manga_lists[0]["entries"]:
            entry = manga_lists[0]["entries"][0]
            recent_manga = f"{entry['media']['title']['romaji']} ({entry['progress']}/{entry['media']['chapters'] or '?'})"
        else:
            recent_manga = "None"

        fav_nodes = user["favourites"]["anime"]["nodes"]
        favourite_anime = fav_nodes[0]["title"]["romaji"] if fav_nodes else "None"

        mean_score = anime_stats.get("meanScore") or 0
        minutes_watched = anime_stats.get("minutesWatched") or 0

        return {
            "username": user["name"],
            "avatar_url": user["avatar"]["large"],
            "recently_watched_anime": recent_anime,
            "recently_read_manga": recent_manga,
            "total_anime": int(anime_stats.get("count") or 0),
            "total_manga": int(manga_stats.get("count") or 0),
            "days_watched": round(minutes_watched / 1440, 1),
            "mean_score": int(round(float(mean_score))),
            "favourite_anime": favourite_anime,
        }
    except Exception as e:
        print(f"Error fetching from AniList: {e}")
        return None


def build_metadata_payload(stats):
    return {
        "anime_user": str(stats["username"]),
        "anime_pfp": str(stats["avatar_url"]),
        "anime_handle": f"@{ANILIST_USERNAME.lower()}",
        "recent_anime": str(stats["recently_watched_anime"]),
        "recent_manga": str(stats["recently_read_manga"]),
        "total_anime": stats["total_anime"],
        "total_manga": stats["total_manga"],
        "days_watched": str(stats["days_watched"]),
        "mean_score": stats["mean_score"],
        "favourite_anime": str(stats["favourite_anime"]),
    }
