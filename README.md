# RMC3 — แปลง CSV กำลังอัดคอนกรีต เข้า Supabase อัตโนมัติ

ไฟล์ชุดนี้ทำหน้าที่:

1. รับไฟล์ CSV ผลทดสอบกำลังอัดคอนกรีต (export จากเครื่องทดสอบ) ที่วางไว้ในโฟลเดอร์ `data/incoming/`
2. แปลง/ทำความสะอาดข้อมูล (วันที่ พ.ศ. → ค.ศ., แยกเลขตัวอย่าง/ค่ายุบตัวจากข้อความ, รวมแถวที่ตัดบรรทัด ฯลฯ)
3. ส่งข้อมูลเข้า Supabase table `concrete_test_results` โดยอัตโนมัติผ่าน **GitHub Actions** ทุกครั้งที่มีการ push ไฟล์ CSV ใหม่
4. สร้างรายงานสรุปผล (`reports/summary.md`) ให้อัตโนมัติ
5. แสดงผลเป็น **หน้าเว็บ dashboard** (`index.html`) ที่เปิดดูได้ผ่าน GitHub Pages — ดึงข้อมูลสด
   จาก Supabase มาแสดงเป็นกราฟ + ตาราง ทุกครั้งที่เปิดหน้า

## โครงสร้างไฟล์

```
index.html         <- หน้าเว็บ dashboard (เปิดผ่าน GitHub Pages) ดึงข้อมูลสดจาก Supabase มาแสดง
data/incoming/     <- วางไฟล์ CSV ใหม่ตรงนี้ (แล้ว push ขึ้น GitHub)
data/processed/    <- ไฟล์ที่ import เข้า Supabase สำเร็จแล้ว จะถูกย้ายมาไว้ที่นี่อัตโนมัติ
sample_data/       <- ไฟล์ตัวอย่างที่ใช้ทดสอบตอนออกแบบระบบ (11569.csv)
scripts/
  parse_csv.py       <- ตรรกะแปลง/ทำความสะอาด CSV (ไม่ยุ่งกับ Supabase)
  import_csv.py      <- อ่าน CSV แล้ว upsert เข้า Supabase
  generate_report.py <- ดึงข้อมูลจาก Supabase มาสรุปเป็น reports/summary.md
supabase/schema.sql  <- SQL สร้างตาราง + RLS policy (รันครั้งเดียวใน Supabase SQL Editor)
.github/workflows/import.yml <- GitHub Actions workflow ที่รันทุกอย่างอัตโนมัติ
```

## ขั้นตอนติดตั้ง (ทำครั้งเดียว)

### 1. สร้างตารางใน Supabase

เปิด Supabase project ของคุณ (`asulsstgrtbwtddopngw`) → เมนู **SQL Editor** → วางเนื้อหาไฟล์
`supabase/schema.sql` ทั้งหมด แล้วกด Run

> **หมายเหตุสำคัญเรื่อง API key:** ใช้ **secret key** (`sb_secret_...`) สำหรับ `SUPABASE_KEY` ใน
> GitHub Secret เท่านั้น — key ชนิดนี้ทำงานเทียบเท่า service_role คือ bypass RLS ได้อัตโนมัติ ไม่ต้อง
> เปิด policy insert/update ให้ role anon เลย ส่วน **publishable key** (`sb_publishable_...`) ที่ให้
> มาตอนแรก schema.sql เปิด policy **select อย่างเดียว** ให้ role anon ไว้ เพราะ `index.html`
> (หน้าเว็บ dashboard) ฝัง publishable key นี้ไว้ในโค้ดฝั่ง client เพื่ออ่านข้อมูลมาแสดงผล — ปลอดภัย
> เพราะ key ชนิดนี้ถูกออกแบบมาให้เปิดเผยต่อสาธารณะได้ และไม่มี policy insert/update/delete ให้เลย
> **ห้ามใช้ publishable key ทำ import/upsert เด็ดขาด** (ไม่มีสิทธิ์เขียนข้อมูล) และ **ห้ามเอา secret
> key ไปฝังใน index.html หรือโค้ดฝั่ง client เด็ดขาด** เพราะ secret key bypass RLS ได้ทั้งหมด ใครเห็น
> ก็แก้/ลบข้อมูลได้หมด — secret key ใช้ใน GitHub Actions (ฝั่ง server) เท่านั้น

