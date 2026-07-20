import asyncio
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.issuer_names import extract_issuer_search_query
from app.models import BondScreenerItem
from app.rating_reports import _fetch_acra_report, get_issuer_rating_reports
import httpx
from app.rating_reports import _ssl_verify


async def test_acra_queries() -> None:
    queries = ["ПИК", "ПИК СЗ", "ПИК – специализированный застройщик"]
    async with httpx.AsyncClient(
        timeout=30,
        verify=_ssl_verify(),
        follow_redirects=True,
    ) as client:
        for query in queries:
            report = await _fetch_acra_report(client, query)
            print("ACRA query", query, "->", bool(report))


async def main() -> None:
    await test_acra_queries()
    bonds = [
        BondScreenerItem(
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
            credit_rating="AAA(RU)",
        ),
        BondScreenerItem(
            figi="test-pik",
            ticker="PIK002",
            name='ПАО "ПИК СЗ" БО-001P-02',
            isin="",
            currency="rub",
            sector="real_estate",
            exchange="MOEX",
            nominal=Decimal("1000"),
            nkd=Decimal("0"),
            coupon_per_year=4,
            floating_coupon=False,
            perpetual=False,
            amortization=False,
            buy_available=True,
            for_qual_investor=False,
            subordinated=False,
            is_ofz=False,
            credit_rating="ruB+",
        ),
    ]

    for bond in bonds:
        reports = await get_issuer_rating_reports(bond)
        print("\n===", bond.ticker, reports.issuer_query)
        print("errors:", reports.errors)
        if reports.acra:
            print("ACRA:", reports.acra.title[:120])
            print("  url:", reports.acra.url)
            print("  text:", reports.acra.text[:200], "...")
        else:
            print("ACRA: not found")
        if reports.expert_ra:
            print("Expert:", reports.expert_ra.title[:120])
            print("  url:", reports.expert_ra.url)
            print("  text:", reports.expert_ra.text[:200], "...")
        else:
            print("Expert: not found")


if __name__ == "__main__":
    asyncio.run(main())
