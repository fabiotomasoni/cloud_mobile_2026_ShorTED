#!/usr/bin/env python3
"""
Backfill ShorTED media metadata without rerunning the AI pipeline.

Modes:
  enrich-s3    Invoke Media_Enricher for processed S3 JSON files.
  mongo-media  Copy media fields from enriched S3 JSON files into MongoDB talks/snacks.
  all          Run enrich-s3, then mongo-media.

Default is dry-run. Use --apply to invoke Lambda or update MongoDB.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable

import boto3

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


MEDIA_FIELDS = (
    "embedUrl",
    "thumbnailUrl",
    "thumbnailUrlHd",
    "thumbnailUrlFullHd",
    "hlsUrl",
    "mp4Url",
    "mediaExtractedAt",
    "mediaExtractionVersion",
    "mediaExtractionStatus",
    "mediaExtractionError",
)


@dataclass(frozen=True)
class BackfillConfig:
    mode: str
    processed_bucket: str
    enriched_bucket: str
    prefix: str
    media_enricher_function: str
    mongodb_uri: str
    mongodb_db: str
    apply: bool
    limit: int | None
    sleep_seconds: float
    skip_existing_enriched: bool
    only_completed_media: bool
    only_mongo_slugs: bool
    missing_media_only: bool
    workers: int
    local_extract: bool
    request_timeout_seconds: int


def parse_args() -> BackfillConfig:
    parser = argparse.ArgumentParser(description="Backfill ShorTED media metadata.")
    parser.add_argument("--mode", choices=("enrich-s3", "mongo-media", "all"), default="all")
    parser.add_argument("--processed-bucket", default=os.environ.get("PROCESSED_BUCKET_NAME", "shorted-processed"))
    parser.add_argument("--enriched-bucket", default=os.environ.get("ENRICHED_BUCKET_NAME", "shorted-processed-enriched"))
    parser.add_argument("--prefix", default=os.environ.get("BACKFILL_PREFIX", "videos/"))
    parser.add_argument("--media-enricher-function", default=os.environ.get("MEDIA_ENRICHER_FUNCTION", "Media_Enricher"))
    parser.add_argument("--mongodb-uri", default=os.environ.get("MONGODB_URI", ""))
    parser.add_argument("--mongodb-db", default=os.environ.get("MONGODB_DB", "shorted"))
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of keys to process.")
    parser.add_argument("--sleep-seconds", type=float, default=0.2, help="Delay between Lambda invokes.")
    parser.add_argument("--apply", action="store_true", help="Actually invoke Lambda/update MongoDB.")
    parser.add_argument("--no-skip-existing-enriched", action="store_true", help="Invoke Media_Enricher even if enriched object already exists.")
    parser.add_argument("--include-failed-media", action="store_true", help="Update MongoDB even when mediaExtractionStatus is not completed.")
    parser.add_argument("--only-mongo-slugs", action="store_true", help="Enrich/update only slugs already present in MongoDB talks/snacks.")
    parser.add_argument("--include-existing-media", action="store_true", help="With --only-mongo-slugs, include Mongo slugs that already have media fields.")
    parser.add_argument("--workers", type=int, default=1, help="Concurrent Media_Enricher invokes for enrich-s3.")
    parser.add_argument("--local-extract", action="store_true", help="Extract TED media locally instead of invoking Media_Enricher Lambda.")
    parser.add_argument("--request-timeout-seconds", type=int, default=15, help="HTTP timeout for local TED requests.")
    args = parser.parse_args()

    return BackfillConfig(
        mode=args.mode,
        processed_bucket=args.processed_bucket,
        enriched_bucket=args.enriched_bucket,
        prefix=args.prefix,
        media_enricher_function=args.media_enricher_function,
        mongodb_uri=args.mongodb_uri,
        mongodb_db=args.mongodb_db,
        apply=args.apply,
        limit=args.limit,
        sleep_seconds=args.sleep_seconds,
        skip_existing_enriched=not args.no_skip_existing_enriched,
        only_completed_media=not args.include_failed_media,
        only_mongo_slugs=args.only_mongo_slugs,
        missing_media_only=not args.include_existing_media,
        workers=max(1, args.workers),
        local_extract=args.local_extract,
        request_timeout_seconds=args.request_timeout_seconds,
    )


def iter_json_keys(s3, bucket: str, prefix: str, limit: int | None) -> Iterable[str]:
    paginator = s3.get_paginator("list_objects_v2")
    seen = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            key = item["Key"]
            if not key.endswith(".json"):
                continue
            yield key
            seen += 1
            if limit is not None and seen >= limit:
                return


def object_exists(s3, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except s3.exceptions.ClientError as error:
        code = error.response.get("Error", {}).get("Code")
        if code in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def run_enrich_s3(config: BackfillConfig) -> None:
    s3 = boto3.client("s3")
    lambda_client = None if config.local_extract else boto3.client("lambda")
    target_slugs = load_target_slugs(config) if config.only_mongo_slugs else None
    existing_enriched = set(list_all_keys(s3, config.enriched_bucket, config.prefix)) if config.skip_existing_enriched else set()
    skipped = 0
    scanned = 0
    payloads: list[dict] = []

    if target_slugs is not None:
        print(f"target Mongo slugs: {len(target_slugs)}")
    if existing_enriched:
        print(f"existing enriched keys: {len(existing_enriched)}")

    for key in iter_json_keys(s3, config.processed_bucket, config.prefix, config.limit):
        scanned += 1
        if scanned % 500 == 0:
            print(f"progress: scanned={scanned} payloads={len(payloads)} skipped={skipped}")

        if target_slugs is not None:
            data = load_s3_json(s3, config.processed_bucket, key)
            slug = data.get("slug")
            if slug not in target_slugs:
                skipped += 1
                continue

        if key in existing_enriched:
            skipped += 1
            continue

        payload = {"bucket": config.processed_bucket, "file_key": key}
        if not config.apply:
            action = "local extract" if config.local_extract else f"invoke {config.media_enricher_function}"
            print(f"dry-run {action}: {json.dumps(payload)}")
        else:
            payloads.append(payload)

    print(f"enrich-s3 scan done: scanned={scanned} payloads={len(payloads)} skipped={skipped}")

    if config.apply and payloads:
        print(f"enrich-s3 executing {len(payloads)} jobs with {config.workers} workers")
        if config.workers == 1:
            for i, payload in enumerate(payloads, 1):
                run_enrich_job(lambda_client, config, payload)
                if i % 100 == 0:
                    print(f"enrich-s3 progress: {i}/{len(payloads)}")
        else:
            done = 0
            with ThreadPoolExecutor(max_workers=config.workers) as executor:
                futures = {executor.submit(run_enrich_job, lambda_client, config, p): p for p in payloads}
                for future in as_completed(futures):
                    future.result()
                    done += 1
                    if done % 100 == 0:
                        print(f"enrich-s3 progress: {done}/{len(payloads)}")

    invoked = len(payloads) if config.apply else scanned - skipped
    print(f"enrich-s3 summary: scanned={scanned} invoked={invoked} skipped={skipped} apply={config.apply}")


def list_all_keys(s3, bucket: str, prefix: str) -> list[str]:
    keys: list[str] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            key = item["Key"]
            if key.endswith(".json"):
                keys.append(key)
    return keys


def run_enrich_job(lambda_client, config: BackfillConfig, payload: dict) -> None:
    if config.local_extract:
        enrich_locally(config, payload)
    else:
        invoke_media_enricher(lambda_client, config, payload)


def invoke_media_enricher(lambda_client, config: BackfillConfig, payload: dict) -> None:
    key = payload["file_key"]
    response = lambda_client.invoke(
        FunctionName=config.media_enricher_function,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode("utf-8"),
    )
    raw_body = response["Payload"].read().decode("utf-8")
    status_code = response.get("StatusCode")
    if status_code != 200 or response.get("FunctionError"):
        raise RuntimeError(f"Media_Enricher failed for {key}: status={status_code} body={raw_body}")
    print(f"invoked {config.media_enricher_function}: {key}")
    if config.sleep_seconds > 0:
        time.sleep(config.sleep_seconds)


def enrich_locally(config: BackfillConfig, payload: dict) -> None:
    s3 = boto3.client("s3")
    key = payload["file_key"]
    data = load_s3_json(s3, config.processed_bucket, key)
    enriched = enrich_talk_local(data, config)
    s3.put_object(
        Bucket=config.enriched_bucket,
        Key=key,
        Body=json.dumps(enriched, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )
    print(f"local enriched: {key} status={enriched.get('mediaExtractionStatus')}")
    if config.sleep_seconds > 0:
        time.sleep(config.sleep_seconds)


def enrich_talk_local(data: dict, config: BackfillConfig) -> dict:
    now = iso_utc_now()
    slug = data.get("slug", "")
    embed_url = f"https://embed.ted.com/talks/{urllib.parse.quote(slug)}" if slug else ""

    try:
        if not slug:
            raise RuntimeError("slug is required")

        media = extract_ted_media_local(slug, data.get("url", ""), config.request_timeout_seconds)
        return {
            **data,
            **media,
            "mediaExtractedAt": now,
            "mediaExtractionVersion": "ted-media-enricher-local-v1",
            "mediaExtractionStatus": "completed",
        }
    except Exception as error:
        thumb = data.get("thumbnailUrl") or data.get("imageUrl") or data.get("image") or ""
        return {
            **data,
            "embedUrl": embed_url,
            "thumbnailUrl": thumb,
            "thumbnailUrlHd": normalise_thumbnail_url(thumb, 1280, 720) if thumb else "",
            "thumbnailUrlFullHd": normalise_thumbnail_url(thumb, 1920, 1080) if thumb else "",
            "hlsUrl": data.get("hlsUrl", ""),
            "mp4Url": data.get("mp4Url", ""),
            "mediaExtractedAt": now,
            "mediaExtractionVersion": "ted-media-enricher-local-v1",
            "mediaExtractionStatus": "failed",
            "mediaExtractionError": str(error),
        }


def extract_ted_media_local(slug: str, talk_url: str, timeout_seconds: int) -> dict:
    embed_url = f"https://embed.ted.com/talks/{urllib.parse.quote(slug)}"
    body = http_get_text(embed_url, timeout_seconds)
    next_data = extract_next_data(body)
    media = extract_media_from_next_data(next_data)

    if not media.get("thumbnailUrl") and talk_url:
        media["thumbnailUrl"] = fetch_oembed_thumbnail(talk_url, timeout_seconds)

    thumb = media.get("thumbnailUrl", "")
    return {
        "embedUrl": embed_url,
        "thumbnailUrl": thumb,
        "thumbnailUrlHd": normalise_thumbnail_url(thumb, 1280, 720),
        "thumbnailUrlFullHd": normalise_thumbnail_url(thumb, 1920, 1080),
        "hlsUrl": media.get("hlsUrl", ""),
        "mp4Url": media.get("mp4Url", ""),
    }


def http_get_text(url: str, timeout_seconds: int) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ShorTED-Media-Backfill/1.0",
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8")


def extract_next_data(body: str) -> dict:
    marker = '<script id="__NEXT_DATA__" type="application/json">'
    start = body.find(marker)
    if start < 0:
        raise RuntimeError("__NEXT_DATA__ script not found")
    json_start = start + len(marker)
    end = body.find("</script>", json_start)
    if end < 0:
        raise RuntimeError("__NEXT_DATA__ closing script tag not found")
    return json.loads(html.unescape(body[json_start:end]))


def extract_media_from_next_data(next_data: dict) -> dict:
    strings = unique(collect_url_strings(next_data))
    hls_urls = [value for value in strings if re.search(r"\.m3u8(\?|$)", value, re.IGNORECASE)]
    mp4_urls = [value for value in strings if re.search(r"\.mp4(\?|$)", value, re.IGNORECASE)]
    image_urls = [value for value in strings if re.search(r"\.(jpg|jpeg|png|webp)(\?|$)", value, re.IGNORECASE)]
    ted_images = [value for value in image_urls if re.search(r"tedcdn|ted\.com", value, re.IGNORECASE)]

    return {
        "hlsUrl": hls_urls[0] if hls_urls else "",
        "mp4Url": pick_best_mp4(mp4_urls),
        "thumbnailUrl": (ted_images or image_urls or [""])[0],
    }


def collect_url_strings(value) -> list[str]:
    if isinstance(value, str):
        return extract_urls_from_string(value)
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(collect_url_strings(item))
        return result
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(collect_url_strings(item))
        return result
    return []


def extract_urls_from_string(value: str) -> list[str]:
    normalised = value.replace("\\u0026", "&")
    if normalised.startswith("http://") or normalised.startswith("https://"):
        return [normalised]
    return re.findall(r"https?://[^\s\"'<>\\]+", normalised)


def unique(values: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def pick_best_mp4(urls: list[str]) -> str:
    if not urls:
        return ""
    return sorted(urls, key=score_mp4, reverse=True)[0]


def score_mp4(url: str) -> int:
    match = re.search(r"(?:-|_)(\d{3,5})k\.mp4", url, re.IGNORECASE) or re.search(r"(\d{3,5})k", url, re.IGNORECASE)
    if match:
        return int(match.group(1))
    if "fallback" in url.lower():
        return 1200
    return 0


def fetch_oembed_thumbnail(talk_url: str, timeout_seconds: int) -> str:
    url = "https://www.ted.com/services/v1/oembed.json?url=" + urllib.parse.quote(talk_url, safe="")
    return json.loads(http_get_text(url, timeout_seconds)).get("thumbnail_url", "")


def normalise_thumbnail_url(url: str, width: int, height: int) -> str:
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query["w"] = str(width)
    query["h"] = str(height)
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))


def iso_utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def load_s3_json(s3, bucket: str, key: str) -> dict:
    response = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(response["Body"].read().decode("utf-8"))


def load_target_slugs(config: BackfillConfig) -> set[str]:
    db = get_mongo_db(config)
    query = mongo_missing_media_query() if config.missing_media_only else {}

    snack_slugs = set(db["snacks"].distinct("talkSlug", query))
    talk_slugs = set(db["talks"].distinct("slug", query))
    return {slug for slug in snack_slugs | talk_slugs if slug}


def mongo_missing_media_query() -> dict:
    return {
        "$or": [
            {"thumbnailUrlFullHd": {"$exists": False}},
            {"thumbnailUrlFullHd": ""},
            {"hlsUrl": {"$exists": False}},
            {"hlsUrl": ""},
            {"mp4Url": {"$exists": False}},
            {"mp4Url": ""},
        ]
    }


def extract_media_update(data: dict, only_completed_media: bool) -> tuple[str, dict] | None:
    slug = data.get("slug")
    if not slug:
        return None
    if only_completed_media and data.get("mediaExtractionStatus") != "completed":
        return None

    update = {field: data.get(field, "") for field in MEDIA_FIELDS if field in data}
    if not any(update.get(field) for field in ("thumbnailUrlFullHd", "hlsUrl", "mp4Url")):
        return None
    return slug, update


def get_mongo_db(config: BackfillConfig):
    if not config.mongodb_uri:
        raise RuntimeError("MONGODB_URI is required for --mode mongo-media or --mode all")
    from pymongo import MongoClient

    client = MongoClient(config.mongodb_uri, serverSelectionTimeoutMS=5000)
    return client[config.mongodb_db]


def run_mongo_media(config: BackfillConfig) -> None:
    s3 = boto3.client("s3")
    db = get_mongo_db(config) if (config.apply or config.only_mongo_slugs) else None
    target_slugs = load_target_slugs(config) if config.only_mongo_slugs else None
    planned = 0
    updated_talks = 0
    updated_snacks = 0
    skipped = 0

    for key in iter_json_keys(s3, config.enriched_bucket, config.prefix, config.limit):
        data = load_s3_json(s3, config.enriched_bucket, key)
        extracted = extract_media_update(data, config.only_completed_media)
        if extracted is None:
            skipped += 1
            print(f"skip no usable media: s3://{config.enriched_bucket}/{key}")
            continue

        slug, media_update = extracted
        if target_slugs is not None and slug not in target_slugs:
            skipped += 1
            continue

        planned += 1
        if not config.apply:
            print(f"dry-run mongo update slug={slug} fields={sorted(media_update.keys())}")
            continue

        talk_result = db["talks"].update_many({"slug": slug}, {"$set": media_update})
        snack_result = db["snacks"].update_many({"talkSlug": slug}, {"$set": media_update})
        updated_talks += talk_result.modified_count
        updated_snacks += snack_result.modified_count
        print(f"updated slug={slug} talks={talk_result.modified_count} snacks={snack_result.modified_count}")

    print(
        "mongo-media summary: "
        f"planned={planned} skipped={skipped} updated_talks={updated_talks} "
        f"updated_snacks={updated_snacks} apply={config.apply}"
    )


def main() -> None:
    config = parse_args()

    print(
        "media_backfill config: "
        f"processed={config.processed_bucket} enriched={config.enriched_bucket} "
        f"prefix={config.prefix} apply={config.apply} limit={config.limit}"
    )

    if config.mode in ("enrich-s3", "all"):
        run_enrich_s3(config)
    if config.mode in ("mongo-media", "all"):
        run_mongo_media(config)


if __name__ == "__main__":
    main()
