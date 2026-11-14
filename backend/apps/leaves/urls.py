from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.leaves import views

router = DefaultRouter()
router.register("leave-requests", views.LeaveRequestViewSet, basename="leave-request")
router.register("leave-courses", views.LeaveCourseViewSet, basename="leave-course")
router.register("leave-approvals", views.LeaveApprovalViewSet, basename="leave-approval")
router.register(
    "leave-role-assignments",
    views.LeaveRoleAssignmentViewSet,
    basename="leave-role-assignment",
)

urlpatterns = [
    # Policy + private attachment download are explicit routes (the latter is
    # open to all three roles, unlike the student/admin request viewset).
    path(
        "leave-requests/policy/",
        views.LeavePolicyView.as_view(),
        name="leave-policy",
    ),
    path(
        "leave-requests/<uuid:pk>/attachments/<uuid:attachment_id>/download/",
        views.LeaveAttachmentDownloadView.as_view(),
        name="leave-attachment-download",
    ),
    # Explicit detail route so the printed A4 document can be served to
    # students, instructors, and admins with its own role-aware scoping.
    path(
        "leave-requests/<uuid:pk>/print/",
        views.LeaveRequestPrintView.as_view(),
        name="leave-request-print",
    ),
    path("", include(router.urls)),
]
