"""
parse_csv.py
============
แปลงไฟล์ CSV ผลทดสอบกำลังอัดคอนกรีต (compressive strength test report)
ที่ export มาจากเครื่องทดสอบ ให้เป็นรายการ record ที่ใช้ insert ลง Supabase ได้

ที่มาของความยุ่งยาก:
- ไฟล์เป็น CSV ที่ export มาจากรายงานที่พิมพ์แบบมีการ "ตัดบรรทัด" อัตโนมัติ
  เมื่อข้อความในช่อง "No./Slump." ยาวเกินไป ทำให้บางแถวข้อมูลมีช่องนี้ว่าง
  แล้วมีแถวถัดไปที่มีแค่ช่องนี้ช่องเดียวโผล่มาแทน (continuation row)
- มีแถว header ซ้ำทุกหน้า, แถว "Print Date/Time", "test by :", "Page :N",
  "TOTAL :" และแถวว่างคั่นระหว่าง record ซึ่งต้องข้ามทิ้ง
- วันที่เป็น พ.ศ. (พุทธศักราช) ต้องแปลงเป็น ค.ศ. (-543)
- ช่อง "No./Slump." เป็นข้อความรวม เช่น "No.1 S.2 cm (Z)" ต้องแยกเป็น
  หมายเลขตัวอย่าง (specimen_no), ค่ายุบตัว (slump_cm), และรหัสตำแหน่ง (location_code)
- ช่อง "Date of Unit" คืออายุคอนกรีตตอนทดสอบ เช่น "7" (7 วัน) หรือ "18h" (18 ชั่วโมง)
"""
import csv
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

LABEL_RE = re.compile(
    r"no\.?\s*(\d+)\s*s\.?\s*([\d.]+)\s*cm\.?\s*\(([^)]+)\)",
    re.IGNORECASE,
)

SKIP_SUBSTRINGS = ("Print Date", "test by", "Page :", "TOTAL")


@dataclass
class Record:
    test_no: int
    test_date: Optional[str]
    test_time: Optional[str]
    element_type: str
    age_label: str
    age_days: Optional[float]
    raw_label: str
    specimen_no: Optional[int]
    slump_cm: Optional[float]
    location_code: Optional[str]
    weight_kg: Optional[float]
    strength_ksc: Optional[float]
    source_file: str


def thai_date_to_iso(thai_date: str) -> Optional[str]:
    """'1/7/2569' (พ.ศ.) -> '2026-07-01' (ค.ศ., ISO)"""
    thai_date = thai_date.strip()
    if not thai_date:
        return None
    try:
        d, m, y = thai_date.split("/")
        gregorian_year = int(y) - 543
        return f"{gregorian_year:04d}-{int(m):02d}-{int(d):02d}"
    except Exception:
        return None


def age_label_to_days(age_label: str) -> Optional[float]:
    age_label = age_label.strip()
    if not age_label:
        return None
    try:
        if age_label.lower().endswith("h"):
            return round(float(age_label[:-1]) / 24.0, 4)
        return float(age_label)
    except Exception:
        return None


def parse_label(raw_label: str):
    """แยก 'No.1 S.2 cm (Z)' -> (1, 2.0, 'Z')"""
    if not raw_label:
        return None, None, None
    m = LABEL_RE.search(raw_label)
    if not m:
        return None, None, None
    specimen_no = int(m.group(1))
    try:
        slump_cm = float(m.group(2))
    except ValueError:
        slump_cm = None
    location_code = m.group(3).strip()
    return specimen_no, slump_cm, location_code


def to_float(val: str) -> Optional[float]:
    val = (val or "").strip()
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        return None


def is_blank_row(fields) -> bool:
    return all((f or "").strip() == "" for f in fields)


def is_header_row(fields) -> bool:
    return len(fields) > 1 and fields[1].strip() == "Test No."


def is_footer_row(line: str) -> bool:
    return any(s in line for s in SKIP_SUBSTRINGS)


def is_continuation_row(fields) -> bool:
    if len(fields) <= 7:
        return False
    if any((fields[i] or "").strip() != "" for i in range(1, 7)):
        return False
    return (fields[7] or "").strip() != ""


def parse_csv_file(path: Path) -> list[Record]:
    raw_lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    records: list[Record] = []

    for line in raw_lines:
        if not line.strip():
            continue
        if is_footer_row(line):
            continue
        fields = line.split(";")
        # pad to at least 13 fields so index access is safe
        fields += [""] * (13 - len(fields))

        if is_blank_row(fields):
            continue
        if is_header_row(fields):
            continue

        test_no_field = fields[1].strip()
        if test_no_field.isdigit():
            raw_label = fields[7].strip()
            specimen_no, slump_cm, location_code = parse_label(raw_label)
            rec = Record(
                test_no=int(test_no_field),
                test_date=thai_date_to_iso(fields[2]),
                test_time=fields[3].strip() or None,
                element_type=fields[4].strip(),
                age_label=fields[6].strip(),
                age_days=age_label_to_days(fields[6]),
                raw_label=raw_label,
                specimen_no=specimen_no,
                slump_cm=slump_cm,
                location_code=location_code,
                weight_kg=to_float(fields[10]),
                strength_ksc=to_float(fields[12]),
                source_file=path.name,
            )
            records.append(rec)
            continue

        if is_continuation_row(fields):
            if records and not records[-1].raw_label:
                raw_label = fields[7].strip()
                specimen_no, slump_cm, location_code = parse_label(raw_label)
                records[-1].raw_label = raw_label
                records[-1].specimen_no = specimen_no
                records[-1].slump_cm = slump_cm
                records[-1].location_code = location_code
            continue

        # anything else (stray footer artifacts) is silently ignored

    return records


def main():
    if len(sys.argv) < 2:
        print("usage: parse_csv.py <file1.csv> [file2.csv ...]")
        sys.exit(1)

    all_records: list[Record] = []
    for arg in sys.argv[1:]:
        path = Path(arg)
        recs = parse_csv_file(path)
        print(f"{path.name}: parsed {len(recs)} records", file=sys.stderr)
        all_records.extend(recs)

    unparsed_labels = [r for r in all_records if r.raw_label and r.specimen_no is None]
    if unparsed_labels:
        print(f"WARNING: {len(unparsed_labels)} records had a raw_label that "
              f"couldn't be split into specimen/slump/code:", file=sys.stderr)
        for r in unparsed_labels[:10]:
            print(f"  test_no={r.test_no} raw_label={r.raw_label!r}", file=sys.stderr)

    missing_labels = [r for r in all_records if not r.raw_label]
    if missing_labels:
        print(f"WARNING: {len(missing_labels)} records ended up with NO label at all "
              f"(continuation row was missing/misaligned):", file=sys.stderr)
        for r in missing_labels[:10]:
            print(f"  test_no={r.test_no}", file=sys.stderr)

    import json
    print(json.dumps([asdict(r) for r in all_records], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
