import pandas as pd

from pyxirr import DayCount
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
            forward_curve_data: pd.DataFrame,
            cpr: float,
            cdr: float,
            cpr_lockout_months: int,
            cdr_lockout_months: int,
            recovery_rate: float,
            payment_frequency: int,
            simulation_frequency: int,
            reinvestment_maturity_months: int,
    ):
        self.report_date = date.today() # Ask about this...

        # Factories
        self.tranche_factory = TrancheFactory(tranche_data, self.report_date)
        self.portfolio_factory = PortfolioFactory(collateral_data, self.report_date, 
                                                  cpr, cdr, recovery_rate, 
                                                  cpr_lockout_months, cdr_lockout_months)
        self.fee_factory = FeeFactory(deal_data, self.report_date)
        self.account_factory = AccountFactory(deal_data)
        self.forward_curve_factory = ForwardRateCurveFactory(forward_curve_data)

        # Assumptions
        self.cpr = cpr
        self.cdr = cdr
        self.recovery_rate = recovery_rate
        self.payment_frequency = payment_frequency
        self.payment_interval = relativedelta(months=(12/payment_frequency))
        self.simulation_interval = relativedelta(months=(12/simulation_frequency))
        self.reinvestment_maturity_months = reinvestment_maturity_months

        # Important dates
        self.reinvestment_end_date = parser.parse(
            deal_data['reinvestment_enddate'], dayfirst=True).date()
        self.next_payment_date = parser.parse(
            deal_data['next_pay_date'], dayfirst=True).date()
        self.non_call_end_date = parser.parse(
            deal_data['non_call_date'], dayfirst=True).date()

    def build(self):
        forward_rate_curves = self.forward_curve_factory.build()
        portfolio = self.portfolio_factory.build(forward_rate_curves)
        principal_account, interest_account = self.account_factory.build()
        debt_tranches, equity_tranche = self.tranche_factory.build(forward_rate_curves['EURIBOR_3MO'])
        expenses_fee, senior_fee, junior_fee, incentive_fee = self.fee_factory.build()

        waterfall_factory = WaterfallFactory(expenses_fee, senior_fee, junior_fee, 
                                             incentive_fee, debt_tranches, equity_tranche)
        
        interest_waterfall = waterfall_factory.build('pay_interest')
        principal_waterfall = waterfall_factory.build('pay_principal')

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


class WaterfallFactory:
    """
    Model factory for building cashflow waterfalls.
    """

    def __init__(self, expenses_fee: Fee, senior_fee: Fee, junior_fee: Fee, 
                 incentive_fee: IncentiveFee, debt_tranches: list[Tranche], 
                 equity_tranche: EquityTranche):
        self.expenses_fee = expenses_fee
        self.senior_fee = senior_fee
        self.junior_fee = junior_fee
        self.incentive_fee = incentive_fee
        self.debt_tranches = debt_tranches
        self.equity_tranche = equity_tranche

    def build(self, payment_method: str):
        payment_map = {
            self.expenses_fee.name: self.expenses_fee.pay,
            self.senior_fee.name: self.senior_fee.pay,
        }

        duplicates = 0
        for tranche in self.debt_tranches:
            key = tranche.rating

            if tranche.rating in payment_map:
                key += str(duplicates)
                duplicates += 1

            payment_map[key] = getattr(tranche, payment_method)

        payment_map |= {
            self.junior_fee.name: self.junior_fee.pay,
            self.incentive_fee.name: self.incentive_fee.pay,
            WaterfallItem.Equity.name: getattr(self.equity_tranche, payment_method),
        }

        return CashflowWaterfall(payment_map, payment_map.keys())
    

class ForwardRateCurveFactory:
    """
    Model factory for building forward-rate curves.
    """

    def __init__(self, forward_curve_data: pd.DataFrame):
        self.data = forward_curve_data

    def build(self) -> dict[str, ForwardRateCurve]:
        forward_curves = {}

        curve_names = [col for col in self.data.columns if col != 'reporting_date']
        dates = pd.to_datetime(self.data['reporting_date']).dt.date.tolist()

        for curve_name in curve_names:
            # Create a ForwardRateCurve for the current curve
            rates = (self.data[curve_name] / 100).tolist()
            forward_curves[curve_name] = ForwardRateCurve(dates, rates)

        return forward_curves
    

class AccountFactory:
    """
    Model factory for building cash accounts.
    """

    def __init__(self, deal_data: pd.DataFrame):
        self.deal_data = deal_data

    def build(self):
        principal_balance = self.deal_data['collection_acc_principal_bal']
        principal_account = Account(principal_balance)
        # FIXME: Remove these hard-coded values
        # For SCULE7
        interest_account = Account(2710770.13)
        # For JUBIL20
        # interest_account = Account(3215276.35)

        return principal_account, interest_account
    

