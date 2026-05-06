import argparse
import csv
import json
import os
import random
import re
import time
from html import unescape
from urllib.parse import urlparse

import requests


GRAPHQL_URL = "https://www.ted.com/graphql"

# Fallback sicuro se non troviamo lingue da HTML.
DEFAULT_LANGUAGES = ["en"]


TRANSCRIPT_QUERY = """
query Transcript($id: ID!, $language: String!) {
  translation(videoId: $id, language: $language) {
    ...TranslationInfo
    paragraphs {
      cues {
        text
        time
        __typename
      }
      __typename
    }
    __typename
  }
  video(id: $id, language: $language) {
    id
    talkExtras {
      footnotes {
        author
        annotation
        date
        linkUrl
        source
        text
        timecode
        title
        category
        __typename
      }
      __typename
    }
    __typename
  }
}

fragment TranslationInfo on Translation {
  id
  language {
    id
    endonym
    englishName
    internalLanguageCode
    rtl
    __typename
  }
  reviewer {
    id
    profilePath
    avatar {
      url
      generatedUrl(type: SVG)
      __typename
    }
    name {
      full
      __typename
    }
    __typename
  }
  translator {
    id
    profilePath
    avatar {
      url
      generatedUrl(type: SVG)
      __typename
    }
    name {
      full
      __typename
    }
    __typename
  }
  __typename
}
"""


class RetryableDownloadError(Exception):
    pass


class NonRetryableDownloadError(Exception):
    pass


def safe_name(value):
    value = str(value).strip()
    value = re.sub(r"[^a-zA-Z0-9_\-.]+", "_", value)
    return value[:180]


def now_string():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def get_video_id_from_url(url):
    parsed = urlparse(url)
    parts = parsed.path.strip("/").split("/")

    if "talks" in parts:
        index = parts.index("talks")
        if index + 1 < len(parts):
            return parts[index + 1]

    return parts[-1]


def find_url_column(fieldnames):
    possible_names = ["url", "talk_url", "link", "ted_url", "video_url"]

    for name in possible_names:
        if name in fieldnames:
            return name

    for name in fieldnames:
        lower_name = name.lower()
        if "url" in lower_name or "link" in lower_name:
            return name

    return None


def find_id_column(fieldnames):
    possible_names = ["id", "talk_id", "ted_id", "dataset_id"]

    for name in possible_names:
        if name in fieldnames:
            return name

    for name in fieldnames:
        lower_name = name.lower()
        if lower_name == "id" or lower_name.endswith("_id"):
            return name

    return None


def find_slug_column(fieldnames):
    possible_names = ["slug", "name", "talk_slug", "video_slug"]

    for name in possible_names:
        if name in fieldnames:
            return name

    for name in fieldnames:
        lower_name = name.lower()
        if "slug" in lower_name:
            return name

    return None


