# GaussDB运维系统 数据库表设计草案（ER级别）

## 1. 说明

本文基于以下模块输出 ER 级别表设计草案：
- 组织与权限
- 值班与请假排班
- 工单流转与状态机
- 分单策略与轮询引擎
- 字段配置与动态表单
- Dashboard 统计分析
- 配置中心与基础数据
- 技术架构与非功能

当前目标是明确核心实体、主外键关系、关键索引建议，不展开到完整物理字段细节（如长度、默认值、约束脚本）。

---

## 2. ER 主干（按业务域）

### 2.1 组织与权限域

#### `sys_user`（用户）
- `id` PK
- `username` UNIQUE
- `display_name`
- `email`
- `phone`
- `status`（active/inactive）
- `is_admin`
- `created_at` / `updated_at`

#### `sys_org_group`（组织/组）
- `id` PK
- `group_code` UNIQUE
- `group_name`
- `group_type`（kernel/control/public_cloud/special）
- `parent_group_id` FK -> `sys_org_group.id`（可空）
- `status`
- `created_at` / `updated_at`

#### `sys_role`（角色）
- `id` PK
- `role_code` UNIQUE（PL/member/BU/temp_view/admin）
- `role_name`
- `status`

#### `sys_permission`（权限点）
- `id` PK
- `perm_code` UNIQUE
- `perm_name`
- `resource_type`（menu/api/button/data_scope）

#### `sys_role_permission`（角色-权限）
- `id` PK
- `role_id` FK -> `sys_role.id`
- `permission_id` FK -> `sys_permission.id`
- UNIQUE(`role_id`, `permission_id`)

#### `sys_user_group_role`（用户-组-角色）
- `id` PK
- `user_id` FK -> `sys_user.id`
- `group_id` FK -> `sys_org_group.id`
- `role_id` FK -> `sys_role.id`
- `is_primary_group`
- UNIQUE(`user_id`, `group_id`, `role_id`)

#### `sys_reviewer_whitelist`（审核白名单）
- `id` PK
- `review_type`（leave/dev_audit/close_audit）
- `module_code`（可空，开发审核按模块）
- `reviewer_user_id` FK -> `sys_user.id`
- `status`

---

### 2.2 排班与请假域

#### `duty_calendar`（日历）
- `id` PK
- `calendar_date` UNIQUE
- `day_type`（workday/weekend/holiday）
- `shift_type`（day/night）

#### `duty_schedule`（值班表头）
- `id` PK
- `schedule_code` UNIQUE
- `schedule_name`
- `schedule_type`（kernel/control/public_cloud/special）
- `applicable_day_type`（workday/night/holiday/all）
- `status`

#### `duty_schedule_member`（值班成员）
- `id` PK
- `schedule_id` FK -> `duty_schedule.id`
- `user_id` FK -> `sys_user.id`
- `order_no`（轮询顺序）
- `weight`（可选，权重轮询）
- `status`
- UNIQUE(`schedule_id`, `user_id`)

#### `leave_request`（请假申请）
- `id` PK
- `applicant_user_id` FK -> `sys_user.id`
- `leave_type`
- `start_time` / `end_time`
- `reason`
- `approval_status`（pending/approved/rejected/cancelled）
- `created_at`

#### `leave_approval_record`（请假审批记录）
- `id` PK
- `leave_request_id` FK -> `leave_request.id`
- `reviewer_user_id` FK -> `sys_user.id`
- `action`（approve/reject）
- `comment`
- `action_time`

#### `duty_substitution`（调班/代班）
- `id` PK
- `schedule_id` FK -> `duty_schedule.id`
- `from_user_id` FK -> `sys_user.id`
- `to_user_id` FK -> `sys_user.id`
- `start_time` / `end_time`
- `reason`
- `status`

---

### 2.3 工单与流转域（核心主域）

#### `ticket`（工单主表）
- `id` PK
- `ticket_no` UNIQUE
- `source_type`（HCS/BU/temp/self）
- `current_stage_code`
- `current_assignee_id` FK -> `sys_user.id`
- `creator_user_id` FK -> `sys_user.id`
- `creator_group_id` FK -> `sys_org_group.id`（可空）
- `is_quality_issue`
- `is_consult_issue`
- `issue_type`（kernel/control/other）
- `priority`
- `status`（processing/closed/cancelled）
- `opened_at` / `closed_at`
- `created_at` / `updated_at`

#### `ticket_stage_def`（阶段定义）
- `id` PK
- `stage_code` UNIQUE（submit/review/ops_analysis/dev_analysis/dev_audit/ops_close/review_close）
- `stage_name`
- `stage_order`
- `status`

