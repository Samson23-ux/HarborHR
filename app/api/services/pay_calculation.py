from decimal import Decimal

from app.core.config import get_settings

SETTINGS = get_settings()


class PayCalculation:
    def __init__(
        self,
        basic: Decimal,
        housing: Decimal,
        transport: Decimal,
        other_allowance: Decimal,
    ):
        self.basic = basic
        self.housing = housing
        self.transport = transport
        self.other_allowance = other_allowance

    def _prorate(self, days_paid: int, calendar_days: int):
        pay_days = Decimal(str(days_paid / calendar_days))

        return {
            "basic": (self.basic * pay_days).quantize(
                Decimal(SETTINGS.ROUNDING_PLACES), rounding=SETTINGS.ROUNDING
            ),
            "housing": (self.housing * pay_days).quantize(
                Decimal(SETTINGS.ROUNDING_PLACES), rounding=SETTINGS.ROUNDING
            ),
            "transport": (self.transport * pay_days).quantize(
                Decimal(SETTINGS.ROUNDING_PLACES), rounding=SETTINGS.ROUNDING
            ),
            "other_allowance": (
                self.other_allowance * pay_days
            ).quantize(Decimal(SETTINGS.ROUNDING_PLACES), rounding=SETTINGS.ROUNDING),
        }

    def calculate_gross(
        self,
        days_paid: int,
        calendar_days: int,
        bonus: Decimal | None = None
    ) -> Decimal:
        prorated_pay: dict = self._prorate(days_paid, calendar_days)

        gross: Decimal = (
            prorated_pay["basic"]
            + prorated_pay["housing"]
            + prorated_pay["transport"]
            + prorated_pay["other_allowance"]
        )

        if bonus:
            gross += bonus

        return gross.quantize(
            Decimal(SETTINGS.ROUNDING_PLACES), rounding=SETTINGS.ROUNDING
        )

    def calculate_pensionable_pay(
        self,
        days_paid: int,
        calendar_days: int,
    ) -> Decimal:
        prorated_pay: dict = self._prorate(days_paid, calendar_days)

        pensionable: Decimal = (
            prorated_pay["basic"] + prorated_pay["housing"] + prorated_pay["transport"]
        )
        return pensionable.quantize(
            Decimal(SETTINGS.ROUNDING_PLACES), rounding=SETTINGS.ROUNDING
        )

    def calculate_pension(
        self, pensionable_pay: Decimal, pension_rate: Decimal
    ) -> Decimal:
        pension: Decimal = (pension_rate / 100) * pensionable_pay
        return pension.quantize(
            Decimal(SETTINGS.ROUNDING_PLACES), rounding=SETTINGS.ROUNDING
        )

    def calculate_annual_gross(
        self, month_gross: Decimal, bonus: Decimal | None = None
    ) -> Decimal:
        annual_gross: Decimal = month_gross * 12

        if bonus:
            annual_gross += bonus

        return annual_gross.quantize(
            Decimal(SETTINGS.ROUNDING_PLACES), rounding=SETTINGS.ROUNDING
        )

    def calculate_relief(
        self, base: Decimal, rate: Decimal, annual_gross: Decimal
    ) -> Decimal:
        relief: Decimal = ((rate / 100) * annual_gross) + base
        return relief.quantize(
            Decimal(SETTINGS.ROUNDING_PLACES), rounding=SETTINGS.ROUNDING
        )

    def calculate_annual_taxable(
        self,
        annual_gross: Decimal,
        employee_pension: Decimal,
        relief: Decimal,
    ) -> Decimal:
        taxable: Decimal = max(annual_gross - (employee_pension * 12) - relief, 0)
        return taxable.quantize(
            Decimal(SETTINGS.ROUNDING_PLACES), rounding=SETTINGS.ROUNDING
        )

    def calculate_annual_tax(self, tax_bands: dict, annual_taxable: Decimal):
        tax: Decimal = Decimal("0.00")

        for rate, value in tax_bands.values():
            if (annual_taxable - value) < Decimal("0.00"):
                tax += (rate / 100) * annual_taxable
                break

            tax += (rate / 100) * value
            annual_taxable -= value

        return tax.quantize(
            Decimal(SETTINGS.ROUNDING_PLACES), rounding=SETTINGS.ROUNDING
        )

    def calculate_paye(self, annual_tax: Decimal, days_paid: int, calendar_days: int):
        paye: Decimal = (annual_tax * days_paid) / (12 * calendar_days)
        return paye.quantize(
            Decimal(SETTINGS.ROUNDING_PLACES), rounding=SETTINGS.ROUNDING
        )

    def calculate_net(
        self,
        gross: Decimal,
        employee_pension: Decimal,
        paye: Decimal,
        reimbursement: Decimal | None = None,
        other_deduction: Decimal | None = None,
    ):
        net: Decimal = gross - employee_pension - paye

        if other_deduction:
            net -= other_deduction

        if reimbursement:
            net += reimbursement

        return net.quantize(
            Decimal(SETTINGS.ROUNDING_PLACES), rounding=SETTINGS.ROUNDING
        )
