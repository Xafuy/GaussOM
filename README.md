# GaussDB 运维系统（GaussDBOM）

## 项目简介

GaussDBOM 是一个面向运维问题处理的流程平台，覆盖提单、审核、分析、闭环到关闭的完整生命周期，支持排班分单、身份路由、字段联动与基础权限控制。

当前版本以 Django + SQLite 实现 MVP，可用于功能演示与流程验证。

## 文档导航

- [需求文档](design/需求文档.md)：当前需求边界与功能说明
- [设计文档](design/设计文档.md)：架构、模块设计与实现状态
- [问题单流程字段与选项](design/问题单流程字段以及选项.txt)：详细字段清单与业务规则来源
- [原始需求](design/原始需求.md)：历史底稿，仅供参考
- [工具文档](工具文档.md)：本地运行、演示数据、账号与排班样例

## 技术栈

- Python 3.6+
- Django 3.2.x
- SQLite（默认）

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

访问：`http://127.0.0.1:8000/`

### Windows 与 SQLite 说明

旧版 Python 自带的 SQLite 可能未启用 JSON1，会导致 Django 的 `JSONField` 在 `migrate` 时报错。本项目工单 `extra_data` 已改为 [`JSONTextField`](tickets/fields.py)（TEXT 存 JSON），**无需 JSON1**。若你仍遇问题，请安装 **Python 3.10+**（官网安装包通常带较新 SQLite）。

## 当前已实现（MVP）

- 运维单七阶段流程（HCS提单 -> 问题审核 -> 运维分析 -> 开发分析 -> 开发审核 -> 运维闭环 -> 问题审核关闭）
- 阶段字段动态渲染（文本/富文本/下拉）与必填校验
- 条件联动字段（按字段值显示/必填）
- 工单列表多视图（我的待处理/我创建/全部）与筛选
- 自动分单（工作日轮值、晚间值班、请假跳过）
- 按提单人身份的分单路由（可后台配置）
- 值班管理月历展示；仅管理员可编辑排班
- RBAC 基础能力（角色、权限点、用户角色）
- 统计分析 Dashboard（人力投入、问题归属、透传分析、SLA趋势、排班联动）
- 中文化演示数据（账号、排班、路由、工单）

## 权限说明（当前策略）

- `staff/superuser` 可进入后台并执行后台管理
- 前台流程操作仍按业务权限点控制：`ticket:advance`、`ticket:transfer`、`ticket:edit_fields`
- 统计看板权限：`dashboard:view`
- 非 `staff/superuser` 用户需绑定角色后获得对应前台操作能力