#### `ticket_transition`（流转记录）
- `id` PK
- `ticket_id` FK -> `ticket.id`
- `from_stage_code`
- `to_stage_code`
- `action_code`（approve/reject/transfer/close/reopen）
- `operator_user_id` FK -> `sys_user.id`
- `from_assignee_id` FK -> `sys_user.id`（可空）
- `to_assignee_id` FK -> `sys_user.id`（可空）
- `comment`
- `created_at`

#### `ticket_assignee_history`（处理人历史）
- `id` PK
- `ticket_id` FK -> `ticket.id`
- `stage_code`
- `assignee_user_id` FK -> `sys_user.id`
- `assign_type`（auto/manual/special/control/designated）
- `assigned_at`

#### `ticket_operation_log`（工单审计日志）
- `id` PK
- `ticket_id` FK -> `ticket.id`
- `operation_type`
- `operator_user_id` FK -> `sys_user.id`
- `before_json`
- `after_json`
- `created_at`

---

### 2.4 分单策略域

#### `dispatch_policy`（策略主表）
- `id` PK
- `policy_code` UNIQUE
- `policy_name`
- `status`
- `effective_from` / `effective_to`
- `version_no`

#### `dispatch_rule`（策略规则）
- `id` PK
- `policy_id` FK -> `dispatch_policy.id`
- `rule_code`
- `priority_no`（数字越小优先级越高）
- `condition_expr`（JSON/表达式）
- `action_type`（assign_schedule/assign_group/fallback_to_creator/...）
- `action_param_json`
- `status`

#### `dispatch_cursor`（轮询游标）
- `id` PK
- `schedule_id` FK -> `duty_schedule.id`
- `biz_scene`（day/kernel/control/special）
- `current_member_id` FK -> `duty_schedule_member.id`
- `updated_at`
- UNIQUE(`schedule_id`, `biz_scene`)

#### `dispatch_decision_log`（分单决策日志）
- `id` PK
- `ticket_id` FK -> `ticket.id`
- `policy_id` FK -> `dispatch_policy.id`
- `hit_rule_id` FK -> `dispatch_rule.id`（可空）
- `decision_path_json`
- `final_assignee_id` FK -> `sys_user.id`
- `fallback_reason`
- `created_at`

#### `dispatch_compensation_record`（转单补偿记录）
- `id` PK
- `ticket_id` FK -> `ticket.id`
- `transfer_type`（control/special/designated）
- `from_user_id` FK -> `sys_user.id`
- `to_user_id` FK -> `sys_user.id`
- `compensation_type`（extra_ticket/update_receive_time/skip_next）
- `status`
- `created_at`

---

### 2.5 动态字段与表单域

#### `form_schema`（表单版本）
- `id` PK
- `schema_code`
- `schema_name`
- `version_no`
- `status`（draft/published/offline）
- `published_at`
- UNIQUE(`schema_code`, `version_no`)

#### `field_definition`（字段定义）
- `id` PK
- `field_code` UNIQUE
- `field_name`
- `field_type`（text/date/rich_text/select/doer_tag）
- `option_set_id` FK -> `field_option_set.id`（可空）
- `validation_json`
- `status`

#### `field_option_set`（选项集）
- `id` PK
- `option_set_code` UNIQUE
- `option_set_name`
- `status`

#### `field_option_item`（选项项）
- `id` PK
- `option_set_id` FK -> `field_option_set.id`
- `option_value`
- `option_label`
- `order_no`
- `status`

#### `stage_field_binding`（阶段字段绑定）
- `id` PK
- `schema_id` FK -> `form_schema.id`
- `stage_code`
- `field_id` FK -> `field_definition.id`
- `is_visible`
- `is_required`
- `is_readonly`
- `display_order`
- UNIQUE(`schema_id`, `stage_code`, `field_id`)

#### `field_rule`（字段联动规则）
- `id` PK
- `schema_id` FK -> `form_schema.id`
- `stage_code`
- `rule_name`
- `condition_expr`
- `action_expr`
- `status`

#### `ticket_field_value`（工单字段值）
- `id` PK
- `ticket_id` FK -> `ticket.id`
- `stage_code`
- `field_code`
- `field_value_text`
- `field_value_json`
- `updated_by` FK -> `sys_user.id`
- `updated_at`
- INDEX(`ticket_id`, `stage_code`)

---

### 2.6 配置中心域

#### `config_namespace`
- `id` PK
- `namespace_code` UNIQUE
- `namespace_name`
- `status`

#### `config_item`
- `id` PK
- `namespace_id` FK -> `config_namespace.id`
- `item_key`
- `item_name`
- `value_type`（string/number/bool/json）
- `status`
- UNIQUE(`namespace_id`, `item_key`)

#### `config_version`
- `id` PK
- `namespace_id` FK -> `config_namespace.id`
- `version_no`
- `status`（draft/published/offline）
- `published_by` FK -> `sys_user.id`（可空）
- `published_at`（可空）