def read_details_ids(details_path):
    ids_by_slug = {}

    if details_path is None or not os.path.exists(details_path):
        return ids_by_slug

    with open(details_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        id_column = find_id_column(fieldnames)
        slug_column = find_slug_column(fieldnames)
        url_column = find_url_column(fieldnames)

        if id_column is None:
            return ids_by_slug

        for row in reader:
            dataset_id = (row.get(id_column) or "").strip()

            if not dataset_id:
                continue

            if slug_column is not None:
                slug = (row.get(slug_column) or "").strip()
                if slug:
                    ids_by_slug[slug] = dataset_id

            if url_column is not None:
                url = (row.get(url_column) or "").strip()
                if url:
                    video_id = get_video_id_from_url(url)
                    ids_by_slug[video_id] = dataset_id

    return ids_by_slug


def read_dataset(csv_path, details_path=None):
    rows = []
    ids_by_slug = read_details_ids(details_path)

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        url_column = find_url_column(fieldnames)
        id_column = find_id_column(fieldnames)
        slug_column = find_slug_column(fieldnames)

        if url_column is None:
            raise Exception(
                "Non trovo una colonna URL nel CSV. "
                "Rinomina la colonna in 'url' oppure passa un CSV con una colonna che contiene 'url' o 'link'."
            )

        for row in reader:
            url = (row.get(url_column) or "").strip()

            if not url:
                continue

            video_id = get_video_id_from_url(url)
            slug = video_id

            if slug_column is not None and (row.get(slug_column) or "").strip():
                slug = (row.get(slug_column) or "").strip()

            dataset_id = ""

            if id_column is not None:
                dataset_id = (row.get(id_column) or "").strip()

            if not dataset_id:
                dataset_id = ids_by_slug.get(slug, "")

            if not dataset_id:
                dataset_id = ids_by_slug.get(video_id, "")

            if not dataset_id:
                dataset_id = safe_name(video_id)

            rows.append({
                "url": url,
                "video_id": video_id,
                "slug": slug,
                "dataset_id": dataset_id,
                "raw_row": row
            })

    return rows


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(path):
    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_output_paths(output_dir, dataset_id, language):
    file_base = f"{safe_name(dataset_id)}_{safe_name(language)}"

    return {
        "structured": os.path.join(output_dir, "structured", f"{file_base}_structured.json"),
        "raw": os.path.join(output_dir, "raw", f"{file_base}_raw.json"),
        "txt": os.path.join(output_dir, "txt", f"{file_base}_txt.txt"),
    }


def build_state_path(output_dir, dataset_id):
    return os.path.join(output_dir, "state", f"{safe_name(dataset_id)}_state.json")


def build_index_path(output_dir):
    return os.path.join(output_dir, "index.json")


def build_debug_dir(output_dir):
    return os.path.join(output_dir, "debug_html_languages")


def save_debug_file(output_dir, dataset_id, suffix, content):
    debug_dir = build_debug_dir(output_dir)
    os.makedirs(debug_dir, exist_ok=True)

    path = os.path.join(debug_dir, f"{safe_name(dataset_id)}_{suffix}")

    with open(path, "w", encoding="utf-8") as f:
        if isinstance(content, str):
            f.write(content)
        else:
            json.dump(content, f, ensure_ascii=False, indent=2)

    return path


def transcript_files_exist(output_dir, dataset_id, language):
    paths = build_output_paths(output_dir, dataset_id, language)

    return (
        os.path.exists(paths["structured"])
        and os.path.exists(paths["raw"])
        and os.path.exists(paths["txt"])
    )


def load_state(output_dir, dataset_id):
    path = build_state_path(output_dir, dataset_id)
    state = load_json(path)

    if state is None:
        return {
            "dataset_id": dataset_id,
            "complete": False,
            "target_languages": [],
            "available_languages": [],
            "downloaded": [],
            "not_available": [],
            "retry_failed": [],
            "errors": []
        }

    return state


def save_state(output_dir, dataset_id, state):
    path = build_state_path(output_dir, dataset_id)
    state["last_updated"] = now_string()
    save_json(path, state)


def load_index(output_dir):
    path = build_index_path(output_dir)

    if not os.path.exists(path):
        return {
            "videos": {},
            "created_at": now_string(),
            "updated_at": now_string()
        }

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_index(output_dir, index):
    index["updated_at"] = now_string()
    save_json(build_index_path(output_dir), index)


def get_index_video(output_dir, dataset_id):
    index = load_index(output_dir)
    return index.get("videos", {}).get(str(dataset_id), {})


def update_index_video(output_dir, dataset_id, payload):
    index = load_index(output_dir)

    videos = index.setdefault("videos", {})
    current = videos.get(str(dataset_id), {})

    current.update(payload)
    current["last_updated"] = now_string()

    videos[str(dataset_id)] = current
    save_index(output_dir, index)


def get_common_headers(video_id=None):
    referer = "https://www.ted.com/"

    if video_id:
        referer = f"https://www.ted.com/talks/{video_id}"

    return {
        "accept": "*/*",
        "client-id": "Zenith production",
        "content-type": "application/json",
        "origin": "https://www.ted.com",
        "referer": referer,
        "x-operation-name": "Transcript",
        "user-agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/147.0.0.0 Safari/537.36"
        ),
    }


