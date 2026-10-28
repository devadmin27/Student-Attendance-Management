# MASTER PROMPT: Student Attendance Management System
## Professional Full-Stack Development Specification for OpenCode

คุณคือ Senior Full-Stack Software Architect, Senior Django Developer, Senior Next.js Developer, Database Architect และ Cybersecurity Engineer มีหน้าที่วิเคราะห์ ออกแบบ พัฒนา ทดสอบ และจัดทำเอกสารระบบ **Student Attendance Management System (SAMS)** ซึ่งเป็นระบบบริหารจัดการการเข้าเรียนของนักศึกษาผ่าน QR Code แบบออนไลน์ สำหรับสถาบันการศึกษา

เป้าหมายคือพัฒนาระบบให้มีคุณภาพระดับ Production-Ready โดยใช้สถาปัตยกรรมที่แยก Front-end, Back-end และ Database อย่างชัดเจน มีความปลอดภัย ใช้งานง่าย รองรับมือถือ และสามารถบำรุงรักษาหรือขยายระบบในอนาคตได้

**ข้อกำหนดสำคัญ:** ให้ดำเนินการพัฒนาระบบจริงภายใน Workspace ของ OpenCode ไม่ใช่เพียงสร้างตัวอย่างหน้าจอหรือเขียนแผนงาน ห้ามหยุดหลังจากสร้างโครงสร้างโปรเจกต์ ต้องพัฒนา API, ฐานข้อมูล, ระบบยืนยันตัวตน, QR Code, Dashboard, การทดสอบ และเอกสารประกอบให้เชื่อมต่อกันได้จริง

---

# 1. Project Information

- Project Name: Student Attendance Management System
- Project Abbreviation: SAMS
- Project Type: Web-Based Student Attendance Management System
- Target Users: ผู้ดูแลระบบ อาจารย์ผู้สอน และนักศึกษา
- Language: ภาษาไทยเป็นภาษาหลัก
- Timezone: Asia/Bangkok
- Date Format: DD/MM/YYYY
- Time Format: 24-hour format
- Default Theme: White–Blue Academic Information System
- Primary Access: Responsive Web Application
- Development Environment: OpenCode
- Front-end: Next.js + TypeScript + Tailwind CSS + SweetAlert2
- Back-end: Django เวอร์ชัน Stable ล่าสุดที่เหมาะสม ณ เวลาพัฒนา พร้อม Django REST Framework
- Database: Supabase PostgreSQL
- API Architecture: REST API
- Authentication: Secure Token-Based Authentication
- QR Code: Dynamic, Time-Limited, Single-Use Attendance Token

ก่อนเริ่มพัฒนา ให้ตรวจสอบเอกสารทางการและเวอร์ชัน Stable ล่าสุดของ Next.js, React, TypeScript, Django, Django REST Framework, PostgreSQL และ Supabase โดยเลือกเวอร์ชันที่เข้ากันได้จริง บันทึกเวอร์ชันที่เลือกไว้ในเอกสารและ Lockfile ห้ามใช้เวอร์ชันทดลองหรือ API ที่เลิกสนับสนุนโดยไม่มีเหตุผลจำเป็น

---

# 2. System Architecture

ออกแบบระบบด้วยสถาปัตยกรรมแยกส่วนดังนี้

```text
Student / Instructor / Administrator
                  |
                  v
       Next.js Web Application
       TypeScript + Tailwind CSS
       SweetAlert2 + QR Scanner
                  |
                  | HTTPS / REST API
                  | Authorization: Bearer Token
                  v
          Django REST API
          Business Logic
          Authentication
          Role Permissions
          QR Token Validation
          Attendance Processing
          Reporting and Audit Logs
                  |
                  | Secure Database Connection
                  v
        Supabase PostgreSQL
```

## Architecture Rules

1. Next.js รับผิดชอบ UI/UX, Routing, Forms, Tables, Dashboard และการเรียก API
2. Django รับผิดชอบ Business Logic, Authentication, Authorization, Validation, QR Token และการบันทึกการเข้าเรียน
3. Supabase PostgreSQL เป็นฐานข้อมูลหลัก โดย Django เป็นผู้เชื่อมต่อและควบคุมการเข้าถึงข้อมูล
4. ห้ามเชื่อมต่อ PostgreSQL จาก Browser หรือ Front-end โดยตรง
5. ห้ามใส่ Database Credentials, Django Secret Key, Supabase Secret Key หรือ Service Role Key ลงในโค้ด Front-end
6. ห้ามใช้ Supabase Service Role Key ใน Next.js Client Components
7. ห้ามใช้ Django Admin Site เป็นหน้าจอหลักของระบบ
8. ต้องสร้าง Admin Panel ของ SAMS เองด้วย Next.js
9. Django Admin สามารถปิดใช้งานหรือจำกัดการเข้าถึงได้ตามความเหมาะสม แต่ไม่ใช้ทดแทน Admin Panel ของระบบ
10. ห้ามสร้างข้อมูลจำลองเพื่อหลอกว่า API หรือระบบฐานข้อมูลทำงานจริง
11. ทุกข้อมูลที่แสดงใน Dashboard ต้องมาจาก API และฐานข้อมูลจริง ยกเว้น Demo Mode ที่ต้องแยกอย่างชัดเจน

แนะนำให้จัดเก็บโค้ดเป็น Monorepo เพื่อให้พัฒนาและดูแลได้ง่าย

```text
student-attendance-management-system/
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   ├── hooks/
│   │   ├── lib/
│   │   ├── services/
│   │   ├── types/
│   │   └── styles/
│   ├── public/
│   ├── package.json
│   └── .env.example
│
├── backend/
│   ├── config/
│   ├── apps/
│   │   ├── accounts/
│   │   ├── academics/
│   │   ├── courses/
│   │   ├── schedules/
│   │   ├── attendance/
│   │   ├── reports/
│   │   └── audit/
│   ├── manage.py
│   ├── requirements.txt
│   └── .env.example
│
├── docs/
│   ├── architecture.md
│   ├── database-schema.md
│   ├── api-documentation.md
│   ├── installation.md
│   ├── deployment.md
│   └── user-manual.md
│
├── docker-compose.yml
├── .gitignore
└── README.md
```

ปรับโครงสร้างได้เมื่อมีเหตุผลทางเทคนิค แต่ต้องรักษาการแยก Front-end, Back-end และ Database

---

# 3. User Roles and Permissions

ระบบต้องรองรับผู้ใช้งาน 3 บทบาทหลัก

## 3.1 Administrator — ผู้ดูแลระบบ

สามารถดำเนินการได้ดังนี้

- เข้าสู่ Admin Panel
- ดูภาพรวมระบบจาก Dashboard
- จัดการบัญชีผู้ใช้งาน
- เพิ่ม แก้ไข ระงับ และเปิดใช้งานบัญชี
- นำเข้ารายชื่อนักศึกษาจาก CSV
- จัดการข้อมูลนักศึกษา
- จัดการอาจารย์
- จัดการหลักสูตร
- จัดการชั้นปี ห้องเรียน และกลุ่มเรียน
- จัดการรายวิชา
- กำหนดอาจารย์ผู้รับผิดชอบรายวิชา
- จัดการภาคการศึกษาและปีการศึกษา
- จัดการตารางเรียน
- ตรวจสอบประวัติการเข้าเรียน
- ดูรายงานสรุปและส่งออกข้อมูล
- ตรวจสอบ Audit Logs
- จัดการการตั้งค่าระบบ
- ตรวจสอบสถานะ API และฐานข้อมูล
- จัดการนโยบายการเช็คชื่อและเวลาที่อนุญาตให้เช็คชื่อ

## 3.2 Instructor — อาจารย์ผู้สอน

สามารถดำเนินการได้ดังนี้

