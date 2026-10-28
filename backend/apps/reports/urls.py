from django.urls import path

from apps.reports import views

urlpatterns = [
    path("reports/attendance/", views.AttendanceReportView.as_view(), name="report-attendance"),
    path("reports/attendance/export/", views.AttendanceReportExportView.as_view(), name="report-attendance-export"),
]
