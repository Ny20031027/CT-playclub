from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class CustomPageNumberPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'

    def get_paginated_response(self, data):
        return Response({
            'code': 200,
            'msg': 'success',
            'data': {
                'count': self.page.paginator.count,
                'page': self.page.number,
                'page_size': self.page.paginator.per_page,
                'results': data
            }
        })
