import json
import re
import time
from pathlib import Path
from typing import Optional, Any

import requests

SEARCH_URL = "https://openlibrary.org/search.json"
BASE_URL = "https://openlibrary.org"

TARGET_BOOKS = 2000
OUTPUT_DIR = Path("books")
OUTPUT_DIR.mkdir(exist_ok=True)

REQUEST_DELAY = 0.4
MAX_RETRIES = 5
TIMEOUT = 30

session = requests.Session()
session.headers.update({
    "User-Agent": "openlibrary-downloader/1.0 (contact: you@example.com)"
})


def safe_filename(name: str) -> str:
    name = re.sub(r"[^\w\s.-]", "", name, flags=re.UNICODE)
    name = re.sub(r"\s+", "_", name).strip("_")
    return name[:120] or "book"


def normalize_description(desc: Any) -> Optional[str]:
    if desc is None:
        return None
    if isinstance(desc, str):
        desc = desc.strip()
        return desc or None
    if isinstance(desc, dict):
        value = desc.get("value")
        if isinstance(value, str):
            value = value.strip()
            return value or None
    return None


def request_with_retry(url: str, params: Optional[dict] = None) -> dict:
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(url, params=params, timeout=TIMEOUT)

            if response.status_code in (500, 502, 503, 504):
                raise requests.HTTPError(
                    f"Server error {response.status_code}",
                    response=response
                )

            response.raise_for_status()
            return response.json()

        except requests.RequestException as exc:
            last_error = exc
            wait_time = min(2 ** attempt, 20)
            print(f"Request failed (attempt {attempt}/{MAX_RETRIES}): {exc}")
            if attempt < MAX_RETRIES:
                print(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)

    raise last_error


def fetch_search_page(page: int) -> dict:
    params = {
        # consulta amplia y estable
        "q": "fiction",
        "fields": "key,title,author_name,first_publish_year,language,subject",
        "page": page,
        "limit": 100,
        "lang": "en"
    }
    return request_with_retry(SEARCH_URL, params=params)


def fetch_work(work_key: str) -> dict:
    url = f"{BASE_URL}{work_key}.json"
    return request_with_retry(url)


def save_book(book_id: str, data: dict) -> None:
    filename = safe_filename(f"{book_id}_{data['title']}.json")
    path = OUTPUT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main() -> None:
    saved = 0
    page = 1
    seen_work_keys = set()

    while saved < TARGET_BOOKS:
        print(f"Fetching page {page}")
        payload = fetch_search_page(page)
        docs = payload.get("docs", [])

        if not docs:
            print("No more results.")
            break

        for doc in docs:
            if saved >= TARGET_BOOKS:
                break

            work_key = doc.get("key")
            title = doc.get("title")
            languages = doc.get("language", [])

            if not work_key or not title:
                continue

            if not str(work_key).startswith("/works/"):
                continue

            # filtro real en cliente
            if "eng" not in languages:
                continue

            if work_key in seen_work_keys:
                continue

            seen_work_keys.add(work_key)

            try:
                time.sleep(REQUEST_DELAY)
                work = fetch_work(work_key)
                description = normalize_description(work.get("description"))

                if not description:
                    continue

                record = {
                    "id": work_key.split("/")[-1],
                    "title": title,
                    "description": description,
                    "authors": doc.get("author_name", []),
                    "first_publish_year": doc.get("first_publish_year"),
                    "subjects": doc.get("subject", []),
                    "language": languages,
                    "openlibrary_url": BASE_URL + work_key
                }

                save_book(record["id"], record)
                saved += 1
                print(f"[{saved}/{TARGET_BOOKS}] Saved: {title}")

            except Exception as e:
                print(f"Error processing {work_key}: {e}")

        page += 1
        time.sleep(REQUEST_DELAY)

    print(f"Finished. Books saved: {saved}")


if __name__ == "__main__":
    main()