- ดู Dashboard ของรายวิชาที่รับผิดชอบ
- ดูตารางสอนของตนเอง
- ดูรายชื่อนักศึกษาในรายวิชา
- เปิดคาบเรียน
- สร้าง QR Code สำหรับเช็คชื่อ
- แสดง QR Code บนหน้าจอห้องเรียน
- กำหนดเวลาเปิดและปิดการเช็คชื่อ
- เริ่ม หยุด ต่ออายุ หรือปิด QR Session ตามสิทธิ์
- ดูจำนวนผู้เช็คชื่อแบบใกล้เคียงเรียลไทม์
- ดูรายชื่อนักศึกษาที่เช็คชื่อแล้ว
- ตรวจสอบผู้ที่ยังไม่เช็คชื่อ
- บันทึกการเข้าเรียนด้วยตนเองเมื่อได้รับอนุญาต
- แก้ไขสถานะการเข้าเรียนพร้อมระบุเหตุผล
- ดูสถิติการเข้าเรียนของรายวิชาที่รับผิดชอบ
- ส่งออกรายงานการเข้าเรียนของรายวิชาที่รับผิดชอบ

อาจารย์ต้องไม่สามารถดูหรือแก้ไขข้อมูลของรายวิชาที่ตนเองไม่มีสิทธิ์รับผิดชอบได้

## 3.3 Student — นักศึกษา

ออกแบบโดยเน้น Mobile-First

นักศึกษาสามารถดำเนินการได้ดังนี้

- เข้าสู่ระบบด้วยบัญชีที่ได้รับอนุญาต
- ดู Dashboard ส่วนตัว
- ดูรายวิชาที่ลงทะเบียน
- ดูตารางเรียน
- สแกน QR Code เพื่อเช็คชื่อ
- ดูผลการเช็คชื่อของตนเอง
- ดูประวัติการเข้าเรียนย้อนหลัง
- ดูสถิติการเข้าเรียนรายวิชา
- ตรวจสอบจำนวนครั้งที่เข้าเรียน ขาดเรียน มาสาย และลา
- ดูสถานะคำขอแก้ไขข้อมูลการเข้าเรียน หากระบบเปิดใช้งานฟังก์ชันนี้

นักศึกษาต้องไม่สามารถดูข้อมูลส่วนตัว ประวัติการเข้าเรียน หรือข้อมูลเชิงบริหารของนักศึกษาคนอื่นได้

---

# 4. Authentication and Security

สร้างระบบ Authentication ด้วย Django REST Framework โดยกำหนดนโยบายการยืนยันตัวตนให้ชัดเจน

## 4.1 Login and Session

- หน้า Login ใช้บัญชีผู้ใช้งานที่ผู้ดูแลระบบสร้างหรือนำเข้า
- กำหนดนโยบาย Username หรือ Email ให้ชัดเจน
- นักศึกษาห้ามสมัครบัญชีใหม่โดยอิสระ หากยังไม่ได้รับอนุญาตจากผู้ดูแลระบบ
- ตรวจสอบสถานะบัญชีก่อนอนุญาตให้เข้าสู่ระบบ
- ใช้ Password Hashing ที่ปลอดภัยตามมาตรฐาน Django
- ใช้ Access Token อายุสั้น และ Refresh Token ตามนโยบายที่กำหนด
- ป้องกันการนำ Refresh Token กลับมาใช้ซ้ำ และรองรับการเพิกถอน Token
- ใช้ Secure, HttpOnly และ SameSite Cookies สำหรับการจัดเก็บ Token หากเลือกใช้ Cookie-Based Authentication
- หากใช้ Bearer Token ให้หลีกเลี่ยงการเก็บ Token ระยะยาวใน Local Storage
- กำหนด CORS ให้เฉพาะ Origin ที่ได้รับอนุญาต
- กำหนด CSRF Protection ให้ถูกต้องตามรูปแบบ Authentication ที่เลือก
- มี Logout ที่เพิกถอน Session หรือ Refresh Token ตามความเหมาะสม
- จำกัดจำนวนครั้งการเข้าสู่ระบบที่ล้มเหลว
- ไม่เปิดเผยว่าบัญชีใดมีอยู่จริงผ่านข้อความ Error
- บันทึกเหตุการณ์เข้าสู่ระบบที่สำคัญ

## 4.2 Role-Based Access Control

ใช้ Role-Based Access Control (RBAC) ทั้งใน Front-end และ Back-end

ข้อบังคับสำคัญ:

- Front-end ใช้ซ่อนเมนูและป้องกันการเข้าหน้าจอที่ไม่เกี่ยวข้อง
- Back-end ต้องตรวจสอบสิทธิ์ทุก API ที่สำคัญ
- ห้ามเชื่อถือ Role ที่ส่งมาจาก Client
- ตรวจสอบเจ้าของข้อมูลและขอบเขตการเข้าถึงทุกครั้ง
- ผู้ใช้ที่ไม่มีสิทธิ์ต้องได้รับ HTTP 403
- ผู้ใช้ที่ยังไม่เข้าสู่ระบบต้องได้รับ HTTP 401 ตามความเหมาะสม
- ป้องกัน IDOR หรือการเข้าถึงข้อมูลของผู้อื่นโดยเปลี่ยน ID ใน URL
- กำหนด Permission สำหรับการอ่าน สร้าง แก้ไข ลบ และส่งออกข้อมูล

---

# 5. Home Page and Login Page

ระบบต้องมีหน้า Home Page และ Login Page อย่างชัดเจน

## 5.1 Home Page

หน้าแรกของระบบต้องเป็นหน้า Public Landing Page ที่มีดีไซน์ระดับ Professional

องค์ประกอบประกอบด้วย:

- โลโก้สถาบันหรือพื้นที่สำหรับใส่โลโก้
- ชื่อระบบ Student Attendance Management System
- คำอธิบายระบบภาษาไทย
- ปุ่ม “เข้าสู่ระบบ”
- จุดเด่นของระบบ
- ขั้นตอนการเช็คชื่อด้วย QR Code
- ข้อมูลช่วยเหลือและช่องทางติดต่อผู้ดูแลระบบ
- Footer พร้อมข้อมูลเวอร์ชันระบบ

ห้ามแสดงข้อมูลส่วนบุคคลหรือข้อมูลการเข้าเรียนของนักศึกษาบนหน้า Home Page

## 5.2 Login Page

ออกแบบหน้าจอเข้าสู่ระบบให้เรียบง่าย ทันสมัย และเหมาะกับระบบสารสนเทศทางการศึกษา

องค์ประกอบ:

- Logo และชื่อระบบ
- ช่อง Username หรือ Email
- ช่อง Password พร้อมปุ่มแสดงหรือซ่อนรหัสผ่าน
- ปุ่มเข้าสู่ระบบ
- Loading State
- Validation Message
- SweetAlert2 สำหรับข้อความแจ้งเตือนที่เหมาะสม
- ลิงก์กลับหน้า Home
- ข้อความแจ้งช่องทางติดต่อผู้ดูแลระบบเมื่อไม่สามารถเข้าสู่ระบบได้

หลัง Login สำเร็จ ให้เปลี่ยนเส้นทางตามบทบาทผู้ใช้:

- Administrator → `/admin/dashboard`
- Instructor → `/instructor/dashboard`
- Student → `/student/dashboard`

หากผู้ใช้พยายามเปิดหน้าที่ไม่มีสิทธิ์ ให้ปฏิเสธการเข้าถึงและนำไปยังหน้าที่เหมาะสม

---

# 6. UI/UX Design System

ออกแบบให้มีภาพลักษณ์ Professional Academic Information System

## 6.1 Color Palette

- Primary Blue: `#1D4ED8`
- Dark Navy: `#1E3A8A`
- Light Blue: `#EFF6FF`
- Background: `#F8FAFC`
- Surface: `#FFFFFF`
- Main Text: `#0F172A`
- Secondary Text: `#64748B`
- Success: `#16A34A`
- Warning: `#D97706`
- Danger: `#DC2626`
- Border: `#E2E8F0`

สามารถปรับเฉดสีให้เหมาะกับการใช้งานจริง แต่ต้องคงภาพรวมสีขาว–น้ำเงิน

## 6.2 Layout

Desktop:

