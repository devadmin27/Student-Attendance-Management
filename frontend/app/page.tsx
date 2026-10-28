import Link from "next/link";

const FEATURES = [
  {
    icon: "📷",
    title: "เช็คชื่อด้วย QR Code",
    desc: "สแกนเข้าเรียนภายในวินาที — token หมุนเวียนอัตโนมัติตาม TTL ป้องกันการถ่ายภาพทรานสพาส",
  },
  {
    icon: "⏱️",
    title: "ตรวจจับมาสายอัตโนมัติ",
    desc: "ระบบคำนวณสถานะเข้าเรียน/มาสาย/ขาดเรียนจากกรอบเวลาที่อาจารย์กำหนด",
  },
  {
    icon: "📈",
    title: "รายงานอัตราการเข้าเรียน",
    desc: "คำนวณตามสูตร (present+late)/(present+late+absent+excused) พร้อมส่งออก CSV",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      <header className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-5">
        <div>
          <div className="text-lg font-bold text-blue-900">SAMS</div>
          <div className="text-xs text-slate-500">Student Attendance Management System</div>
        </div>
        <Link
          href="/login"
          className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800"
        >
          เข้าสู่ระบบ
        </Link>
      </header>

      <main className="mx-auto w-full max-w-5xl px-6 pb-16">
        <section className="py-14 text-center">
          <h1 className="text-3xl font-bold text-slate-900 md:text-4xl">
            ระบบจัดการการเข้าเรียนของนักศึกษา
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-slate-600">
            เช็คชื่อคาบเรียนด้วย QR Code ที่ทำงานบน Supabase PostgreSQL — ปลอดภัยด้วย JWT
            และ Refresh Token แบบ HttpOnly Cookie ตรวจสอบสิทธิ์ RBAC ทุกระดับ
          </p>
          <div className="mt-8 flex justify-center gap-3">
            <Link
              href="/login"
              className="rounded-xl bg-blue-700 px-6 py-3 font-medium text-white shadow hover:bg-blue-800"
            >
              เข้าสู่ระบบใช้งาน
            </Link>
            <a
              href="/docs"
              target="_blank"
              className="rounded-xl border border-blue-200 bg-white px-6 py-3 font-medium text-blue-800 shadow-sm hover:bg-blue-50"
            >
              เอกสาร API
            </a>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="text-3xl" aria-hidden>
                {f.icon}
              </div>
              <h2 className="mt-3 font-semibold text-slate-900">{f.title}</h2>
              <p className="mt-1 text-sm text-slate-600">{f.desc}</p>
            </div>
          ))}
        </section>

        <section className="mt-10 rounded-2xl border border-blue-100 bg-blue-50/60 p-6 text-sm text-slate-700">
          <h2 className="font-semibold text-blue-900">กลุ่มผู้ใช้งาน</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>ผู้ดูแลระบบ — จัดการผู้ใช้ หลักสูตร รายวิชา ภาคการศึกษา และ Audit Log</li>
            <li>อาจารย์ — เปิด/ปิดคาบเช็คชื่อ แสดง QR หมุนเวียน แก้ไขสถานะพร้อมเหตุผลที่บันทึกเป็น Audit</li>
            <li>นักศึกษา — สแกนเข้าเรียน ดูรายวิชา ตารางเรียน และประวัติการเช็คชื่อของตนเอง</li>
          </ul>
        </section>
      </main>

      <footer className="border-t border-slate-200 px-6 py-6 text-center text-xs text-slate-400">
        SAMS v1.0.0 — Next.js + Django REST Framework + Supabase PostgreSQL
      </footer>
    </div>
  );
}
