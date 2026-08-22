from urllib.parse import unquote


OWNER_ROLE_CODES = {'owner', 'admin'}
OA_ROLE_CODES = {
    'owner',
    'general_manager',
    'finance',
    'platform_lead',
    'platform_staff',
}

MENU_PERMISSIONS = [
    ('数据概览', 'menu.dashboard', '/dashboard/', 'fa-chart-line', 10),
    ('打手管理', 'menu.employees', '/employees/', 'fa-user-shield', 20),
    ('客户管理', 'menu.customers', '/customers/', 'fa-user', 30),
    ('客服管理', 'menu.cs_manage', '/cs-manage/', 'fa-headset', 40),
    ('订单管理', 'menu.orders', '/orders/', 'fa-file-text', 50),
    ('财务管理', 'menu.finance', '/finance/', 'fa-wallet', 60),
    ('排班管理', 'menu.schedule', '/schedule/', 'fa-calendar-days', 70),
    ('数据统计', 'menu.statistics', '/statistics/', 'fa-bar-chart', 80),
    ('档案系统', 'menu.archives', '/archives/', 'fa-folder-open', 90),
    ('入驻审核', 'menu.dasher_review', '/dasher-review/', 'fa-id-card', 100),
    ('系统设置', 'menu.system', '/system/', 'fa-gear', 110),
]

ACTION_PERMISSIONS = [
    ('账号查看', 'account.read'),
    ('账号管理', 'account.write'),
    ('角色权限管理', 'account.permission.write'),
    ('打手查看', 'employee.read'),
    ('打手管理', 'employee.write'),
    ('客户查看', 'customer.read'),
    ('客户管理', 'customer.write'),
    ('客服查看', 'cs.read'),
    ('客服管理', 'cs.write'),
    ('订单查看', 'order.read'),
    ('订单管理', 'order.write'),
    ('财务查看', 'finance.read'),
    ('财务操作', 'finance.write'),
    ('排班查看', 'schedule.read'),
    ('排班管理', 'schedule.write'),
    ('统计查看', 'statistics.read'),
    ('档案查看', 'archives.read'),
    ('档案记录', 'archives.write'),
    ('入驻审核查看', 'dasher_review.read'),
    ('入驻审核处理', 'dasher_review.write'),
    ('系统查看', 'system.read'),
    ('系统设置', 'system.write'),
    ('操作日志查看', 'logs.read'),
    ('文件上传', 'upload.write'),
]

ROLE_DEFINITIONS = {
    'owner': {
        'name': '老板',
        'sort': 1,
        'data_scope': 'all',
        'remark': '最高权限：拥有后台全部功能、财务、系统设置、日志和账号权限管理。',
        'permissions': '*',
    },
    'general_manager': {
        'name': '总管理',
        'sort': 2,
        'data_scope': 'all',
        'remark': '全局运营统筹：运营、人事、订单、平台日常；财务只读，不做资金操作。',
        'permissions': {
            'menu.dashboard', 'menu.employees', 'menu.customers', 'menu.cs_manage',
            'menu.orders', 'menu.finance', 'menu.schedule', 'menu.statistics',
            'menu.archives', 'menu.dasher_review',
            'account.read', 'account.write',
            'employee.read', 'employee.write',
            'customer.read', 'customer.write',
            'cs.read', 'cs.write',
            'order.read', 'order.write',
            'finance.read',
            'schedule.read', 'schedule.write',
            'statistics.read',
            'archives.read', 'archives.write',
            'dasher_review.read', 'dasher_review.write',
            'logs.read',
            'upload.write',
        },
    },
    'finance': {
        'name': '财务',
        'sort': 3,
        'data_scope': 'all',
        'remark': '独立财务操作：记账、结算、提现审核、财务报表及导出。',
        'permissions': {
            'menu.dashboard', 'menu.finance',
            'employee.read', 'customer.read', 'order.read',
            'finance.read', 'finance.write',
            'statistics.read',
            'upload.write',
        },
    },
    'platform_lead': {
        'name': '平台负责人',
        'sort': 4,
        'data_scope': 'all',
        'remark': '平台运营协调：订单、客服、档案、基础数据和普通售后处理，不含财务和系统底层设置。',
        'permissions': {
            'menu.dashboard', 'menu.customers', 'menu.cs_manage', 'menu.orders',
            'menu.statistics', 'menu.archives',
            'customer.read', 'customer.write',
            'cs.read', 'cs.write',
            'order.read', 'order.write',
            'statistics.read',
            'archives.read', 'archives.write',
            'upload.write',
        },
    },
    'platform_staff': {
        'name': '平台管理',
        'sort': 5,
        'data_scope': 'self',
        'remark': '基础执行：平台订单跟进、客户问答、档案记录和基础统计，不含审批、财务和系统设置。',
        'permissions': {
            'menu.dashboard', 'menu.customers', 'menu.orders', 'menu.archives',
            'customer.read',
            'order.read',
            'archives.read', 'archives.write',
            'upload.write',
        },
    },
}


