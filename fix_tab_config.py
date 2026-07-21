# -*- coding: utf-8 -*-
import re

file_path = r'D:\CT电竞\PlayClub-WX\miniprogram\app.js'

with open(file_path, 'r', encoding='utf-8-sig') as f:
    content = f.read()

# Replace the dasher tab config to include homepage
old_dasher = """  dasher: [
    { pagePath: '/pages/dispatch-hall/dispatch-hall', text: '派单', icon: 'icon-dispatch' },
    { pagePath: '/pages/profile/profile', text: '我的', icon: 'icon-profile' },
  ],"""

new_dasher = """  dasher: [
    { pagePath: '/pages/index/index', text: '首页', icon: 'icon-home' },
    { pagePath: '/pages/dispatch-hall/dispatch-hall', text: '派单', icon: 'icon-dispatch' },
    { pagePath: '/pages/profile/profile', text: '我的', icon: 'icon-profile' },
  ],"""

content = content.replace(old_dasher, new_dasher)

# Replace the cs tab config to include homepage
old_cs = """  cs: [
    { pagePath: '/pages/cs-home/cs-home', text: '客服', icon: 'icon-cs' },
    { pagePath: '/pages/profile/profile', text: '我的', icon: 'icon-profile' },
  ],"""

new_cs = """  cs: [
    { pagePath: '/pages/index/index', text: '首页', icon: 'icon-home' },
    { pagePath: '/pages/cs-home/cs-home', text: '客服', icon: 'icon-cs' },
    { pagePath: '/pages/profile/profile', text: '我的', icon: 'icon-profile' },
  ],"""

content = content.replace(old_cs, new_cs)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed ROLE_TAB_CONFIG')
