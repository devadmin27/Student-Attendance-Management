"""SAMS dev seed — ข้อมูลทดสอบสำหรับ SQLite dev DB เท่านั้น (production ห้ามใช้!).

รันผ่าน:
  $env:DJANGO_DEBUG="True"; $env:DB_ENGINE="sqlite"
  python manage.py shell -c "exec(open('scripts/seed_dev_data.py', encoding='utf-8').read())"

เนื้อหา:
- ผู้ใช้ 3 บทบาท (รหัสผ่าน dev-only เดียวกัน, ห้ามใช้กับระบบจริง)
- หลักสูตร / กลุ่มเรียน / ภาคการศึกษา 1/2569 (current)
- รายวิชา + เปิดสอน + ตารางเรียน + การลงทะเบียน
- คาบเช็คชื่อ: ย้อนหลัง (closed, มี record จริง) + คาบที่กำลังเปิดวันนี้ (open) + คาบพรุ่งนี้ (scheduled)
"""
import random
from datetime import date, time, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import InstructorProfile, StudentProfile, User
from apps.academics.models import AcademicTerm, ClassGroup, Program
from apps.attendance.models import AttendanceRecord, AttendanceSession
from apps.courses.models import Course, CourseOffering, Enrollment
from apps.schedules.models import ClassSchedule

DEV_PASSWORD = "SamsDev!2026"  # dev-only, SQLite dev DB เท่านั้น
random.seed(42)

THAI_NAMES = [
    ("สมชาย", "ใจดี"), ("มาลี", "รักเรียน"), ("ธนกฤต", "โรจน์รุ่งเรือง"),
    ("สุภาพ", "เพียรงาน"), ("กัญญา", "ดวงแสง"), ("ปิยะ", "สุขสบาย"),
    ("ชeconomicนตรี", "เมตตา"), ("นภัสสร", "ระยิบระยับ"),
]
INSTRUCTOR_NAMES = [("วิชัย", "ศรีสอนดี"), ("อรุณรัตน์", "วิชาชีพ")]