#### `config_value`
- `id` PK
- `version_id` FK -> `config_version.id`
- `config_item_id` FK -> `config_item.id`
- `config_value_json`
- UNIQUE(`version_id`, `config_item_id`)

#### `config_publish_record`
- `id` PK
- `namespace_id` FK -> `config_namespace.id`
- `from_version_id` FK -> `config_version.id`（可空）
- `to_version_id` FK -> `config_version.id`
- `operator_user_id` FK -> `sys_user.id`
- `created_at`

#### `config_audit_log`
- `id` PK
- `namespace_id` FK -> `config_namespace.id`
- `item_key`
- `operator_user_id` FK -> `sys_user.id`
- `before_json`
- `after_json`
- `created_at`

---

### 2.7 统计分析域（可选：先以明细表驱动）

> SQLite 阶段可先不建完整数仓层，仅保留轻量聚合快照表。

#### `ads_ticket_kpi_daily`
- `id` PK
- `stat_date`
- `group_id` FK -> `sys_org_group.id`（可空）
- `user_id` FK -> `sys_user.id`（可空）
- `ticket_count`
- `closed_count`
- `sla_ontime_count`
- `avg_close_minutes`
- UNIQUE(`stat_date`, `group_id`, `user_id`)

#### `ads_stage_funnel_daily`
- `id` PK
- `stat_date`
- `from_stage_code`
- `to_stage_code`
- `transfer_count`
- `transfer_ratio`

---

## 3. 核心关系（ER 文字版）

1. 用户、组织、角色：
- `sys_user` N --- N `sys_org_group`（通过 `sys_user_group_role`）
- `sys_role` N --- N `sys_permission`（通过 `sys_role_permission`）

2. 工单主链路：
- `ticket` 1 --- N `ticket_transition`
- `ticket` 1 --- N `ticket_assignee_history`
- `ticket` 1 --- N `ticket_operation_log`
- `ticket` 1 --- N `ticket_field_value`

3. 分单策略：
- `dispatch_policy` 1 --- N `dispatch_rule`
- `ticket` 1 --- N `dispatch_decision_log`
- `duty_schedule` 1 --- N `duty_schedule_member`
- `duty_schedule` 1 --- 1 `dispatch_cursor`（按 `biz_scene` 唯一）

4. 表单配置：
- `form_schema` 1 --- N `stage_field_binding`
- `field_definition` 1 --- N `stage_field_binding`
- `field_option_set` 1 --- N `field_option_item`

5. 配置中心：
- `config_namespace` 1 --- N `config_item`
- `config_namespace` 1 --- N `config_version`
- `config_version` 1 --- N `config_value`

---

## 4. 索引与唯一约束建议（首批）

- 工单检索：
  - `ticket(ticket_no)` UNIQUE
  - `ticket(current_stage_code, current_assignee_id, status)`
  - `ticket(created_at)`
- 流转检索：
  - `ticket_transition(ticket_id, created_at)`
  - `ticket_transition(to_stage_code, created_at)`
- 分单：
  - `dispatch_decision_log(ticket_id, created_at)`
  - `dispatch_rule(policy_id, priority_no, status)`
- 动态字段：
  - `ticket_field_value(ticket_id, stage_code, field_code)`
- 排班：
  - `duty_calendar(calendar_date)` UNIQUE
  - `duty_schedule_member(schedule_id, order_no)`

---

## 5. Django 落地建议（下一步）

建议按 app 拆分模型：
- `apps/system`：用户、组织、角色、权限
- `apps/duty`：排班、请假、代班
- `apps/ticket`：工单、流转、审计
- `apps/dispatch`：策略、规则、游标、决策日志
- `apps/form`：字段、表单、规则、字段值
- `apps/config_center`：配置域与版本
- `apps/analytics`：统计快照

首批迁移可优先落地：`system + duty + ticket + dispatch`，再接入 `form`。

---

## 6. 待确认项

- 用户是否需要多租户隔离（tenant_id）
- 是否要求软删除（deleted_at）统一规范
- 是否接入外部身份系统（LDAP/OAuth）
- 工单编号规则是否按日期+序列号
- Dashboard 是否需要近实时刷新（分钟级）还是日级离线

---

## 7. Django 模型初稿（已实现）

工程内已按 `apps/*` 拆分并实现对应 `models.py`，并已生成迁移；`AUTH_USER_MODEL` 为 `system.SysUser`（表名 `sys_user`）。

| 域 | 路径 |
|----|------|
| 组织与权限 | `apps/system/models.py` |
| 值班与请假 | `apps/duty/models.py` |
| 工单与流转 | `apps/ticket/models.py` |
| 分单策略 | `apps/dispatch/models.py` |
| 动态表单 | `apps/form/models.py` |
| 配置中心 | `apps/config_center/models.py` |
| 统计快照 | `apps/analytics/models.py` |
