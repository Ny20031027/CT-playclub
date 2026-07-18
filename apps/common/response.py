from rest_framework.response import Response


def success_response(data=None, msg='success', code=200):
    return Response({
        'code': code,
        'msg': msg,
        'data': data
    }, status=code if code < 400 else 200)


def error_response(msg='error', code=400, data=None):
    return Response({
        'code': code,
        'msg': msg,
        'data': data
    }, status=200)
