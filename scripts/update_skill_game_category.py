#!/usr/bin/env python
"""
更新技能的游戏分类关联
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from apps.employee.models import EmployeeSkill
from apps.wx.models import GameCategory


# 技能category到游戏分类的映射
CATEGORY_MAP = {
    'MOBA': ['王者荣耀', '英雄联盟'],
    '射击': ['和平精英', '绝地求生', '穿越火线', 'CSGO', 'CS2', '无畏契约', '三角洲行动'],
    'RPG': ['原神'],
}


def main():
    print('更新技能的游戏分类关联...')
    
    # 获取游戏分类
    games = {game.name: game for game in GameCategory.objects.filter(status=True)}
    
    # 更新技能
    skills = EmployeeSkill.objects.all()
    updated = 0
    for skill in skills:
        category = skill.category
        game_names = CATEGORY_MAP.get(category, [])
        
        # 找到第一个匹配的游戏分类
        for game_name in game_names:
            if game_name in games:
                skill.game_category = games[game_name]
                skill.save(update_fields=['game_category'])
                print(f'  {skill.name} ({category}) -> {game_name}')
                updated += 1
                break
        else:
            print(f'  {skill.name} ({category}) -> 未找到匹配')
    
    print(f'\n完成! 更新了 {updated} 个技能')


if __name__ == '__main__':
    main()
