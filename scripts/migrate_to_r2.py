"""
Migrate local uploads to Cloudflare R2 using multipart upload.
Each file is split into 512 KB parts to avoid connection timeouts on slow networks.

Usage:
  python scripts/migrate_to_r2.py               # default 3 workers
  python scripts/migrate_to_r2.py --workers 2
  python scripts/migrate_to_r2.py --dry-run
  python scripts/migrate_to_r2.py --force       # re-upload already-uploaded
"""
import sys, os, argparse, mimetypes, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import functools

sys.stdout.reconfigure(encoding="utf-8")
print = functools.partial(print, flush=True)

import boto3
from botocore.config import Config as BotoConfig
from pathlib import Path

# ── R2 credentials ────────────────────────────────────────────────────────────
ACCOUNT_ID = "28c7a2284bad6930b719d160a5e692fa"
ACCESS_KEY = "03dc8e5506b1e9394db2c8337eae0c44"
SECRET_KEY = "9f877ba9e0aed2cf4ac67c2ded67e91b5f654a1ba5d5477e4471cd60c20abf27"
BUCKET     = "clawfans"
PUBLIC_URL = "https://assets.tinyclaw.dev"
ENDPOINT   = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"

PART_SIZE  = 5 * 1024 * 1024   # unused now; all files < 5 MB so put_object is used
UPLOADS_DIR = Path(__file__).parent.parent / "backend" / "uploads"
IMAGE_EXTS  = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

print_lock = Lock()


def make_client():
    cfg = BotoConfig(
        retries={"max_attempts": 3, "mode": "adaptive"},
        connect_timeout=60,
        read_timeout=600,   # 10 min — large files take ~90s on slow connections
    )
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name="auto",
        config=cfg,
    )


def list_existing_keys(s3) -> set:
    keys = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET):
        for obj in page.get("Contents", []):
            keys.add(obj["Key"])
    return keys


def upload_multipart(s3, key: str, data: bytes, mime: str) -> None:
    """Upload data in 512 KB parts. Required for large files on slow connections."""
    mpu = s3.create_multipart_upload(
        Bucket=BUCKET, Key=key,
        ContentType=mime, CacheControl="public, max-age=31536000",
    )
    upload_id = mpu["UploadId"]
    parts = []
    try:
        for i, offset in enumerate(range(0, len(data), PART_SIZE), start=1):
            chunk = data[offset:offset + PART_SIZE]
            resp = s3.upload_part(
                Bucket=BUCKET, Key=key, UploadId=upload_id,
                PartNumber=i, Body=chunk,
            )
            parts.append({"PartNumber": i, "ETag": resp["ETag"]})
        s3.complete_multipart_upload(
            Bucket=BUCKET, Key=key, UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )
    except Exception:
        s3.abort_multipart_upload(Bucket=BUCKET, Key=key, UploadId=upload_id)
        raise


def upload_one(f: Path, retries: int = 3) -> tuple[str, bool, str]:
    rel  = f.relative_to(UPLOADS_DIR.parent)
    key  = rel.as_posix()
    mime = mimetypes.guess_type(str(f))[0] or "image/png"

    for attempt in range(retries):
        try:
            s3 = make_client()
            with open(f, "rb") as fh:
                data = fh.read()
            # All files are < 5 MB; use put_object with extended timeout
            s3.put_object(
                Bucket=BUCKET, Key=key, Body=data,
                ContentType=mime, CacheControl="public, max-age=31536000",
            )
            return key, True, f"{PUBLIC_URL}/{key}"
        except Exception as e:
            if attempt < retries - 1:
                wait = 5 * (attempt + 1)
                time.sleep(wait)
            else:
                return key, False, str(e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run",  action="store_true")
    parser.add_argument("--force",    action="store_true")
    parser.add_argument("--workers",  type=int, default=3)
    args = parser.parse_args()

    s3_main = make_client()

    files = sorted(f for f in UPLOADS_DIR.rglob("*")
                   if f.is_file() and f.suffix.lower() in IMAGE_EXTS)
    print(f"Found {len(files)} image files")

    if args.dry_run:
        for f in files[:5]:
            print(f"  {f.relative_to(UPLOADS_DIR.parent).as_posix()}")
        print(f"  … {len(files)} total")
        return

    print("Fetching existing R2 keys …")
    existing = set() if args.force else list_existing_keys(s3_main)
    print(f"  R2 already contains {len(existing)} objects")

    to_upload = [f for f in files
                 if f.relative_to(UPLOADS_DIR.parent).as_posix() not in existing]
    skipped = len(files) - len(to_upload)
    print(f"  To upload: {len(to_upload)}  Already done (skip): {skipped}")

    if not to_upload:
        print("Nothing to do.")
        return

    done = 0; failed = 0
    start = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(upload_one, f): f for f in to_upload}
        for fut in as_completed(futures):
            key, ok, msg = fut.result()
            done += 1
            elapsed = time.time() - start
            rate = done / elapsed
            eta = (len(to_upload) - done) / rate if rate else 0
            label = f"[{done}/{len(to_upload)} | ETA ~{eta/60:.0f}m]"
            with print_lock:
                if ok:
                    print(f"{label} OK  {key}")
                else:
                    failed += 1
                    print(f"{label} FAIL  {key[:60]}: {msg[:80]}")

    print()
    print("=" * 60)
    elapsed = time.time() - start
    print(f"Done={done-failed}  Failed={failed}  Skipped={skipped}  Time={elapsed/60:.1f}min")
    print(f"Public base: {PUBLIC_URL}/uploads/")
    if failed:
        print("Re-run to retry failed files (skipped files are already in R2).")


if __name__ == "__main__":
    main()
