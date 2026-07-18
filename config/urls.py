from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.shortcuts import render
from datetime import date

def login_view(request):
    return render(request, 'pages/login.html')

def dashboard_view(request):
    return render(request, 'pages/dashboard.html', {'today': date.today().isoformat()})

def employees_view(request):
    return render(request, 'pages/employees.html')

def customers_view(request):
    return render(request, 'pages/customers.html')

def orders_view(request):
    return render(request, 'pages/orders.html')

def finance_view(request):
    return render(request, 'pages/finance.html')

def schedule_view(request):
    return render(request, 'pages/schedule.html', {'today': date.today().isoformat()})

def statistics_view(request):
    return render(request, 'pages/statistics.html')

def system_view(request):
    return render(request, 'pages/system.html')

def cs_manage_view(request):
    return render(request, 'pages/cs-manage.html')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', login_view, name='login'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('employees/', employees_view, name='employees'),
    path('customers/', customers_view, name='customers'),
    path('orders/', orders_view, name='orders'),
    path('finance/', finance_view, name='finance'),
    path('schedule/', schedule_view, name='schedule'),
    path('statistics/', statistics_view, name='statistics'),
    path('system/', system_view, name='system'),
    path('cs-manage/', cs_manage_view, name='cs-manage'),
    path('api/account/', include('apps.account.urls')),
    path('api/employee/', include('apps.employee.urls')),
    path('api/customer/', include('apps.customer.urls')),
    path('api/order/', include('apps.order.urls')),
    path('api/finance/', include('apps.finance.urls')),
    path('api/schedule/', include('apps.schedule.urls')),
    path('api/statistics/', include('apps.statistics.urls')),
    path('api/notice/', include('apps.notice.urls')),
    path('api/upload/', include('apps.upload.urls')),
    path('api/system/', include('apps.system.urls')),
    path('api/wx/', include('apps.wx.urls')),
    re_path(r'^$', login_view),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
