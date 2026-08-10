from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.order.models import OrderChatGroup


class Command(BaseCommand):
    help = '删除已超过72小时有效期的订单服务群及其消息'

    def handle(self, *args, **options):
        queryset = OrderChatGroup.objects.filter(expires_at__lte=timezone.now())
        count = queryset.count()
        queryset.delete()
        self.stdout.write(self.style.SUCCESS(f'已删除 {count} 个过期订单服务群'))
