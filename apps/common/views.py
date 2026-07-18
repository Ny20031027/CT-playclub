import requests
from django.http import HttpResponse
from django.views import View


class FrontendProxyView(View):
    def get(self, request, path=None):
        frontend_url = f"http://localhost:8081/{path}" if path else "http://localhost:8081/"
        try:
            response = requests.get(frontend_url, stream=True)
            content_type = response.headers.get('Content-Type', 'text/html')
            return HttpResponse(response.content, content_type=content_type)
        except Exception as e:
            return HttpResponse(f"Frontend proxy error: {str(e)}", status=503)
