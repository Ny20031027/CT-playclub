# -*- coding: utf-8 -*-
import re

file_path = r'D:\CT电竞\PlayClub-WX\miniprogram\pages\index\index.js'

with open(file_path, 'r', encoding='utf-8-sig') as f:
    content = f.read()

# Add userType to onLoad
old = """  onLoad: function() {
    var app = getApp();
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 44,
    });
    this.loadData();
  },"""

new = """  onLoad: function() {
    var app = getApp();
    var userInfo = app.globalData.userInfo || {};
    var userType = app.getUserType ? app.getUserType(userInfo) : (userInfo.user_type || 'customer');
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 44,
      userType: userType,
    });
    this.loadData();
  },"""

content = content.replace(old, new)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed index.js')