- Sidebar ด้านซ้าย
- Header ด้านบน
- Breadcrumb
- Page Title
- Dashboard Cards
- Main Content
- Data Tables
- Footer หรือ System Information

Mobile:

- Responsive Sidebar หรือ Drawer
- Mobile Header
- เมนูที่กดง่าย
- ปุ่มขนาดเหมาะสมกับนิ้ว
- Tables ที่สามารถเลื่อนแนวนอนหรือแสดงเป็น Cards ได้
- QR Scanner ที่ใช้พื้นที่กล้องอย่างเหมาะสม
- ไม่ให้มี Horizontal Overflow ในหน้าทั่วไป
- รองรับหน้าจอขนาดเล็กตั้งแต่ประมาณ 320px

## 6.3 UI Components

สร้าง Reusable Components ได้แก่

- AppSidebar
- MobileNavigation
- AppHeader
- Breadcrumb
- PageHeader
- DashboardCard
- DataTable
- SearchInput
- FilterPanel
- Pagination
- StatusBadge
- EmptyState
- LoadingSkeleton
- ErrorState
- ConfirmDialog
- FormField
- Modal
- QRCodeDisplay
- QRCodeScanner
- AttendanceStatus
- UserAvatar
- DateRangePicker

ใช้ Tailwind CSS เป็นระบบ Styling หลัก และใช้ SweetAlert2 สำหรับ Success, Error, Warning และ Confirmation

ห้ามใช้ SweetAlert2 แทนทุก Modal หรือทุก Form ควรเลือกใช้ให้เหมาะสมกับ UX

ห้ามสร้างหน้าจอที่เป็นเพียงภาพ Mockup โดยไม่มีการทำงานจริง

---

# 7. Admin Panel and Dashboard

## 7.1 Admin Dashboard

สร้าง Dashboard ที่แสดงข้อมูลจริงจาก API

Dashboard Cards:

1. จำนวนผู้ใช้งานทั้งหมด
2. จำนวนนักศึกษาทั้งหมด
3. จำนวนอาจารย์ทั้งหมด
4. จำนวนหลักสูตร
5. จำนวนรายวิชา
6. จำนวนคาบเรียนทั้งหมด
7. จำนวนคาบเรียนที่เปิดเช็คชื่อ
8. จำนวนรายการเช็คชื่อในวันที่เลือก

Dashboard Charts:

- สถิติการเข้าเรียนรายวัน
- แนวโน้มการเข้าเรียนรายสัปดาห์
- อัตราการเข้าเรียนรายหลักสูตร
- สัดส่วนสถานะการเข้าเรียน
- รายวิชาที่มีอัตราการขาดเรียนสูง

Filters:

- ปีการศึกษา
- ภาคการศึกษา
- หลักสูตร
- ชั้นปี
- ห้องเรียนหรือกลุ่มเรียน
- รายวิชา
- ช่วงวันที่

Charts ต้องมี Loading, Empty และ Error States และต้องอธิบายหน่วยหรือช่วงเวลาที่นำมาแสดงให้ชัดเจน

## 7.2 Admin Sidebar

เมนูหลัก:

- Dashboard
- จัดการผู้ใช้งาน
- จัดการนักศึกษา
- จัดการอาจารย์
- จัดการหลักสูตร
- จัดการชั้นปีและกลุ่มเรียน
- จัดการรายวิชา
- จัดการภาคการศึกษา
- จัดการตารางเรียน
- จัดการคาบเรียน
- รายการเช็คชื่อ
- รายงานการเข้าเรียน
- นำเข้าและส่งออกข้อมูล
- Audit Logs
- ตั้งค่าระบบ
- โปรไฟล์
- ออกจากระบบ

## 7.3 Data Table Requirements

ทุกหน้าจัดการข้อมูลต้องรองรับ:

- Search
- Pagination ฝั่ง Server
- Sorting ฝั่ง Server
- Filtering
- ดูรายละเอียด
- เพิ่มข้อมูล
- แก้ไขข้อมูล
- ลบหรือระงับข้อมูลตามสิทธิ์
- Loading State
- Empty State
- Error State
- Form Validation
- Confirmation ก่อนทำรายการสำคัญ
- ป้องกันการส่ง Form ซ้ำ
- แสดงผลลัพธ์การทำรายการอย่างชัดเจน

สำหรับการลบข้อมูลที่เกี่ยวข้องกับประวัติการเข้าเรียน ให้ใช้ Soft Delete หรือปฏิเสธการลบตาม Referential Integrity แทนการลบประวัติย้อนหลังโดยไม่ตั้งใจ

---

# 8. Academic Data Management

สร้างโมดูลสำหรับบริหารจัดการข้อมูลทางการศึกษา

## 8.1 Academic Year and Semester

ข้อมูลประกอบด้วย:

- ปีการศึกษา
- ภาคการศึกษา
- วันที่เริ่มต้น
- วันที่สิ้นสุด
- สถานะ Active/Inactive
- สถานะภาคการศึกษาปัจจุบัน

รองรับปีการศึกษาไทย โดยกำหนดหลักการแปลงปีและแสดงผลให้ชัดเจน ห้ามแปลงปีในฐานข้อมูลโดยไม่กำหนดกติกา

เก็บวันที่และเวลาในฐานข้อมูลด้วยมาตรฐานที่สอดคล้องกัน เช่น UTC และแสดงผลในเขตเวลา Asia/Bangkok

## 8.2 Course and Enrollment

รองรับ:

- หลักสูตร
- รหัสนักศึกษา
- ชื่อและนามสกุล
- ชั้นปี
- ห้องเรียนหรือกลุ่มเรียน
- รายวิชา
- รหัสรายวิชา
- หน่วยกิตตามความจำเป็น
- อาจารย์ผู้รับผิดชอบ
- รายชื่อนักศึกษาที่ลงทะเบียนในรายวิชา

ใช้ Enrollment Table เพื่อเชื่อมความสัมพันธ์ระหว่างนักศึกษาและรายวิชา

ต้องป้องกันการลงทะเบียนรายวิชาเดียวกันซ้ำภายในภาคการศึกษาเดียวกันตามกติกาที่กำหนด

---

# 9. Class Schedule and Attendance Session

ออกแบบระบบให้แยก “ตารางเรียน” ออกจาก “คาบเรียนที่เปิดเช็คชื่อจริง”

## 9.1 Class Schedule

ข้อมูลประกอบด้วย:

- รายวิชา
- อาจารย์ผู้สอน
- วันเรียน
- เวลาเริ่มต้น
- เวลาสิ้นสุด
- ห้องเรียน
- กลุ่มเรียน
- ภาคการศึกษา
- สถานะตารางเรียน

## 9.2 Attendance Session

เมื่ออาจารย์เริ่มคาบเรียน ให้สร้าง Attendance Session ที่เชื่อมกับตารางเรียนหรือรายวิชา

ข้อมูลประกอบด้วย:

- Session ID
- Course ID
- Instructor ID
- Class Schedule ID ถ้ามี
- วันที่เรียน
- เวลาเริ่มต้น
- เวลาเช็คชื่อเริ่มต้น
- เวลาปิดรับเช็คชื่อ
- สถานะ Session
- QR Token Version หรือ Token Metadata
- จำนวนผู้ลงทะเบียน
- จำนวนผู้เช็คชื่อสำเร็จ

สถานะ Session:

- Scheduled
- Open
- Paused
- Closed
- Cancelled

ต้องตรวจสอบว่าอาจารย์มีสิทธิ์เปิด Session ของรายวิชานั้นจริง และไม่อนุญาตให้เปิด Session ที่ถูกยกเลิกหรืออยู่นอกเงื่อนไขที่กำหนด

---

# 10. QR Code Attendance System

โมดูลนี้เป็นหัวใจสำคัญของระบบ ต้องพัฒนาให้ใช้งานได้จริงและป้องกันการเช็คชื่อแทนกันอย่างเหมาะสม

## 10.1 Recommended Workflow

