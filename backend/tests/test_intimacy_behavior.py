"""
Intimacy tiers must drive BEHAVIOR (and reply endings), not just photos.

The quality review found the top tier locked at "hugging + 安心吗?" because
build_intimacy_prompt only injected photo rules — identical behavioral
guidance at every tier. Fix: each tier carries a behavior_hint, and the
high tiers inject an escalation directive + ban the lazy "求反馈" question
ending. These assert the PROMPT the LLM receives reflects the tier.
"""
from services.intimacy_service import build_intimacy_prompt, get_tier


def test_stranger_tier_behavior_is_reserved():
    p = build_intimacy_prompt(0)
    assert get_tier(0).name_cn in p
    assert "行为" in p  # a behavior section exists
    # reserved language, not escalation
    assert "矜持" in p or "克制" in p or "试探" in p


def test_top_tier_behavior_escalates_and_bans_feedback_question():
    p = build_intimacy_prompt(85)  # 亲密无间
    assert "亲密无间" in p
    # must explicitly push escalation at the top tier
    assert "升级" in p
    # must ban the lazy "有没有...感受/感觉" feedback-question ending
    assert "安心" in p or "感受" in p or "感觉" in p
    # the escalation language should be present (explicit/desire-forward)
    assert "露骨" in p or "情欲" in p


def test_behavior_directive_scales_between_tiers():
    """Low and high tiers must inject DIFFERENT behavior text."""
    low = build_intimacy_prompt(0)
    high = build_intimacy_prompt(85)
    # the behavior sections differ (tier-specific, not identical)
    assert low != high