class TrancheFactory:
    """
    Model factory for building a capital structure of tranches.
    """

    def __init__(self, tranche_data: pd.DataFrame, report_date: date):
        self.tranche_data = tranche_data
        self.report_date = report_date

    def build(self, euribor_3mo: ForwardRateCurve):
        debt_tranches = []
        equity_tranche = None

        for i, item in self.tranche_data.iterrows():
            rating = item['comp_rating']
            balance = item['cur_balance']
            coupon = item['coupon'] / 100
            margin = item['margin'] / 100
            is_fixed_rate = 'fix' in item['tranche_type']
            
            if is_fixed_rate:
                day_count = DayCount.THIRTY_360_ISDA
            else:
                day_count = DayCount.ACT_360

            if rating == 'Equity' or rating == 'EQTY':
                equity_tranche = EquityTranche(balance, self.report_date)
            else:
                tranche = Tranche(rating, balance, margin, coupon, self.report_date,
                                   is_fixed_rate, euribor_3mo, day_count)
                debt_tranches.append(tranche)

        sort_order = ['AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'Equity']
        sorted_tranches = sorted(
            debt_tranches,
            key=lambda inv: sort_order.index(inv.rating)
        )

        return sorted_tranches, equity_tranche


class FeeFactory:
    """
    Model factory for building a set of fees paid in a CLO.
    """

    def __init__(self, deal_data: pd.DataFrame, report_date: date):
        self.deal_data = deal_data
        self.report_date = report_date

    def build(self):
        # FIXME don't use hard-coded values
        senior_expenses_fixed_fee = 0 # 300_000 
        senior_expenses_variable_fee = 0 # 0.000225

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


class PortfolioFactory:
    """
    Model factory for building a portfolio of assets underlying a CLO.
    """

    def __init__(self, 
                 collateral_data: pd.DataFrame, 
                 report_date: date, cpr: float,
                 cdr: float, 
                 recovery_rate: float, 
                 cpr_lockout_months: int,
                 cdr_lockout_months: int,
                 forward_rate_curves: dict[str, ForwardRateCurve] = None):
        self.collateral_data = collateral_data
        self.report_date = report_date
        self.cpr = cpr
        self.cdr = cdr
        self.recovery_rate = recovery_rate
        self.forward_rate_curves = forward_rate_curves
        self.cpr_lockout_end_date = self.report_date + relativedelta(months=cpr_lockout_months)
        self.cdr_lockout_end_date = self.report_date + relativedelta(months=cdr_lockout_months)

    def build(self, forward_rate_curves: dict[str, ForwardRateCurve]) -> Portfolio:
        assets = self.collateral_data.apply(
            self.build_asset, axis=1, args=[forward_rate_curves]).tolist()
        return Portfolio(assets)

    def build_asset(self, asset_data: pd.Series, forward_rate_curves: dict[str, ForwardRateCurve]) -> Asset:
        maturity_date = parser.parse(
            asset_data['maturitydate'], dayfirst=True).date()
        figi = asset_data.get('bbg_id')

        # Don't add matured assets to the portfolio
        if maturity_date <= self.report_date:
            raise ValueError(f"asset has already matured: {figi} matures on {maturity_date} but reporting date is {self.report_date}")

        if not pd.notna(figi):
            figi = asset_data.get('loanxid')

        if asset_data.get('defaulted'):
            coupon = 0.0 # Defaulted assets don't earn interest.
            spread = 0.0
        else:
            coupon = asset_data.get('grosscoupon') / 100
            spread = asset_data.get('spread') / 100

        asset_params = dict(
            figi=figi,
            balance=float(asset_data.get('facevalue')),
            price=asset_data.get('mark_value') / 100,
            spread=spread,
            initial_coupon=coupon,
            payment_frequency=int(asset_data.get('pay_freq')),
            report_date=self.report_date,
            next_payment_date=parser.parse(
                asset_data['next_pay_date'], dayfirst=True).date(),
            maturity_date=maturity_date,
            cpr=self.cpr,
            cdr=self.cdr,
            recovery_rate=self.recovery_rate,
            cpr_lockout_end_date=self.cpr_lockout_end_date,
            cdr_lockout_end_date=self.cdr_lockout_end_date,
        )

        # FIXME don't use a hardcoded value for the rate curve
        forward_rate_curve = forward_rate_curves['EURIBOR_3MO']
        asset_kind = asset_data.get('type').lower()
        if asset_kind == 'loan':
            asset_params |= dict(forward_rate_curve=forward_rate_curve)

        return (Loan if asset_kind == 'loan' else Bond)(**asset_params)