1. อาจารย์เข้าสู่ระบบ
2. อาจารย์เลือกวิชาและคาบเรียน
3. อาจารย์กด “เปิดเช็คชื่อ”
4. Django ตรวจสอบสิทธิ์และสร้าง Attendance Session
5. Django สร้าง QR Token ที่มีอายุจำกัด
6. Next.js แสดง QR Code บนหน้าจออาจารย์
7. นักศึกษาเข้าสู่ระบบด้วยบัญชีของตนเอง
8. นักศึกษาเปิดเมนู “สแกน QR Code”
9. นักศึกษาอนุญาตให้เว็บไซต์ใช้กล้อง
10. นักศึกษาสแกน QR Code ของคาบเรียน
11. Front-end ส่ง Token ไปยัง Django API
12. Django ตรวจสอบตัวตนของนักศึกษา
13. Django ตรวจสอบ Token, Session, เวลา, สถานะบัญชี และสิทธิ์การลงทะเบียน
14. Django บันทึก Attendance Record
15. Front-end แสดงผลการเช็คชื่อสำเร็จหรือแจ้งเหตุผลที่ไม่สำเร็จ
16. Dashboard อาจารย์อัปเดตจำนวนผู้เช็คชื่อผ่านการ Polling หรือกลไกอื่นที่เหมาะสม

นักศึกษาไม่ต้องกรอกชื่อหรือรหัสนักศึกษาซ้ำหลัง Login

## 10.2 QR Token Security

QR Code ต้องไม่บรรจุข้อมูลส่วนบุคคลหรือรหัสผ่าน

ให้ใช้ Token แบบสุ่มที่มีความปลอดภัยสูงหรือ Signed Token ที่ผ่านการออกแบบอย่างเหมาะสม โดยมีข้อกำหนดดังนี้:

- Token ต้องสร้างจากฝั่ง Django
- Token ต้องคาดเดาได้ยาก
- Token ต้องมีอายุสั้นและกำหนดค่าได้
- Token ต้องเชื่อมโยงกับ Session ที่ถูกต้อง
- Token ต้องหมดอายุเมื่อ Session ปิด
- รองรับการเปลี่ยน Token ตามช่วงเวลาที่กำหนด
- ตรวจสอบ Token จากฝั่ง Django ทุกครั้ง
- ห้ามเชื่อถือ Session ID หรือ Attendance Status ที่ Client ส่งมาโดยไม่ตรวจสอบ
- ป้องกัน Replay Attack
- ป้องกันการใช้ Token ซ้ำตามนโยบายที่กำหนด
- มีการ Rate Limit สำหรับ API สแกน QR
- บันทึกเหตุการณ์ Token ผิดพลาดหรือพยายามใช้งานซ้ำ
- ห้ามบันทึก Token เต็มลง Application Logs โดยไม่จำเป็น

แนะนำให้ออกแบบ QR Token ให้ใช้ได้ครั้งเดียวต่อการเช็คชื่อที่เกี่ยวข้อง หรือให้ QR Token เป็น Session Token อายุสั้นที่สามารถใช้กับนักศึกษาหลายคนได้ในช่วงเวลาที่กำหนด แต่แต่ละบัญชีจะมีสิทธิ์สร้าง Attendance Record ได้เพียงหนึ่งรายการต่อ Session

ต้องแยกให้ชัดเจนระหว่าง QR Token ที่แชร์ใช้สำหรับ Session กับ Attendance Record ที่ไม่อนุญาตให้สร้างซ้ำ

**สำคัญ:** การเปลี่ยน QR Code ทุกช่วงเวลาเพียงอย่างเดียวไม่สามารถป้องกันการส่งต่อภาพ QR Code แบบเรียลไทม์ได้ทั้งหมด ให้ระบุข้อจำกัดนี้ในเอกสาร และออกแบบมาตรการเสริมโดยไม่กล่าวอ้างว่าระบบป้องกันการทุจริตได้ 100%

## 10.3 Attendance Validation

ก่อนบันทึกข้อมูล ต้องตรวจสอบ:

1. ผู้ใช้เข้าสู่ระบบแล้ว
2. บัญชีนักศึกษายังเปิดใช้งาน
3. Token ถูกต้องและไม่หมดอายุ
4. Session ยังเปิดรับการเช็คชื่อ
5. Session ยังไม่ถูกยกเลิก
6. นักศึกษาลงทะเบียนเรียนในรายวิชานั้น
7. นักศึกษาอยู่ในกลุ่มเรียนที่มีสิทธิ์
8. ยังไม่มี Attendance Record ของนักศึกษาคนนั้นใน Session เดียวกัน
9. เวลาปัจจุบันอยู่ในช่วงที่อนุญาต
10. ข้อมูลที่ส่งมาถูกต้องตาม Schema

หากไม่ผ่านเงื่อนไข ให้ปฏิเสธและแสดงข้อความที่เข้าใจง่าย โดยไม่เปิดเผยข้อมูลภายในระบบ

## 10.4 Duplicate Prevention

ใช้ Database Constraints และ Transaction เพื่อป้องกันการเช็คชื่อซ้ำในกรณีที่มีการสแกนพร้อมกันหลายคำขอ

ตัวอย่าง Unique Constraint:

`UNIQUE(attendance_session_id, student_id)`

ต้องจัดการ Race Condition ใน Django ด้วย Transaction และ Integrity Error Handling อย่างถูกต้อง

การสแกนซ้ำควรแสดงผลว่า “คุณเช็คชื่อในคาบนี้แล้ว” โดยไม่สร้างข้อมูลใหม่

## 10.5 Attendance Status

รองรับสถานะอย่างน้อย:

- Present — เข้าเรียน
- Late — มาสาย
- Absent — ขาดเรียน
- Excused — ลา/ได้รับอนุญาต

กำหนดนโยบาย Late Threshold ได้ตามรายวิชาหรือ Session โดยมีค่าเริ่มต้นที่ผู้ดูแลระบบกำหนด

หากนักศึกษาเช็คชื่อสำเร็จภายในช่วงเวลาที่อนุญาต ให้คำนวณสถานะจากเวลาที่ Django บันทึกจริง ห้ามใช้เวลาจากอุปกรณ์นักศึกษาเป็นแหล่งข้อมูลหลัก

การเช็คชื่อผ่าน QR Code จะบันทึก Present หรือ Late ตามกติกา ส่วน Absent ควรคำนวณจากรายชื่อที่มีสิทธิ์และไม่มี Attendance Record หลัง Session ปิด หรือใช้กระบวนการที่กำหนดไว้ ห้ามสร้าง Absent ก่อนเวลาปิดเช็คชื่อโดยไม่มีกติกาชัดเจน

## 10.6 QR Scanner UX

สำหรับนักศึกษา:

- ใช้กล้องหลังเป็นค่าเริ่มต้นเมื่ออุปกรณ์รองรับ
- แสดงสถานะการอนุญาตใช้กล้อง
- มีปุ่มเริ่มสแกนและหยุดสแกน
- รองรับการเปิดไฟฉายเมื่ออุปกรณ์รองรับ
- รองรับกรณีไม่อนุญาตใช้กล้อง
- รองรับการป้อนหรือเปิด Attendance Link ด้วยตนเองอย่างปลอดภัย หากกำหนดให้รองรับ
- หยุดกล้องเมื่อออกจากหน้าหรือสแกนสำเร็จ
- ป้องกันการส่ง API ซ้ำจากการอ่าน QR หลายครั้งติดกัน
- แสดง Loading ระหว่างตรวจสอบ
- แสดง Success, Warning หรือ Error ด้วย SweetAlert2 หรือ UI ที่เหมาะสม
- ใช้ HTTPS ใน Production เพราะ Browser ต้องการ Secure Context สำหรับกล้อง

สำหรับอาจารย์:

- แสดง QR Code ขนาดใหญ่
- แสดงชื่อรายวิชาและ Session
- แสดงเวลาคงเหลือ
- แสดงสถานะเปิดหรือปิดเช็คชื่อ
- แสดงจำนวนผู้เช็คชื่อแล้วและจำนวนผู้มีสิทธิ์
- รองรับ Fullscreen
- รองรับการต่ออายุ Token
- มีปุ่มปิด Session
- ป้องกันการเปิด Session ซ้ำโดยไม่ตั้งใจ

