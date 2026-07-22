"""
import_csv.py
=============
อ่านไฟล์ CSV ผลทดสอบกำลังอัดคอนกรีต (ใช้ parse_csv.py) แล้ว upsert เข้า Supabase
table `concrete_test_results` ผ่าน PostgREST API โดยตรง (ไม่พึ่ง supabase-py
เพื่อลด dependency)

ต้องตั้งค่า environment variables ก่อนรัน:
  SUPABASE_URL   เช่น https://xxxxx.supabase.co
  SUPABASE_KEY   anon/publishable key หรือ service_role/secret key

การรัน:
  python scripts/import_csv.py data/incoming/*.csv
  python scripts/import_csv.py data/incoming/*.csv --move-to data/processed --dry-run
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

import requests

from parse_csv import parse_csv_file, Record

TABLE = "concrete_test_results"
BATCH_SIZE = 200


def get_supabase_config():
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        print("ERROR: ต้องตั้งค่า env var SUPABASE_URL และ SUPABASE_KEY ก่อนรัน", file=sys.stderr)
        sys.exit(1)
    return url, key


def upsert_records(records: list[Record], url: str, key: str, dry_run: bool = False):
    if not records:
        return 0

    endpoint = f"{url}/rest/v1/{TABLE}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    params = {"on_conflict": "test_no"}

    total = 0
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        payload = [
            {k: v for k, v in r.__dict__.items()}
            for r in batch
        ]
        if dry_run:
            print(f"[dry-run] would upsert {len(payload)} rows (batch {i // BATCH_SIZE + 1})")
            total += len(payload)
            continue

        resp = requests.post(endpoint, headers=headers, params=params, json=payload, timeout=30)
        if resp.status_code not in (200, 201, 204):
            print(f"ERROR upserting batch {i // BATCH_SIZE + 1}: "
                  f"{resp.status_code} {resp.text}", file=sys.stderr)
            resp.raise_for_status()
        total += len(payload)
        print(f"upserted batch {i // BATCH_SIZE + 1}: {len(payload)} rows")

    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", help="ไฟล์ CSV ที่จะ import")
    ap.add_argument("--move-to", help="ย้ายไฟล์ไปโฟลเดอร์นี้หลัง import สำเร็จ (เช่น data/processed)")
    ap.add_argument("--dry-run", action="store_true", help="parse อย่างเดียว ไม่ยิงเข้า Supabase จริง")
    args = ap.parse_args()

    url = key = None
    if not args.dry_run:
        url, key = get_supabase_config()

    grand_total = 0
    for file_arg in args.files:
        path = Path(file_arg)
        if not path.exists():
            print(f"skip: {path} ไม่พบไฟล์", file=sys.stderr)
            continue

        records = parse_csv_file(path)
        print(f"{path.name}: parsed {len(records)} rows")

        n = upsert_records(records, url, key, dry_run=args.dry_run)
        grand_total += n

        if args.move_to and not args.dry_run:
            dest_dir = Path(args.move_to)
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(dest_dir / path.name))
            print(f"moved {path.name} -> {dest_dir}/")

    print(f"\nรวมทั้งหมด: {grand_total} rows")


if __name__ == "__main__":
    main()