def get_html_headers():
    return {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "accept-language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "user-agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/147.0.0.0 Safari/537.36"
        ),
    }


def make_retryable_error_from_response(response, label):
    retry_after = response.headers.get("retry-after")
    message = f"{label} HTTP {response.status_code}: {response.text[:300]}"

    error = RetryableDownloadError(message)
    error.retry_after = None

    if retry_after:
        try:
            error.retry_after = float(retry_after)
        except ValueError:
            error.retry_after = None

    return error


def looks_like_non_retryable_graphql_error(data):
    text = json.dumps(data, ensure_ascii=False).lower()

    non_retryable_patterns = [
        "405: not allowed",
        "method not allowed",
        "404",
        "not found",
        "not supported",
        "does not exist",
        "video not found"
    ]

    for pattern in non_retryable_patterns:
        if pattern in text:
            return True

    return False


def run_with_retries(label, fn, max_retries=6, base_wait=3.0, max_wait=90.0):
    attempt = 0

    while True:
        try:
            return fn()
        except RetryableDownloadError as e:
            attempt += 1

            if attempt > max_retries:
                raise RetryableDownloadError(
                    f"Retry esauriti dopo {max_retries} tentativi su {label}. Ultimo errore: {e}"
                )

            retry_after = getattr(e, "retry_after", None)

            if retry_after is not None:
                wait_seconds = retry_after + random.uniform(0, 1.5)
                print(f"    retry-after ricevuto: attendo {wait_seconds:.1f}s")
            else:
                wait_seconds = min(max_wait, base_wait * (2 ** (attempt - 1)))
                wait_seconds = wait_seconds + random.uniform(0, 2.0)

            print(f"    retry {attempt}/{max_retries} tra {wait_seconds:.1f}s: {e}")
            time.sleep(wait_seconds)


def fetch_ted_page_html_once(url):
    try:
        response = requests.get(
            url,
            headers=get_html_headers(),
            timeout=35
        )
    except requests.exceptions.Timeout as e:
        raise RetryableDownloadError(f"Timeout HTML: {e}")
    except requests.exceptions.ConnectionError as e:
        raise RetryableDownloadError(f"Connection error HTML: {e}")
    except requests.exceptions.RequestException as e:
        raise RetryableDownloadError(f"Request error HTML: {e}")

    if response.status_code in [408, 425, 429, 500, 502, 503, 504]:
        raise make_retryable_error_from_response(response, "Pagina TED HTML")

    if response.status_code in [400, 401, 403, 404]:
        raise NonRetryableDownloadError(
            f"Pagina TED HTML HTTP {response.status_code}: {response.text[:300]}"
        )

    if response.status_code != 200:
        raise RetryableDownloadError(
            f"Pagina TED HTML HTTP {response.status_code}: {response.text[:300]}"
        )

    return response.text


def fetch_ted_page_html(url, args):
    return run_with_retries(
        label=f"{url}/html",
        fn=lambda: fetch_ted_page_html_once(url),
        max_retries=min(args.max_retries, 4),
        base_wait=args.retry_base_wait,
        max_wait=min(args.retry_max_wait, 120)
    )


def normalize_language_code(code):
    clean = unescape(str(code)).strip().lower()

    if clean == "zh-hans":
        return "zh-cn"

    if clean == "zh-hant":
        return "zh-tw"

    if re.fullmatch(r"[a-z]{2,3}(-[a-z]{2,3})?", clean):
        return clean

    return None