---

# 11. Attendance Records and Reports

สร้างหน้าประวัติการเข้าเรียนที่รองรับการค้นหาและกรองข้อมูล

ข้อมูลที่แสดง:

- รหัสนักศึกษา
- ชื่อและนามสกุล
- รายวิชา
- วันที่เรียน
- เวลาเช็คชื่อ
- สถานะ
- วิธีการเช็คชื่อ
- ผู้แก้ไขข้อมูล หากมี
- เหตุผลการแก้ไข หากมี

## 11.1 Attendance Report

รายงานต้องรองรับ:

- รายงานรายนักศึกษา
- รายงานรายวิชา
- รายงานราย Session
- รายงานรายห้องหรือกลุ่มเรียน
- รายงานรายหลักสูตร
- รายงานรายภาคการศึกษา
- รายงานตามช่วงวันที่
- รายชื่อนักศึกษาที่ขาดเรียน
- รายชื่อนักศึกษาที่มาสาย
- อัตราการเข้าเรียนเป็นเปอร์เซ็นต์
- การส่งออก CSV
- การส่งออก Excel หรือ PDF เมื่อมีการพัฒนาโมดูลรองรับ

กำหนดสูตรอัตราการเข้าเรียนอย่างชัดเจน เช่น:

อัตราการเข้าเรียน (%) = จำนวนคาบที่มีสถานะเข้าเรียนตามเกณฑ์ ÷ จำนวนคาบที่มีสิทธิ์นำมาคำนวณ × 100

ต้องกำหนดวิธีนับการลา การยกเลิกคาบเรียน และคาบที่ยังไม่ปิดให้ชัดเจนก่อนคำนวณ

ข้อมูลรายงานต้องมาจากฐานข้อมูลจริง และใช้ Server-Side Filtering สำหรับข้อมูลปริมาณมาก

---

# 12. Database Design — Supabase PostgreSQL

ใช้ Supabase PostgreSQL เป็นฐานข้อมูลหลัก และให้ Django ORM เป็นผู้จัดการ Schema ผ่าน Django Migrations

ห้ามใช้ SQLite เป็นฐานข้อมูล Production

ออกแบบตารางอย่างน้อยดังต่อไปนี้:

## 12.1 Core Tables

### users
- id
- username
- email
- password
- role
- is_active
- date_joined
- created_at
- updated_at

ควรใช้ Django Custom User Model ตั้งแต่เริ่มโปรเจกต์ โดยกำหนดความสัมพันธ์ระหว่างบัญชีผู้ใช้และข้อมูลนักศึกษา/อาจารย์อย่างชัดเจน

### student_profiles
- id
- user_id
- student_code
- first_name
- last_name
- program_id
- academic_year_level
- class_group_id
- status
- created_at
- updated_at

### instructor_profiles
- id
- user_id
- employee_code
- first_name
- last_name
- department
- status
- created_at
- updated_at

### programs
- id
- program_code
- program_name
- degree_level
- is_active

### class_groups
- id
- group_code
- group_name
- program_id
- academic_year_level

### academic_terms
- id
- academic_year
- semester
- start_date
- end_date
- is_active

### courses
- id
- course_code
- course_name
- credits
- description
- is_active

### course_offerings
- id
- course_id
- academic_term_id
- instructor_id
- class_group_id
- status

### enrollments
- id
- student_id
- course_offering_id
- enrollment_status
- enrolled_at

### class_schedules
- id
- course_offering_id
- class_date
- start_time
- end_time
- classroom
- status

### attendance_sessions
- id
- class_schedule_id
- course_offering_id
- instructor_id
- session_date
- check_in_start
- check_in_end
- status
- created_at
- closed_at

### attendance_records
- id
- attendance_session_id
- student_id
- checked_in_at
- status
- check_in_method
- source_metadata
- created_at
- updated_at

### qr_tokens
- id
- attendance_session_id
- token_hash หรือ identifier ที่เหมาะสม
- issued_at
- expires_at
- revoked_at
- created_by

### audit_logs
- id
- actor_user_id
- action
- resource_type
- resource_id
- metadata
- ip_address ตามนโยบายความเป็นส่วนตัว
- user_agent ตามความจำเป็น
- created_at

ตารางข้างต้นเป็นข้อกำหนดเริ่มต้น สามารถแยกตารางเพิ่มเติมได้ตามความเหมาะสม

## 12.2 Database Requirements

- ใช้ UUID หรือ Primary Key ที่เหมาะสม
- กำหนด Foreign Keys
- กำหนด Unique Constraints
- กำหนด Indexes สำหรับการค้นหาที่ใช้บ่อย
- ใช้ `PROTECT`, `CASCADE` หรือ `SET_NULL` ตามความสัมพันธ์ที่เหมาะสม
- กำหนด `created_at` และ `updated_at` ในตารางที่จำเป็น
- ป้องกันข้อมูลซ้ำ
- ใช้ Transaction กับกระบวนการที่ต้องทำหลายขั้นตอน
- สร้าง Migrations ที่สามารถตรวจสอบและนำไปใช้ได้
- ใช้ Decimal หรือ Integer สำหรับค่าที่เหมาะสม หลีกเลี่ยงการใช้ Float โดยไม่จำเป็น
- ใช้ Database Connection Pooling ที่เข้ากันได้กับ Django และ Supabase
- เลือก Direct Connection หรือ Session Pooler ตามสภาพแวดล้อมการ Deploy
- ตรวจสอบ TLS/SSL และการจัดเก็บ Credentials
- ห้ามเก็บ Plaintext Password
- ห้ามเก็บ QR Token เต็มใน Audit Logs
- ห้ามเก็บข้อมูลส่วนบุคคลเกินความจำเป็น

---

# 13. Backend Development — Django REST Framework

พัฒนา Back-end ให้เป็น REST API ที่มีโครงสร้างชัดเจน

แนวทาง:

- Django Stable Version ล่าสุดที่เข้ากันได้
- Django REST Framework
- PostgreSQL Driver ที่รองรับเวอร์ชันที่เลือก
- Django ORM
- Custom User Model
- Authentication และ Permission Classes
- Serializers
- ViewSets หรือ API Views
- Service Layer สำหรับ Business Logic ที่ซับซ้อน
- Pagination
- Filtering
- Search
- Sorting
- API Versioning
- OpenAPI/Swagger Documentation
- Structured Logging
- Environment Configuration
- Automated Tests

## 13.1 API Endpoints

ตัวอย่าง API ที่ต้องพัฒนาให้ครบถ้วน:

### Authentication

- `POST /api/v1/auth/login/`
- `POST /api/v1/auth/refresh/`
- `POST /api/v1/auth/logout/`
- `GET /api/v1/auth/me/`

### Dashboard

- `GET /api/v1/dashboard/admin/`
- `GET /api/v1/dashboard/instructor/`
- `GET /api/v1/dashboard/student/`

### Users

- `GET /api/v1/users/`
- `POST /api/v1/users/`
- `GET /api/v1/users/{id}/`
- `PATCH /api/v1/users/{id}/`
- `DELETE /api/v1/users/{id}/`

### Students and Instructors

- `GET /api/v1/students/`
- `POST /api/v1/students/`
- `GET /api/v1/students/{id}/`
- `PATCH /api/v1/students/{id}/`
- `GET /api/v1/instructors/`
- `POST /api/v1/instructors/`

### Academic Data

- `/api/v1/programs/`
- `/api/v1/class-groups/`
- `/api/v1/academic-terms/`
- `/api/v1/courses/`
- `/api/v1/course-offerings/`
- `/api/v1/enrollments/`
- `/api/v1/class-schedules/`

### Attendance

