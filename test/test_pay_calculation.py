from decimal import Decimal

import pytest

from app.api.services.pay_calculation import PayCalculation

# Rule version 2026-01 (R-43): band -> (rate, band width)
TAX_BANDS = {
    "1": (Decimal("7.00"), Decimal("300000.00")),
    "2": (Decimal("11.00"), Decimal("300000.00")),
    "3": (Decimal("15.00"), Decimal("500000.00")),
    "4": (Decimal("19.00"), Decimal("500000.00")),
    "5": (Decimal("21.00"), Decimal("1600000.00")),
    "6": (Decimal("24.00"), Decimal("3200000.00")),
}
RELIEF_BASE = Decimal("200000.00")
RELIEF_RATE = Decimal("20.00")
EMPLOYEE_PENSION_RATE = Decimal("8.00")
EMPLOYER_PENSION_RATE = Decimal("10.00")


@pytest.fixture
def calc() -> PayCalculation:
    return PayCalculation(
        basic=Decimal("300000.00"),
        housing=Decimal("150000.00"),
        transport=Decimal("50000.00"),
        other_allowance=Decimal("100000.00"),
    )


def _full_month_annual_tax(
    calc: PayCalculation, calendar_days: int, bonus: Decimal | None = None
):
    """R-40 to R-43 on unprorated amounts, optionally with a bonus added to AG (R-46)"""
    month_gross = calc.calculate_gross(calendar_days, calendar_days)
    annual_gross = calc.calculate_annual_gross(month_gross, bonus)

    pensionable = calc.calculate_pensionable_pay(calendar_days, calendar_days)
    employee_pension = calc.calculate_pension(pensionable, EMPLOYEE_PENSION_RATE)
    relief = calc.calculate_relief(RELIEF_BASE, RELIEF_RATE, annual_gross)
    annual_taxable = calc.calculate_annual_taxable(
        annual_gross, employee_pension, relief
    )

    return (
        annual_gross,
        relief,
        annual_taxable,
        calc.calculate_annual_tax(TAX_BANDS, annual_taxable),
    )


