# -*- coding: utf-8 -*-
"""生成CT电竞运营成本预算报告PDF"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# 注册中文字体
font_paths = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
]
font_name = "Helvetica"
for fp in font_paths:
    if os.path.exists(fp):
        try:
            pdfmetrics.registerFont(TTFont("Chinese", fp))
            font_name = "Chinese"
            break
        except:
            pass

# 样式
styles = getSampleStyleSheet()
title_style = ParagraphStyle("Title_CN", parent=styles["Title"],
    fontName=font_name, fontSize=22, leading=28, spaceAfter=12)
h1_style = ParagraphStyle("H1_CN", parent=styles["Heading1"],
    fontName=font_name, fontSize=16, leading=22, spaceBefore=16, spaceAfter=8,
    textColor=colors.HexColor("#1a5276"))
h2_style = ParagraphStyle("H2_CN", parent=styles["Heading2"],
    fontName=font_name, fontSize=13, leading=18, spaceBefore=12, spaceAfter=6,
    textColor=colors.HexColor("#2e86c1"))
body_style = ParagraphStyle("Body_CN", parent=styles["BodyText"],
    fontName=font_name, fontSize=10, leading=15, spaceAfter=6)
bold_style = ParagraphStyle("Bold_CN", parent=body_style,
    fontName=font_name, fontSize=10, leading=15)
small_style = ParagraphStyle("Small_CN", parent=body_style,
    fontName=font_name, fontSize=8, leading=11, textColor=colors.grey)
center_style = ParagraphStyle("Center_CN", parent=body_style,
    fontName=font_name, alignment=1)
highlight_style = ParagraphStyle("Highlight_CN", parent=body_style,
    fontName=font_name, fontSize=12, leading=16, textColor=colors.HexColor("#c0392b"))

def make_table(data, col_widths=None):
    tbl = Table(data, hAlign="LEFT", colWidths=col_widths)
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME",   (0, 0), (-1, -1), font_name),
        ("FONTSIZE",   (0, 0), (-1, 0), 9),
        ("FONTSIZE",   (0, 1), (-1, -1), 9),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
    tbl.setStyle(style)
    return tbl

# 构建文档
doc = SimpleDocTemplate(
    "CT电竞运营成本预算报告.pdf", pagesize=A4,
    leftMargin=20*mm, rightMargin=20*mm,
    topMargin=25*mm, bottomMargin=25*mm,
    title="CT电竞运营成本预算报告",
    author="CT电竞技术团队",
)

story = []

# === 封面 ===
story.append(Spacer(1, 60*mm))
story.append(Paragraph("CT电竞（PlayClub）", title_style))
story.append(Paragraph("微信云托管运营成本预算报告", ParagraphStyle("sub", parent=title_style, fontSize=18, leading=24)))
story.append(Spacer(1, 20*mm))

cover_line = Table([[""]], colWidths=[160*mm])
cover_line.setStyle(TableStyle([
    ("LINEBELOW", (0, 0), (0, 0), 2, colors.HexColor("#2e86c1")),
]))
story.append(cover_line)
story.append(Spacer(1, 15*mm))

story.append(Paragraph("目标规模：日活 1,000 用户", body_style))
story.append(Paragraph("编制日期：2026年7月19日", body_style))
story.append(Paragraph("编制单位：CT电竞技术团队", body_style))
story.append(Spacer(1, 30*mm))
story.append(Paragraph("仅供投资决策参考", small_style))
story.append(PageBreak())

# === 目录 ===
story.append(Paragraph("目录", h1_style))
toc_items = [
    "一、项目概述", "二、用户行为模型", "三、资源配置方案",
    "四、详细成本测算", "五、月度总费用汇总", "六、不同规模成本对比",
    "七、与传统服务器方案对比", "八、年度预算规划", "九、投资建议"
]
for item in toc_items:
    story.append(Paragraph(item, body_style))
story.append(PageBreak())

# === 一、项目概述 ===
story.append(Paragraph("一、项目概述", h1_style))
story.append(Paragraph(
    "CT电竞（PlayClub）是一个游戏代练/陪玩服务平台，基于 Django + MySQL + 微信小程序架构。",
    body_style))

data = [
    ["模块", "说明"],
    ["用户管理", "客户、打手（员工）双角色体系"],
    ["订单系统", "发布→接单→进行中→完成→评价，全流程管理"],
    ["排班系统", "打手排班与时段管理"],
    ["财务系统", "收入统计、提现管理"],
    ["数据统计", "运营数据看板"],
    ["文件上传", "头像、订单图片等"],
]
story.append(make_table(data, col_widths=[40*mm, 120*mm]))
story.append(Spacer(1, 8*mm))

# === 二、用户行为模型 ===
story.append(Paragraph("二、用户行为模型（1000 DAU）", h1_style))

story.append(Paragraph("2.1 用户活跃特征", h2_style))
data = [
    ["指标", "数值", "说明"],
    ["日活用户（DAU）", "1,000", "目标规模"],
    ["人均日访问次数", "3 次", "早/中/晚各一次"],
    ["人均日 API 请求数", "30 次", "含页面加载、数据查询、操作提交"],
    ["日总请求数", "30,000 次", "1000 × 30"],
    ["活跃时段", "08:00-24:00", "16 小时"],
    ["高峰时段", "12:00-14:00, 19:00-23:00", "约 6 小时"],
]
story.append(make_table(data, col_widths=[45*mm, 45*mm, 70*mm]))
story.append(Spacer(1, 6*mm))

story.append(Paragraph("2.2 并发模型", h2_style))
data = [
    ["时段", "在线用户", "并发请求", "实例数"],
    ["高峰（6h）", "150-200", "15-20", "2"],
    ["正常（8h）", "80-120", "8-12", "1"],
    ["低谷（2h）", "20-40", "2-4", "1"],
    ["深夜（8h）", "0-10", "0-1", "0（缩容）"],
]
story.append(make_table(data, col_widths=[40*mm, 40*mm, 40*mm, 40*mm]))
story.append(Spacer(1, 8*mm))

# === 三、资源配置方案 ===
story.append(Paragraph("三、资源配置方案", h1_style))
data = [
    ["资源", "配置", "说明"],
    ["容器（服务）", "1 核 2GB", "Django + Gunicorn，3 个 worker"],
    ["实例副本数", "最小 0，最大 3", "自动扩缩容，无流量时零成本"],
    ["MySQL", "弹性 0.25-16 CCU", "Serverless，按需伸缩"],
    ["数据库存储", "5GB（初期）", "按实际存储量计费"],
    ["对象存储", "5GB", "用户头像、订单图片"],
]
story.append(make_table(data, col_widths=[35*mm, 45*mm, 80*mm]))
story.append(Spacer(1, 8*mm))

# === 四、详细成本测算 ===
story.append(Paragraph("四、详细成本测算", h1_style))

story.append(Paragraph("4.1 容器（服务）费用", h2_style))
story.append(Paragraph("定价：CPU 0.055 元/(核·时)，内存 0.032 元/(GB·时)", body_style))
data = [
    ["时段", "时长", "配置", "CPU 消耗", "内存消耗"],
    ["高峰", "6h", "1核2GB×2", "12 核·时", "24 GB·时"],
    ["正常", "9h", "1核2GB×1", "9 核·时", "18 GB·时"],
    ["低谷", "1h", "1核2GB×1", "1 核·时", "2 GB·时"],
    ["深夜", "8h", "0 实例", "0", "0"],
    ["日合计", "", "", "22 核·时", "44 GB·时"],
]
story.append(make_table(data, col_widths=[28*mm, 22*mm, 35*mm, 35*mm, 35*mm]))
story.append(Spacer(1, 4*mm))
story.append(Paragraph("月费用：CPU 660×0.055 = 36.30 元 + 内存 1320×0.032 = 42.24 元 = <b>78.54 元/月</b>", body_style))
story.append(Spacer(1, 6*mm))

story.append(Paragraph("4.2 MySQL 数据库费用", h2_style))
story.append(Paragraph("定价：算力 0.342 元/(CCU·时)，存储 0.00485 元/(GB·时)", body_style))
data = [
    ["时段", "时长", "算力", "存储"],
    ["白天活跃", "16h", "0.5 CCU", "5 GB"],
    ["深夜低活", "8h", "0.25 CCU", "5 GB"],
    ["日合计", "", "10 CCU·时", "120 GB·时"],
]
story.append(make_table(data, col_widths=[35*mm, 30*mm, 45*mm, 45*mm]))
story.append(Spacer(1, 4*mm))
story.append(Paragraph("月费用：算力 300×0.342 = 102.60 元 + 存储 3600×0.00485 = 17.46 元 = <b>120.06 元/月</b>", body_style))
story.append(Spacer(1, 6*mm))

story.append(Paragraph("4.3 公网流量费用", h2_style))
story.append(Paragraph("定价：0.8 元/GB", body_style))
story.append(Paragraph("日流量 30,000×50KB = 1.5 GB → 月流量 45 GB → <b>月费用 36.00 元</b>", body_style))
story.append(Spacer(1, 8*mm))

# === 五、月度总费用汇总 ===
story.append(Paragraph("五、月度总费用汇总", h1_style))

story.append(Paragraph("5.1 正式运营期（3 个月后）", h2_style))
data = [
    ["费用项", "月费用（元）", "占比"],
    ["容器（服务）", "78.54", "31.4%"],
    ["MySQL 数据库", "120.06", "48.1%"],
    ["公网流量", "36.00", "14.4%"],
    ["对象存储", "0.75", "0.3%"],
    ["静态资源", "2.10", "0.8%"],
    ["构建", "2.50", "1.0%"],
    ["合计", "239.95", "100%"],
]
story.append(make_table(data, col_widths=[55*mm, 50*mm, 55*mm]))
story.append(Spacer(1, 6*mm))

story.append(Paragraph("5.2 首 3 个月（含免费额度）", h2_style))
story.append(Paragraph("微信云托管为首个环境提供 3 个月免费额度，容器和数据库算力基本全覆盖。", body_style))
story.append(Paragraph("首 3 个月实际费用：<b>约 51 元/月</b>（主要是超额的流量和存储费用）", highlight_style))
story.append(Spacer(1, 8*mm))

# === 六、不同规模对比 ===
story.append(Paragraph("六、不同规模成本对比", h1_style))
data = [
    ["日活规模", "容器费用", "数据库费用", "流量费用", "月总计"],
    ["500 DAU", "39 元", "60 元", "18 元", "117 元"],
    ["1,000 DAU", "79 元", "120 元", "36 元", "240 元"],
    ["2,000 DAU", "157 元", "240 元", "72 元", "480 元"],
    ["5,000 DAU", "393 元", "600 元", "180 元", "1,199 元"],
    ["10,000 DAU", "785 元", "1,201 元", "360 元", "2,399 元"],
]
story.append(make_table(data, col_widths=[30*mm, 30*mm, 35*mm, 30*mm, 35*mm]))
story.append(Spacer(1, 8*mm))

# === 七、传统方案对比 ===
story.append(Paragraph("七、与传统服务器方案对比（1000 DAU）", h1_style))
data = [
    ["方案", "月费用", "优势", "劣势"],
    ["微信云托管", "~240 元", "自动扩缩容、免运维", "按量付费"],
    ["腾讯云 ECS+RDS", "~350 元", "固定成本可预测", "需自行运维"],
    ["轻量服务器+自建", "~150 元", "成本最低", "单点故障风险"],
]
story.append(make_table(data, col_widths=[35*mm, 25*mm, 45*mm, 45*mm]))
story.append(Spacer(1, 4*mm))
story.append(Paragraph("结论：微信云托管在 1000 DAU 规模下，成本低于传统 ECS 方案约 30%，且具备自动扩缩容和免运维优势。", bold_style))
story.append(Spacer(1, 8*mm))

# === 八、年度预算 ===
story.append(Paragraph("八、年度预算规划", h1_style))

story.append(Paragraph("8.1 保守预估（1000 DAU 稳定运营）", h2_style))
data = [
    ["阶段", "时间", "月费用", "阶段费用"],
    ["冷启动期", "第 1-3 个月", "~51 元", "153 元"],
    ["稳定运营期", "第 4-12 个月", "~240 元", "2,160 元"],
    ["年度合计", "", "", "2,313 元"],
]
story.append(make_table(data, col_widths=[35*mm, 35*mm, 35*mm, 40*mm]))
story.append(Spacer(1, 6*mm))

story.append(Paragraph("8.2 增长预估（500→2000 DAU）", h2_style))
data = [
    ["阶段", "时间", "DAU", "月费用", "阶段费用"],
    ["冷启动期", "第 1-3 月", "500", "~30 元", "90 元"],
    ["增长期", "第 4-6 月", "1,000", "~240 元", "720 元"],
    ["扩张期", "第 7-9 月", "1,500", "~360 元", "1,080 元"],
    ["成熟期", "第 10-12 月", "2,000", "~480 元", "1,440 元"],
    ["年度合计", "", "", "", "3,330 元"],
]
story.append(make_table(data, col_widths=[28*mm, 28*mm, 25*mm, 30*mm, 35*mm]))
story.append(Spacer(1, 8*mm))

# === 九、投资建议 ===
story.append(Paragraph("九、投资建议", h1_style))

story.append(Paragraph("核心结论", h2_style))
conclusions = [
    "1. 极低的启动成本：首 3 个月仅需约 51 元/月，年运营成本约 2,300 元",
    "2. 弹性可扩展：从 100 到 10,000 DAU，无需迁移架构，自动扩缩容",
    "3. 免运维：无需服务器运维人员，团队专注业务开发",
    "4. 微信生态深度集成：天然支持小程序登录、支付、消息推送",
]
for c in conclusions:
    story.append(Paragraph(c, body_style))
story.append(Spacer(1, 6*mm))

story.append(Paragraph("建议配置路径", h2_style))
data = [
    ["阶段", "DAU", "推荐配置", "月预算"],
    ["MVP 验证期", "< 500", "0.5核1G + MySQL 0.25CCU", "100 元"],
    ["初创运营期", "500-2000", "1核2G + MySQL 0.5CCU", "300 元"],
    ["规模增长期", "2000-5000", "2核4G + MySQL 1CCU", "800 元"],
    ["成熟稳定期", "5000-10000", "4核8G + MySQL 2CCU", "2,000 元"],
]
story.append(make_table(data, col_widths=[30*mm, 28*mm, 55*mm, 30*mm]))
story.append(Spacer(1, 15*mm))

# 页脚
story.append(Paragraph("— 本报告由 CT电竞技术团队编制，仅供投资决策参考 —", center_style))
story.append(Paragraph("数据来源：微信云托管官方定价 (developers.weixin.qq.com)", small_style))

# 生成
doc.build(story)
print("PDF generated: CT电竞运营成本预算报告.pdf")