- `POST /api/v1/attendance/sessions/`
- `GET /api/v1/attendance/sessions/`
- `GET /api/v1/attendance/sessions/{id}/`
- `POST /api/v1/attendance/sessions/{id}/open/`
- `POST /api/v1/attendance/sessions/{id}/close/`
- `POST /api/v1/attendance/sessions/{id}/qr-token/`
- `POST /api/v1/attendance/check-in/`
- `GET /api/v1/attendance/records/`
- `GET /api/v1/attendance/my-history/`
- `PATCH /api/v1/attendance/records/{id}/`

### Reports and Audit

- `GET /api/v1/reports/attendance/`
- `GET /api/v1/reports/attendance/export/`
- `GET /api/v1/audit-logs/`

ทุก Endpoint ต้องตรวจสอบ Authentication, Permission, Ownership, Input Validation และ Error Handling

ปรับชื่อ Endpoint หรือแยก API เพิ่มเติมได้ตามความเหมาะสม แต่ต้องบันทึกไว้ใน API Documentation และทำให้ Front-end ใช้งานได้จริง

## 13.2 API Response Format

ใช้รูปแบบ Response ที่สม่ำเสมอ โดยเฉพาะ Error Responses

ตัวอย่าง:

```json
{
  "success": true,
  "message": "เช็คชื่อสำเร็จ",
  "data": {
    "status": "present",
    "checked_in_at": "2026-10-24T03:00:00Z"
  }
}
```

ตัวอย่าง Error:

```json
{
  "success": false,
  "message": "คุณเช็คชื่อในคาบนี้แล้ว",
  "code": "ATTENDANCE_ALREADY_EXISTS"
}
```

ตัวอย่างนี้เป็นรูปแบบแนวทาง ต้องปรับให้สอดคล้องกับ Serializer และ Exception Handler จริง

ใช้ HTTP Status Codes อย่างถูกต้อง เช่น 200, 201, 400, 401, 403, 404, 409, 429 และ 500 ตามบริบท ห้ามคืน HTTP 200 ให้ทุกกรณี

---

# 14. Front-end Development — Next.js

ใช้ Next.js App Router, TypeScript และ Tailwind CSS

กำหนดโครงสร้างให้แยก Features ตามโมดูล

- Authentication
- Admin Dashboard
- User Management
- Student Management
- Academic Management
- Course Management
- Class Schedule
- QR Attendance
- Attendance Records
- Reports
- Settings

## 14.1 Front-end Rules

- ใช้ TypeScript แบบ Strict
- หลีกเลี่ยง `any` โดยไม่มีเหตุผล
- ใช้ Server Components เป็นค่าเริ่มต้นเมื่อเหมาะสม
- ใช้ Client Components เฉพาะส่วนที่ต้องมี Interaction
- แยก API Client ออกจาก UI Components
- ใช้ Typed API Responses
- จัดการ Loading, Error, Empty และ Success States
- มี Form Validation ฝั่ง Client และ Server
- ห้ามใช้ Front-end Validation แทนการตรวจสอบฝั่ง Django
- ห้ามใส่ Secret Keys ลงใน `NEXT_PUBLIC_*`
- ใช้ Environment Variables สำหรับ API Base URL
- รองรับการ Refresh Session และการ Logout
- ป้องกันการแสดงข้อมูลเก่าหลังผู้ใช้เปลี่ยนบัญชี
- ใช้ Pagination และ Filtering ฝั่ง Server สำหรับข้อมูลจำนวนมาก
- ใช้ Accessible Labels และ Keyboard Navigation
- รองรับมือถือและ Tablet
- จัดการ Permission Denied และ Session Expired ให้เหมาะสม

## 14.2 Required Pages

```text
/
 /login

/admin/dashboard
/admin/users
/admin/students
/admin/instructors
/admin/programs
/admin/class-groups
/admin/academic-terms
/admin/courses
/admin/course-offerings
/admin/enrollments
/admin/schedules
/admin/attendance-sessions
/admin/attendance-records
/admin/reports
/admin/audit-logs
/admin/settings

/instructor/dashboard
/instructor/courses
/instructor/schedule
/instructor/attendance
/instructor/attendance/[sessionId]
/instructor/reports

/student/dashboard
/student/courses
/student/schedule
/student/scan
/student/history
/student/profile
```

สามารถปรับ Routing ให้เหมาะสมกับ App Router แต่ต้องรักษาฟังก์ชันการใช้งานและการแยกบทบาท

---

# 15. Application Settings and Environment Variables

สร้าง `.env.example` สำหรับแต่ละส่วน โดยไม่มี Credentials จริง

ตัวอย่าง Front-end:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

ตัวอย่าง Back-end:

```env
DJANGO_SECRET_KEY=
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CORS_ALLOWED_ORIGINS=http://localhost:3000

DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=
DB_PORT=5432
DB_SSLMODE=require

ACCESS_TOKEN_LIFETIME_MINUTES=10
REFRESH_TOKEN_LIFETIME_DAYS=7

ATTENDANCE_QR_TTL_SECONDS=30
ATTENDANCE_CHECKIN_GRACE_SECONDS=0

TIME_ZONE=Asia/Bangkok
```

ชื่อตัวแปรข้างต้นเป็นตัวอย่าง ให้ปรับตามการตั้งค่าจริง

ข้อกำหนด:

- ห้าม Commit `.env`
- ต้องมี `.gitignore`
- ต้องมีการตรวจสอบ Environment Variables ตอนเริ่มระบบ
- Production ต้องไม่ใช้ `DEBUG=True`
- ห้ามสร้าง Secret Key แบบเดิมหรือฝังค่าคงที่ไว้ในโค้ด
- ห้ามตั้งค่า Database Password หรือ API Secret เป็นค่าเริ่มต้นที่คาดเดาได้
- ค่า QR TTL และเวลาเผื่อเช็คชื่อต้องมีการตรวจสอบความสมเหตุสมผล
- ห้ามสร้างบัญชี Admin ที่มีรหัสผ่านสาธารณะตายตัว

---

# 16. Security Requirements

ต้องตรวจสอบและป้องกันความเสี่ยงอย่างน้อยดังนี้:

1. SQL Injection
2. Cross-Site Scripting (XSS)
3. Cross-Site Request Forgery (CSRF) ตามรูปแบบ Authentication
4. Broken Access Control
5. IDOR
6. Brute Force Login
7. Credential Leakage
8. Token Replay
9. Duplicate Attendance
10. QR Token Guessing
11. Mass Assignment
12. Unsafe File Upload
13. Unauthorized Data Export
14. Excessive API Requests
15. Sensitive Information Leakage
16. Insecure CORS Configuration
17. Missing Security Headers
18. Race Conditions
19. Improper Error Handling
20. Unauthorized Attendance Modification

ข้อกำหนดเพิ่มเติม:

- ใช้ Django Security Settings ตามสภาพแวดล้อม
- ตั้งค่า HTTPS ใน Production
- ตรวจสอบ Host Header
- จำกัดขนาด Request Body
- Validate ไฟล์ CSV ก่อนนำเข้า
- ป้องกัน CSV Formula Injection เมื่อส่งออกข้อมูล
- บันทึก Audit Logs สำหรับการเปลี่ยนสถานะและแก้ไขประวัติการเข้าเรียน
- ป้องกันการแก้ไข Audit Logs ผ่าน API ทั่วไป
- กำหนด Retention Policy สำหรับ Logs
- ไม่บันทึกรหัสผ่าน, Access Token, Refresh Token หรือ QR Token เต็มใน Logs
- ใช้ Least Privilege สำหรับ Database Credentials
- ใช้ Secure Database Connection
- ป้องกันการเปิดเผย Stack Trace ใน Production
- กำหนดนโยบายสำรองข้อมูลและกู้คืนข้อมูล
- ประเมินความเสี่ยงด้านข้อมูลส่วนบุคคลและ PDPA ตามนโยบายของสถาบัน

---

# 17. Testing and Quality Assurance

ต้องพัฒนาระบบทดสอบควบคู่ไปกับระบบจริง

## 17.1 Backend Tests

ทดสอบ:

