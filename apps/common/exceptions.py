from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        response.data = {
            'code': response.status_code,
            'msg': response.data.get('detail', str(exc)) if isinstance(response.data, dict) else str(response.data),
            'data': None
        }
        return response

    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return Response({
        'code': status.HTTP_500_INTERNAL_SERVER_ERROR,
        'msg': str(exc),
        'data': None
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BusinessException(APIException):
    status_code = 400
    default_detail = '业务异常'
    default_code = 'business_error'

    def __init__(self, detail=None, code=None):
        self.detail = detail or self.default_detail
        self.code = code or self.status_code
        super().__init__(detail=self.detail)