class TestPayCalculation:
    def test_example_1_full_month(self, calc: PayCalculation):
        """Example 1 — R-10, R-30, R-31, R-40, R-41, R-42, R-43, R-44, R-50"""
        days_paid, calendar_days = 31, 31  # 2026-05

        gross = calc.calculate_gross(days_paid, calendar_days)
        pensionable = calc.calculate_pensionable_pay(days_paid, calendar_days)
        employee_pension = calc.calculate_pension(pensionable, EMPLOYEE_PENSION_RATE)
        employer_pension = calc.calculate_pension(pensionable, EMPLOYER_PENSION_RATE)

        annual_gross, relief, annual_taxable, annual_tax = _full_month_annual_tax(
            calc, calendar_days
        )
        paye = calc.calculate_paye(annual_tax, days_paid, calendar_days)
        net = calc.calculate_net(gross, employee_pension, paye)

        assert gross == Decimal("600000.00")
        assert pensionable == Decimal("500000.00")
        assert employee_pension == Decimal("40000.00")
        assert employer_pension == Decimal("50000.00")
        assert annual_gross == Decimal("7200000.00")
        assert relief == Decimal("1640000.00")
        assert annual_taxable == Decimal("5080000.00")
        assert annual_tax == Decimal("1011200.00")
        assert paye == Decimal("84266.67")
        assert net == Decimal("475733.33")

    def test_example_2_mid_month_joiner(self, calc: PayCalculation):
        """Example 2 — R-20, R-21, R-30, R-31, R-44, R-50"""
        days_paid, calendar_days = 20, 30  # 2026-06, hired 2026-06-11

        gross = calc.calculate_gross(days_paid, calendar_days)
        pensionable = calc.calculate_pensionable_pay(days_paid, calendar_days)
        employee_pension = calc.calculate_pension(pensionable, EMPLOYEE_PENSION_RATE)
        employer_pension = calc.calculate_pension(pensionable, EMPLOYER_PENSION_RATE)

        # PAYE uses the full-month annual tax, prorated once at the end
        *_, annual_tax = _full_month_annual_tax(calc, calendar_days)
        paye = calc.calculate_paye(annual_tax, days_paid, calendar_days)
        net = calc.calculate_net(gross, employee_pension, paye)

        assert gross == Decimal("400000.00")
        assert pensionable == Decimal("333333.33")
        assert employee_pension == Decimal("26666.67")
        assert employer_pension == Decimal("33333.33")
        assert paye == Decimal("56177.78")
        assert net == Decimal("317155.55")

    def test_example_3_one_off_bonus(self, calc: PayCalculation):
        """Example 3 — R-11, R-30, R-41, R-46, R-50"""
        days_paid, calendar_days = 31, 31  # 2026-08
        bonus = Decimal("500000.00")

        gross = calc.calculate_gross(days_paid, calendar_days) + bonus
        pensionable = calc.calculate_pensionable_pay(days_paid, calendar_days)
        employee_pension = calc.calculate_pension(pensionable, EMPLOYEE_PENSION_RATE)

        *_, annual_tax = _full_month_annual_tax(calc, calendar_days)
        (
            annual_gross_with_bonus,
            relief_with_bonus,
            annual_taxable_with_bonus,
            annual_tax_with_bonus,
        ) = _full_month_annual_tax(calc, calendar_days, bonus=bonus)

        bonus_tax = annual_tax_with_bonus - annual_tax
        paye = calc.calculate_paye(annual_tax, days_paid, calendar_days) + bonus_tax
        net = calc.calculate_net(gross, employee_pension, paye)

        assert gross == Decimal("1100000.00")
        assert employee_pension == Decimal("40000.00")
        assert annual_gross_with_bonus == Decimal("7700000.00")
        assert relief_with_bonus == Decimal("1740000.00")
        assert annual_taxable_with_bonus == Decimal("5480000.00")
        assert bonus_tax == Decimal("96000.00")
        assert paye == Decimal("180266.67")
        assert net == Decimal("879733.33")

    def test_example_4_prorated_segment(self, calc: PayCalculation):
        """Example 3 — R-11, R-30, R-41, R-46, R-50"""
        days_paid_s_1, days_paid_s_2, calendar_days = 15, 16, 31

        gross_s_1 = calc.calculate_gross(days_paid_s_1, calendar_days)
        pensionable_s_1 = calc.calculate_pensionable_pay(days_paid_s_1, calendar_days)
        annual_gross_s_1, relief_s_1, annual_taxable_s_1, annual_tax_s_1 = (
            _full_month_annual_tax(calc, calendar_days)
        )

        calc.basic = Decimal("360000.00")

        gross_s_2 = calc.calculate_gross(days_paid_s_2, calendar_days)
        pensionable_s_2 = calc.calculate_pensionable_pay(days_paid_s_2, calendar_days)
        annual_gross_s_2, relief_s_2, annual_taxable_s_2, annual_tax_s_2 = (
            _full_month_annual_tax(calc, calendar_days)
        )

        employee_pension = calc.calculate_pension(
            pensionable_s_1 + pensionable_s_2, EMPLOYEE_PENSION_RATE
        )
        employer_pension = calc.calculate_pension(
            pensionable_s_1 + pensionable_s_2, EMPLOYER_PENSION_RATE
        )

        paye_s_1 = calc.calculate_paye(annual_tax_s_1, days_paid_s_1, calendar_days)
        paye_s_2 = calc.calculate_paye(annual_tax_s_2, days_paid_s_2, calendar_days)

        paye = paye_s_1 + paye_s_2

        net = calc.calculate_net(gross_s_1 + gross_s_2, employee_pension, paye)

        assert gross_s_1 == Decimal("290322.59")
        assert gross_s_2 == Decimal("340645.15")
        assert employee_pension == Decimal("42477.42")
        assert employer_pension == Decimal("53096.77")
        assert annual_gross_s_1 == Decimal("7200000.00")
        assert annual_gross_s_2 == Decimal("7920000.00")
        assert relief_s_1 == Decimal("1640000.00")
        assert relief_s_2 == Decimal("1784000.00")
        assert annual_taxable_s_1 == Decimal("5080000.00")
        assert annual_taxable_s_2 == Decimal("5598400.00")
        assert annual_tax_s_1 == Decimal("1011200.00")
        assert annual_tax_s_2 == Decimal("1135616.00")
        assert paye == Decimal("89617.89")
        assert net == Decimal("498872.43")
