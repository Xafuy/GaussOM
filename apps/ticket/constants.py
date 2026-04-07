"""工单阶段编码（与模块03设计一致）。"""

STAGE_SUBMIT = "submit"
STAGE_REVIEW = "review"
STAGE_OPS_ANALYSIS = "ops_analysis"
STAGE_DEV_ANALYSIS = "dev_analysis"
STAGE_DEV_AUDIT = "dev_audit"
STAGE_OPS_CLOSE = "ops_close"
STAGE_REVIEW_CLOSE = "review_close"

ORDERED_STAGES = [
    STAGE_SUBMIT,
    STAGE_REVIEW,
    STAGE_OPS_ANALYSIS,
    STAGE_DEV_ANALYSIS,
    STAGE_DEV_AUDIT,
    STAGE_OPS_CLOSE,
    STAGE_REVIEW_CLOSE,
]

STAGE_LABELS = {
    STAGE_SUBMIT: "HCS提单",
    STAGE_REVIEW: "问题审核",
    STAGE_OPS_ANALYSIS: "运维人员分析",
    STAGE_DEV_ANALYSIS: "开发人员分析",
    STAGE_DEV_AUDIT: "开发人员审核",
    STAGE_OPS_CLOSE: "运维人员闭环",
    STAGE_REVIEW_CLOSE: "问题审核关闭",
}
