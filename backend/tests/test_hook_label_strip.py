"""
Weak models (e.g. Peach-9B) echo the Hook System's internal labels
("SECRET TEASE:", "MEMORY CALLBACK:", ...) into the visible reply, which breaks
immersion and makes the chat feel incoherent. strip_hook_labels removes any
leaked label so the user never sees scaffolding text.
"""
from services.chat_service import strip_hook_labels


def test_strips_leading_label():
    out = strip_hook_labels("SECRET TEASE:上一个让我动心的人，有点像你")
    assert "SECRET TEASE" not in out
    assert "上一个让我动心的人" in out


def test_strips_label_mid_text_and_markdown():
    out = strip_hook_labels("好呀～*Secret Tease:* 主人知道吗？")
    assert "Secret Tease" not in out.lower() or "secret tease" not in out.lower()
    assert "主人知道吗" in out


def test_strips_all_known_labels_case_insensitive():
    for lbl in ["CLIFFHANGER", "QUESTION", "MEMORY CALLBACK",
                "EMOTIONAL CRACK", "PROGRESS HINT", "INTERRUPTED CONFESSION"]:
        out = strip_hook_labels(f"{lbl}：这是一句正文")
        assert lbl not in out
        assert "这是一句正文" in out


def test_strips_generic_hook_and_chinese_label():
    # peach-9B also leaks the bare "Hook:" / "钩子:" scaffolding
    assert "Hook" not in strip_hook_labels("Hook:你更喜欢我穿什么颜色的内衣？")
    assert "钩子" not in strip_hook_labels("*钩子: 要不要再往上掀一点？*")
    assert "你更喜欢我穿什么颜色" in strip_hook_labels("Hook:你更喜欢我穿什么颜色的内衣？")


def test_preserves_normal_reply():
    s = "我想你了，今天过得怎么样？*轻轻靠近你*"
    assert strip_hook_labels(s) == s
