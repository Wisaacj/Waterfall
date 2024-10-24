import utils
import pandas as pd

from datetime import date
from pyxirr import DayCount
from dateutil import parser
from clo_arg_parser import Arguments
from dateutil.relativedelta import relativedelta

from model import (
    Account,
    Asset,
    Tranche,
    EquityTranche,
    Fee,
    IncentiveFee,
    CLO,
    WaterfallItem,
    CashflowWaterfall,
    Portfolio,
    ForwardRateCurve,
    AssetKind,
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
            args: Arguments,
    ):
        self.report_date = date.today()

        # Convert the fee rebate from basis points to a percentage.
        args.fee_rebate = args.fee_rebate / 10000

        # Factories
        self.tranche_factory = TrancheFactory(tranche_data, self.report_date)
        self.portfolio_factory = PortfolioFactory(collateral_data, self.report_date, 
                                                  args.cpr, args.cdr, args.recovery_rate, 
                                                  args.cpr_lockout_months, args.cdr_lockout_months,
                                                  args.use_top_down_defaults)
        self.fee_factory = FeeFactory(deal_data, self.report_date, args.fee_rebate)
        self.account_factory = AccountFactory(deal_data)
        self.forward_curve_factory = ForwardRateCurveFactory(forward_curve_data)

        # Assumptions
        self.cpr = args.cpr
        self.cdr = args.cdr
        self.recovery_rate = args.recovery_rate
        self.payment_frequency = args.payment_frequency
        self.payment_interval = relativedelta(months=(12/args.payment_frequency))
        self.simulation_interval = relativedelta(months=(12/args.simulation_frequency))
        self.rp_extension_months = args.rp_extension_months
        self.reinvestment_maturity_months = args.reinvestment_maturity_months
        self.liquidation_type = args.liquidation_type
        self.use_top_down_defaults = args.use_top_down_defaults

        # Important dates
        self.reinvestment_end_date = utils.parse_date(deal_data['reinvestment_enddate']) + relativedelta(months=args.rp_extension_months)
        self.next_payment_date = utils.parse_date(deal_data['next_pay_date'])
        self.non_call_end_date = utils.parse_date(deal_data['non_call_date'])
        
        # Tests
        if pd.notna(deal_data['wal_limit']):
            self.wal_limit_years = float(deal_data['wal_limit'])
        else:
            self.wal_limit_years = args.wal_limit_years

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
            wal_limit_years=self.wal_limit_years,
            liquidation_type=self.liquidation_type,
            use_top_down_defaults=self.use_top_down_defaults,
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
        principal_balance = float(self.deal_data['collection_acc_principal_bal'])
        principal_account = Account(principal_balance)
        interest_account = Account(0)

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
        equity_tranche = EquityTranche(0, self.report_date)

        for _, item in self.tranche_data.iterrows():
            rating = item['tranche']
            tranche_type = item['tranche_type'].lower()
            balance = float(item['cur_balance'])
            coupon = float(item['coupon']) / 100

            # Ignore fully amortised tranches
            if balance <= 0:
                continue
            
            is_equity_tranche = tranche_type == 'jun_sub'
            is_fixed_rate = 'fix' in tranche_type

            if is_fixed_rate or is_equity_tranche:
                day_count = DayCount.THIRTY_360_ISDA
                margin = 0
            else:
                day_count = DayCount.ACT_360
                margin = float(item['margin']) / 100

            if is_equity_tranche:
                # NOTE that, currently, we fold all equity tranches into one.
                balance += equity_tranche.balance
                equity_tranche = EquityTranche(balance, self.report_date)
            else:
                tranche = Tranche(rating, balance, margin, coupon, self.report_date,
                                   is_fixed_rate, euribor_3mo, day_count)
                debt_tranches.append(tranche)

        # Sort tranches by rating (alphabetically)
        sorted_tranches = sorted(debt_tranches, key=lambda inv: inv.rating)

        return sorted_tranches, equity_tranche