def run():
    if User.objects.exists():
        print("seed: ⤋ มีข้อมูลอยู่แล้ว — ไม่ seed ซ้ำ")
        return

    with transaction.atomic():
        # --- ผู้ใช้ ---
        admin = User.objects.create_user("admin", "admin@dev.local", DEV_PASSWORD, role="admin")
        admin.is_staff = admin.is_superuser = True
        admin.save(update_fields=["is_staff", "is_superuser"])

        instructors = []
        for i, (fn, ln) in enumerate(INSTRUCTOR_NAMES, start=1):
            u = User.objects.create_user(
                f"instructor{i}", f"instructor{i}@dev.local", DEV_PASSWORD, role="instructor"
            )
            InstructorProfile.objects.filter(user=u).update(
                employee_code=f"T{i:04d}", first_name=fn, last_name=ln,
                department="ภาควิชาวิทยาการคอมพิวเตอร์", status="active",
            )
            instructors.append(InstructorProfile.objects.get(user=u))

        program = Program.objects.get_or_create(
            program_code="CS-2569",
            defaults={"program_name": "วิทยาการคอมพิวเตอร์ (ปริญญาตรี)", "degree_level": "bachelor"},
        )[0]
        group = ClassGroup.objects.create(
            group_code="CS-2569-1", group_name="ห้อง 1 — วิทยาการคอมพิวเตอร์",
            program=program, academic_year_level=1,
        )
        group2 = ClassGroup.objects.create(
            group_code="CS-2568-3", group_name="ห้อง 3 — ชั้นปีที่ 3",
            program=program, academic_year_level=3,
        )
        term = AcademicTerm.objects.create(
            academic_year=2569, semester="1",
            start_date=date(2569 - 543, 6, 1), end_date=date(2569 - 543, 10, 31),
            is_active=True, is_current=True,
        )

        students = []
        for i in range(1, 9):
            fn, ln = THAI_NAMES[(i - 1) % len(THAI_NAMES)]
            u = User.objects.create_user(
                f"student{i:02d}", f"student{i:02d}@dev.local", DEV_PASSWORD, role="student"
            )
            StudentProfile.objects.filter(user=u).update(
                student_code=f"65000{i:03d}",
                first_name=fn, last_name=ln,
                program=program, class_group=group if i <= 6 else group2,
                academic_year_level=1 if i <= 6 else 3, status="active",
            )
            students.append(StudentProfile.objects.get(user=u))

        # --- รายวิชา + เปิดสอน ---
        course_specs = [
            ("30110001", "พื้นฐานการเขียนโปรแกรมคอมพิวเตอร์", Decimal("3")),
            ("30110002", "โครงสร้างข้อมูลและอัลกอริทึม", Decimal("3")),
            ("30110003", "ระบบฐานข้อมูล", Decimal("3")),
        ]
        courses = [
            Course.objects.create(course_code=code, course_name=name, credits=c)
            for code, name, c in course_specs
        ]
        offerings = []
        for idx, course in enumerate(courses):
            offering = CourseOffering.objects.create(
                course=course, academic_term=term,
                instructor=instructors[idx % len(instructors)],
                class_group=group, status="open",
            )
            offerings.append(offering)
            Enrollment.objects.bulk_create(
                [
                    Enrollment(student=s, course_offering=offering, enrollment_status="enrolled")
                    for s in students[:6]  # กลุ่ม 1 (6 คน) — กลุ่ม 3 ยังไม่สมัครรายวิชานี้
                ]
            )
            weekday = (idx * 2) % 5  # จันทร์/พุธ/ศุกร์ กระจายกัน
            ClassSchedule.objects.create(
                course_offering=offering, weekday=weekday,
                start_time=time(9 + idx, 0), end_time=time(10 + idx + 1, 0),
                classroom=f"อาคารสีชมพู {idx + 1}01", status="active",
            )

        # --- คาบเช็คชื่อย้อนหลัง (closed) — 5 คาบต่อวิชา, กระจาย 30 วันล่าสุด ---
        status_pool = ["present", "present", "present", "late", "absent", "excused"]
        now = timezone.now()
        today = timezone.localdate()
        for offering in offerings:
            instructor = offering.instructor
            for k in range(5, 0, -1):  # 14, 21, 28, 35, 42 วันก่อนวันนี้
                day = today - timedelta(days=14 + 7 * (k - 1))
                start = timezone.make_aware(
                    timezone.datetime.combine(day, time(9, 0))
                )
                end = start + timedelta(hours=1)
                AttendanceSession.objects.create(
                    course_offering=offering, instructor=instructor,
                    session_date=day, check_in_start=start, check_in_end=end,
                    late_threshold_minutes=15, status="closed",
                    closed_at=end + timedelta(minutes=20),
                )
        closed = AttendanceSession.objects.filter(status="closed")
        for session in closed:
            for s in students[:6]:
                st = random.choice(status_pool)
                AttendanceRecord.objects.create(
                    attendance_session=session, student=s, status=st,
                    check_in_method="qr" if st in ("present", "late") else "manual",
                )

        # --- คาบวันนี้ (open) สำหรับทดสอบสแกน QR สด ---
        open_offer = offerings[0]
        sess = AttendanceSession.objects.create(
            course_offering=open_offer, instructor=open_offer.instructor,
            session_date=today,
            check_in_start=now - timedelta(minutes=5),
            check_in_end=now + timedelta(hours=1),
            late_threshold_minutes=15, status="open",
        )
        # มี 2 คนเช็คชื่อแล้ว เพื่อทดสอบ duplicate จาก UI
        for s in students[:2]:
            AttendanceRecord.objects.create(
                attendance_session=sess, student=s, status="present",
                check_in_method="manual", edit_reason="seed: บันทึกล่วงหน้าเพื่อทดสอบ",
                source_metadata={"seed": True},
            )

        # --- คาบพรุ่งนี้ (scheduled) ---
        AttendanceSession.objects.create(
            course_offering=offerings[1], instructor=offerings[1].instructor,
            session_date=today + timedelta(days=1),
            check_in_start=now + timedelta(days=1),
            check_in_end=now + timedelta(days=1, hours=1),
            late_threshold_minutes=15, status="scheduled",
        )

        print("seed: ✓ เสร็จ — users:", User.objects.count(),
              "| sessions:", AttendanceSession.objects.count(),
              "| records:", AttendanceRecord.objects.count())


run()
