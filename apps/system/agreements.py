import json
from copy import deepcopy

from .models import Config


AGREEMENTS_CONFIG_KEY = 'mini_agreements'


DEFAULT_AGREEMENTS = [
    {
        'key': 'user_agreement',
        'title': '用户协议',
        'summary': '适用于登录、充值、下单等平台基础服务。',
        'content': (
            '欢迎使用黑金电竞陪玩平台。\n\n'
            '1. 您在使用本平台服务前，应仔细阅读并充分理解本协议内容。\n'
            '2. 您应保证提交的账号资料、联系方式及订单信息真实、准确、完整。\n'
            '3. 您不得利用平台从事违法违规、损害他人权益或破坏平台秩序的行为。\n'
            '4. 平台将根据订单规则、服务说明及实际履约情况处理订单、售后与争议。\n'
            '5. 如您继续使用本平台，即表示您已阅读并同意本协议。'
        ),
        'sort': 0,
        'status': True,
    },
    {
        'key': 'privacy_policy',
        'title': '隐私政策',
        'summary': '说明平台如何收集、使用与保护您的个人信息。',
        'content': (
            '我们重视并保护您的个人信息与隐私安全。\n\n'
            '1. 平台可能收集您的微信身份标识、昵称、头像、联系方式、游戏账号、订单信息等必要数据。\n'
            '2. 上述信息仅用于登录认证、订单履约、客服沟通、安全风控及平台服务改进。\n'
            '3. 未经您授权或法律法规要求，平台不会向无关第三方泄露您的个人信息。\n'
            '4. 您可以在小程序内管理个人资料与游戏账号信息。\n'
            '5. 如对隐私保护有疑问，可联系平台客服处理。'
        ),
        'sort': 1,
        'status': True,
    },
    {
        'key': 'recharge_agreement',
        'title': '充值协议',
        'summary': '适用于黑钻充值、到账、赠送与消费规则。',
        'content': (
            '请在充值前仔细阅读本协议。\n\n'
            '1. 黑钻为平台虚拟权益，可用于平台内订单消费。\n'
            '2. 充值档位、到账黑钻和赠送黑钻以充值页面展示及后台配置为准。\n'
            '3. 充值成功后黑钻通常立即到账，如遇异常请及时联系客服。\n'
            '4. 黑钻不支持私下交易、转卖或用于平台外用途。\n'
            '5. 因用户操作错误造成的充值或消费，请第一时间联系客服协助核实。'
        ),
        'sort': 2,
        'status': True,
    },
    {
        'key': 'dasher_entry_agreement',
        'title': '打手入驻协议',
        'summary': '适用于打手提交入驻资料、接单与履约规范。',
        'content': (
            '请在提交打手入驻申请前仔细阅读本协议。\n\n'
            '1. 您应保证提交的身份、联系方式、游戏能力等资料真实有效。\n'
            '2. 入驻审核通过后，应按照平台规则接单、履约并保持良好服务态度。\n'
            '3. 接单后不得私下交易、恶意弃单、泄露客户账号信息或从事违规行为。\n'
            '4. 平台可根据订单完成情况、客户评价、违规记录等调整接单权限。\n'
            '5. 如您提交入驻申请，即表示您已阅读并同意本协议。'
        ),
        'sort': 3,
        'status': True,
    },
]


def _normalize_agreement(item, fallback=None):
    fallback = fallback or {}
    key = str(item.get('key') or fallback.get('key') or '').strip()
    title = str(item.get('title') or fallback.get('title') or '').strip()
    content = str(item.get('content') or fallback.get('content') or '').replace('\\n', '\n').strip()
    summary = str(item.get('summary') or fallback.get('summary') or '').strip()
    if not key or not title:
        return None
    return {
        'key': key,
        'title': title,
        'summary': summary,
        'content': content,
        'sort': int(item.get('sort', fallback.get('sort', 0)) or 0),
        'status': bool(item.get('status', fallback.get('status', True))),
    }


def get_agreements(active_only=True):
    """读取小程序协议配置，未配置时返回默认协议。"""
    defaults = deepcopy(DEFAULT_AGREEMENTS)
    defaults_by_key = {item['key']: item for item in defaults}
    merged = {item['key']: item for item in defaults}

    cfg = Config.objects.filter(key=AGREEMENTS_CONFIG_KEY, is_deleted=False).first()
    if cfg and cfg.value:
        try:
            parsed = json.loads(cfg.value)
            if isinstance(parsed, list):
                for index, item in enumerate(parsed):
                    if not isinstance(item, dict):
                        continue
                    key = str(item.get('key') or '').strip()
                    normalized = _normalize_agreement(
                        {**item, 'sort': item.get('sort', index)},
                        defaults_by_key.get(key),
                    )
                    if normalized:
                        merged[normalized['key']] = normalized
        except Exception:
            pass

    agreements = sorted(merged.values(), key=lambda item: (item.get('sort', 0), item.get('key', '')))
    if active_only:
        agreements = [item for item in agreements if item.get('status', True)]
    return agreements


def get_agreement(slug):
    slug = str(slug or '').strip()
    for item in get_agreements(active_only=True):
        if item['key'] == slug:
            return item
    return None
