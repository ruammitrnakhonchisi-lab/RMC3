-- ============================================================================
-- schema.sql
-- รันไฟล์นี้ใน Supabase Dashboard -> SQL Editor (ครั้งเดียวตอนตั้งค่าโปรเจกต์)
-- สร้างตารางเก็บผลทดสอบกำลังอัดคอนกรีต + ตั้งค่า Row Level Security (RLS)
-- ============================================================================

create table if not exists public.concrete_test_results (
    id             bigserial primary key,
    test_no        bigint unique not null,        -- เลข Test No. จากเครื่องทดสอบ (unique)
    test_date      date,                            -- วันที่ทดสอบ (แปลงจาก พ.ศ. เป็น ค.ศ. แล้ว)
    test_time      time,                            -- เวลาที่ทดสอบ
    element_type   text,                            -- ประเภทชิ้นงาน เช่น Plank, Pile i 22x22
    age_label      text,                             -- อายุคอนกรีตดิบจากไฟล์ เช่น "7", "18h"
    age_days       numeric,                          -- อายุคอนกรีตแปลงเป็นหน่วยวัน
    raw_label      text,                             -- ข้อความ No./Slump. ดิบ เช่น "No.1 S.2 cm (Z)"
    specimen_no    int,                              -- หมายเลขตัวอย่าง (1/2/3)
    slump_cm       numeric,                          -- ค่ายุบตัว (ซม.)
    location_code  text,                             -- รหัสตำแหน่ง เช่น Z, b
    weight_kg      numeric,                          -- น้ำหนักตัวอย่าง (กก.)
    strength_ksc   numeric,                          -- กำลังอัด (กก./ตร.ซม. -- ksc)
    source_file    text,                             -- ชื่อไฟล์ CSV ต้นทาง (ใช้ตรวจสอบย้อนหลัง)
    created_at     timestamptz not null default now()
);

comment on table public.concrete_test_results is
    'ผลทดสอบกำลังอัดคอนกรีต นำเข้าอัตโนมัติจากไฟล์ CSV ของเครื่องทดสอบผ่าน GitHub Actions';

create index if not exists idx_concrete_test_results_test_date
    on public.concrete_test_results (test_date);
create index if not exists idx_concrete_test_results_element_type
    on public.concrete_test_results (element_type);

-- ----------------------------------------------------------------------------
-- Row Level Security
-- ใช้ secret key (sb_secret_...) ใน GitHub Actions สำหรับ import/upsert ซึ่ง key
-- ชนิดนี้ทำงานเทียบเท่า service_role คือ "bypass RLS" โดยอัตโนมัติอยู่แล้ว
-- จึงไม่ต้องเปิด policy ให้ role "anon" เลย -- เปิด RLS ไว้เฉย ๆ ก็เพียงพอ ทำให้
-- ตารางนี้เข้าถึงไม่ได้เลยจาก client ฝั่งเบราว์เซอร์ที่ถือ publishable/anon key
-- (ปลอดภัยกว่าเดิม เพราะ workflow อื่นจะเขียนข้อมูลลงตารางนี้ไม่ได้แม้จะมี anon key หลุดไป)
--
-- ถ้าในอนาคตอยากทำหน้าเว็บ/แอปที่อ่านข้อมูลจากตารางนี้ตรง ๆ ด้วย publishable key
-- (เช่น ทำ dashboard ฝั่ง frontend) ค่อยมาเปิด policy "for select to anon" เพิ่มทีหลัง
-- ----------------------------------------------------------------------------
alter table public.concrete_test_results enable row level security;

drop policy if exists "anon can insert" on public.concrete_test_results;
drop policy if exists "anon can update (upsert)" on public.concrete_test_results;
drop policy if exists "anon can read" on public.concrete_test_results;
-- ไม่สร้าง policy ใด ๆ ให้ anon -- เข้าถึงตารางนี้ได้เฉพาะผ่าน secret/service_role key เท่านั้น
