"""
domain.py
「グループ支払い管理・割り勘計算システム」のコアとなるデータモデルと基本ロジックを提供する。
"""

from typing import List, Any
from pydantic import BaseModel, root_validator
import math

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

    def payment_summaries(self) -> 'PaymentSummaryCollection':
        # 各ユーザーの資産・負債を集計し、PaymentSummaryCollectionを返す
        summaries: List[PaymentSummary] = []
        for u in self.users:
            assets = [p.asset(u) for p in self.payments if p.payer.alike(u)]
            debts = [p.debt(u) for p in self.payments if any(payee.alike(u) for payee in p.payees)]
            summaries.append(
                PaymentSummary(
                    user=u,
                    assets=AssetCollection(__root__=assets),
                    debts=DebtCollection(__root__=debts)
                )
            )
        return PaymentSummaryCollection(__root__=summaries)


class Exchange(BaseModel):
    price: int
    payee: User
    payer: User


# Collections
class UserCollection(BaseModel):
    __root__: List[User]

    def contains(self, u: User) -> bool:
        return any(user.alike(u) for user in self.__root__)

    def __len__(self) -> int:
        return len(self.__root__)

    def __iter__(self):
        return iter(self.__root__)


class AssetCollection(BaseModel):
    __root__: List[Asset]

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


class PaymentCollection(BaseModel):
    __root__: List[Payment]

    def extract_debts(self, u: User) -> DebtCollection:
        debts = [p.debt(u) for p in self.__root__ if any(payee.alike(u) for payee in p.payees)]
        return DebtCollection(__root__=debts)

    def extract_assets(self, u: User) -> AssetCollection:
        assets = [p.asset(u) for p in self.__root__ if p.payer.alike(u)]
        return AssetCollection(__root__=assets)

    def __iter__(self):
        return iter(self.__root__)


class ExchangeCollection(BaseModel):
    __root__: List[Exchange]

    def __iter__(self):
        return iter(self.__root__)


# 2人の間の一時的な集計
class TmpSummary:
    def __init__(self, user: User, total: int) -> None:
        self.user = user
        self.total = total

    def done(self) -> bool:
        return self.total == 0

    def resolve(self, subject: 'TmpSummary') -> Exchange:
        # 両方正負同符号 or どちらかが0の場合は無効
        if self.total * subject.total >= 0:
            raise ValueError('invalid resolve')

        # 1. 完全に相殺できる場合
        if self.total + subject.total == 0:
            price = abs(self.total)
            self.total = 0
            subject.total = 0
            payee = bigger(self, subject).user
            payer = smaller(self, subject).user
            return Exchange(price=price, payee=payee, payer=payer)

        # 2. self が相殺される場合 (abs(self) < abs(subject))
        if abs(self.total) < abs(subject.total):
            price = abs(self.total)
            subject.total = self.total + subject.total
            self.total = 0
            payee = bigger(self, subject).user
            payer = smaller(self, subject).user
            return Exchange(price=price, payee=payee, payer=payer)

        # 3. subject が相殺される場合 (その他)
        price = abs(subject.total)
        self.total = self.total + subject.total
        subject.total = 0
        payee = bigger(self, subject).user
        payer = smaller(self, subject).user
        return Exchange(price=price, payee=payee, payer=payer)


def bigger(a: TmpSummary, b: TmpSummary) -> TmpSummary:
    return a if a.total >= b.total else b

def smaller(a: TmpSummary, b: TmpSummary) -> TmpSummary:
    return a if a.total <= b.total else b


class PaymentSummary(BaseModel):
    user: User
    assets: AssetCollection
    debts: DebtCollection

    def total(self) -> int:
        return self.assets.asset_sum() - self.debts.debt_sum()

    def total_abs(self) -> int:
        return abs(self.total())

    def tmp_summary(self) -> TmpSummary:
        return TmpSummary(user=self.user, total=self.total())


class PaymentSummaryCollection(BaseModel):
    __root__: List[PaymentSummary]
    
    # ex:
    # summaries = PaymentSummaryCollection(__root__=[
    # PaymentSummary(user=A, paid=2000, share=1000),
    # PaymentSummary(user=B, paid= 500, share=1000),
    # PaymentSummary(user=C, paid= 500, share=1000),
    # ])
    
    def __iter__(self):
        return iter(self.__root__)

    def exchnange(self) -> ExchangeCollection:
        # 各ユーザーの一時的な集計を取得
        tmps = [ps.tmp_summary() for ps in self.__root__]
        exchanges = []
        while True:
            unsettled = [t for t in tmps if not t.done()]
            if len(unsettled) < 2:
                break
            pos = next((t for t in unsettled if t.total > 0), None)
            neg = next((t for t in unsettled if t.total < 0), None)
            if pos is None or neg is None:
                break
            exchanges.append(pos.resolve(neg))
        return ExchangeCollection(__root__=exchanges)