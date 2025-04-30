import pytest
from schemas.domain import TmpSummary
from schemas.domain import User

@pytest.mark.parametrize("total_a, total_b, expect_a, expect_b,", [
    (1000, -300, 700, 0),    # A=1000, B=-300 → A=700, B=0
    (300, -1000, 0, -700),   # A=300, B=-1000 → A=0, B=-700
    (-1000, 300, -700, 0),   # A=-1000, B=300 → A=-700, B=0
    (-300, 1000, 0, 700),    # A=-300, B=1000 → A=0, B=700
    (1000, -1000, 0, 0),     # 完全相殺 → 両方 0
])
def test_resolve_updates_totals(total_a, total_b, expect_a, expect_b):
    userA = User(id="A", name="A")
    userB = User(id="B", name="B")

    # +: 受け取る -:支払う 
    summaryA = TmpSummary(userA, total_a)    # A: 誰かから「1000」を受け取る
    summaryB = TmpSummary(userB, total_b)   # B: 誰かに「1000」を支払う

    ex = summaryA.resolve(summaryB)

    # assert 条件, メッセージ
    assert summaryA.total == expect_a, f"A: expected {expect_a}, got {summaryA.total}"
    assert summaryB.total == expect_b, f"B: expected {expect_b}, got {summaryB.total}"

@pytest.mark.parametrize("t1, t2", [
    (0,  100),
    (50, 0),
    (10, 20),   # 同符号(+) は invalid
    (-5, -7),   # 同符号(-) は invalid
])

def test_resolve_invalid_raises(t1, t2):
    """両者の積 >= 0 のとき、ValueError を出力"""
    u1 = User(id="X", name="X")
    u2 = User(id="Y", name="Y")
    s1 = TmpSummary(user=u1, total=t1)
    s2 = TmpSummary(user=u2, total=t2)

    with pytest.raises(ValueError):
        s1.resolve(s2)