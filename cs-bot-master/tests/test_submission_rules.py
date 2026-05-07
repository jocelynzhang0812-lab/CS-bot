"""测试入表规则配置加载与新场景（转人工、回答错误）"""
import asyncio
import sys
sys.path.insert(0, ".")

from csbot.config.loader import (
    get_config,
    get_intent_keywords,
    get_submission_rules,
    get_router_actions,
    should_submit,
)
from csbot.nlp.intake import CSIntakeSkill
from csbot.sops.router import CSSOPRouterSkill
from csbot.feedback.report import CSBugReportSkill
from csbot.sops.responses import CSResponseTemplatesSkill


def test_config_load():
    """测试配置能被正确加载"""
    cfg = get_config()
    assert "submission_rules" in cfg
    assert "intent_keywords" in cfg
    assert "router_actions" in cfg
    print("✅ 配置加载成功")


def test_intent_keywords_from_config():
    """测试意图关键词从配置读取"""
    kw = get_intent_keywords()
    assert "human_request" in kw
    assert "wrong_answer" in kw
    assert "转人工" in kw["human_request"]
    assert "回答错误" in kw["wrong_answer"]
    print("✅ 意图关键词配置正确")


def test_submission_rules():
    """测试入表规则判断"""
    # tech_bug + 信息完整 → 入表
    r1 = should_submit("tech_bug", collected_complete=True)
    assert r1["should_submit"] is True
    assert r1["issue_type"] == "bug"
    print("✅ tech_bug 完整 → 入表")

    # tech_bug + 信息不完整 → 不入表（继续收集）
    r2 = should_submit("tech_bug", collected_complete=False)
    assert r2["should_submit"] is False
    print("✅ tech_bug 不完整 → 不入表")

    # human_request → 入表 + 转人工
    r3 = should_submit("human_request")
    assert r3["should_submit"] is True
    assert r3["issue_type"] == "human_request"
    assert r3["human_handoff"] is True
    print("✅ human_request → 入表 + 转人工")

    # wrong_answer → 入表
    r4 = should_submit("wrong_answer")
    assert r4["should_submit"] is True
    assert r4["issue_type"] == "wrong_answer"
    assert r4["human_handoff"] is False
    print("✅ wrong_answer → 入表")

    # special_request → 不入表
    r5 = should_submit("tech_bug", is_special=True)
    assert r5["should_submit"] is False
    print("✅ special_request → 不入表")

    # kb_hit → 不入表
    r6 = should_submit("faq", kb_hit=True)
    assert r6["should_submit"] is False
    print("✅ kb_hit → 不入表")


async def test_intake_human_request():
    """测试 intake 识别转人工意图"""
    skill = CSIntakeSkill()
    result = await skill.execute("我要转人工", mentioned=True)
    assert result.result["intent"] == "human_request"
    assert result.result["is_human_request"] is True
    print("✅ '我要转人工' → human_request 意图")

    result2 = await skill.execute("找人工客服", mentioned=True)
    assert result2.result["intent"] == "human_request"
    print("✅ '找人工客服' → human_request 意图")


async def test_intake_wrong_answer():
    """测试 intake 识别回答错误意图"""
    skill = CSIntakeSkill()
    result = await skill.execute("你说错了", mentioned=True)
    assert result.result["intent"] == "wrong_answer"
    assert result.result["is_wrong_answer"] is True
    print("✅ '你说错了' → wrong_answer 意图")

    result2 = await skill.execute("回答不对，答非所问", mentioned=True)
    assert result2.result["intent"] == "wrong_answer"
    print("✅ '回答不对，答非所问' → wrong_answer 意图")


async def test_router_new_intents():
    """测试 router 对新意图的路由"""
    skill = CSSOPRouterSkill()

    r1 = await skill.execute(intent="human_request")
    assert r1.result["next_step"] == "human_handoff_with_table"
    assert r1.result["should_submit"] is True
    print("✅ human_request → human_handoff_with_table")

    r2 = await skill.execute(intent="wrong_answer")
    assert r2.result["next_step"] == "wrong_answer_table"
    assert r2.result["should_submit"] is True
    print("✅ wrong_answer → wrong_answer_table")

    r3 = await skill.execute(intent="special_request", is_special=True)
    assert r3.result["next_step"] == "human_handoff"
    assert r3.result["should_submit"] is False
    print("✅ special_request → human_handoff（不入表）")


async def test_bug_report_issue_type():
    """测试 bug report 支持不同 issue_type"""
    skill = CSBugReportSkill()
    collected = {"product_type": "desktop", "issue_desc": "测试"}

    r1 = await skill.execute(collected, issue_type="bug")
    assert "新 Bug 上报" in r1.result["card_markdown"]
    print("✅ issue_type=bug → 新 Bug 上报")

    r2 = await skill.execute(collected, issue_type="human_request")
    assert "用户要求转人工" in r2.result["card_markdown"]
    assert r2.result["issue_type"] == "human_request"
    print("✅ issue_type=human_request → 用户要求转人工")

    r3 = await skill.execute(collected, issue_type="wrong_answer")
    assert "用户反馈回答错误" in r3.result["card_markdown"]
    assert r3.result["issue_type"] == "wrong_answer"
    print("✅ issue_type=wrong_answer → 用户反馈回答错误")


async def test_response_templates():
    """测试话术模板包含新场景"""
    skill = CSResponseTemplatesSkill()
    r1 = await skill.execute("human_request_submitted")
    assert "转接人工" in r1.result["reply"]
    print("✅ human_request_submitted 话术存在")

    r2 = await skill.execute("wrong_answer_submitted")
    assert "复盘" in r2.result["reply"]
    print("✅ wrong_answer_submitted 话术存在")


async def main():
    test_config_load()
    test_intent_keywords_from_config()
    test_submission_rules()
    await test_intake_human_request()
    await test_intake_wrong_answer()
    await test_router_new_intents()
    await test_bug_report_issue_type()
    await test_response_templates()
    print("\n🎉 入表规则配置与新场景测试全部通过！")


if __name__ == "__main__":
    asyncio.run(main())
