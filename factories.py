import pandas as pd

from datetime import date
from dateutil import parser
from dateutil.relativedelta import relativedelta

from model import (
    Account,
    Asset,
    Loan,
    Bond,
    Tranche,
    EquityTranche,
    Fee,
    IncentiveFee,
    CLO,
    WaterfallItem,
    CashflowWaterfall,
    Portfolio,
    ForwardRateCurve
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
            simulation_frequency: int,
            reinvestment_maturity_months: int,
    ):
        self.report_date = date.today()  # Ask about this...

        self.deal_data = deal_data
        self.tranche_data = tranche_data
        self.portfolio_factory = PortfolioFactory(
            collateral_data, self.report_date, cpr, cdr, recovery_rate)

        # Assumptions
        self.cpr = cpr
        self.cdr = cdr
        self.recovery_rate = recovery_rate
        self.payment_frequency = payment_frequency
        self.payment_interval = relativedelta(months=(12/payment_frequency))
        self.simulation_interval = relativedelta(
            months=(12/simulation_frequency))
        self.reinvestment_maturity_months = reinvestment_maturity_months

        # Dates
        self.reinvestment_end_date = parser.parse(
            self.deal_data['reinvestment_enddate'], dayfirst=True).date()
        self.next_payment_date = parser.parse(
            self.deal_data['next_pay_date'], dayfirst=True).date()
        self.non_call_end_date = parser.parse(
            self.deal_data['non_call_date'], dayfirst=True).date()

    def build(self):
        portfolio = self.portfolio_factory.build()
        principal_account, interest_account = self.build_cash_accounts()
        debt_tranches, equity_tranche = self.build_tranches()
        expenses_fee, senior_fee, junior_fee, incentive_fee = self.build_fees()

        interest_waterfall = self.build_waterfall(
            'pay_interest', expenses_fee, senior_fee, junior_fee, incentive_fee, 
            debt_tranches, equity_tranche)
        principal_waterfall = self.build_waterfall(
            'pay_principal', expenses_fee, senior_fee, junior_fee, incentive_fee,
            debt_tranches, equity_tranche)

        return CLO(
            report_date=self.report_date,
            next_payment_date=self.next_payment_date,
            reinvestment_end_date=self.reinvestment_end_date,
            non_call_end_date=self.non_call_end_date,
            portfolio=portfolio,
            tranches=debt_tranches+[equity_tranche],
            fees=[expenses_fee, senior_fee, junior_fee],
            incentive_fee=incentive_fee,
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

    def build_waterfall(self, payment_method: str, expenses_fee: Fee, senior_fee: Fee, 
                        junior_fee: Fee, incentive_fee: IncentiveFee, debt_tranches: list[Tranche],
                        equity_tranche: EquityTranche):
        payment_map = {
            expenses_fee.name: expenses_fee.pay,
            senior_fee.name: senior_fee.pay,
        }

        duplicates = 0
        for tranche in debt_tranches:
            key = tranche.rating

            if tranche.rating in payment_map:
                key += str(duplicates)
                duplicates += 1

            payment_map[key] = getattr(tranche, payment_method)

        payment_map |= {
            junior_fee.name: junior_fee.pay,
            incentive_fee.name: incentive_fee.pay,
            WaterfallItem.Equity.name: getattr(equity_tranche, payment_method),
        }

        return CashflowWaterfall(payment_map, payment_map.keys())

    def build_fees(self):
        # FIXME don't use hard-coded values
        senior_expenses_fixed_fee = 0#300_000 
        senior_expenses_variable_fee =0# 0.000225

        senior_management_fee = self.deal_data['deal_sen_mgt_fees'] / 100
        junior_management_fee = self.deal_data['deal_sub_mgt_fees'] / 100

        incentive_fee_balance = self.deal_data['deal_inc_mgt_fee_irr_balances']
        incentive_fee_hurdle_rate = self.deal_data['deal_inc_mgt_fee_irr_threshold'] / 100
        incentive_fee_diversion_rate = self.deal_data['deal_inc_mgt_fee_excess_pcts'] / 100

        # The fees' balances are set later by the CLO.
        senior_expenses_fee = Fee(0, senior_expenses_variable_fee,
                               self.report_date, WaterfallItem.SeniorExpensesFee,
                                 senior_expenses_fixed_fee)
        senior_management_fee = Fee(0, senior_management_fee,
                         self.report_date, WaterfallItem.SeniorMgmtFee)
        junior_management_fee = Fee(0, junior_management_fee,
                         self.report_date, WaterfallItem.JuniorMgmtFee)
        incentive_fee = IncentiveFee(incentive_fee_balance, incentive_fee_hurdle_rate,
                                      incentive_fee_diversion_rate, self.report_date)

        return senior_expenses_fee, senior_management_fee, junior_management_fee, incentive_fee

    def build_tranches(self):
        debt_tranches = []
        equity_tranche = None

        for i, item in self.tranche_data.iterrows():
            rating = item['comp_rating']
            balance = item['cur_balance']
            coupon = item['coupon'] / 100

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
        principal_balance = self.deal_data['collection_acc_principal_bal']
        principal_account = Account(principal_balance)
        # Remove these hard-coded values later
        # For SCULE7
        interest_account = Account(2710770.13)
        # For JUBIL20
        # interest_account = Account(3215276.35)

        return principal_account, interest_account


class PortfolioFactory:
    """
    Model factory for building a portfolio of assets underlying a CLO.
    """

    def __init__(self, collateral_data: pd.DataFrame, report_date: date, cpr: float,
                 cdr: float, recovery_rate: float, forward_rate_curves: dict[str, ForwardRateCurve] = None):
        self.collateral_data = collateral_data
        self.report_date = report_date
        self.cpr = cpr
        self.cdr = cdr
        self.recovery_rate = recovery_rate
        self.forward_rate_curves = forward_rate_curves

    def build(self) -> Portfolio:
        assets = self.collateral_data.apply(self.build_asset, axis=1).tolist()
        return Portfolio(assets)

    def build_asset(self, asset_data: pd.Series) -> Asset:
        maturity_date = parser.parse(
            asset_data['maturitydate'], dayfirst=True).date()

        # Don't add matured assets to the portfolio
        if maturity_date <= self.report_date:
            raise Exception()

        figi = asset_data.get('bbg_id')
        if not pd.notna(figi):
            figi = asset_data.get('loanxid')

        if asset_data.get('defaulted'):
            coupon = 0.0 # Defaulted assets don't earn interest.
        else:
            coupon = asset_data.get('grosscoupon') / 100

        asset_params = dict(
            figi=figi,
            balance=float(asset_data.get('facevalue')),
            price=asset_data.get('mark_value') / 100,
            coupon=coupon,
            payment_frequency=int(asset_data.get('pay_freq')),
            report_date=self.report_date,
            next_payment_date=parser.parse(
                asset_data['next_pay_date'], dayfirst=True).date(),
            maturity_date=maturity_date,
            cpr=self.cpr,
            cdr=self.cdr,
            recovery_rate=self.recovery_rate,
        )

        if (asset_kind := asset_data.get('type').lower()) == 'loan':
            asset_params |= dict(forward_rate_curve=None)

        return (Loan if asset_kind == 'loan' else Bond)(**asset_params)