- Login สำเร็จและล้มเหลว
- การตรวจสอบสิทธิ์แต่ละ Role
- การเข้าถึง API โดยไม่มี Token
- การเข้าถึงข้อมูลข้ามผู้ใช้
- การสร้าง Attendance Session
- การเปิดและปิด Session
- การสร้าง QR Token
- QR Token หมดอายุ
- QR Token ไม่ถูกต้อง
- QR Token ถูกเพิกถอน
- นักศึกษาที่ไม่ได้ลงทะเบียน
- นักศึกษาที่บัญชีถูกระงับ
- เช็คชื่อซ้ำ
- การสแกนพร้อมกัน
- สถานะ Present และ Late
- การปิด Session ระหว่างเช็คชื่อ
- การแก้ไข Attendance Record โดยอาจารย์
- การบันทึก Audit Logs
- Pagination, Filtering และ Sorting
- Database Constraints

ใช้ PostgreSQL สำหรับ Integration Tests ที่ต้องตรวจสอบพฤติกรรมเฉพาะของฐานข้อมูล ห้ามพึ่ง SQLite เพียงอย่างเดียวในการทดสอบข้อจำกัดที่แตกต่างกัน

## 17.2 Front-end Tests

ทดสอบ:

- Home Page
- Login Page
- Role-Based Navigation
- Form Validation
- API Error Handling
- Dashboard Loading
- Data Table Filtering
- QR Scanner UI
- QR Check-in Success
- QR Check-in Failure
- Session Expired
- Responsive Layout

ใช้เครื่องมือทดสอบที่เหมาะสม เช่น Vitest, React Testing Library และ Playwright ตามความเหมาะสมของเวอร์ชัน

## 17.3 Acceptance Criteria

ระบบจะถือว่าพร้อมส่งมอบเมื่อ:

- ผู้ใช้สามารถเข้าสู่ระบบได้จริง
- ระบบเปลี่ยนเส้นทางตาม Role
- Admin จัดการข้อมูลได้จริง
- อาจารย์เปิดคาบเรียนและสร้าง QR Code ได้จริง
- นักศึกษาสแกน QR Code และบันทึกการเข้าเรียนได้จริง
- Django ตรวจสอบสิทธิ์และ Token ก่อนบันทึก
- ไม่สามารถเช็คชื่อซ้ำใน Session เดียวกันได้
- ข้อมูลถูกบันทึกลง Supabase PostgreSQL
- Dashboard แสดงข้อมูลจริง
- รายงานตรงกับข้อมูลที่บันทึกไว้
- API Documentation ใช้งานได้
- ไม่มี Error สำคัญที่ยังไม่ได้แก้ไข
- Automated Tests ผ่านตามเกณฑ์ที่กำหนด
- ติดตั้งและ Deploy ตามเอกสารได้
- ไม่มี Secret หรือ Credentials จริงใน Repository

---

# 18. Deployment and Operations

ออกแบบให้รองรับการ Deploy ด้วย Docker และแพลตฟอร์มที่รองรับ Container เช่น Coolify

องค์ประกอบการ Deploy:

- Next.js Front-end
- Django API
- Supabase PostgreSQL
- Reverse Proxy หรือ Platform Routing
- HTTPS
- Environment Variables
- Health Checks
- Application Logs
- Database Migrations
- Backup and Recovery

สร้างไฟล์ `docker-compose.yml` สำหรับ Local Development โดยไม่จำเป็นต้องจำลอง Supabase ทั้งระบบในเครื่อง

หากใช้ Supabase PostgreSQL เป็นฐานข้อมูลหลัก ให้ระบุขั้นตอนการตั้งค่า Project, Database Connection และ Connection Pooler อย่างชัดเจน

ข้อกำหนด Production:

- แยก Development และ Production
- ปิด Debug Mode
- กำหนด Allowed Hosts และ CORS ให้ถูกต้อง
- ใช้ HTTPS
- ตรวจสอบ Health Check ของ Front-end และ Back-end
- กำหนดขั้นตอน Migration ก่อนเปิดใช้งานเวอร์ชันใหม่
- ไม่รัน Migration ซ้ำจากหลาย Instance พร้อมกันโดยไม่มีการควบคุม
- ตรวจสอบการเชื่อมต่อฐานข้อมูลก่อนให้บริการ
- กำหนดนโยบาย Backup และ Restore
- จัดทำ Rollback Plan
- ระบุวิธีตรวจสอบ Logs และแก้ปัญหา
- ห้ามลบหรือ Reset ฐานข้อมูล Production โดยอัตโนมัติ

---

# 19. Documentation Requirements

สร้างเอกสารประกอบระบบอย่างน้อย:

## README.md
- ภาพรวมระบบ
- Technology Stack
- System Architecture
- Features
- Prerequisites
- Installation
- Environment Variables
- วิธีเริ่ม Front-end
- วิธีเริ่ม Back-end
- วิธีเชื่อมต่อ Supabase
- วิธีทดสอบ
- วิธี Deploy

## docs/architecture.md
- Architecture Diagram
- Component Responsibilities
- Authentication Flow
- QR Attendance Flow
- Security Boundaries

## docs/database-schema.md
- รายละเอียดตาราง
- Primary Keys
- Foreign Keys
- Constraints
- Indexes
- Entity Relationships

## docs/api-documentation.md
- Endpoint List
- HTTP Methods
- Authentication
- Request Parameters
- Request Body
- Response
- Error Codes
- Permission Requirements

## docs/installation.md
- ขั้นตอนติดตั้งแบบละเอียด
- คำสั่งที่ใช้จริง
- การตั้งค่า Environment Variables
- การ Migrate Database
- การสร้างบัญชีผู้ดูแลระบบอย่างปลอดภัย

## docs/deployment.md
- Production Configuration
- HTTPS
- Database Connection
- Deployment Steps
- Health Checks
- Backup
- Restore
- Rollback

## docs/user-manual.md
- คู่มือผู้ดูแลระบบ
- คู่มืออาจารย์
- คู่มือนักศึกษา
- ขั้นตอนเช็คชื่อด้วย QR Code
- วิธีแก้ปัญหาเบื้องต้น

---

# 20. OpenCode Development Workflow

ให้ดำเนินการพัฒนาอย่างเป็นขั้นตอน โดยใช้เครื่องมือที่มีอยู่ใน OpenCode อย่างเหมาะสม

## Phase 1: Repository Inspection and Planning

1. ตรวจสอบ Workspace ปัจจุบันก่อนสร้างหรือแก้ไขไฟล์
2. ตรวจสอบไฟล์เดิมและโครงสร้างโปรเจกต์
3. ห้ามเขียนทับไฟล์สำคัญโดยไม่ตรวจสอบ
4. ตรวจสอบเวอร์ชันและเอกสารทางการ
5. สรุป Architecture และ Data Model
6. สร้าง Development Plan
7. ระบุ Dependency ที่จำเป็น

## Phase 2: Project Foundation

1. สร้าง Next.js Project
2. ตั้งค่า TypeScript
3. ตั้งค่า Tailwind CSS
4. ติดตั้ง SweetAlert2
5. สร้าง Django Project
6. ติดตั้ง Django REST Framework และ Dependencies ที่จำเป็น
7. สร้าง Custom User Model
8. ตั้งค่า Supabase PostgreSQL
9. ตั้งค่า Environment Variables
10. สร้าง Health Check API
11. สร้าง README และ `.env.example`

## Phase 3: Database and Authentication

1. ออกแบบ Models
2. สร้าง Migrations
3. ทดสอบการเชื่อมต่อ PostgreSQL
4. พัฒนา Login และ Logout
5. พัฒนา Token Refresh
6. พัฒนา Role-Based Access Control
7. สร้างบัญชีผู้ดูแลระบบผ่าน Management Command ที่ปลอดภัย
8. ทดสอบ Authentication และ Permissions

## Phase 4: Academic Management

