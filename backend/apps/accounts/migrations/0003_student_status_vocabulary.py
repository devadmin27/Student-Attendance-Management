from django.db import migrations, models

# Old values describe account usability; the new values describe enrolment
# state. Mapping preserves the closest business meaning for existing rows.
FORWARD = {
    "active": "studying",
    "suspended": "leave_of_absence",
    "inactive": "withdrawn",
}

REVERSE = {
    "studying": "active",
    "leave_of_absence": "suspended",
    "withdrawn": "inactive",
    "graduated": "inactive",
}


def map_status(apps, mapping):
    StudentProfile = apps.get_model("accounts", "StudentProfile")
    for old, new in mapping.items():
        StudentProfile.objects.filter(status=old).update(status=new)


def forwards(apps, schema_editor):
    map_status(apps, FORWARD)


def backwards(apps, schema_editor):
    map_status(apps, REVERSE)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_alter_instructorprofile_department"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name="studentprofile",
            name="status",
            field=models.CharField(
                choices=[
                    ("studying", "กำลังศึกษา"),
                    ("graduated", "สำเร็จการศึกษา"),
                    ("withdrawn", "ลาออก"),
                    ("leave_of_absence", "พักการเรียน"),
                ],
                default="studying",
                max_length=16,
                verbose_name="สถานะ",
            ),
        ),
    ]
