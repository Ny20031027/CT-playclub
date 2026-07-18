#!/usr/bin/env python
"""
创建测试数据脚本
运行方式: python scripts/create_test_data.py
"""
import os
import sys
import django

# 设置Django环境
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from apps.account.models import User
from apps.employee.models import Employee, EmployeeSkill, EmployeeSkillRelation, EmployeeTag
from apps.customer.models import Customer
from apps.wx.models import GameCategory, Banner, Announcement


def create_game_categories():
    """创建游戏分类"""
    games = [
        {'name': '王者荣耀', 'icon': 'https://img.cdn.qqgame.qq.com/market/item/img/0_1644791720789.png', 'sort': 1},
        {'name': '和平精英', 'icon': 'https://img.cdn.qqgame.qq.com/market/item/img/0_1644791720789.png', 'sort': 2},
        {'name': '英雄联盟', 'icon': 'https://img.cdn.qqgame.qq.com/market/item/img/0_1644791720789.png', 'sort': 3},
        {'name': '原神', 'icon': 'https://img.cdn.qqgame.qq.com/market/item/img/0_1644791720789.png', 'sort': 4},
        {'name': '绝地求生', 'icon': 'https://img.cdn.qqgame.qq.com/market/item/img/0_1644791720789.png', 'sort': 5},
        {'name': '穿越火线', 'icon': 'https://img.cdn.qqgame.qq.com/market/item/img/0_1644791720789.png', 'sort': 6},
        {'name': 'CSGO', 'icon': 'https://img.cdn.qqgame.qq.com/market/item/img/0_1644791720789.png', 'sort': 7},
        {'name': '永劫无间', 'icon': 'https://img.cdn.qqgame.qq.com/market/item/img/0_1644791720789.png', 'sort': 8},
    ]
    
    created_games = []
    for game_data in games:
        game, created = GameCategory.objects.get_or_create(
            name=game_data['name'],
            defaults=game_data
        )
        created_games.append(game)
        status = '创建' if created else '已存在'
        print(f'  {status}: {game.name}')
    
    return created_games


def create_employee_skills(games):
    """创建陪玩技能"""
    skills = []
    for game in games:
        skill, created = EmployeeSkill.objects.get_or_create(
            name=f'{game.name}陪玩',
            defaults={
                'category': game.name,
                'sort': 1,
                'status': True,
            }
        )
        # 关联游戏分类（如果EmployeeSkill有game_category字段）
        # skill.game_category = game
        # skill.save()
        skills.append(skill)
        status = '创建' if created else '已存在'
        print(f'  {status}: {skill.name}')
    
    return skills


def create_employee_tags():
    """创建陪玩标签"""
    tags_data = [
        {'name': '技术好', 'color': '#6EC6FF'},
        {'name': '声音好听', 'color': '#79E2AE'},
        {'name': '有耐心', 'color': '#FFB74D'},
        {'name': '会聊天', 'color': '#E57373'},
        {'name': '带飞', 'color': '#BA68C8'},
        {'name': '教学认真', 'color': '#4FC3F7'},
        {'name': '准时守信', 'color': '#81C784'},
        {'name': '配合默契', 'color': '#FFD54F'},
    ]
    
    tags = []
    for tag_data in tags_data:
        tag, created = EmployeeTag.objects.get_or_create(
            name=tag_data['name'],
            defaults=tag_data
        )
        tags.append(tag)
        status = '创建' if created else '已存在'
        print(f'  {status}: {tag.name}')
    
    return tags


