"""
domain.py
「グループ支払い管理・割り勘計算システム」のコアとなるデータモデルと基本ロジックを提供する。
"""

from typing import List, Any
from pydantic import BaseModel, root_validator

# Base
class User(BaseModel):
    id: str
    name: str

    def alike(self, other: "User") -> bool:
        return self.id == other.id


class Asset(BaseModel):
    price: int
    owner: User


class Debt(BaseModel):
    price: int
    debtor: User


class Payment(BaseModel):
    id: str
    price: int
    payer: User
    payees: List[User]

    def debt(self, u: User) -> Debt:
        # 1人当たりの負担額を計算
        divider = len(self.payees)
        per = self.price // divider
        return Debt(price=per, debtor=u)

    def asset(self, u: User) -> Asset:
        # 支払った人には全額を“資産”として返却
        return Asset(price=self.price, owner=u)


class Event(BaseModel):
    id: str
    users: List[User]
    payments: List[Payment]

    def debt_for_user(self, u: User) -> List[Debt]:
        if not any(user.alike(u) for user in self.users):
            raise ValueError("user not found")
        # 誰からいくら払ってもらったかを抽出
        return [p.debt(u) for p in self.payments if any(payee.alike(u) for payee in p.payees)]

    def assets_for_user(self, u: User) -> List[Asset]:
        if not any(user.alike(u) for user in self.users):
            raise ValueError("user not found")
        # 誰にいくらい払ったかを抽出
        return [p.asset(u) for p in self.payments if p.payer.alike(u)]


class Exchange(BaseModel):
    price: int
    payee: User
    payer: User


# Collections
class UserCollection(BaseModel):
    # __root__: このクラス全体がリスト1個だけでできている
    __root__: List[User]

    # 渡ってきたユーザがこのコレクションに含まれているか
    def contains(self, u: User) -> bool:
        return any(user.alike(u) for user in self.__root__)

    # コレクションの人数を取得
    def __len__(self) -> int:
        return len(self.__root__)

    # イテレータとして扱える（for文で回せる）
    def __iter__(self):
        return iter(self.__root__)


class AssetCollection(BaseModel):
    # Asset型だけのリストを持っている（単一リストを扱う特別な方法）
    __root__: List[Asset]

    # コレクションに含まれるすべてのAssetのpriceの合計を取得
    def asset_sum(self) -> int:
        return sum(asset.price for asset in self.__root__)

    def __iter__(self):
        return iter(self.__root__)


class DebtCollection(BaseModel):
    __root__: List[Debt]

    def debt_sum(self) -> int:
        return sum(debt.price for debt in self.__root__)

    def __iter__(self):
        return iter(self.__root__)


# 複数のPayment（支払い）をまとめて管理
class PaymentCollection(BaseModel):
    __root__: List[Payment]

    # 支払いの中でu（与えられたユーザー）が払われた分（負債）を抽出
    def extract_debts(self, u: User) -> DebtCollection:
        debts = [p.debt(u) for p in self.__root__ if any(payee.alike(u) for payee in p.payees)]
        return DebtCollection(__root__=debts)

    # 支払いの中でuが支払った分（資産）を抽出
    def extract_assets(self, u: User) -> AssetCollection:
        assets = [p.asset(u) for p in self.__root__ if p.payer.alike(u)]
        return AssetCollection(__root__=assets)

    def __iter__(self):
        return iter(self.__root__)


class ExchangeCollection(BaseModel):
    __root__: List[Exchange]

    def __iter__(self):
        return iter(self.__root__)


class TmpSummary:
    def __init__(self, user: User, total: int) -> None:
        self.user = user
        self.total = total

    def done(self) -> bool:
        return self.total == 0

    def resolve(self, subject: "TmpSummary") -> Exchange:
        # 両方正負同符号 or どちらかが0の場合は無効
        if self.total * subject.total >= 0:
            raise ValueError("invalid resolve")

        # ① 完全に相殺できる場合
        if self.total + subject.total == 0:
            # 両者を0にして終了
            self.total = 0
            subject.total = 0
            payee = bigger(self, subject).user
            payer = smaller(self, subject).user
            return Exchange(price=self.total, payee=payee, payer=payer)

        # ② self が相殺される場合 (abs(self) < abs(subject))
        if abs(self.total) < abs(subject.total):
            subject.total = self.total + subject.total
            price = abs(self.total)
            self.total = 0
            payee = bigger(self, subject).user
            payer = smaller(self, subject).user
            return Exchange(price=price, payee=payee, payer=payer)

        # ③ subject が相殺される場合 (その他)
        self.total = self.total + subject.total
        price = abs(subject.total)
        subject.total = 0
        payee = bigger(self, subject).user
        payer = smaller(self, subject).user
        return Exchange(price=price, payee=payee, payer=payer)


def bigger(a: TmpSummary, b: TmpSummary) -> TmpSummary:
    return a if a.total >= b.total else b

def smaller(a: TmpSummary, b: TmpSummary) -> TmpSummary:
    return a if a.total <= b.total else b