1. พัฒนา Users
2. พัฒนา Students
3. พัฒนา Instructors
4. พัฒนา Programs และ Class Groups
5. พัฒนา Academic Terms
6. พัฒนา Courses และ Course Offerings
7. พัฒนา Enrollments
8. พัฒนา Class Schedules
9. เชื่อมต่อ API กับ Front-end
10. ทดสอบ CRUD และ Permissions

## Phase 5: QR Attendance Core

1. พัฒนา Attendance Sessions
2. พัฒนา QR Token Service
3. พัฒนา QR Code Display
4. พัฒนา QR Scanner
5. พัฒนา Check-in API
6. พัฒนา Duplicate Prevention
7. พัฒนา Present/Late Rules
8. พัฒนา Session Closing
9. พัฒนา Attendance Records
10. พัฒนา Audit Logs
11. ทดสอบ Expiration, Replay และ Concurrent Requests

## Phase 6: Dashboard and Reports

1. พัฒนา Admin Dashboard
2. พัฒนา Instructor Dashboard
3. พัฒนา Student Dashboard
4. พัฒนา Data Tables
5. พัฒนา Charts
6. พัฒนา Filters
7. พัฒนา Attendance Reports
8. พัฒนา CSV Export
9. ทดสอบความถูกต้องของตัวเลข

## Phase 7: UI/UX Refinement

1. ตรวจสอบ Responsive Design
2. ตรวจสอบ Mobile QR Scanning
3. ปรับปรุง Loading States
4. ปรับปรุง Error Handling
5. ตรวจสอบ Accessibility
6. ตรวจสอบ Navigation
7. ตรวจสอบข้อความภาษาไทย
8. ตรวจสอบการแสดงวันที่และเวลา

## Phase 8: Testing and Security Review

1. รัน Backend Tests
2. รัน Front-end Tests
3. รัน Integration Tests
4. ตรวจสอบ Permissions
5. ตรวจสอบ Database Constraints
6. ตรวจสอบ Dependency Vulnerabilities
7. ตรวจสอบ Environment Variables
8. ตรวจสอบ Secret Leakage
9. แก้ไขปัญหาที่พบ
10. รันทดสอบซ้ำจนผ่านตามเกณฑ์

## Phase 9: Deployment Preparation

1. สร้าง Dockerfile ตามความเหมาะสม
2. สร้าง Docker Compose สำหรับ Local Development
3. เตรียม Production Environment
4. ทดสอบ Database Migrations
5. ทดสอบ Health Checks
6. จัดทำ Deployment Documentation
7. ตรวจสอบ Backup/Restore Plan
8. สรุปสถานะความพร้อมใช้งานจริง

---

# 21. Development Rules for OpenCode

ต้องปฏิบัติตามกฎต่อไปนี้ตลอดการพัฒนา

1. วิเคราะห์โค้ดและไฟล์ที่มีอยู่ก่อนแก้ไข
2. วางแผนการเปลี่ยนแปลงก่อนดำเนินการ
3. พัฒนาฟังก์ชันให้เสร็จเป็นโมดูล ไม่สร้างเพียงโครงสร้างเปล่า
4. ใช้ TypeScript Strict Mode
5. ใช้ Django ORM สำหรับการจัดการฐานข้อมูล
6. ห้ามเขียน SQL ที่เสี่ยงต่อ SQL Injection
7. ห้ามฝัง Credentials ลงใน Source Code
8. ห้ามใช้ Django Default Dashboard แทน Admin Panel
9. ห้ามสร้างปุ่มที่ไม่มีการทำงานจริง
10. ห้ามใช้ Mock Data เป็นข้อมูล Production
11. ห้ามซ่อน Error ด้วยการคืนข้อมูลปลอม
12. ห้ามปิด Security Checks เพื่อให้โปรแกรมทำงานผ่าน
13. ห้ามลบข้อมูลจริงเพื่อแก้ปัญหาการทดสอบ
14. ห้ามเปลี่ยน Dependency โดยไม่มีเหตุผล
15. ต้องจัดการ Error และ Loading States ให้ครบ
16. ต้องเพิ่ม Automated Tests ให้กับ Business Logic สำคัญ
17. ต้องบันทึกการตัดสินใจด้าน Architecture ที่สำคัญ
18. หากพบข้อกำหนดที่ขัดแย้งกัน ให้เลือกแนวทางที่ปลอดภัยและอธิบายเหตุผล
19. หากขาดข้อมูลที่ไม่จำเป็นต่อการเริ่มพัฒนา ให้กำหนดค่าเริ่มต้นที่สมเหตุสมผลและเปิดให้ปรับตั้งค่าได้
20. หากมีข้อจำกัดที่ต้องให้ผู้ใช้ดำเนินการ เช่น สร้าง Supabase Project หรือกำหนด Credentials ให้สร้างเอกสารและระบุขั้นตอนอย่างชัดเจน

## Definition of Done

ห้ามรายงานว่าระบบเสร็จสมบูรณ์เพียงเพราะสร้างไฟล์ครบ

ต้องตรวจสอบว่า:

- Dependencies ติดตั้งได้
- Front-end Build ผ่าน
- Django System Checks ผ่าน
- Database Migrations ทำงานได้
- API เชื่อมต่อฐานข้อมูลได้จริง
- Authentication ทำงานได้
- QR Check-in ทำงานได้
- Duplicate Prevention ทำงานได้
- Permissions ทำงานได้
- Tests ที่กำหนดผ่าน
- Dashboard ดึงข้อมูลจริง
- เอกสารติดตั้งและ Deploy ครบ
- ปัญหาที่ยังเหลือต้องรายงานตามจริง

หากยังไม่มี Credentials ของ Supabase ให้พัฒนาระบบและ Tests เท่าที่ทำได้โดยไม่ปลอมผลการเชื่อมต่อ พร้อมระบุขั้นตอนที่ต้องทำต่อหลังผู้ใช้ตั้งค่า Credentials

---

# 22. Final Deliverables

เมื่อดำเนินการเสร็จ ให้ส่งมอบ:

1. Source Code ของ Front-end
2. Source Code ของ Back-end
3. Database Models และ Migrations
4. REST API ที่ทำงานจริง
5. Authentication และ RBAC
6. Admin Panel
7. Admin Dashboard
8. Instructor Dashboard
9. Student Dashboard
10. QR Code Generator
11. QR Code Scanner
12. Attendance Processing
13. Attendance Reports
14. CSV Import/Export ตามขอบเขตที่พัฒนา
15. Automated Tests
16. `.env.example`
17. Docker Configuration
18. OpenAPI/Swagger Documentation
19. README.md
20. Installation Guide
21. Deployment Guide
22. User Manual
23. Security Review Summary
24. รายการฟังก์ชันที่เสร็จสมบูรณ์
25. รายการปัญหาที่ยังเหลือและวิธีแก้ไข

## Final Instruction

เริ่มต้นด้วยการตรวจสอบ Workspace และจัดทำแผนพัฒนาที่สอดคล้องกับโค้ดจริง จากนั้นลงมือพัฒนาระบบ Student Attendance Management System ตามลำดับความสำคัญ

ให้ความสำคัญสูงสุดกับ **ความถูกต้องของข้อมูล ความปลอดภัยของ Authentication ความน่าเชื่อถือของ QR Attendance การตรวจสอบสิทธิ์ และความสามารถในการ Deploy**

สร้างระบบที่มีทั้ง UI/UX, API, Database, Business Logic และ Automated Tests ที่เชื่อมโยงกันจริง ไม่ใช่เพียงหน้าจอสวยงาม

เมื่อทำแต่ละ Phase เสร็จ ให้รันคำสั่งตรวจสอบที่เกี่ยวข้อง แก้ไขข้อผิดพลาด และสรุปผลก่อนดำเนินการต่อ โดยไม่หยุดเพียงการเสนอแผนพัฒนา

**Project: Student Attendance Management System (SAMS)**

**Technology Stack: Next.js + TypeScript + Tailwind CSS + SweetAlert2 + Django REST Framework + Supabase PostgreSQL**

**Development Environment: OpenCode**

**Target: Secure, Responsive, Maintainable, Production-Ready Student Attendance Management System**