### 2. ตั้งค่า GitHub Secrets

ไปที่ repo บน GitHub → **Settings → Secrets and variables → Actions → New repository secret**
แล้วเพิ่ม 2 ค่า:

| Name | Value |
|---|---|
| `SUPABASE_URL` | `https://asulsstgrtbwtddopngw.supabase.co` |
| `SUPABASE_KEY` | secret key ของคุณ (ขึ้นต้นด้วย `sb_secret_...`) |

**อย่า commit ค่าเหล่านี้ลงในโค้ดเด็ดขาด** เก็บเป็น GitHub secret เท่านั้น สคริปต์ทุกตัวอ่านค่า
จาก environment variable `SUPABASE_URL` / `SUPABASE_KEY` เสมอ secret key นี้เป็นกุญแจสำคัญที่สุด
ของโปรเจกต์ (bypass RLS ได้ทั้งหมด) — อย่าแปะไว้ในแชทหรือไฟล์ใด ๆ อีก ถ้าเผลอแชร์ไปแล้วแนะนำเข้า
Supabase Dashboard → Settings → API แล้วกด regenerate key ใหม่

### 3. Push โค้ดชุดนี้เข้า repo

Repo `RMC3` ตอนนี้มีแค่ README เปล่า ให้ก็อปไฟล์ทั้งหมดในชุดนี้เข้าไปที่ root ของ repo แล้ว
commit + push ครั้งแรก (จะยังไม่ trigger workflow เพราะยังไม่มีไฟล์ใน `data/incoming/`)

> **หมายเหตุเรื่องความเป็นส่วนตัว:** ถ้า repo เป็น public ข้อมูลกำลังอัดที่ push เข้าไป (วันที่ทดสอบ
> ประเภทชิ้นงาน ค่ากำลังอัด ฯลฯ) จะมองเห็นได้จากภายนอก ถ้าไม่ต้องการให้คนอื่นเห็นข้อมูลนี้ แนะนำเปลี่ยน
> repo เป็น **private** (GitHub → Settings → General → Danger Zone → Change visibility) — **ถ้า repo
> เป็น private ต้องเปิด GitHub Pages แบบ paid plan** (GitHub Pages สำหรับ private repo ใช้ได้เฉพาะ
> องค์กร/บัญชีที่มี GitHub Pro ขึ้นไป) ไม่งั้นหน้า dashboard (`index.html`) จะเปิดจากภายนอกไม่ได้
> — ถ้าอยากได้ทั้ง private repo และหน้าเว็บดูได้ ให้พิจารณาย้าย `index.html` ไปโฮสต์ที่อื่นแทน (เช่น
> Netlify/Vercel/Cloudflare Pages ซึ่งรองรับ private source repo บน free plan)

### 4. เปิดหน้าเว็บ dashboard ผ่าน GitHub Pages

หลัง push ไฟล์ `index.html` เข้า repo แล้ว:

1. ไปที่ repo → **Settings → Pages**
2. หัวข้อ **Build and deployment → Source** เลือก **Deploy from a branch**
3. **Branch** เลือก `main` และโฟลเดอร์เลือก **/ (root)** แล้วกด **Save**
4. รอ 1-2 นาที (GitHub จะรัน workflow ชื่อ "pages build and deployment" ให้อัตโนมัติ) แล้วเข้า
   `https://ruammitrnakhonchisi-lab.github.io/RMC3/` — ควรเห็นหน้า dashboard แทนหน้า 404

**ถ้ายังขึ้น 404:** เช็คแท็บ **Actions** ว่า job "pages build and deployment" รันสำเร็จ (สีเขียว)
หรือยัง ถ้ายังไม่มี job นี้เลย แปลว่ายังไม่ได้ตั้งค่า Source ในขั้นตอนที่ 2-3 ข้างต้น

