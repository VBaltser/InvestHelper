import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rating_reports import get_issuer_rating_reports
from app.models import BondScreenerItem
from decimal import Decimal


async def main() -> None:
    bond = BondScreenerItem(
        figi="test-sber",
        ticker="SBER23",
        name='ПАО "Сбербанк" БО-001P-01',
        isin="",
        currency="rub",
        sector="financial",
        exchange="MOEX",
        nominal=Decimal("1000"),
        nkd=Decimal("0"),
        coupon_per_year=2,
        floating_coupon=False,
        perpetual=False,
        amortization=False,
        buy_available=True,
        for_qual_investor=False,
        subordinated=False,
        is_ofz=False,
    )
    reports = await get_issuer_rating_reports(bond)
    if reports.expert_ra:
        print("Expert title:", reports.expert_ra.title)
        print("Expert url:", reports.expert_ra.url)
        print("Expert text start:", reports.expert_ra.text[:500])


if __name__ == "__main__":
    asyncio.run(main())
