"""Serializers for auth, users, students, instructors."""
import uuid

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import StudentProfile, User, InstructorProfile


THAI_ROLE_LABELS = dict(User._meta.get_field("role").choices)


class UserSerializer(serializers.ModelSerializer):
    student_code = serializers.CharField(
        source="student_profile.student_code", read_only=True, default=None
    )

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "role", "is_active",
            "date_joined", "created_at", "updated_at", "student_code",
        ]
        read_only_fields = ["id", "date_joined", "created_at", "updated_at"]

    def validate_role(self, value):
        request = self.context.get("request")
        if request and not getattr(request.user, "role", "") == "admin":
            # Self role edits are forbidden; role changes are admin-only.
            raise serializers.ValidationError("เฉพาะผู้ดูแลระบบเท่านั้นที่แก้ไขบทบาทได้")
        return value


class UserCreateSerializer(serializers.ModelSerializer):
    """Admin-only user creation honouring mass-assignment protection:
    role must be explicit; password is validated, hashed, never echoed."""


    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    confirm_password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ["id", "username", "email", "role", "password", "confirm_password", "is_active"]

    def validate_role(self, value):
        roles = {choice[0] for choice in User._meta.get_field("role").choices}
        if value not in roles:
            raise serializers.ValidationError("บทบาทไม่ถูกต้อง")
        return value

    def validate(self, attrs):
        password = attrs.get("password")
        if password:
            if attrs.get("confirm_password") and attrs["confirm_password"] != password:
                raise serializers.ValidationError({"confirm_password": "รหัสผ่านยืนยันไม่ตรงกัน"})
            try:
                validate_password(password)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    def create(self, validated):
        password = validated.pop("password")
        validated.pop("confirm_password", None)
        user = User(**validated)
        user.set_password(password)  # hashed storage, never plaintext
        user.save()
        return user


class StudentProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    account_active = serializers.BooleanField(source="user.is_active", read_only=True)
    program_name = serializers.CharField(source="program.program_name", read_only=True, default=None)
    class_group_name = serializers.CharField(source="class_group.group_name", read_only=True, default=None)

    class Meta:
        model = StudentProfile
        fields = [
            "id", "user", "username", "email", "account_active",
            "student_code", "first_name", "last_name", "program", "program_name",
            "academic_year_level", "class_group", "class_group_name", "status",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "user", "created_at", "updated_at"]

    def validate_status(self, value):
        statuses = {c[0] for c in StudentProfile._meta.get_field("status").choices}
        if value not in statuses:
            raise serializers.ValidationError("สถานะไม่ถูกต้อง")
        return value


class InstructorProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = InstructorProfile
        fields = [
            "id", "user", "username", "email",
            "employee_code", "first_name", "last_name", "department", "status",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "user", "created_at", "updated_at"]


class DynamicQuerysetField(serializers.PrimaryKeyRelatedField):
    """Relates lazily to avoid import-time cycles."""

    def __init__(self, **kwargs):
        self.model_name = kwargs.pop("model_name", "")
        super().__init__(**kwargs)

    def get_queryset(self):
        from apps.academics.models import ClassGroup, Program

        return {
            "program": Program.objects.all(),
            "class_group": ClassGroup.objects.all(),
        }[self.model_name]


class StudentCreateSerializer(serializers.ModelSerializer):
    """Admin creates user account + student profile in one request."""

    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    password = serializers.CharField(write_only=True)
    student_code = serializers.CharField(max_length=32)
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    program = DynamicQuerysetField(
        model_name="program", allow_null=True, required=False
    )
    academic_year_level = serializers.IntegerField(min_value=1, max_value=8, default=1)
    class_group = DynamicQuerysetField(
        model_name="class_group", allow_null=True, required=False
    )

    class Meta:
        model = StudentProfile
        fields = [
            "id", "username", "email", "password",
            "student_code", "first_name", "last_name",
            "program", "academic_year_level", "class_group", "status",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.academics.models import ClassGroup, Program  # local import; avoids cycles
        self.fields["program"].queryset = Program.objects.all()
        self.fields["class_group"].queryset = ClassGroup.objects.all()

    def validate_username(self, value):
        exists = User.objects.filter(username__iexact=value).exists()
        if exists:
            raise serializers.ValidationError("ชื่อผู้ใช้นี้ถูกใช้แล้ว")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated):
        password = validated.pop("password")
        username = validated.pop("username")
        email = validated.pop("email", "")
        try:
            with transaction.atomic():
                with_user = User.objects.create_user(
                    username=username, email=email, password=password, role="student"
                )
                # create_user already inserted the StudentProfile via
                # UserManager._ensure_profile (student_code=auto-...) — update
                # that row instead of inserting a second one for the same
                # OneToOne user_id (UniqueViolation on Postgres → 500).
                student = StudentProfile.objects.get(user=with_user)
                for field, value in validated.items():
                    setattr(student, field, value)
                student.save()
                return student
        except IntegrityError as exc:
            raise serializers.ValidationError("มีบัญชีหรือรหัสนักศึกษานี้อยู่แล้ว") from exc


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class SAMSLoginSerializer(TokenObtainPairSerializer):
    """Login that also carries SAMS role/profile claims for the front-end."""

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        profile = None
        student = getattr(user, "student_profile", None)
        instructor = getattr(user, "instructor_profile", None)
        if student is not None:
            profile = {
                "student_code": student.student_code,
                "first_name": student.first_name,
                "last_name": student.last_name,
            }
        elif instructor is not None:
            profile = {
                "employee_code": user.instructor_profile.employee_code,
                "first_name": user.instructor_profile.first_name,
                "last_name": user.instructor_profile.last_name,
            }
        data["user"] = {
            "id": str(user.id),
            "username": user.username,
            "role": user.role,
            "role_th": THAI_ROLE_LABELS.get(user.role, user.role),
            "profile": profile,
        }
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["username"] = user.username
        return token


class MeSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()
    role_th = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "role", "role_th", "profile"]

    def get_role_th(self, user):
        return THAI_ROLE_LABELS.get(user.role, user.role)

    def get_profile(self, user):
        student = getattr(user, "student_profile", None)
        instructor = getattr(user, "instructor_profile", None)
        if student is not None:
            return {
                "student_code": student.student_code,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "program_id": str(student.program_id) if student.program_id else None,
                "class_group_id": str(student.class_group_id) if student.class_group_id else None,
            }
        if instructor is not None:
            return {
                "employee_code": instructor.employee_code,
                "first_name": instructor.first_name,
                "last_name": instructor.last_name,
                "department": instructor.department,
            }
        return None