def discover_languages_from_transcript_select(html):
    """
    Metodo principale.
    Legge le option del select della lingua transcript:
    <select ...>
      <option value="it">Italiano</option>
    </select>
    """
    found = set()

    select_blocks = re.findall(
        r"<select\b[^>]*>(.*?)</select>",
        html,
        flags=re.IGNORECASE | re.DOTALL
    )

    for select_html in select_blocks:
        options = re.findall(
            r"<option\b[^>]*\bvalue=[\"']([^\"']+)[\"'][^>]*>",
            select_html,
            flags=re.IGNORECASE | re.DOTALL
        )

        valid_options = []

        for value in options:
            code = normalize_language_code(value)
            if code:
                valid_options.append(code)

        # Evitiamo select generici: consideriamo affidabili quelli con almeno 2 lingue.
        if len(valid_options) >= 2:
            for code in valid_options:
                found.add(code)

    return sorted(found)


def discover_languages_from_html_alternates(html):
    """
    Fallback solo HTML.
    Legge link tipo:
    <link rel="alternate" hrefLang="it" href="...?language=it">
    """
    found = set()

    patterns = [
        r"hrefLang=[\"']([^\"']+)[\"']\s+href=[\"'][^\"']+\?language=([^\"']+)[\"']",
        r"hreflang=[\"']([^\"']+)[\"']\s+href=[\"'][^\"']+\?language=([^\"']+)[\"']",
        r"\?language=([a-z]{2,3}(?:-[a-z]{2,3})?)"
    ]

    for pattern in patterns:
        for match in re.findall(pattern, html, flags=re.IGNORECASE):
            candidate = match[-1] if isinstance(match, tuple) else match
            code = normalize_language_code(candidate)

            if code and code != "x-default":
                found.add(code)

    return sorted(found)


def discover_available_languages_from_html(item, args):
    dataset_id = item["dataset_id"]
    url = item["url"]

    indexed = get_index_video(args.output, dataset_id)

    if indexed.get("available_languages") and not args.force_language_discovery:
        languages = indexed.get("available_languages", [])
        print(f"  index: lingue già indicizzate ({len(languages)})")
        return languages

    try:
        html = fetch_ted_page_html(url, args)

    except NonRetryableDownloadError as e:
        print(f"  html discovery non disponibile: {e}")

        discovery_status = {
            "method": "html_only",
            "error": str(e),
            "select_languages": [],
            "select_languages_count": 0,
            "alternate_languages": [],
            "alternate_languages_count": 0,
            "chosen_languages": [],
            "chosen_languages_count": 0,
            "last_checked": now_string()
        }

        update_index_video(args.output, dataset_id, {
            "dataset_id": dataset_id,
            "video_id": item["video_id"],
            "url": url,
            "available_languages": [],
            "discovery_status": discovery_status,
            "html_discovery_error": str(e)
        })

        return []

    except RetryableDownloadError:
        raise

    except Exception as e:
        print(f"  html discovery errore inatteso: {e}")

        discovery_status = {
            "method": "html_only",
            "error": str(e),
            "select_languages": [],
            "select_languages_count": 0,
            "alternate_languages": [],
            "alternate_languages_count": 0,
            "chosen_languages": [],
            "chosen_languages_count": 0,
            "last_checked": now_string()
        }

        update_index_video(args.output, dataset_id, {
            "dataset_id": dataset_id,
            "video_id": item["video_id"],
            "url": url,
            "available_languages": [],
            "discovery_status": discovery_status,
            "html_discovery_error": str(e)
        })

        return []

    if args.debug_html:
        save_debug_file(args.output, dataset_id, "page.html", html)

    select_languages = discover_languages_from_transcript_select(html)
    alternate_languages = discover_languages_from_html_alternates(html)

    # Priorità assoluta al select del transcript.
    languages = select_languages or alternate_languages

    discovery_status = {
        "method": "html_only",
        "select_languages": select_languages,
        "select_languages_count": len(select_languages),
        "alternate_languages": alternate_languages,
        "alternate_languages_count": len(alternate_languages),
        "chosen_languages": languages,
        "chosen_languages_count": len(languages),
        "last_checked": now_string()
    }

    if args.debug_html:
        save_debug_file(args.output, dataset_id, "html_languages.json", {
            "url": url,
            **discovery_status
        })

    if select_languages:
        print(f"  html select lingue trovate: {', '.join(select_languages)}")
    elif alternate_languages:
        print(f"  html alternate lingue trovate: {', '.join(alternate_languages)}")
    else:
        print("  html: nessuna lingua trovata")

    update_index_video(args.output, dataset_id, {
        "dataset_id": dataset_id,
        "video_id": item["video_id"],
        "url": url,
        "available_languages": languages,
        "discovery_status": discovery_status
    })

    return languages


