from django.db import migrations


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

ALL_PERMISSION_CODES = {code for _, code, *_ in MENU_PERMISSIONS} | {code for _, code in ACTION_PERMISSIONS}

ROLE_DEFINITIONS = {
    'owner': {
        'name': '老板',
        'sort': 1,
        'data_scope': 'all',
        'remark': '最高权限：拥有后台全部功能、财务、系统设置、日志和账号权限管理。',
        'permissions': ALL_PERMISSION_CODES,
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


def seed_oa_permissions(apps, schema_editor):
    Permission = apps.get_model('account', 'Permission')
    Role = apps.get_model('account', 'Role')

    permission_by_code = {}
    for name, code, path, icon, sort in MENU_PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'type': 'menu',
                'path': path,
                'icon': icon,
                'sort': sort,
                'visible': True,
                'status': True,
                'is_deleted': False,
            },
        )
        permission_by_code[code] = permission

    for index, (name, code) in enumerate(ACTION_PERMISSIONS, start=1):
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'type': 'api',
                'sort': 1000 + index,
                'visible': False,
                'status': True,
                'is_deleted': False,
            },
        )
        permission_by_code[code] = permission

    for code, role_config in ROLE_DEFINITIONS.items():
        role, _ = Role.objects.update_or_create(
            code=code,
            defaults={
                'name': role_config['name'],
                'sort': role_config['sort'],
                'status': True,
                'data_scope': role_config['data_scope'],
                'remark': role_config['remark'],
                'is_deleted': False,
            },
        )
        role.permissions.set(
            permission_by_code[permission_code]
            for permission_code in role_config['permissions']
            if permission_code in permission_by_code
        )

    admin_role = Role.objects.filter(code='admin').first()
    if admin_role:
        admin_role.permissions.add(*permission_by_code.values())


def unseed_oa_permissions(apps, schema_editor):
    Role = apps.get_model('account', 'Role')
    Permission = apps.get_model('account', 'Permission')
    Role.objects.filter(code__in=ROLE_DEFINITIONS.keys()).delete()
    Permission.objects.filter(code__in=ALL_PERMISSION_CODES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0007_user_auth_invalid_before'),
    ]

    operations = [
        migrations.RunPython(seed_oa_permissions, reverse_code=unseed_oa_permissions),
    ]
