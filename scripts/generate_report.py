"""
generate_report.py
===================
ดึงข้อมูลผลทดสอบกำลังอัดคอนกรีตจาก Supabase มาสรุปเป็นรายงาน Markdown
(ใช้ดูสรุปรวมได้เร็ว ๆ โดยไม่ต้องเปิด Supabase dashboard เอง)

ต้องตั้งค่า env var เหมือน import_csv.py:
  SUPABASE_URL, SUPABASE_KEY

การรัน:
  python scripts/generate_report.py --out reports/summary.md
"""
import argparse
import os
import statistics
import sys
from collections import defaultdict

import requests

TABLE = "concrete_test_results"

# ค่ากำลังอัดที่ต่ำผิดปกติ (เช่น 0.000 หรือใกล้ 0) มักแปลว่าทดสอบผิดพลาด/เครื่อง error
# ไม่ใช่ค่ากำลังอัดจริงของคอนกรีต จึงตั้ง threshold ไว้เตือนแยกออกมา
SUSPECT_STRENGTH_THRESHOLD = 5.0


def fetch_all_rows(url: str, key: str):
    endpoint = f"{url}/rest/v1/{TABLE}"
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    rows = []
    offset = 0
    page_size = 1000
    while True:
        headers["Range-Unit"] = "items"
        headers["Range"] = f"{offset}-{offset + page_size - 1}"
        resp = requests.get(endpoint, headers=headers, params={"select": "*"}, timeout=30)
        resp.raise_for_status()
        chunk = resp.json()
        rows.extend(chunk)
        if len(chunk) < page_size:
            break
        offset += page_size
    return rows


def build_report(rows: list[dict]) -> str:
    if not rows:
        return "# รายงานสรุปผลทดสอบกำลังอัดคอนกรีต\n\nยังไม่มีข้อมูลในตาราง\n"

    lines = []
    lines.append("# รายงานสรุปผลทดสอบกำลังอัดคอนกรีต")
    lines.append("")
    lines.append(f"จำนวนตัวอย่างทั้งหมด: **{len(rows)}** รายการ")
    lines.append("")

    # สรุปตาม element_type + age_label
    groups = defaultdict(list)
    for r in rows:
        key = (r.get("element_type") or "-", r.get("age_label") or "-")
        strength = r.get("strength_ksc")
        if strength is not None:
            groups[key].append(strength)

    lines.append("## สรุปตามประเภทชิ้นงาน / อายุ")
    lines.append("")
    lines.append("| ประเภทชิ้นงาน | อายุ | จำนวน | ค่าเฉลี่ย (ksc) | ต่ำสุด | สูงสุด |")
    lines.append("|---|---|---|---|---|---|")
    for (element_type, age_label), values in sorted(groups.items()):
        avg = statistics.mean(values)
        lines.append(
            f"| {element_type} | {age_label} | {len(values)} | "
            f"{avg:.1f} | {min(values):.1f} | {max(values):.1f} |"
        )
    lines.append("")

    # แถวที่ค่ากำลังอัดต่ำผิดปกติ (น่าสงสัยว่าทดสอบผิดพลาด)
    suspects = [
        r for r in rows
        if r.get("strength_ksc") is not None and r["strength_ksc"] < SUSPECT_STRENGTH_THRESHOLD
    ]
    if suspects:
        lines.append(f"## ⚠ ค่ากำลังอัดต่ำผิดปกติ (< {SUSPECT_STRENGTH_THRESHOLD} ksc) — ควรตรวจสอบ")
        lines.append("")
        lines.append("| Test No. | วันที่ | ประเภทชิ้นงาน | ค่า (ksc) | ที่มาไฟล์ |")
        lines.append("|---|---|---|---|---|")
        for r in suspects:
            lines.append(
                f"| {r.get('test_no')} | {r.get('test_date')} | {r.get('element_type')} | "
                f"{r.get('strength_ksc')} | {r.get('source_file')} |"
            )
        lines.append("")

    # แถวที่ label แยกไม่ออก (raw_label ว่าง หรือ parse ไม่ได้) — เผื่อไฟล์ในอนาคตมีรูปแบบแปลกใหม่
    unparsed = [r for r in rows if not r.get("specimen_no")]
    if unparsed:
        lines.append(f"## ⚠ รายการที่แยกข้อมูล No./Slump. ไม่สำเร็จ ({len(unparsed)} รายการ)")
        lines.append("")
        lines.append("| Test No. | raw_label | ที่มาไฟล์ |")
        lines.append("|---|---|---|")
        for r in unparsed[:50]:
            lines.append(f"| {r.get('test_no')} | {r.get('raw_label')} | {r.get('source_file')} |")
        lines.append("")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/summary.md")
    args = ap.parse_args()

    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        print("ERROR: ต้องตั้งค่า env var SUPABASE_URL และ SUPABASE_KEY ก่อนรัน", file=sys.stderr)
        sys.exit(1)

    rows = fetch_all_rows(url, key)
    report = build_report(rows)

    out_path = args.out
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"เขียนรายงานไปที่ {out_path} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
