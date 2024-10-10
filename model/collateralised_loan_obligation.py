from datetime import date
from dateutil.relativedelta import relativedelta

from . import day_counter
from .account import Account
from .asset import Asset
from .enums import *
from .equity_tranche import EquityTranche
from .tranche import Tranche
from .portfolio import Portfolio
from .snapshots import *
from .waterfall import CashflowWaterfall
from .fee import Fee, IncentiveFee


class CLO:
    """
    Class representing a Collateralised Loan Obligation.
    """
    def __init__(
        self, 
        report_date: date,
        next_payment_date: date,
        reinvestment_end_date: date,
        non_call_end_date: date,
        portfolio: Portfolio,
        tranches: list[Tranche],
        fees: list[Fee],
        incentive_fee: IncentiveFee,
        interest_waterfall: CashflowWaterfall, 
        principal_waterfall: CashflowWaterfall,
        principal_account: Account,
        interest_account: Account,
        payment_frequency: int,
        cpr: float,
        cdr: float,
        recovery_rate: float,
        reinvestment_maturity_months: int,
        wal_limit_years: int,
        liquidation_type: LiquidationType,
    ):
        """
        Instantiates a CLO.
        
        :param report_date: the date the deal report was generated on.
        :param next_payment_date: the next date the CLO's debt tranches will pay.
        :param reinvestment_end_date: the date the CLO will stop reinvesting all swept principal.
        :param non_call_end_date: the date after which options can be exercised.
        :param portfolio: the portfolio of assets.
        :param tranches: the set of tranches.
        :param interest_waterfall: the interest payment waterfall.
        :param principal_waterfall: the principal payment waterfall.
        :param principal_account: the cash account for holding swept principal.
        :param interest_account: the cash account for holding swept interest.
        :param payment_frequency: the number of times a year the CLO pays interest/principal to its tranches.
        """
        # Portfolio of assets
        self.portfolio = portfolio
        self.interest_swept = 0
        self.principal_swept = 0
        
        # Reinvestment attributes
        self.principal_reinvested = 0
        self.num_reinvestment_assets = 0
        self.reinvestment_maturity_months = reinvestment_maturity_months

        # Various dates for the CLO
        self.report_date = report_date
        self.last_simulation_date = None
        self.simulate_until = report_date

        # Tests
        self.wal_limit_years = wal_limit_years

        # Fees
        self.fees = fees
        self.incentive_fee = incentive_fee
        
        # Tranches
        self.tranches = tranches
        self.equity_tranche: EquityTranche = tranches[-1]
        
        # Waterfalls
        self.interest_waterfall = interest_waterfall
        self.principal_waterfall = principal_waterfall
        
        # Accounts
        self.interest_account = interest_account
        self.principal_account = principal_account

        # Assumptions
        self.cpr = cpr
        self.cdr = cdr
        self.recovery_rate = recovery_rate
        
        self.next_payment_date = next_payment_date
        self.payment_day = next_payment_date.day

        self.non_call_end_date = non_call_end_date
        self.reinvestment_end_date = reinvestment_end_date
        
        self.payment_frequency = payment_frequency
        self.payment_interval = relativedelta(months=(12/payment_frequency))

        self.in_liquidation = False
        self.liquidation_type = liquidation_type
        # Determine the liquidation date of the CLO according to Timo's instructions.
        if self.report_date <= self.reinvestment_end_date:
            # Inside the reinvestment period.
            self.liquidation_date = self.reinvestment_end_date + relativedelta(years=2)
        else:
            # Outside the reinvestment period.
            portfolio_maturity_haircut = 18
            portfolio_maturity_months = int(self.portfolio.weighted_average_life * 12)
            haircut_portfolio_maturity = self.report_date + relativedelta(months=portfolio_maturity_months - portfolio_maturity_haircut)
            self.liquidation_date = min(self.report_date + relativedelta(months=18), haircut_portfolio_maturity)
        
        # We need to backdate all tranche and fee accruals from the last payment date to the report date.
        # We do this by initialising the prior_payment_date of the tranches and fees to the prior payment date.
        self.prior_payment_date = self.next_payment_date - self.payment_interval
        self.cutoff_date = day_counter.sub_uk_business_days(self.prior_payment_date, 8)
        
        for tranche in self.tranches:
            tranche.last_simulation_date = self.prior_payment_date
        
        # Give the fees their initial balances 
        for fee in self.fees:
            fee.last_simulation_date = self.prior_payment_date
            fee.balance = self.aggregate_collateral_balance

        self.portfolio.backdate(self.cutoff_date)
        self.portfolio.simulate(self.report_date)

        self.interest_swept = self.portfolio.sweep_interest(self.interest_account)
        self.principal_swept = self.portfolio.sweep_principal(self.principal_account)

        # A history of snapshots.
        self.history = []
        # Take a snapshot of the CLO before simulating.
        self.take_snapshot()
        self.calc_first_simulation_date(report_date)
            
    def __str__(self):
        """
        Returns a string representation of the CLO.
        """
        return 'CLO'
    
    @property
    def debt_tranches(self) -> list[Tranche]:
        """
        Returns a list of debt tranches.
        """
        return [tranche for tranche in self.tranches if not tranche.is_equity_tranche]
    
    @property
    def continue_simulating(self) -> bool:
        """
        Returns whether or not to continue simulating the CLO.
        """
        return self.aggregate_collateral_balance > 0 or (self.in_liquidation and self.simulate_until <= self.liquidation_date) or self.portfolio.total_interest_accrued > 0
        
    @property
    def total_debt(self) -> float:
        """
        Returns the sum of the debt tranches' balances (tranches excluding the Equity tranche).
        """
        return sum(tranche.balance for tranche in self.tranches if not tranche.is_equity_tranche)
    
    @property
    def aggregate_collateral_balance(self) -> float:
        """
        Returns the total asset value of the portfolio + the principal account balance. 
        """
        return self.portfolio.total_asset_balance + self.principal_account.balance
    
    @property
    def equity_par_nav(self) -> float:
        """
        Returns the net asset value of the equity tranche.
        """
        return self.portfolio.total_asset_balance - self.total_debt
    
    @property
    def equity_nav(self) -> float:
        pass

    @property
    def equity_nav_90(self) -> float:
        pass

    @property
    def equity_nav_override(self) -> float:
        pass

    @property
    def in_reinvestment_period(self) -> bool:
        """
        Returns whether or not the CLO is in the reinvestment period.
        """
        return self.simulate_until <= self.reinvestment_end_date
    
    def simulate(self):
        """
        Simulates the CLO's cashflows until all the assets have matured and the principal balance
        has been paid off.
        """
        while self.continue_simulating:
            should_liquidate = self.simulate_until >= self.liquidation_date and not self.in_liquidation
            on_payment_date = self.simulate_until == self.next_payment_date
            
            # Liquidate the CLO if we are past the liquidation date.
            if should_liquidate:
                liquidation_date = self.simulate_until + relativedelta(days=14)
                redemption_date = self.simulate_until + relativedelta(months=1)
                self.liquidate(liquidation_date, redemption_date, self.liquidation_type)

            self.portfolio.simulate(self.simulate_until)
            
            # Sweep accrued interest and principal paid from the portfolio.
            self.interest_swept = self.portfolio.sweep_interest(self.interest_account)
            self.principal_swept = self.portfolio.sweep_principal(self.principal_account)

            for fee in self.fees:
                fee.simulate(self.simulate_until)
            self.incentive_fee.simulate(self.simulate_until)
            
            for tranche in self.tranches: 
                tranche.simulate(self.simulate_until)
                
            self.principal_reinvested = 0
            if self.in_reinvestment_period:
                self.principal_reinvested = self.reinvest()
            
            # Run the cashflow waterfall on payment dates.
            if on_payment_date:
                # Only update the fees' balances on a payment month. Furthermore, their balances are set *before* 
                # payments are run down the principal waterfall. This is an peculiarity with the purpose of 
                # earning more fees for the CLO manager. 
                for fee in self.fees:
                    fee.balance = self.aggregate_collateral_balance
                
                # Run the payments down the cashflow waterfalls.
                self.interest_waterfall.pay(self.interest_account, PaymentSource.Interest)
                self.principal_waterfall.pay(self.principal_account, PaymentSource.Amortization)

                # Fix coupons for the next accrual period.
                for tranche in self.debt_tranches:
                    tranche.update_coupon(self.simulate_until + relativedelta(months=1))
                
                # Bump the next payment date forward.
                self.next_payment_date += self.payment_interval
            
            self.take_snapshot()
            self.last_simulation_date = self.simulate_until

            # Bump the next simulation date forward. Simulate at 1 month intervals.
            self.simulate_until = self.simulate_until + relativedelta(months=1)
            self.simulate_until = day_counter.safely_set_day(self.simulate_until, self.payment_day)

    def liquidate(self, accrual_date: date, liquidation_date: date, liquidation_type: LiquidationType):
        self.in_liquidation = True
        self.liquidation_date = liquidation_date

        self.portfolio.liquidate(accrual_date, liquidation_type)

        for tranche in self.tranches:
            tranche.notify_of_liquidation(liquidation_date)

        for fee in self.fees:
            fee.notify_of_liquidation(liquidation_date)

        self.incentive_fee.notify_of_liquidation(liquidation_date)
        
    def reinvest(self) -> float:
        """
        Reinvests the CLO principal balance based on the CLO reinvestment profile.
        
        :return: the amount of principal reinvested.
        """
        as_of_date = self.simulate_until
        
        # We can't reinvest if we have no money.
        if self.principal_account.balance <= 0: 
            return 0
        
        # Request the entire principal account balance for reinvestment.
        cash = self.principal_account.request_debit(self.principal_account.balance)
        
        next_payment_date = self.next_payment_date
        if as_of_date == next_payment_date:
            # Increment the reinvestment asset's next payment date if the current_date 
            # is a payment date (the reinvestment asset won't pay anything this period
            # as it's only just been instantiated).
            next_payment_date += self.payment_interval
        
        # Create a reinvestment asset and add it to the portfolio.
        asset = self.reinvest_using_wavgs(cash, as_of_date, next_payment_date)
        self.portfolio.add_asset(asset)
        self.num_reinvestment_assets += 1
        
        return cash
    
    def reinvest_using_wavgs(self, cash: float, current_date: date, next_payment_date: date) -> Asset:
        """
        Reinvests the CLO principal balance into a new asset using weighted average
        coupon and price of the portfolio.
        
        :param cash: the amount of money available to reinvest.
        :param current_date: the current date to simulate until.
        :param next_payment_date: the next date the asset is due to pay on.
        """
        name = f"Reinvestment Asset {self.num_reinvestment_assets} (WA)"
                
        # The price of a reinvestment asset shouldn't be higher than 100%.
        price = min(self.portfolio.weighted_average_price, 1)
        coupon = self.portfolio.weighted_average_coupon
        spread = self.portfolio.weighted_average_spread
        cpr_lockout_end_date = self.portfolio.cpr_lockout_end_date
        cdr_lockout_end_date = self.portfolio.cdr_lockout_end_date
        curve = self.portfolio.forward_rate_curves['EURIBOR_3MO']
        balance = cash / price

        # Calculate the maturity of the reinvestment asset.
        # maturity = self.calculate_reinvestment_maturity(balance, current_date)
        maturity = current_date + relativedelta(months=self.reinvestment_maturity_months)

        return Asset(name, AssetKind.Loan, balance, price, price, spread, coupon, self.payment_frequency, 
            current_date, next_payment_date, maturity, cpr_lockout_end_date, cdr_lockout_end_date,
            self.cpr, self.cdr, self.recovery_rate, curve, is_floating_rate=True)
    
    def calculate_reinvestment_maturity(self, balance: float, current_date: date) -> date:
        """
        Calculates the optimal maturity for a reinvestment asset that maintains the WAL limit.

        :param balance: the balance of the reinvestment asset.
        :param current_date: the current date of reinvestment.
        :return: The maturity date for the new asset.
        :raises ValueError: If no valid maturity can be calculated within the WAL limit.
        """
        total_balance = self.portfolio.total_asset_balance + balance
        current_wal = self.portfolio.weighted_average_life

        # Calculate the maximum allowable WAL contribution from the new asset
        max_wal_contribution = (self.wal_limit_years * total_balance - current_wal * self.portfolio.total_asset_balance) / balance
        
        if max_wal_contribution <= 0:
            raise ValueError("WAL limit has been breached. No valid maturity can be calculated.")

        # Convert the maximum WAL contribution into a maturity in months from the report date
        max_maturity_months = int(max_wal_contribution * 12)
        # Calculate the maturity date by adding max_maturity_months to the report date
        maturity = self.report_date + relativedelta(months=max_maturity_months)
        # Ensure the maturity is not earlier than one month from the current date
        maturity = max(maturity, current_date + relativedelta(months=1))
        # Ensure the maturity is not later than 15 years from the report date
        maturity = min(maturity, self.report_date + relativedelta(years=15))

        return maturity

    def calc_first_simulation_date(self, report_date: date):
        """
        Works out the date from which the simulations should start by stepping back in time
        until we reach the earliest possible simulation date in the future.
        
        :param report_date: the date the deal report was generated on.
        """
        if not report_date < self.next_payment_date:
            # Guard against the report date being invalid.
            raise Exception(f"The report date, {report_date}, cannot be after the next payment date, {self.next_payment_date}.")
        
        self.last_simulation_date = report_date
        month_delta = 0
        
        # Find the first month that is before the report date.
        while report_date <= self.next_payment_date + relativedelta(months=month_delta):
            month_delta -= 1
            
        # At this point we have the first month that is before the report date. 
        # We want the month after, so we increment the delta by 1.
        month_delta += 1
        self.simulate_until = self.next_payment_date + relativedelta(months=month_delta)
            
    def take_snapshot(self):
        """
        Takes a snapshot of the CLO's attributes. test comment
        """
        self.history.append(CLOSnapshot(
            date                            = self.simulate_until,
            interest_swept                   = self.interest_swept,
            interest_accrued                  = self.portfolio.total_interest_accrued,
            principal_swept                  = self.principal_swept,
            principal_reinvested             = self.principal_reinvested,
            interest_account_balance          = self.interest_account.balance,
            principal_account_balance         = self.principal_account.balance,
            total_debt                      = self.total_debt,
            total_asset_par               = self.portfolio.total_asset_balance,
            weighted_average_spread        = self.portfolio.weighted_average_spread,
            weighted_average_coupon        = self.portfolio.weighted_average_coupon,
            weighted_average_price         = self.portfolio.weighted_average_price,
            weighted_average_life          = self.portfolio.weighted_average_life,
            nav                            = (self.principal_account.balance + self.portfolio.market_value - self.total_debt) / self.equity_tranche.balance,
            nav_90                         = (self.principal_account.balance + self.portfolio.market_value_90 - self.total_debt) / self.equity_tranche.balance,
        ))