import pandas as pd

from datetime import date
from dateutil import parser
from dateutil.relativedelta import relativedelta

from model import (
    Account,
    Asset,
    Tranche,
    EquityTranche,
    Fee,
    CLO,
    WaterfallItem,
    CashflowWaterfall,
    Portfolio
)


class CLOFactory:
    """
    Model factory for building CLOs. We assume that provided data is already clean.
    """

    def __init__(
            self,
            deal_data: pd.DataFrame,
            tranche_data: pd.DataFrame,
            collateral_data: pd.DataFrame,
            cpr: float,
            cdr: float,
            recovery_rate: float,
            payment_frequency: int,
            simulation_interval: int,
            senior_management_fee: float,
            junior_management_fee: float,
            non_call_end_date: date,
            reinvestment_maturity_months: int,
            ):
        self.deal_data = deal_data
        self.tranche_data = tranche_data
        self.collateral_data = collateral_data

        # Assumptions
        self.cpr = cpr
        self.cdr = cdr
        self.recovery_rate = recovery_rate
        self.payment_frequency = payment_frequency
        self.payment_interval = relativedelta(months=(12/payment_frequency))
        self.simulation_interval = simulation_interval
        self.senior_management_fee = senior_management_fee
        self.junior_management_fee = junior_management_fee
        self.non_call_end_date = non_call_end_date
        self.reinvestment_maturity_months = reinvestment_maturity_months

        # Dates
        self.report_date = date.today() # Ask about this
        self.reinvestment_end_date = parser.parse(self.deal_data['reinvestment_end_date']).date()

    def build(self):
        portfolio = self.build_portfolio()
        principal_account, interest_account = self.build_cash_accounts()
        debt_tranches, equity_tranche = self.build_tranches()
        senior_fee, junior_fee = self.build_fees()

        interest_waterfall = self.build_waterfall('pay_interest', senior_fee, junior_fee, debt_tranches, equity_tranche)
        principal_waterfall = self.build_waterfall('pay_principal', senior_fee, junior_fee, debt_tranches, equity_tranche)

        return CLO(
            report_date=self.report_date,
            next_payment_date=self.report_date+self.payment_interval,
            reinvestment_end_date=self.reinvestment_end_date,
            non_call_end_date=self.non_call_end_date,
            portfolio=portfolio,
            tranches=debt_tranches+[equity_tranche],
            management_fees=[senior_fee, junior_fee],
            interest_waterfall=interest_waterfall,
            principal_waterfall=principal_waterfall,
            principal_account=principal_account,
            interest_account=interest_account,
            payment_frequency=self.payment_frequency,
            cpr=self.cpr,
            cdr=self.cdr,
            recovery_rate=self.recovery_rate,
            reinvestment_maturity_months=self.reinvestment_maturity_months,
        )

    def build_waterfall(self, payment_method: str, senior_fee: Fee, junior_fee: Fee, debt_tranches: list[Tranche], equity_tranche: EquityTranche):
        payment_map = {
            WaterfallItem.SeniorMgmtFee.value: senior_fee.pay,
        }

        duplicates = 0
        for tranche in debt_tranches:
            key = tranche.rating

            if tranche.rating in payment_map:
                key += str(duplicates)
                duplicates += 1

            payment_map[key] = getattr(tranche, payment_method)

        payment_map |= {
            WaterfallItem.JuniorMgmtFee.value: junior_fee.pay,
            'Equity': getattr(equity_tranche, payment_method),
        }

        return CashflowWaterfall(payment_map, payment_map.keys())

    def build_fees(self):
        # The fees' balances will be set later by the CLO.
        senior_fee = Fee(0, self.senior_management_fee, self.report_date, WaterfallItem.SeniorMgmtFee)
        junior_fee = Fee(0, self.junior_management_fee, self.report_date, WaterfallItem.JuniorMgmtFee)

        return senior_fee, junior_fee

    def build_tranches(self):
        debt_tranches = []
        equity_tranche = None

        for i, item in self.tranche_data.iterrows():
            rating = item['comp_rating']
            balance = item['cur_balance']
            coupon = item['margin'] / 100

            if rating == 'Equity' or rating == 'EQTY':
                equity_tranche = EquityTranche(balance, self.report_date)
                continue

            tranche = Tranche(rating, balance, coupon, self.report_date)
            debt_tranches.append(tranche)

        if equity_tranche is None:
            raise ValueError("Could not find an equity tranche.")

        sort_order = ['AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'Equity']
        sorted_tranches = sorted(
            debt_tranches, 
            key=lambda inv: sort_order.index(inv.rating)
        )

        return sorted_tranches, equity_tranche

    def build_cash_accounts(self):
        principal_balance = self.deal_data['collection_acc_principal_balance']
        principal_account = Account(principal_balance)
        interest_account = Account(0)

        return principal_account, interest_account

    def build_portfolio(self):
        assets = []

        for i, item in self.collateral_data.iterrows():
            id = item['asset_name']
            balance = int(item['face_value'].replace(',',''))
            price = item['mark_value'] / 100
            coupon = item['spread'] / 100
            maturity_date = parser.parse(item['maturity_date']).date()

            # Don't add matured assets to the portfolio.
            if maturity_date <= self.report_date:
                continue

            asset = Asset(
                id=id,
                balance=balance,
                price=price,
                coupon=coupon,
                payment_frequency=self.payment_frequency,
                report_date=self.report_date,
                next_payment_date=self.report_date+self.payment_interval, # Ask about this
                maturity_date=maturity_date,
                cpr=self.cpr,
                cdr=self.cdr,
                recovery_rate=self.recovery_rate,
            )
            assets.append(asset)

        return Portfolio(assets)