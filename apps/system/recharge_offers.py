import json
from decimal import Decimal, InvalidOperation

from .models import Config


RECHARGE_OFFERS_KEY = 'recharge_offers'
DEFAULT_RECHARGE_OFFERS = [
    {'amount': 10, 'coins': 100, 'bonus_coins': 0},
    {'amount': 50, 'coins': 500, 'bonus_coins': 50},
    {'amount': 100, 'coins': 1000, 'bonus_coins': 150},
    {'amount': 500, 'coins': 5000, 'bonus_coins': 1000},
]


def _to_decimal(value):
    try:
        return Decimal(str(value or 0)).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0.00')


def _to_int(value):
    try:
        return int(value or 0)
    except (ValueError, TypeError):
        return 0


def normalize_recharge_offer(raw, index=0):
    amount = _to_decimal(raw.get('amount', raw.get('real_amount', raw.get('price', 0))))
    coins = _to_int(raw.get('coins', raw.get('credited_coins', 0)))
    bonus_coins = max(0, _to_int(raw.get('bonus_coins', raw.get('bonus', 0))))
    sort = _to_int(raw.get('sort', index))
    status = raw.get('status', True)
    if isinstance(status, str):
        status = status.lower() not in ('false', '0', 'no', 'off')

    if amount <= 0 or coins <= 0:
        return None

    return {
        'id': raw.get('id') or index + 1,
        'amount': float(amount),
        'coins': coins,
        'bonus_coins': bonus_coins,
        'total_coins': coins + bonus_coins,
        'sort': sort,
        'status': bool(status),
    }


def get_recharge_offers(active_only=True):
    cfg = Config.objects.filter(
        key=RECHARGE_OFFERS_KEY, is_deleted=False
    ).first()
    raw_items = DEFAULT_RECHARGE_OFFERS
    if cfg and cfg.value:
        try:
            parsed = json.loads(cfg.value)
            if isinstance(parsed, list):
                raw_items = parsed
        except (TypeError, ValueError):
            raw_items = DEFAULT_RECHARGE_OFFERS

    offers = []
    seen_amounts = set()
    for index, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue
        offer = normalize_recharge_offer(item, index)
        if not offer:
            continue
        if active_only and not offer['status']:
            continue
        amount_key = str(_to_decimal(offer['amount']))
        if amount_key in seen_amounts:
            continue
        seen_amounts.add(amount_key)
        offers.append(offer)

    return sorted(offers, key=lambda x: (x['sort'], x['amount'], x['id']))


def resolve_recharge_coins(amount):
    amount_decimal = _to_decimal(amount)
    for offer in get_recharge_offers(active_only=True):
        if _to_decimal(offer['amount']) == amount_decimal:
            return offer['total_coins'], offer
    return int(amount_decimal * Decimal('10')), None