**ถ้าหน้าเว็บขึ้น "โหลดข้อมูลไม่สำเร็จ":** แปลว่ารัน `supabase/schema.sql` ยังไม่ครบ หรือ policy
`"anon can read"` ยังไม่ถูกสร้าง — กลับไปรัน `supabase/schema.sql` ทั้งไฟล์อีกรอบใน SQL Editor
(รันซ้ำได้ปลอดภัย เพราะใช้ `create if not exists` / `drop policy if exists` ทุกจุด)

## การใช้งานประจำวัน

1. เอาไฟล์ CSV ใหม่จากเครื่องทดสอบ วางไว้ใน `data/incoming/`
2. `git add data/incoming/<ไฟล์ใหม่>.csv && git commit -m "add new test results" && git push`
3. GitHub Actions จะรันอัตโนมัติ: parse → upsert เข้า Supabase → ย้ายไฟล์ไป `data/processed/` →
   สร้าง `reports/summary.md` ใหม่ → commit ผลกลับเข้า repo เอง
4. ดูผลได้ 3 ทาง: เปิด **หน้าเว็บ dashboard** ที่ `https://ruammitrnakhonchisi-lab.github.io/RMC3/`
   (ข้อมูลอัปเดตสดทันทีที่รีเฟรชหน้า ไม่ต้องรอ workflow), เปิด `reports/summary.md` ใน repo,
   หรือดูสรุปในแท็บ **Actions** ของ GitHub (job summary จะโชว์ตารางสรุปให้เลย)

หรือจะรันเองแบบ manual ก็ได้จากแท็บ **Actions → Import CSV -> Supabase → Run workflow**

## รันทดสอบในเครื่องตัวเอง (ไม่ยุ่งกับ Supabase จริง)

```bash
pip install -r requirements.txt
python scripts/parse_csv.py sample_data/11569.csv       # แค่ parse ดูผลลัพธ์เป็น JSON
python scripts/import_csv.py sample_data/11569.csv --dry-run   # จำลอง import โดยไม่ยิงเข้า Supabase
```

รันจริงในเครื่องตัวเอง (ต้องตั้งค่า env var ก่อน):

```bash
export SUPABASE_URL="https://asulsstgrtbwtddopngw.supabase.co"
export SUPABASE_KEY="sb_publishable_xxxxxxxx"
python scripts/import_csv.py sample_data/11569.csv --move-to data/processed
python scripts/generate_report.py --out reports/summary.md
```

## รูปแบบข้อมูลที่รองรับ

ไฟล์ CSV ต้นทางเป็นรายงานที่ export จากเครื่องทดสอบ แต่ละแถวข้อมูลมีคอลัมน์ (คั่นด้วย `;`):

```
;Test No.;Date;Time;Customer;;Date of Unit;No./Slump.;;Weight( Kg.);;;Kgm/Cm
```

สคริปต์ `parse_csv.py` จะ:
- ข้ามแถว header ที่พิมพ์ซ้ำทุกหน้า, แถว `Page :N`, `Print Date/Time`, `test by :`, `TOTAL :`, แถวว่าง
- รวมแถว "ตัดบรรทัด" ที่ข้อความ `No./Slump.` ล้นไปอยู่แถวถัดไปเดี่ยว ๆ เข้ากับแถวข้อมูลด้านบน
- แปลงวันที่ พ.ศ. → ค.ศ. (`1/7/2569` → `2026-07-01`)
- แปลงอายุคอนกรีต `Date of Unit` (`"7"`=7 วัน, `"18h"`=18 ชั่วโมง) เป็น `age_days`
- แยก `No./Slump.` เช่น `"No.1 S.2 cm (Z)"` เป็น `specimen_no=1`, `slump_cm=2.0`, `location_code="Z"`

ทดสอบกับไฟล์ตัวอย่าง `sample_data/11569.csv` (303 รายการ) แล้ว parse ได้ครบ 303 รายการตรงกับ
0898378413
บรรทัด `TOTAL : 303` ท้ายไฟล์พอดี โดยไม่มี label ไหนแยกไม่ออกเลย

ถ้าเจอไฟล์ CSV รูปแบบใหม่ที่ parse ไม่ครบ หรือ `raw_label` แยกไม่ออก ให้ดู warning ที่ขึ้นตอนรัน
`parse_csv.py` (จะ list test_no ที่มีปัญหาให้) และดูหัวข้อ "⚠" ใน `reports/summary.md`
