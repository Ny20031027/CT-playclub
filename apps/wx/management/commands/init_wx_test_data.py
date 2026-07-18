import random
import string
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from django.db import transaction

from apps.account.models import User
from apps.customer.models import Customer
from apps.employee.models import (
    Employee, EmployeeSkill, EmployeeTag, EmployeeSkillRelation,
    EmployeeWallet, EmployeeStatus
)
from apps.wx.models import WxUser, GameCategory, Banner, Announcement


class Command(BaseCommand):
    help = '初始化微信小程序测试数据（游戏分类、陪玩师、老板用户）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='清空已有测试数据后重新创建',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('正在清空测试数据...')
            EmployeeSkillRelation.objects.filter(
                employee__user__username__startswith='test_emp_'
            ).delete()
            Employee.objects.filter(user__username__startswith='test_emp_').delete()
            WxUser.objects.filter(openid__startswith='test_openid_').delete()
            User.objects.filter(username__startswith='test_emp_').delete()
            User.objects.filter(username__startswith='test_boss_').delete()
            GameCategory.objects.filter(name__in=[
                '王者荣耀', '和平精英', '英雄联盟', '原神', '无畏契约',
                '三角洲行动', '绝地求生', 'CS2', '永劫无间', '暗区突围'
            ]).delete()
            Banner.objects.filter(title__startswith='测试').delete()
            Announcement.objects.filter(title__startswith='测试').delete()
            self.stdout.write('测试数据已清空')

        self.stdout.write('正在创建游戏分类...')
        game_data = [
            {'name': '王者荣耀', 'icon': '/assets/icons/game-wzry.png'},
            {'name': '和平精英', 'icon': '/assets/icons/game-hpjy.png'},
            {'name': '英雄联盟', 'icon': '/assets/icons/game-lol.png'},
            {'name': '原神', 'icon': '/assets/icons/game-ys.png'},
            {'name': '无畏契约', 'icon': '/assets/icons/game-wwqy.png'},
            {'name': '三角洲行动', 'icon': '/assets/icons/game-sjz.png'},
            {'name': '绝地求生', 'icon': '/assets/icons/game-jdqs.png'},
            {'name': 'CS2', 'icon': '/assets/icons/game-cs2.png'},
        ]
        games = []
        for idx, item in enumerate(game_data):
            game, _ = GameCategory.objects.get_or_create(
                name=item['name'],
                defaults={'icon': item['icon'], 'sort': idx, 'status': True}
            )
            games.append(game)

        self.stdout.write('正在创建技能...')
        skill_data = [
            {'name': '王者荣耀陪玩', 'category': 'MOBA', 'game': '王者荣耀'},
            {'name': '和平精英陪玩', 'category': '射击', 'game': '和平精英'},
            {'name': '英雄联盟陪玩', 'category': 'MOBA', 'game': '英雄联盟'},
            {'name': '原神代肝', 'category': 'RPG', 'game': '原神'},
            {'name': '无畏契约陪玩', 'category': '射击', 'game': '无畏契约'},
            {'name': '三角洲行动陪玩', 'category': '射击', 'game': '三角洲行动'},
            {'name': '绝地求生陪玩', 'category': '射击', 'game': '绝地求生'},
            {'name': 'CS2陪玩', 'category': '射击', 'game': 'CS2'},
        ]
        game_map = {g.name: g for g in games}
        skills = []
        for idx, item in enumerate(skill_data):
            skill, _ = EmployeeSkill.objects.get_or_create(
                name=item['name'],
                defaults={
                    'category': item['category'],
                    'game_category': game_map.get(item['game']),
                    'sort': idx,
                    'status': True,
                }
            )
            skills.append(skill)

        self.stdout.write('正在创建标签...')
        tag_data = [
            {'name': '声优', 'color': '#FF6B9D'},
            {'name': '技术大神', 'color': '#4ECDC4'},
            {'name': '温柔耐心', 'color': '#45B7D1'},
            {'name': '搞笑担当', 'color': '#F7DC6F'},
            {'name': '新人推荐', 'color': '#BB8FCE'},
            {'name': '通宵在线', 'color': '#85C1E2'},
        ]
        tags = []
        for item in tag_data:
            tag, _ = EmployeeTag.objects.get_or_create(
                name=item['name'],
                defaults={'color': item['color'], 'status': True}
            )
            tags.append(tag)

        self.stdout.write('正在创建陪玩师...')
        emp_names = [
            '小甜心', '大神带队', '温柔姐姐', '野王哥哥', '萌妹陪玩',
            '技术流', '搞笑陪玩', '声优小姐姐', '全能选手', '夜猫子',
            '电竞少女', 'carry全场', '暖心陪玩', '狙击手', '中单法王',
        ]
        genders = ['male', 'female']
        levels = ['new', 'normal', 'silver', 'gold', 'diamond', 'king']
        emp_users = []
        employees = []
        for i, name in enumerate(emp_names):
            username = f'test_emp_{i+1:03d}'
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'nickname': name,
                    'gender': random.choice(genders),
                    'password': make_password('test123456'),
                }
            )
            if created:
                openid = f'test_openid_emp_{i+1:03d}'
                WxUser.objects.get_or_create(
                    openid=openid,
                    defaults={
                        'user': user,
                        'nickname': name,
                        'gender': 2 if user.gender == 'female' else 1,
                    }
                )
            emp_users.append(user)

            employee, emp_created = Employee.objects.get_or_create(
                user=user,
                defaults={
                    'employee_no': f'EMP{1000+i+1}',
                    'real_name': name,
                    'nickname': name,
                    'gender': user.gender,
                    'age': random.randint(18, 28),
                    'level': random.choice(levels),
                    'status': 'idle',
                    'online_status': random.choice([True, True, False]),
                    'rating': round(random.uniform(4.5, 5.0), 1),
                    'order_count': random.randint(0, 999),
                    'intro': f'你好，我是{name}，擅长多种游戏，快来找我一起玩吧！',
                    'sort': i,
                }
            )
            if emp_created:
                EmployeeWallet.objects.get_or_create(employee=employee)
                EmployeeStatus.objects.get_or_create(employee=employee)
                # 随机分配 1-3 个技能和标签
                emp_skills = random.sample(skills, random.randint(1, min(3, len(skills))))
                for skill in emp_skills:
                    EmployeeSkillRelation.objects.get_or_create(
                        employee=employee,
                        skill=skill,
                        defaults={
                            'level': random.choice(['intermediate', 'skilled', 'master']),
                            'unit_price': Decimal(random.randint(20, 100)),
                        }
                    )
                emp_tags = random.sample(tags, random.randint(1, min(3, len(tags))))
                employee.tags.set(emp_tags)
            employees.append(employee)

        self.stdout.write('正在创建老板测试用户...')
        boss_names = ['老板一号', '老板二号', '老板三号']
        for i, name in enumerate(boss_names):
            username = f'test_boss_{i+1:03d}'
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'nickname': name,
                    'gender': 'unknown',
                    'password': make_password('test123456'),
                }
            )
            if created:
                openid = f'test_openid_boss_{i+1:03d}'
                WxUser.objects.get_or_create(
                    openid=openid,
                    defaults={
                        'user': user,
                        'nickname': name,
                        'gender': 0,
                    }
                )
                Customer.objects.get_or_create(
                    user=user,
                    defaults={'nickname': name}
                )

        self.stdout.write('正在创建轮播图和公告...')
        Banner.objects.get_or_create(
            title='测试轮播1',
            defaults={
                'image': '/assets/images/banner1.png',
                'link_url': '',
                'sort': 0,
                'status': True,
            }
        )
        Banner.objects.get_or_create(
            title='测试轮播2',
            defaults={
                'image': '/assets/images/banner2.png',
                'link_url': '',
                'sort': 1,
                'status': True,
            }
        )
        Announcement.objects.get_or_create(
            title='测试公告：欢迎体验陪玩平台',
            defaults={
                'content': '欢迎体验我们的陪玩平台，海量优质陪玩师等你来选择！',
                'type': 'info',
                'sort': 0,
                'status': True,
            }
        )

        self.stdout.write(self.style.SUCCESS(
            f'初始化完成：{len(games)} 个游戏分类，{len(skills)} 个技能，'
            f'{len(employees)} 个陪玩师，{len(boss_names)} 个老板用户'
        ))