def get_target_languages(item, args):
    if args.languages:
        requested = [lang.strip().lower() for lang in args.languages.split(",") if lang.strip()]

        if args.filter_requested_by_html:
            available = discover_available_languages_from_html(item, args)

            if available:
                return sorted(set(requested) & set(available))

            return requested

        return requested

    available = discover_available_languages_from_html(item, args)

    if available:
        return sorted(set(available))

    if args.fallback_all_languages:
        return [
            "en", "it", "es", "fr", "de", "pt", "pt-br", "zh-cn", "zh-tw", "ja", "ko",
            "ar", "ru", "nl", "tr", "pl", "ro", "el", "he", "hi", "id", "vi", "th",
            "cs", "da", "fi", "hu", "no", "sv", "uk", "bg", "hr", "sk", "sl", "sr",
            "ca", "eu", "gl", "fa", "ur", "bn", "ta", "te", "ml", "mr", "sw"
        ]

    return DEFAULT_LANGUAGES


def graphql_post_once(video_id, operation_name, query, variables, timeout=45):
    payload = {
        "operationName": operation_name,
        "variables": variables,
        "query": query
    }

    headers = get_common_headers(video_id)
    headers["x-operation-name"] = operation_name

    try:
        response = requests.post(
            GRAPHQL_URL,
            headers=headers,
            json=payload,
            timeout=timeout
        )
    except requests.exceptions.Timeout as e:
        raise RetryableDownloadError(f"Timeout GraphQL: {e}")
    except requests.exceptions.ConnectionError as e:
        raise RetryableDownloadError(f"Connection error GraphQL: {e}")
    except requests.exceptions.RequestException as e:
        raise RetryableDownloadError(f"Request error GraphQL: {e}")

    if response.status_code in [408, 425, 429, 500, 502, 503, 504]:
        raise make_retryable_error_from_response(response, "GraphQL")

    if response.status_code in [400, 401, 403, 404]:
        raise NonRetryableDownloadError(
            f"GraphQL HTTP {response.status_code}: {response.text[:300]}"
        )

    if response.status_code != 200:
        raise RetryableDownloadError(
            f"GraphQL HTTP {response.status_code}: {response.text[:300]}"
        )

    try:
        return response.json()
    except ValueError as e:
        raise RetryableDownloadError(f"Risposta GraphQL non JSON: {e}")


def fetch_transcript(video_id, language, max_retries=6, base_wait=3.0, max_wait=90.0):
    def call():
        data = graphql_post_once(
            video_id=video_id,
            operation_name="Transcript",
            query=TRANSCRIPT_QUERY,
            variables={
                "id": video_id,
                "language": language
            },
            timeout=45
        )

        if "errors" in data:
            if looks_like_non_retryable_graphql_error(data):
                raise NonRetryableDownloadError(
                    f"GraphQL non retryable error: {data['errors']}"
                )

            raise RetryableDownloadError(f"GraphQL error: {data['errors']}")

        return data

    return run_with_retries(
        label=f"{video_id}/{language}",
        fn=call,
        max_retries=max_retries,
        base_wait=base_wait,
        max_wait=max_wait
    )


def normalize_transcript(dataset_id, video_id, url, language, data):
    translation = data.get("data", {}).get("translation")

    if translation is None:
        return None

    segments = []

    for paragraph_index, paragraph in enumerate(translation.get("paragraphs", [])):
        for cue in paragraph.get("cues", []):
            segments.append({
                "paragraph_index": paragraph_index,
                "time": cue.get("time"),
                "text": cue.get("text")
            })

    if len(segments) == 0:
        return None

    return {
        "dataset_id": dataset_id,
        "video_id": video_id,
        "url": url,
        "language": language,
        "language_info": translation.get("language"),
        "segments": segments
    }


