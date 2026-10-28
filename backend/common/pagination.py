"""Server-side pagination for data tables."""
from collections import OrderedDict

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response(
            OrderedDict(
                [
                    ("success", True),
                    ("message", "โหลดข้อมูลสำเร็จ"),
                    ("data", data),
                    ("pagination", OrderedDict(self.metadata())),
                ]
            )
        )

    def metadata(self) -> dict:
        return {
            "count": self.page.paginator.count,
            "pages": self.page.paginator.num_pages,
            "current": self.page.number,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "page_size": self.get_page_size(self.request) if self.request else self.page_size,
        }
