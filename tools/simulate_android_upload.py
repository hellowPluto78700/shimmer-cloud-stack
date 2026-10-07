#!/usr/bin/env python3
"""Upload a real Shimmer recording using the Android HTTP contract (stdlib only)."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid


API_BASE = "https://wwr1eh4vg9.execute-api.us-east-2.amazonaws.com"
BUCKET = "shimmer-server-clone-databucket-wn9atsyogh42"
ROOT = Path(__file__).resolve().parents[1]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    # Never follow an unexpected redirect to another API or rewrite a signed URL.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


HTTP = urllib.request.build_opener(NoRedirect)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def response_detail(raw):
    text = raw.decode("utf-8", errors="replace")
    return re.sub(
        r"(?i)(X-Amz-(?:Credential|Signature|Security-Token)=)[^&\s<\"]+",
        r"\1[REDACTED]", text,
    )[:2000]


def request(stage, method, url, body=None, content_type=None, as_json=True):
    headers = {"Content-Type": content_type} if content_type else {}
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with HTTP.open(req, timeout=45) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"{stage}: HTTP {error.code}: {response_detail(error.read())}"
        ) from None
    except urllib.error.URLError as error:
        raise RuntimeError(f"{stage}: network failure: {error.reason}") from None
    require(200 <= status < 300, f"{stage}: HTTP {status}: {response_detail(raw)}")
    if as_json:
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise RuntimeError(f"{stage}: HTTP {status}, invalid JSON: {response_detail(raw)}") from None
        require(not isinstance(result, dict) or not result.get("error"),
                f"{stage}: HTTP {status}: {response_detail(raw)}")
    else:
        result = raw
    print(f"  HTTP {status}", flush=True)
    return result


def signed_url(payload, field):
    require(isinstance(payload, dict) and isinstance(payload.get(field), str),
            f"Response missing {field}")
    url = payload[field]
    parsed = urllib.parse.urlsplit(url)
    require(parsed.scheme == "https" and parsed.hostname == f"{BUCKET}.s3.us-east-2.amazonaws.com"
            and parsed.port in (None, 443) and not parsed.username and not parsed.password,
            "Refusing presigned URL outside the NEW clone bucket's regional HTTPS endpoint")
    return url


def find_record(value, filename):
    if isinstance(value, dict):
        if value.get("full_file_name") == filename:
            return value
        for child in value.values():
            found = find_record(child, filename)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_record(child, filename)
            if found is not None:
                return found
    return None


def load_fixture(path):
    if path:
        fixture = Path(path).expanduser()
        return fixture.read_bytes(), str(fixture)
    fixture = ROOT / "shimmer-data-sync-api/test_files/000"
    if fixture.is_file():
        return fixture.read_bytes(), str(fixture)
    # Real raw recording exists in repository history, not in the current checkout.
    result = subprocess.run(
        ["git", "-C", str(ROOT / "shimmer-data-sync-api"), "show", "b19efb0:test_files/000"],
        capture_output=True, check=True,
    )
    return result.stdout, "shimmer-data-sync-api@b19efb0:test_files/000 (Git history)"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default=API_BASE, help="NEW clone API only")
    parser.add_argument("--file", help="Real raw Shimmer fixture; default: repository/history test_files/000")
    parser.add_argument("--filename", help="Upload basename; default: unique Android-style name")
    args = parser.parse_args()
    base = args.api_base.rstrip("/")
    if base != API_BASE:
        parser.error("For safety, --api-base must identify the NEW clone API: " + API_BASE)
    filename = args.filename or (
        f"SIM_ANDROID_{uuid.uuid4().hex[:8]}__"
        f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}__SIMULATOR__Shimmer_SIM-001__000.txt"
    )
    require(filename and not any(c in filename for c in "/\\\r\n") and filename not in (".", ".."),
            "--filename must be a basename, not a path")
    raw, source = load_fixture(args.file)
    require(raw, "Fixture is empty")
    print(f"Fixture: {source}\nBytes: {len(raw)}\nSHA-256: {hashlib.sha256(raw).hexdigest()}"
          f"\nAPI: {base}\nUploaded filename: {filename}", flush=True)

    def api(stage, method, path, payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        return request(stage, method, base + path, body,
                       "application/json" if body is not None else None)

    print("[1/8] POST missing-files: must be missing (no overwrite)", flush=True)
    result = api("initial missing-files", "POST", "/missing-files/", [filename])
    require(result == {"missing_files": [filename]},
            f"Expected missing filename before upload; got {result!r}. Choose a fresh --filename.")
    print("PASS initial missing-files", flush=True)

    print("[2/8] GET generate-upload-url", flush=True)
    result = api("upload URL", "GET", "/generate-upload-url/?" + urllib.parse.urlencode({"filename": filename}))
    upload_url = signed_url(result, "upload_url")
    print("PASS presigned upload URL (credentials/signature not printed)", flush=True)

    print("[3/8] PUT raw bytes to returned S3 URL (Content-Type: text/plain)", flush=True)
    request("S3 PUT", "PUT", upload_url, raw, "text/plain", as_json=False)
    print("PASS S3 upload", flush=True)

    print("[4/8] POST decode-and-store", flush=True)
    decoded = api("decode-and-store", "POST", "/decode-and-store/", {"full_file_name": filename})
    expected_key = f"decode/{Path(filename).stem}_decoded.json"
    require(isinstance(decoded, dict) and decoded.get("filename") == filename
            and decoded.get("decode_s3_key") == expected_key
            and decoded.get("recordedTimestamp") and decoded.get("endRecordedTimestamp"),
            f"Unexpected decode success response: {decoded!r}")
    print("PASS decode-and-store", flush=True)

    print("[5/8] POST missing-files: must no longer be missing", flush=True)
    result = api("second missing-files", "POST", "/missing-files/", [filename])
    require(result == {"missing_files": []}, f"Uploaded filename still missing: {result!r}")
    print("PASS second missing-files", flush=True)

    print("[6/8] GET files/combined-meta (dashboard decoded metadata path)", flush=True)
    metadata = api("dashboard metadata", "GET", "/files/combined-meta/")
    record = find_record(metadata, filename)
    require(record is not None, "Uploaded recording absent from dashboard metadata")
    for field in ("decode_s3_key", "recordedTimestamp", "endRecordedTimestamp"):
        require(record.get(field) == decoded[field], f"Metadata mismatch for {field}")
    print("PASS decoded metadata visible to dashboard", flush=True)

    query = urllib.parse.urlencode({"full_file_name": filename})
    print("[7/8] Download decoded S3 JSON via get-decoded-file-url", flush=True)
    result = api("decoded download URL", "GET", "/get-decoded-file-url/?" + query)
    arrays = request("decoded JSON", "GET", signed_url(result, "download_url"))
    require(isinstance(arrays, dict) and isinstance(arrays.get("timestampCal"), list)
            and arrays["timestampCal"], "Decoded JSON has no timestampCal samples")
    print(f"PASS decoded output: {len(arrays['timestampCal'])} timestamp samples", flush=True)

    print("[8/8] Download raw S3 object and compare original bytes", flush=True)
    result = api("raw download URL", "GET", "/generate-download-url/?" + urllib.parse.urlencode({"filename": filename}))
    uploaded = request("raw download", "GET", signed_url(result, "download_url"), as_json=False)
    require(uploaded == raw, "Raw S3 object differs from original fixture")
    print("PASS raw object byte-for-byte verification", flush=True)
    print("Frontend search item: " + json.dumps({
        field: record.get(field) for field in (
            "full_file_name", "device", "patient", "date", "shimmer_device",
            "recordedTimestamp", "endRecordedTimestamp", "decode_s3_key",
        )
    }, indent=2), flush=True)
    print("PASS all stages; test recording retained in NEW backend", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"FAIL: {error}", file=sys.stderr, flush=True)
        sys.exit(1)
