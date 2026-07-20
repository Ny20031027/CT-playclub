# -*- coding: utf-8 -*-
import re

file_path = r'D:\CT电竞\PlayClub-WX\miniprogram\pages\employees\employees.js'

with open(file_path, 'r', encoding='utf-8-sig') as f:
    content = f.read()

# Fix the title
content = re.sub(r"title: '[^']+',", "title: '陪陪列表',", content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed employees.js')
