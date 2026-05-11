"""CS Bot 工具自动注册模块。

当 Kitty worker 或其他入口导入 csbot 包时，自动初始化所有 Skill 并注册到 ToolRegistry。
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from csbot.storage.bitable import BitableClient
from csbot.feedback.collector import CSFeedbackCollectorSkill
from csbot.feedback.report import CSBugReportSkill
from csbot.feedback.tracker import CSTicketTrackerSkill
from csbot.feedback.product_feedback import CSProductFeedbackSkill
from csbot.nlp.intake import CSIntakeSkill
from csbot.nlp.emotion import CSEmotionSkill
from csbot.nlp.clarify import CSClarifySkill
from csbot.sops.guardrails import CSGuardrailsSkill
from csbot.sops.output_reviewer import CSOutputReviewerSkill
from csbot.sops.self_check import CSSelfCheckSkill
from csbot.sops.responses import CSResponseTemplatesSkill
from csbot.sops.router import CSSOPRouterSkill
from csbot.sops.self_diagnosis import CSSelfDiagnosisSkill
from csbot.sops.follow_up import CSFollowUpSOP
from csbot.sops.human_handoff import CSHumanHandoffSkill
from csbot.storage.daily import CSDailyReportSkill


_TOOLS_INITIALIZED = False


def init_tools():
    """初始化并注册所有 CS Bot Skill 到 ToolRegistry。"""
    global _TOOLS_INITIALIZED
    if _TOOLS_INITIALIZED:
        return

    bitable = BitableClient()

    # 注册所有 Skills（BaseTool.__init__ 会自动注册到 ToolRegistry）
    CSBugReportSkill()
    CSFeedbackCollectorSkill(bitable=bitable)
    CSTicketTrackerSkill(bitable=bitable)
    CSDailyReportSkill()
    CSIntakeSkill()
    CSEmotionSkill()
    CSClarifySkill()
    CSGuardrailsSkill()
    CSOutputReviewerSkill()
    CSSelfCheckSkill()
    CSResponseTemplatesSkill()
    CSSOPRouterSkill()
    CSSelfDiagnosisSkill()
    CSFollowUpSOP()
    CSHumanHandoffSkill()

    # 产品建议表格（独立配置）
    pf_app_token = os.getenv("PRODUCT_FEEDBACK_APP_TOKEN")
    pf_table_id = os.getenv("PRODUCT_FEEDBACK_TABLE_ID")
    if pf_app_token and pf_table_id:
        CSProductFeedbackSkill(
            bitable=bitable,
            app_token=pf_app_token,
            table_id=pf_table_id,
        )

    _TOOLS_INITIALIZED = True