def all_permission_codes():
    return {code for _, code, *_ in MENU_PERMISSIONS} | {code for _, code in ACTION_PERMISSIONS}


def role_permission_codes(role_code):
    permissions = ROLE_DEFINITIONS.get(role_code, {}).get('permissions', set())
    if permissions == '*':
        return all_permission_codes()
    return set(permissions)


def user_is_owner(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    try:
        return bool(OWNER_ROLE_CODES.intersection(set(user.get_role_codes())))
    except Exception:
        return False


def user_has_permission(user, permission_code):
    if user_is_owner(user):
        return True
    try:
        return permission_code in user.get_user_permissions()
    except Exception:
        return False


def required_permission_for_request(path, method):
    path = unquote(path or '')
    method = (method or 'GET').upper()
    is_read = method in {'GET', 'HEAD', 'OPTIONS'}

    if not path.startswith('/api/'):
        return None
    if path.startswith('/api/wx/'):
        return None
    if path.startswith('/api/account/auth/'):
        return None
    if path in {
        '/api/account/users/info/',
        '/api/account/users/menus/',
        '/api/account/users/permissions/',
        '/api/account/users/change-password/',
    }:
        return None

    if path.startswith('/api/upload/'):
        return 'upload.write'
    if path.startswith('/api/finance/'):
        return 'finance.read' if is_read else 'finance.write'
    if path.startswith('/api/statistics/'):
        return 'statistics.read'
    if path.startswith('/api/schedule/'):
        return 'schedule.read' if is_read else 'schedule.write'
    if path.startswith('/api/order/'):
        return 'order.read' if is_read else 'order.write'

    if path.startswith('/api/customer/archive-records/') or path.startswith('/api/employee/archive-records/'):
        return 'archives.read' if is_read else 'archives.write'
    if path.startswith('/api/customer/cs-'):
        return 'cs.read' if is_read else 'cs.write'
    if path.startswith('/api/customer/'):
        return 'customer.read' if is_read else 'customer.write'
    if path.startswith('/api/employee/employees/') or path.startswith('/api/employee/wallets/') or path.startswith('/api/employee/contracts/') or path.startswith('/api/employee/statuses/'):
        return 'employee.read' if is_read else 'employee.write'
    if path.startswith('/api/employee/'):
        return 'dasher_review.read' if is_read else 'dasher_review.write'

    if path.startswith('/api/account/login-logs/'):
        return 'logs.read' if is_read else 'account.write'
    if path.startswith('/api/account/roles/') or path.startswith('/api/account/permissions/'):
        return 'account.read' if is_read else 'account.permission.write'
    if path.startswith('/api/account/'):
        return 'account.read' if is_read else 'account.write'

    if path.startswith('/api/system/operation-logs/') or path.startswith('/api/system/error-logs/'):
        return 'logs.read' if is_read else 'system.write'
    if path.startswith('/api/system/'):
        return 'system.read' if is_read else 'system.write'

    return None
