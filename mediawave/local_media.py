"""Local media filename and folder parsing helpers for MediaWave."""

import hashlib
import os
import re


TITLE_STOPWORDS = frozenset({"the", "a", "an", "of", "in", "at", "to", "and", "or", "is", "it"})


def stable_hash(value):
    return hashlib.sha1(str(value).encode("utf-8")).hexdigest()


def format_program_title(path):
    name = os.path.splitext(os.path.basename(path))[0]
    return name.replace("_", " ").replace("`", "'")


def normalize_title(value):
    cleaned = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
    return re.sub(r"\s+", " ", cleaned)


def clean_local_title_piece(value):
    text = str(value or "").replace(".", " ")
    text = re.sub(r"\s+", " ", text.strip().strip("-_–—:| ")).strip()
    return text


def normalized_filename_title(path):
    title = format_program_title(path)
    title = re.sub(r"[._]+", " ", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def _folder_is_genre_category(folder_norm, file_norm):
    folder_words = set(folder_norm.split()) - TITLE_STOPWORDS
    file_words = set(file_norm.split()) - TITLE_STOPWORDS
    return not folder_words or not bool(folder_words & file_words)


def _tv_result(show, season, episode, title):
    show = clean_local_title_piece(show)
    title = clean_local_title_piece(title or f"Episode {episode}")
    season = int(season)
    episode = int(episode)
    return {
        "media_type": "tv",
        "show_name": show,
        "timeline_title": show,
        "detail_title": f"{show} - S{season:02d}E{episode:02d} - {title}",
        "detail_summary": "",
        "season_number": season,
        "season_label": f"Season {season}",
        "episode_number": episode,
        "episode_title": title,
        "match_key": normalize_title(show),
    }


def parse_local_media(path):
    base = normalized_filename_title(path)
    patterns = [
        r"^(?P<show>.+?)\s*-\s*(?P<season>\d{1,2})[xX](?P<episode>\d{1,3})\s*-\s*(?P<title>.+)$",
        r"^(?P<show>.+?)\s+(?P<season>\d{1,2})[xX](?P<episode>\d{1,3})(?:\s*[- ]\s*(?P<title>.+))?$",
        r"^(?P<show>.+?)\s+[Ss](?P<season>\d{1,2})[Ee](?P<episode>\d{1,3})(?:\s*[- ]\s*(?P<title>.+))?$",
        r"^(?P<show>.+?)\s*-\s*[Ss](?P<season>\d{1,2})[Ee](?P<episode>\d{1,3})(?:\s*-\s*(?P<title>.+))?$",
        r"^(?P<show>.+?)\s*-\s*(?:episode|ep)\s*(?P<episode>\d{1,3})\s*[-: ]+\s*(?P<title>.+)$",
        r"^(?P<show>.+?)\s*-\s*(?P<episode>\d{1,3})\s*-\s*(?P<title>.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, base, re.IGNORECASE)
        if match:
            season = int(match.group("season")) if match.groupdict().get("season") else 1
            episode = int(match.group("episode"))
            title = match.groupdict().get("title") or f"Episode {episode}"
            return _tv_result(match.group("show"), season, episode, title)

    parent = os.path.basename(os.path.dirname(path))
    grandparent = os.path.basename(os.path.dirname(os.path.dirname(path)))
    parent_title = format_program_title(parent) if parent else ""
    grandparent_title = format_program_title(grandparent) if grandparent else ""
    fallback_title = clean_local_title_piece(base)
    season_number = None
    season_source = parent_title
    season_match = re.search(r"\bseason\s*(\d{1,2})\b", parent_title, re.IGNORECASE)
    if not season_match and grandparent_title:
        season_match = re.search(r"\bseason\s*(\d{1,2})\b", grandparent_title, re.IGNORECASE)
        season_source = grandparent_title
    if season_match:
        season_number = int(season_match.group(1))

    if grandparent_title and re.search(r"\b(specials?|extras?|bonus|ova)\b", parent_title, re.IGNORECASE):
        special_match = re.match(
            r"^(?:(?:special|episode|ep)\s*)?(?P<episode>\d{1,3})\s*[-._ ]+\s*(?P<title>.+)$",
            fallback_title,
            re.IGNORECASE,
        )
        episode_number = int(special_match.group("episode")) if special_match else None
        episode_title = clean_local_title_piece((special_match.groupdict().get("title") if special_match else "") or fallback_title)
        return {
            "media_type": "tv",
            "show_name": grandparent_title,
            "timeline_title": grandparent_title,
            "detail_title": f"{grandparent_title} - Specials - {episode_title}",
            "detail_summary": "",
            "season_number": 0,
            "season_label": "Specials",
            "episode_number": episode_number,
            "episode_title": episode_title,
            "match_key": normalize_title(grandparent_title),
        }

    inferred_show = grandparent_title if season_number is not None and season_source == parent_title and grandparent_title else parent_title
    if season_number is not None and season_source == grandparent_title and parent_title:
        inferred_show = parent_title

    inferred_patterns = [
        r"^(?:[Ss](?P<season>\d{1,2})[Ee](?P<episode>\d{1,3})|(?P<season_x>\d{1,2})[xX](?P<episode_x>\d{1,3}))\s*(?:[- ]\s*)?(?P<title>.+)?$",
        r"^(?P<episode>\d{1,3})\s*[-._ ]+\s*(?P<title>.+)$",
        r"^(?:episode|ep)\s*(?P<episode>\d{1,3})\s*[-._ ]+\s*(?P<title>.+)$",
        r"^(?P<episode>\d{1,3})$",
    ]
    if inferred_show:
        for pattern in inferred_patterns:
            match = re.match(pattern, fallback_title, re.IGNORECASE)
            if not match:
                continue
            groupdict = match.groupdict()
            episode = int(groupdict.get("episode") or groupdict.get("episode_x"))
            season = int(groupdict.get("season") or groupdict.get("season_x") or season_number or 1)
            title = clean_local_title_piece(groupdict.get("title") or f"Episode {episode}")
            return _tv_result(inferred_show, season, episode, title)

    if parent_title and parent_title.lower() not in fallback_title.lower():
        norm_parent = normalize_title(parent_title)
        norm_fallback = normalize_title(fallback_title)
        show_name = fallback_title if _folder_is_genre_category(norm_parent, norm_fallback) else parent_title
    else:
        show_name = fallback_title
    return {
        "media_type": "movie",
        "show_name": show_name,
        "timeline_title": fallback_title,
        "detail_title": fallback_title,
        "detail_summary": "",
        "match_key": normalize_title(show_name or fallback_title),
    }


def infer_on_demand_structure(path, channel_root):
    root = os.path.realpath(channel_root or "")
    full_path = os.path.realpath(path or "")
    if not root or not full_path:
        return {}
    try:
        relative = os.path.relpath(full_path, root)
    except ValueError:
        return {}
    if relative.startswith(".."):
        return {}
    parts = [part for part in relative.split(os.sep) if part and part != "."]
    if len(parts) < 2:
        return {}
    show_folder = format_program_title(parts[0])
    subsection_folder = format_program_title(parts[1]) if len(parts) >= 3 else ""
    return {
        "group_label": show_folder,
        "section_label": subsection_folder,
    }


def metadata_lookup_key(path, local):
    if local.get("media_type") == "tv":
        return f"tv::{local.get('match_key', normalize_title(local.get('show_name', '')))}"
    return f"movie::{stable_hash(path)}"


def media_lineup_sort_key(path):
    local = parse_local_media(path)
    show = normalize_title(local.get("show_name") or "")
    title = normalize_title(local.get("episode_title") or local.get("detail_title") or format_program_title(path))
    season = local.get("season_number")
    episode = local.get("episode_number")
    try:
        season_number = int(season)
    except (TypeError, ValueError):
        season_number = 9999
    try:
        episode_number = int(episode)
    except (TypeError, ValueError):
        episode_number = 9999
    media_rank = 0 if local.get("media_type") == "tv" else 1
    return (media_rank, show, season_number, episode_number, title, normalize_title(os.path.basename(path)))
