import asyncio
import json
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from apps.notice.models import UserNotice


_notice_clients = {}


def build_user_notice_payload(user_notice):
    notice = user_notice.notice
    raw_extra = notice.extra if notice else ''
    extra_data = {}
    if raw_extra:
      try:
          extra_data = json.loads(raw_extra)
      except (TypeError, ValueError):
          extra_data = {}
    subtype = extra_data.get('type') or (notice.type if notice else '')
    category = extra_data.get('category') or (notice.type if notice else 'other')
    return {
        'id': user_notice.id,
        'title': notice.title if notice else '',
        'content': notice.content if notice else '',
        'type': notice.type if notice else '',
        'subtype': subtype,
        'category': category,
        'type_label': get_notice_type_label(subtype, category),
        'level': notice.level if notice else '',
        'is_read': user_notice.is_read,
        'extra': raw_extra,
        'jump_url': notice.jump_url if notice else '',
        'created_at': user_notice.created_at.strftime('%Y-%m-%d %H:%M'),
    }


def get_notice_type_label(subtype, category):
    type_label_map = {
        'order_candidate_applied': '接单申请',
        'order_candidate_withdrawn': '撤回申请',
        'order_selected': '客户选中',
        'order_confirmed': '待开始',
        'order_started': '服务中',
        'order_completed': '已完结',
        'order_reviewed': '评价',
        'order_cancelled': '已取消',
        'order_transferring': '转单',
        'order_removed': '被移除',
        'cs_request': '客服请求',
        'team_invite': '组队邀请',
        'order_invite': '订单邀请',
        'system': '系统',
        'order': '订单',
        'finance': '财务',
        'activity': '活动',
    }
    return type_label_map.get(subtype, type_label_map.get(category, '通知'))


def get_unread_count(user_id):
    return UserNotice.objects.filter(user_id=user_id, is_read=False, is_deleted=False).count()


def push_user_notice(user_notice):
    user_id = getattr(user_notice, 'user_id', None)
    if not user_id:
        return
    payload = {
        'event': 'notice.created',
        'unread_count': get_unread_count(user_id),
        'notice': build_user_notice_payload(user_notice),
    }
    push_to_user(user_id, payload)


def push_unread_count(user_id):
    if not user_id:
        return
    push_to_user(user_id, {
        'event': 'notice.unread_changed',
        'unread_count': get_unread_count(user_id),
    })


def push_to_user(user_id, payload):
    clients = list(_notice_clients.get(int(user_id), []))
    if not clients:
        return
    message = json.dumps(payload, ensure_ascii=False)
    for client in clients:
        try:
            asyncio.run_coroutine_threadsafe(client.send_json(message), client.loop)
        except RuntimeError:
            unregister_client(user_id, client)


def register_client(user_id, client):
    _notice_clients.setdefault(int(user_id), set()).add(client)


def unregister_client(user_id, client):
    clients = _notice_clients.get(int(user_id))
    if not clients:
        return
    clients.discard(client)
    if not clients:
        _notice_clients.pop(int(user_id), None)


class NoticeClient:
    def __init__(self, send, loop):
        self._send = send
        self.loop = loop

    async def send_json(self, message):
        await self._send({'type': 'websocket.send', 'text': message})


class NoticeWebSocketApp:
    async def __call__(self, scope, receive, send):
        user_id = self.get_user_id(scope)
        if not user_id:
            await send({'type': 'websocket.close', 'code': 4401})
            return

        await send({'type': 'websocket.accept'})
        client = NoticeClient(send, asyncio.get_running_loop())
        register_client(user_id, client)
        await self.send_initial_state(user_id, client)
        try:
            while True:
                message = await receive()
                message_type = message.get('type')
                if message_type == 'websocket.disconnect':
                    break
                if message_type == 'websocket.receive':
                    await self.handle_receive(message, client)
        finally:
            unregister_client(user_id, client)

    def get_user_id(self, scope):
        query = parse_qs((scope.get('query_string') or b'').decode())
        token = (query.get('token') or [''])[0]
        if not token:
            return None
        try:
            access_token = AccessToken(token)
            return int(access_token.get('user_id') or 0)
        except Exception:
            return None

    async def send_initial_state(self, user_id, client):
        count = await sync_to_async(get_unread_count)(user_id)
        await client.send_json(json.dumps({
            'event': 'notice.unread_changed',
            'unread_count': count,
            'server_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }, ensure_ascii=False))

    async def handle_receive(self, message, client):
        text = message.get('text') or ''
        if text == 'ping':
            await client.send_json(json.dumps({'event': 'pong'}, ensure_ascii=False))