def create_test_employees(skills, tags):
    """创建测试陪玩师"""
    employees_data = [
        {
            'username': 'employee_001',
            'nickname': '小甜心',
            'real_name': '王小明',
            'gender': 'female',
            'age': 22,
            'level': 'gold',
            'rating': 4.9,
            'order_count': 328,
            'intro': '王者荣耀国服最强辅助，擅长保护队友，带你上分无忧',
            'online_status': True,
            'status': 'idle',
        },
        {
            'username': 'employee_002',
            'nickname': '大神带队',
            'real_name': '李大伟',
            'gender': 'male',
            'age': 25,
            'level': 'diamond',
            'rating': 5.0,
            'order_count': 512,
            'intro': '英雄联盟王者段位，擅长打野和中单，带你轻松上分',
            'online_status': True,
            'status': 'idle',
        },
        {
            'username': 'employee_003',
            'nickname': '温柔姐姐',
            'real_name': '张温柔',
            'gender': 'female',
            'age': 24,
            'level': 'silver',
            'rating': 4.8,
            'order_count': 256,
            'intro': '原神深渊满星大佬，帮你打材料和深渊',
            'online_status': False,
            'status': 'idle',
        },
        {
            'username': 'employee_004',
            'nickname': '吃鸡高手',
            'real_name': '陈小刚',
            'gender': 'male',
            'age': 23,
            'level': 'gold',
            'rating': 4.7,
            'order_count': 189,
            'intro': '和平精英职业选手，带你吃鸡不是梦',
            'online_status': True,
            'status': 'idle',
        },
        {
            'username': 'employee_005',
            'nickname': '声音甜妹',
            'real_name': '刘小美',
            'gender': 'female',
            'age': 21,
            'level': 'normal',
            'rating': 4.6,
            'order_count': 156,
            'intro': '声音超甜，陪你聊天打游戏，让游戏不再孤单',
            'online_status': True,
            'status': 'idle',
        },
        {
            'username': 'employee_006',
            'nickname': '电竞教练',
            'real_name': '赵教练',
            'gender': 'male',
            'age': 28,
            'level': 'king',
            'rating': 4.9,
            'order_count': 892,
            'intro': '前职业选手，专业教学，让你快速提升技术',
            'online_status': True,
            'status': 'idle',
        },
    ]
    
    employees = []
    for emp_data in employees_data:
        # 创建用户
        user, created = User.objects.get_or_create(
            username=emp_data['username'],
            defaults={
                'nickname': emp_data['nickname'],
                'is_staff': False,
            }
        )
        if created:
            user.set_password('123456')
            user.save()
        
        # 创建陪玩师
        employee, emp_created = Employee.objects.get_or_create(
            user=user,
            defaults={
                'employee_no': f'EMP{user.id:04d}',
                'real_name': emp_data['real_name'],
                'nickname': emp_data['nickname'],
                'gender': emp_data['gender'],
                'age': emp_data['age'],
                'level': emp_data['level'],
                'rating': emp_data['rating'],
                'order_count': emp_data['order_count'],
                'intro': emp_data['intro'],
                'online_status': emp_data['online_status'],
                'status': emp_data['status'],
            }
        )
        
        # 随机分配技能和标签
        if emp_created or not employee.skills.exists():
            # 分配2-3个技能
            import random
            skill_count = random.randint(2, 3)
            selected_skills = random.sample(skills, min(skill_count, len(skills)))
            for skill in selected_skills:
                EmployeeSkillRelation.objects.get_or_create(
                    employee=employee,
                    skill=skill,
                    defaults={
                        'level': 'skilled',
                        'unit_price': random.randint(25, 80),
                    }
                )
        
        if emp_created or not employee.tags.exists():
            # 分配2-4个标签
            import random
            tag_count = random.randint(2, 4)
            selected_tags = random.sample(tags, min(tag_count, len(tags)))
            employee.tags.set(selected_tags)
        
        employees.append(employee)
        status = '创建' if emp_created else '已存在'
        print(f'  {status}: {employee.nickname}')
    
    return employees


def create_banners():
    """创建轮播图"""
    banners_data = [
        {'title': '新用户首单立减10元', 'image': '/assets/images/banner1.png', 'sort': 1},
        {'title': '五一特惠活动', 'image': '/assets/images/banner2.png', 'sort': 2},
    ]
    
    for banner_data in banners_data:
        banner, created = Banner.objects.get_or_create(
            title=banner_data['title'],
            defaults=banner_data
        )
        status = '创建' if created else '已存在'
        print(f'  {status}: {banner.title}')


def create_announcements():
    """创建公告"""
    announcements_data = [
        {'title': '欢迎使用CT电竞陪玩平台', 'content': '专业游戏陪玩，让游戏更有趣', 'type': 'info', 'sort': 1},
        {'title': '新用户注册送优惠券', 'content': '新用户注册即送10元优惠券', 'type': 'activity', 'sort': 2},
    ]
    
    for ann_data in announcements_data:
        ann, created = Announcement.objects.get_or_create(
            title=ann_data['title'],
            defaults=ann_data
        )
        status = '创建' if created else '已存在'
        print(f'  {status}: {ann.title}')


def main():
    print('=' * 50)
    print('开始创建测试数据')
    print('=' * 50)
    
    print('\n1. 创建游戏分类...')
    games = create_game_categories()
    
    print('\n2. 创建陪玩技能...')
    skills = create_employee_skills(games)
    
    print('\n3. 创建陪玩标签...')
    tags = create_employee_tags()
    
    print('\n4. 创建测试陪玩师...')
    employees = create_test_employees(skills, tags)
    
    print('\n5. 创建轮播图...')
    create_banners()
    
    print('\n6. 创建公告...')
    create_announcements()
    
    print('\n' + '=' * 50)
    print('测试数据创建完成！')
    print(f'  游戏分类: {GameCategory.objects.count()} 个')
    print(f'  陪玩技能: {EmployeeSkill.objects.count()} 个')
    print(f'  陪玩标签: {EmployeeTag.objects.count()} 个')
    print(f'  陪玩师: {Employee.objects.count()} 个')
    print(f'  轮播图: {Banner.objects.count()} 个')
    print(f'  公告: {Announcement.objects.count()} 个')
    print('=' * 50)


if __name__ == '__main__':
    main()
