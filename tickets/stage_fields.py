"""
各阶段表单字段定义，与 design/需求文档.md / 问题单流程字段以及选项.txt 对齐。
widget: text | textarea | select | date | user_select
"""

from .models import TicketStage


def _row(
    key,
    label,
    widget="text",
    required=False,
    options=None,
    show_when=None,
    required_when=None,
):
    return {
        "key": key,
        "label": label,
        "widget": widget,
        "required": required,
        "options": options or [],
        "show_when": show_when or {},
        "required_when": required_when or {},
    }


STAGE_FIELD_DEFS = {
    TicketStage.HCS_SUBMIT: [
        _row("start_date", "起始日期", required=True),
        _row("site", "局点", required=True),
        _row(
            "business_env",
            "业务环境",
            required=True,
            widget="select",
            options=[
                "生产环境（巡检）",
                "生产环境（运维）",
                "生产环境（影响业务）",
                "已投产业务测试环境",
                "交付阶段",
                "POC阶段",
            ],
        ),
        _row(
            "severity",
            "问题严重性",
            required=True,
            widget="select",
            options=["一般", "严重", "致命", "事故"],
        ),
        _row(
            "problem_component",
            "问题组件",
            required=True,
            widget="select",
            options=["内核问题", "管控问题"],
        ),
        _row("hcs_version", "HCS版本号"),
        _row("hcs_or_light", "HCS/轻量化", widget="select", options=["HCS", "轻量化"]),
        _row("ecare_no", "eCare单号"),
        _row("hcs_owner", "HCS负责人"),
        _row("issue_description", "问题描述", "textarea", required=True),
        _row(
            "disposition",
            "处理方式",
            required=True,
            widget="select",
            options=[],
        ),
    ],
    TicketStage.ISSUE_REVIEW: [
        _row(
            "disposition",
            "处理方式",
            required=True,
            widget="select",
            options=[],
        ),
        _row("close_reason", "返回原因/关闭原因", "textarea"),
        _row("issue_type_prejudge", "问题类型初步判断", required=True),
    ],
    TicketStage.OPS_ANALYSIS: [
        _row("disposition", "处理方式", required=True, widget="select", options=[]),
        _row("introduced_module", "问题引入模块", required=True),
        _row("start_date", "起始日期"),
        _row("severity", "问题严重性"),
        _row("site", "局点"),
        _row("owned_module", "问题归属模块", required=True, widget="module_cascade"),
        _row("is_quality_issue", "是否质量问题", required=True, widget="select", options=["是", "否"]),
        _row("issue_type", "问题类型", required=True),
        _row("product_line", "产品线"),
        _row("root_cause_category", "根因分类"),
        _row("dts_no", "DTS单号"),
        _row(
            "business_env",
            "业务环境",
            widget="select",
            options=[
                "生产环境（巡检）",
                "生产环境（运维）",
                "生产环境（影响业务）",
                "已投产业务测试环境",
                "交付阶段",
                "POC阶段",
            ],
        ),
        _row("event_level", "事件级别"),
        _row("instance_short_name", "实例简称"),
        _row("problem_component", "问题组件"),
        _row("customer_voice", "客户声音"),
        _row("business_name", "业务名称"),
        _row("gauss_version", "高斯版本"),
        _row("deployment_form", "部署形态", widget="select", options=["集中式", "分布式", "小型化"]),
        _row("kernel_upgrade_involved", "是否涉及内核升级", widget="select", options=["是", "否"]),
        _row("kernel_upgrade_time", "内核升级时间"),
        _row("baseline_before_upgrade", "升级前基线版本"),
        _row("control_version", "管控版本"),
        _row("upgrade_status", "升级状态", widget="select", options=["升级观察期", "升级已提交"]),
        _row("issue_description", "问题描述", "textarea"),
        _row("error_message", "报错信息", "textarea"),
        _row("log_investigation", "日志排查情况", "textarea"),
        _row("progress_tracking", "问题进展跟踪", "textarea", required=True),
        _row("has_coredump", "是否有coredump文件"),
        _row("has_core_stack", "是否有core堆栈"),
        _row("core_stack_text", "core堆栈（文字版）", "textarea"),
    ],
    TicketStage.DEV_ANALYSIS: [
        _row("disposition", "处理方式", required=True, widget="select", options=[]),
        _row("introduced_module", "问题引入模块", required=True),
        _row("is_frontend_pass", "是否前端透传", widget="select", options=["是", "否"]),
        _row("owned_module", "问题归属模块", required=True, widget="module_cascade"),
        _row("pass_to_version", "是否透传至版本", widget="select", options=["是", "否"]),
        _row("feature", "特性"),
        _row("dts_no", "DTS单号"),
        _row(
            "version_pass_reason",
            "版本透传原因分析",
            "textarea",
            show_when={"pass_to_version": ["是"]},
        ),
        _row("is_quality_issue", "是否质量问题", required=True, widget="select", options=["是", "否"]),
        _row("is_consultation", "是否咨询问题", widget="select", options=["是", "否"]),
        _row("co_handlers", "协同处理人", widget="user_multi_select"),
        _row("punshi_involved", "磐石版本是否涉及"),
        _row("workaround", "规避措施", "textarea"),
        _row("recovery_method", "恢复方法", "textarea"),
        _row("root_cause", "问题根因", "textarea", required=True),
        _row("progress_tracking", "问题进展跟踪", "textarea", required=True),
        _row("dfx_gap", "DFX能力GAP", "textarea"),
        _row(
            "error_archive",
            "报错信息归档（core、报错、内存堆积上下文文字版）",
            "textarea",
        ),
    ],
    TicketStage.DEV_REVIEW: [
        _row("disposition", "处理方式", required=True, widget="select", options=[]),
        _row("need_alert", "是否需要预警", required=True, widget="select", options=["是", "否"]),
        _row("business_impact", "业务影响程度", required=True),
        _row("sla_analysis", "SLA分析", "textarea"),
        _row("dfx_gap", "DFX能力GAP", "textarea"),
    ],
    TicketStage.OPS_CLOSURE: [
        _row("disposition", "处理方式", required=True, widget="select", options=[]),
        _row("involves_fault_recovery", "是否涉及故障恢复", required=True, widget="select", options=["是", "否"]),
        _row("recovery_duration", "故障到恢复用时"),
        _row("feature", "特性"),
        _row("punshi_involved", "磐石版本是否涉及"),
        _row("is_consultation", "是否咨询问题", widget="select", options=["是", "否"]),
        _row("use_doer_assist", "是否使用Doer辅助", widget="select", options=["是", "否"]),
        _row("co_handlers", "协同处理人", widget="user_multi_select"),
        _row("workaround", "规避措施", "textarea"),
        _row("recovery_method", "恢复方法", "textarea"),
        _row("root_cause", "问题根因", "textarea", required=True),
        _row("external_reply", "对外答复", "textarea", required=True),
        _row(
            "frontend_pass_reason",
            "前端透传原因分析",
            "textarea",
            show_when={"is_frontend_pass": ["是"]},
        ),
        _row("dfx_gap", "DFX能力GAP", "textarea"),
        _row(
            "error_archive",
            "报错信息归档（core、报错、内存堆积上下文文字版）",
            "textarea",
            show_when={"root_cause_category": ["contains:core", "contains:崩溃", "contains:内存"]},
            required_when={"root_cause_category": ["contains:core", "contains:崩溃", "contains:内存"]},
        ),
        _row("issue_report_upload", "上传问题报告"),
    ],
    TicketStage.AUDIT_CLOSE: [
        _row("disposition", "处理方式", required=True, widget="select", options=[]),
        _row("need_alert", "是否需要预警", required=True, widget="select", options=["是", "否"]),
        _row("business_impact", "业务影响程度", required=True),
        _row("dfx_gap", "DFX能力GAP", "textarea"),
    ],
}