def save_txt(path, transcript):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        for segment in transcript["segments"]:
            f.write(segment["text"].replace("\n", " ").strip() + "\n")


def is_video_complete_from_state_only(output_dir, dataset_id):
    state = load_state(output_dir, dataset_id)

    if not state.get("complete"):
        return False

    target_languages = state.get("target_languages", [])
    downloaded = state.get("downloaded", [])
    not_available = state.get("not_available", [])

    if not target_languages:
        return False

    accounted = set(downloaded) | set(not_available)

    if accounted != set(target_languages):
        return False

    for language in downloaded:
        if not transcript_files_exist(output_dir, dataset_id, language):
            return False

    return True


def is_video_complete(output_dir, dataset_id, target_languages):
    state = load_state(output_dir, dataset_id)

    if not state.get("complete"):
        return False

    previous_targets = set(state.get("target_languages", []))
    current_targets = set(target_languages)

    if previous_targets != current_targets:
        return False

    downloaded = set(state.get("downloaded", []))
    not_available = set(state.get("not_available", []))

    accounted = downloaded | not_available

    if accounted != current_targets:
        return False

    for language in downloaded:
        if not transcript_files_exist(output_dir, dataset_id, language):
            return False

    return True


def mark_video_complete_if_possible(output_dir, dataset_id, target_languages, state):
    downloaded = set(state.get("downloaded", []))
    not_available = set(state.get("not_available", []))
    target_set = set(target_languages)

    accounted = downloaded | not_available

    all_downloaded_files_exist = True

    for language in downloaded:
        if not transcript_files_exist(output_dir, dataset_id, language):
            all_downloaded_files_exist = False
            break

    state["complete"] = accounted == target_set and all_downloaded_files_exist
    save_state(output_dir, dataset_id, state)

    return state["complete"]


def add_unique(list_obj, value):
    if value not in list_obj:
        list_obj.append(value)


def remove_if_present(list_obj, value):
    while value in list_obj:
        list_obj.remove(value)


def sleep_between_requests(args):
    time.sleep(args.sleep + random.uniform(0, args.sleep_jitter))


def update_index_from_state(args, dataset_id, video_id, url, target_languages, state, complete=None):
    if complete is None:
        complete = state.get("complete", False)

    update_index_video(args.output, dataset_id, {
        "dataset_id": dataset_id,
        "video_id": video_id,
        "url": url,
        "available_languages": state.get("available_languages", []),
        "target_languages": target_languages,
        "downloaded_languages": state.get("downloaded", []),
        "not_available_languages": state.get("not_available", []),
        "retry_failed_languages": state.get("retry_failed", []),
        "complete": complete
    })


