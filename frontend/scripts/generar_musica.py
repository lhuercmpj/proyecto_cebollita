"""Arma el catalogo de musica de la pagina: src/data/music.js.

Cada estilo es una lista fija de temas (IDs de video de YouTube), no una playlist
de terceros, para que nunca suene algo de otro genero. El script lee los albumes
oficiales de YouTube Music, comprueba que cada video se pueda embeber (oEmbed) y
limpia los titulos.

Uso (solo libreria estandar, necesita internet):
    python scripts/generar_musica.py

Para agregar musica: sumar un album a ALBUMS (ID `OLAK5uy_...` de la URL del
album en music.youtube.com) o IDs sueltos a SINGLES, y volver a ejecutar.
"""

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "src" / "data" / "music.js"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36", "Cookie": "CONSENT=YES+1; SOCS=CAI"}

# estilo -> [(id de album, artista, maximo de temas)]
ALBUMS = {
    "jazz": [
        ("OLAK5uy_mmONSYZrJHWbgB5-b4KKa5onZnHfdj1fc", "Miles Davis", 5),  # Kind of Blue
        ("OLAK5uy_kEReN5gYSsljhOw0uTSgNDZ-WlAcxz4IE", "Ella Fitzgerald & Louis Armstrong", 11),  # Ella and Louis
        ("OLAK5uy_kT4WsarfRaytnvA8aSj-Wq-JtcFN8JQyc", "Dave Brubeck Quartet", 7),  # Time Out
    ],
    "bossa": [
        ("OLAK5uy_lP19Qhu_LFyrd2MPB1uJU0W3OmkEnbOAs", "Stan Getz & João Gilberto", 8),  # Getz/Gilberto
        ("OLAK5uy_mMP_Lfy2IRk0Cw-prxQaEv9y2y-yVIURM", "Antonio Carlos Jobim", 10),  # Wave
    ],
    "clasica": [
        ("OLAK5uy_nKzkF98FttccfWbBxFrDU2wkXKKDull5Q", None, 26),  # Classical Spa Music (solo piano clasico)
    ],
}

# Pop (girly): temas elegidos a mano.
SINGLES = {
    "pop": [
        "OsfAnsMY21M", "htg8v0g_4e4", "JhCA0y_ya6w", "mEhYtnHQAUw", "QBtVFL0Qefs", "ACNwMzZejQQ",
        "R67_mMSyGRg", "1jZhOIRHPYY", "m2ibM-RFliU", "TfOsGnWy8qA", "ZqYGW8uXL0I", "tVdr_JWmnsA",
        "SF8OVaA6YNM", "5Rm6589agOM", "Faq-ODnfIPw",
    ],
}


def fetch_album(list_id):
    req = urllib.request.Request(f"https://www.youtube.com/playlist?list={list_id}&hl=es", headers=UA)
    html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
    data = json.loads(re.search(r"var ytInitialData = (\{.*?\});</script>", html, re.S).group(1))
    found = []

    def walk(node):
        if isinstance(node, dict):
            lockup = node.get("lockupViewModel")
            if lockup and len(lockup.get("contentId", "")) == 11:
                found.append(lockup["contentId"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return list(dict.fromkeys(found))


def oembed(video_id):
    """(titulo, canal) si el video se puede embeber; None si no (YouTube responde 401/404)."""
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        data = json.load(urllib.request.urlopen(url, timeout=15))
    except urllib.error.HTTPError:
        return None
    return data["title"], data["author_name"]


def clean_title(title):
    title = re.sub(r"\((feat\.|Audio|Official Audio|Official).*?\)", "", title)
    title = re.sub(r"\[.*?\]", "", title)
    title = re.sub(r"\s+-\s+Classical Piano Music.*$", "", title)
    title = re.sub(r"^Miles Davis - ", "", title)
    return re.sub(r"\s+", " ", title).strip(" -")


def main():
    catalog = {}
    for style, albums in ALBUMS.items():
        tracks = []
        for list_id, artist, limit in albums:
            for video_id in fetch_album(list_id)[:limit]:
                info = oembed(video_id)
                if not info:
                    print("  sin embeber, se omite:", video_id)
                    continue
                title, channel = info
                title = clean_title(title)
                if artist is None and " - " in title:  # clasica: "Obra - Compositor"
                    title, artist_name = title.rsplit(" - ", 1)
                else:
                    artist_name = artist or channel.replace(" - Topic", "")
                tracks.append({"id": video_id, "title": title, "artist": artist_name})
        catalog[style] = tracks
    for style, ids in SINGLES.items():
        tracks = []
        for video_id in ids:
            info = oembed(video_id)
            if not info:
                print("  sin embeber, se omite:", video_id)
                continue
            title, channel = info
            tracks.append({"id": video_id, "title": clean_title(title), "artist": channel.replace(" - Topic", "")})
        catalog[style] = tracks

    OUT.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(catalog, ensure_ascii=False, indent=2)
    OUT.write_text(f"// Generado por scripts/generar_musica.py. No editar a mano.\nexport const TRACKS = {body};\n", encoding="utf-8")
    for style, tracks in catalog.items():
        print(f"{style}: {len(tracks)} temas")


if __name__ == "__main__":
    main()
