"""卡片墙组件：payload 构造纯函数测试。"""
from app_pages import _signal_lab_gallery as g


def test_signal_class_known():
    assert g.signal_class("BUY") == "buy"
    assert g.signal_class("SELL") == "sell"
    assert g.signal_class("IGNORE_BUY") == "ignore"
    assert g.signal_class("NOT_BUY") == "notbuy"
    assert g.signal_class("LONG / BUY") == "long"


def test_signal_class_fallback():
    assert g.signal_class("UNKNOWN_X").startswith("sig-")


def test_build_cards_payload():
    thumbs = {"as:000993:1h|2025-07-27": "<svg>t</svg>"}
    cases = [{"id": "r1", "name": "闽东电力", "date": "2025-07-27",
              "code": "as:000993:1h", "signal": "BUY"}]
    cards = g.build_cards_payload(cases, thumbs)
    assert cards[0]["id"] == "r1"
    assert cards[0]["name"] == "闽东电力"
    assert cards[0]["dateLabel"] == "2025.07.27"
    assert cards[0]["signal"] == "BUY"
    assert cards[0]["thumb"] == "<svg>t</svg>"


def test_build_cards_payload_missing_thumb_uses_placeholder():
    cards = g.build_cards_payload(
        [{"id": "r1", "name": "n", "date": "2025-01-01", "code": "c", "signal": "SELL"}], {}
    )
    assert cards[0]["thumb"].startswith("<svg")