def get_field_defs_for_stage(stage, context=None):
    defs = [dict(i) for i in STAGE_FIELD_DEFS.get(stage, [])]
    context = context or {}
    date_keys = {"start_date", "kernel_upgrade_time"}
    user_keys = {"co_handlers", "hcs_owner"}

    disposition_options_map = {
        TicketStage.HCS_SUBMIT: [
            "提交至问题审核",
            "进入运维人员分析（运维自提单，值班系统分单）",
        ],
        TicketStage.ISSUE_REVIEW: ["打回HCS提单", "进入运维人员分析（值班系统分单）"],
        TicketStage.OPS_ANALYSIS: [
            "分配其他运维人员（同阶段）",
            "指定开发人员分析",
            "指定开发人员闭环",
            "进入运维人员闭环",
        ],
        TicketStage.DEV_ANALYSIS: ["分配其他开发人员（同阶段）", "进入开发人员闭环"],
        TicketStage.DEV_REVIEW: ["进入运维人员闭环"],
        TicketStage.OPS_CLOSURE: ["进入问题审核关闭"],
        TicketStage.AUDIT_CLOSE: ["问题解决关闭", "返回运维人员闭环"],
    }
    if stage in disposition_options_map:
        for fd in defs:
            if fd["key"] == "disposition":
                fd["options"] = disposition_options_map[stage]
                break
    for fd in defs:
        if fd["key"] in date_keys and fd.get("widget") == "text":
            fd["widget"] = "date"
        if fd["key"] in user_keys and fd.get("widget") == "text":
            fd["widget"] = "user_select"
    return defs


def get_module_tree():
    from .models import ModuleArea

    rows = []
    areas = ModuleArea.objects.filter(is_active=True).prefetch_related("sub_areas")
    for area in areas:
        children = [
            {"name": sa.name}
            for sa in area.sub_areas.all()
            if getattr(sa, "is_active", True)
        ]
        if not children:
            continue
        rows.append({"name": area.name, "children": children})
    return rows
