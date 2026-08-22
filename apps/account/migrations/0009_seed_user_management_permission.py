from django.db import migrations


def seed_user_management_permission(apps, schema_editor):
    Permission = apps.get_model('account', 'Permission')
    Role = apps.get_model('account', 'Role')

    permission, _ = Permission.objects.update_or_create(
        code='menu.users',
        defaults={
            'name': '用户管理',
            'type': 'menu',
            'path': '/users/',
            'icon': 'fa-users-gear',
            'sort': 105,
            'visible': True,
            'status': True,
            'is_deleted': False,
        },
    )
    Role.objects.filter(code__in=['owner', 'admin', 'general_manager']).update(status=True, is_deleted=False)
    for role in Role.objects.filter(code__in=['owner', 'admin', 'general_manager']):
        role.permissions.add(permission)


def unseed_user_management_permission(apps, schema_editor):
    Permission = apps.get_model('account', 'Permission')
    Permission.objects.filter(code='menu.users').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0008_seed_oa_roles_permissions'),
    ]

    operations = [
        migrations.RunPython(seed_user_management_permission, reverse_code=unseed_user_management_permission),
    ]