def main():
    parser = argparse.ArgumentParser(
        description="Scarica transcript TED/TEDx da un CSV usando GraphQL Transcript e discovery lingue solo da HTML."
    )

    parser.add_argument("--csv", default="final_list.csv")
    parser.add_argument("--details", default="details.csv")
    parser.add_argument("--output", default="transcripts")
    parser.add_argument("--languages", default=None)
    parser.add_argument("--sleep", type=float, default=0.25)
    parser.add_argument("--sleep-jitter", type=float, default=0.35)
    parser.add_argument("--max-retries", type=int, default=8)
    parser.add_argument("--retry-base-wait", type=float, default=5.0)
    parser.add_argument("--retry-max-wait", type=float, default=180.0)
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--force-language-discovery", action="store_true")
    parser.add_argument("--debug-html", action="store_true")
    parser.add_argument("--fallback-all-languages", action="store_true")
    parser.add_argument("--filter-requested-by-html", action="store_true")

    args = parser.parse_args()

    rows = read_dataset(args.csv, args.details)

    summary = {
        "csv": args.csv,
        "details": args.details,
        "output": args.output,
        "total_rows": len(rows),
        "downloaded": [],
        "not_available": [],
        "errors": [],
        "retry_failed": [],
        "skipped_complete_videos": [],
        "started_at": now_string()
    }

    print(f"Talk trovati nel CSV: {len(rows)}")
    print("Modalità lingue:", args.languages if args.languages else "HTML only")

    for talk_index, item in enumerate(rows, start=1):
        url = item["url"]
        video_id = item["video_id"]
        dataset_id = item["dataset_id"]

        print(f"\n[{talk_index}/{len(rows)}] dataset_id={dataset_id} slug={video_id}")

        # Skip veloce solo quando le lingue richieste sono esplicite.
        # Se invece non passo --languages, devo prima fare discovery HTML,
        # perché le target_languages potrebbero essere più ampie della run precedente.
        if args.languages and not args.force and is_video_complete_from_state_only(args.output, dataset_id):
            print("  skip video completo da state")
            summary["skipped_complete_videos"].append({
                "dataset_id": dataset_id,
                "video_id": video_id,
                "url": url
            })
            continue
            
        target_languages = get_target_languages(item, args)

        if not target_languages:
            print("  nessuna lingua target trovata")
            update_index_video(args.output, dataset_id, {
                "dataset_id": dataset_id,
                "video_id": video_id,
                "url": url,
                "available_languages": [],
                "target_languages": [],
                "complete": False,
                "note": "nessuna lingua target trovata"
            })
            continue

        if not args.force and is_video_complete(args.output, dataset_id, target_languages):
            print(f"  skip video completo: {len(target_languages)} lingue già verificate")
            summary["skipped_complete_videos"].append({
                "dataset_id": dataset_id,
                "video_id": video_id,
                "url": url,
                "target_languages": target_languages
            })
            continue

        state = load_state(args.output, dataset_id)
        indexed = get_index_video(args.output, dataset_id)

        state["dataset_id"] = dataset_id
        state["video_id"] = video_id
        state["url"] = url
        state["target_languages"] = target_languages
        state["available_languages"] = indexed.get("available_languages", state.get("available_languages", []))
        state.setdefault("downloaded", [])
        state.setdefault("not_available", [])
        state.setdefault("retry_failed", [])
        state.setdefault("errors", [])
        state["complete"] = False

        print(f"  lingue target: {', '.join(target_languages)}")
        save_state(args.output, dataset_id, state)

        for language in target_languages:
            paths = build_output_paths(args.output, dataset_id, language)

            json_path = paths["structured"]
            raw_path = paths["raw"]
            txt_path = paths["txt"]

            if not args.force and transcript_files_exist(args.output, dataset_id, language):
                print(f"  skip {language}: file già presenti")
                add_unique(state["downloaded"], language)
                remove_if_present(state["retry_failed"], language)
                save_state(args.output, dataset_id, state)
                update_index_from_state(args, dataset_id, video_id, url, target_languages, state)
                continue

            if not args.force and language in state.get("not_available", []):
                print(f"  skip {language}: già verificata come non disponibile")
                update_index_from_state(args, dataset_id, video_id, url, target_languages, state)
                continue

            try:
                data = fetch_transcript(
                    video_id,
                    language,
                    max_retries=args.max_retries,
                    base_wait=args.retry_base_wait,
                    max_wait=args.retry_max_wait
                )

                transcript = normalize_transcript(dataset_id, video_id, url, language, data)

                if transcript is None:
                    print(f"  no {language}: non disponibile")

                    add_unique(state["not_available"], language)
                    remove_if_present(state["retry_failed"], language)

                    save_state(args.output, dataset_id, state)
                    update_index_from_state(args, dataset_id, video_id, url, target_languages, state)

                    summary["not_available"].append({
                        "dataset_id": dataset_id,
                        "video_id": video_id,
                        "url": url,
                        "language": language
                    })

                    save_json(os.path.join(args.output, "summary.json"), summary)
                    sleep_between_requests(args)
                    continue

                save_json(json_path, transcript)
                save_json(raw_path, data)
                save_txt(txt_path, transcript)

                print(f"  ok {language}: {len(transcript['segments'])} segmenti")

                add_unique(state["downloaded"], language)
                remove_if_present(state["retry_failed"], language)

                save_state(args.output, dataset_id, state)
                update_index_from_state(args, dataset_id, video_id, url, target_languages, state)

                summary["downloaded"].append({
                    "dataset_id": dataset_id,
                    "video_id": video_id,
                    "url": url,
                    "language": language,
                    "segments": len(transcript["segments"]),
                    "structured_path": json_path,
                    "raw_path": raw_path,
                    "txt_path": txt_path
                })

                save_json(os.path.join(args.output, "summary.json"), summary)

            except RetryableDownloadError as e:
                print(f"  retry_failed {language}: {e}")

                add_unique(state["retry_failed"], language)

                state["errors"].append({
                    "language": language,
                    "error": str(e),
                    "type": "retryable",
                    "time": now_string()
                })

                save_state(args.output, dataset_id, state)
                update_index_from_state(args, dataset_id, video_id, url, target_languages, state)

                error_item = {
                    "dataset_id": dataset_id,
                    "video_id": video_id,
                    "url": url,
                    "language": language,
                    "error": str(e),
                    "type": "retryable"
                }

                summary["retry_failed"].append(error_item)
                summary["errors"].append(error_item)

                save_json(os.path.join(args.output, "summary.json"), summary)

                if args.stop_on_error:
                    raise

            except Exception as e:
                print(f"  error {language}: {e}")

                # Gli errori non retryable, ad esempio 404/405, vengono considerati
                # lingua non disponibile, così il video può diventare completo
                # e non viene riprovato all'infinito nelle run successive.
                add_unique(state["not_available"], language)
                remove_if_present(state["retry_failed"], language)

                state["errors"].append({
                    "language": language,
                    "error": str(e),
                    "type": "non_retryable",
                    "time": now_string()
                })

                save_state(args.output, dataset_id, state)
                update_index_from_state(args, dataset_id, video_id, url, target_languages, state)

                error_item = {
                    "dataset_id": dataset_id,
                    "video_id": video_id,
                    "url": url,
                    "language": language,
                    "error": str(e),
                    "type": "non_retryable"
                }

                summary["errors"].append(error_item)
                summary["not_available"].append({
                    "dataset_id": dataset_id,
                    "video_id": video_id,
                    "url": url,
                    "language": language
                })

                save_json(os.path.join(args.output, "summary.json"), summary)

                if args.stop_on_error:
                    raise

            sleep_between_requests(args)

        complete = mark_video_complete_if_possible(args.output, dataset_id, target_languages, state)
        update_index_from_state(args, dataset_id, video_id, url, target_languages, state, complete=complete)

        if complete:
            print("  video completo")
        else:
            print("  video incompleto: verrà riprovato al prossimo lancio")

        save_json(os.path.join(args.output, "summary.json"), summary)

    summary["finished_at"] = now_string()
    save_json(os.path.join(args.output, "summary.json"), summary)

    print("\nFine.")
    print(f"Transcript scaricati in questa esecuzione: {len(summary['downloaded'])}")
    print(f"Non disponibili rilevati in questa esecuzione: {len(summary['not_available'])}")
    print(f"Retry falliti in questa esecuzione: {len(summary['retry_failed'])}")
    print(f"Errori totali in questa esecuzione: {len(summary['errors'])}")
    print(f"Video già completi saltati: {len(summary['skipped_complete_videos'])}")
    print(f"Summary: {os.path.join(args.output, 'summary.json')}")
    print(f"Index: {build_index_path(args.output)}")

    if args.debug_html:
        print(f"Debug HTML: {build_debug_dir(args.output)}")


if __name__ == "__main__":
    main()