class FeeFactory:
    """
    Model factory for building a set of fees paid in a CLO.
    """

    def __init__(self, deal_data: pd.DataFrame, report_date: date, fee_rebate: float):
        self.deal_data = deal_data
        self.report_date = report_date
        self.fee_rebate = fee_rebate

    def build(self):
        senior_expenses_fixed_fee = 300_000 
        senior_expenses_variable_fee = 0.000225

        senior_management_fee = float(self.deal_data['deal_sen_mgt_fees']) / 100
        junior_management_fee = float(self.deal_data['deal_sub_mgt_fees']) / 100

        incentive_fee_balance = float(self.deal_data['deal_inc_mgt_fee_irr_balances'])
        incentive_fee_hurdle_rate = float(self.deal_data['deal_inc_mgt_fee_irr_threshold']) / 100
        incentive_fee_diversion_rate = float(self.deal_data['deal_inc_mgt_fee_excess_pcts']) / 100

        # The fees' balances are set later by the CLO.
        senior_expenses_fee = Fee(0, senior_expenses_variable_fee,
                               self.report_date, WaterfallItem.SeniorExpensesFee, senior_expenses_fixed_fee)
        senior_management_fee = Fee(0, senior_management_fee,
                         self.report_date, WaterfallItem.SeniorMgmtFee)
        junior_management_fee = Fee(0, junior_management_fee,
                         self.report_date, WaterfallItem.JuniorMgmtFee, 0, self.fee_rebate)
        
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
                 use_top_down_defaults: bool):
        self.collateral_data = collateral_data
        self.report_date = report_date
        self.cpr = cpr
        self.cdr = cdr
        self.recovery_rate = recovery_rate
        self.cpr_lockout_end_date = self.report_date + relativedelta(months=cpr_lockout_months)

        if use_top_down_defaults:
            # When using top-down defaults, we delay the calculation of defaults until the liquidation date.
            self.cdr_lockout_end_date = date(9999, 12, 31)
        else:
            self.cdr_lockout_end_date = self.report_date + relativedelta(months=cdr_lockout_months)

    def build(self, forward_rate_curves: dict[str, ForwardRateCurve]) -> Portfolio:
        try:
            assets = self.collateral_data.apply(
                self.build_asset, axis=1, args=[forward_rate_curves]).tolist()
            assets = [a for a in assets if a is not None]
            return Portfolio(assets, forward_rate_curves)
        except Exception as e:
            raise Exception(f"Failed to build portfolio, possibly because there is no collateral data for this deal. Please check 'Loan-UK.csv'.")

    def build_asset(self, asset_data: pd.Series, forward_rate_curves: dict[str, ForwardRateCurve]) -> Asset:
        figi = asset_data['bbg_id']
        balance = float(asset_data['face_value'])
        asset_kind = AssetKind.from_string(asset_data['inv_type'])

        if balance <= 0 or asset_kind == AssetKind.Equity:
            return None

        maturity_date = utils.parse_date(asset_data['maturity_date'])
        next_payment_date = utils.parse_date(asset_data['next_pay_date'])
        payment_frequency = int(asset_data['pay_freq'])
        is_floating_rate = asset_data['fix_or_float'].lower() == 'float'
        price = float(asset_data['mark_value']) / 100
        price_ovr = price # FIXME: Handle price overrides

        # Don't add matured assets to the portfolio
        if maturity_date <= self.report_date:
            return None

        if not pd.notna(figi):
            figi = asset_data['loanx_id']
        if not pd.notna(price):
            price = 1.0 # Default price is 100%

        # FIXME: Handle defaulted assets more gracefully
        # if asset_data.get('defaulted'):
        #     coupon = spread = 0.0 # Defaulted assets don't earn interest.
        # else:
        coupon = float(asset_data['gross_coupon']) / 100
        spread = float(asset_data['spread']) / 100

        forward_rate_curve = forward_rate_curves\
            .get(f'EURIBOR_{12//payment_frequency}MO', forward_rate_curves['EURIBOR_3MO'])

        return Asset(
            figi=figi,
            asset_kind=asset_kind,
            balance=balance,
            price=price,
            price_ovr=price_ovr,
            spread=spread,
            initial_coupon=coupon,
            payment_frequency=payment_frequency,
            report_date=self.report_date,
            next_payment_date=next_payment_date,
            maturity_date=maturity_date,
            cpr_lockout_end_date=self.cpr_lockout_end_date,
            cdr_lockout_end_date=self.cdr_lockout_end_date,
            cpr=self.cpr,
            cdr=self.cdr,
            recovery_rate=self.recovery_rate,
            forward_rate_curve=forward_rate_curve,
            is_floating_rate=is_floating_rate
        )