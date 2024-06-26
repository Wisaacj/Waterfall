from datetime import date
from dateutil.relativedelta import relativedelta

from .account import Account
from .asset import Asset
from .enums import *
from .equity_tranche import EquityTranche
from .tranche import Tranche
from .portfolio import Portfolio
from .snapshots import *
from .waterfall import CashflowWaterfall
from .fee import Fee


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
        management_fees: list[Fee],
        interest_waterfall: CashflowWaterfall, 
        principal_waterfall: CashflowWaterfall,
        principal_account: Account,
        interest_account: Account,
        payment_frequency: int,
        cpr: float,
        cdr: float,
        recovery_rate: float,
        reinvestment_maturity_months: int,
    ) -> None:
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

        # Fees
        self.management_fees = management_fees
        
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
        
        # A history of snapshots.
        self.history = []
        
        # Take a snapshot of the inital values of the CLO's attributes.
        self.take_snapshot()
        
        self.next_payment_date = next_payment_date
        self.calc_first_simulation_date(report_date)    
        self.non_call_end_date = non_call_end_date
        self.reinvestment_end_date = reinvestment_end_date
        
        self.payment_frequency = payment_frequency
        self.payment_interval = relativedelta(months=(12/payment_frequency))
        
        # We need to backdate all tranche and fee accruals from the last payment date to the report date.
        # We do this by initialising the lastPaymentDate of the tranches and fees to the prior payment date.
        prior_payment_date = self.next_payment_date - self.payment_interval
        
        for tranche in self.tranches:
            tranche.last_simulation_date = prior_payment_date
        
        # Give the fees their initial balances 
        for fee in self.management_fees:
            fee.last_simulation_date = prior_payment_date
            fee.balance = self.aggregate_collateral_balance 
            
    def __str__(self):
        """
        Returns a string representation of the CLO.
        """
        return 'CLO'
    
    @property
    def continue_simulating(self) -> bool:
        """
        Returns whether or not to continue simulating the CLO. This checks if the ACB is greater than zero 
        and whether the option to stop simulating once all original debt balances reach zero has been enabled.
        """
        return self.aggregate_collateral_balance > 0
        
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
    def debt_tranches(self) -> list[Tranche]:
        """
        Returns a list of debt tranches.
        """
        return [tranche for tranche in self.tranches if not tranche.is_equity_tranche]
    
    @property
    def equity_par_nav(self) -> float:
        """
        Returns the net asset value of the equity tranche.
        """
        return self.portfolio.total_asset_balance - self.total_debt
    
    def simulate(self):
        """
        Simulates the CLO's cashflows until all the assets have matured and the principal balance
        has been paid off.
        """
        while self.continue_simulating:   
            self.portfolio.simulate(self.simulate_until)
            
            # Sweep the interest and principal from the portfolio of loans.
            self.interest_swept = self.portfolio.sweep_interest(self.interest_account)
            self.principal_swept = self.portfolio.sweep_principal(self.principal_account)
            
            for fee in self.management_fees:
                fee.simulate(self.simulate_until)
            
            for tranche in self.tranches: 
                tranche.simulate(self.simulate_until)
                
            self.principal_reinvested = 0
            # Reinvest if we are within the reinvestment period.
            if self.simulate_until <= self.reinvestment_end_date:
                self.principal_reinvested = self.reinvest()
            
            if self.simulate_until == self.next_payment_date:
                # Only update the fees' balances on a payment month. Furthermore, their balances are set *before* 
                # payments are run down the principal waterfall. This is an peculiarity with the purpose of 
                # earning more fees for the CLO manager. 
                for fee in self.management_fees:
                    fee.balance = self.aggregate_collateral_balance
                
                # Run the payments down the cashflow waterfalls.
                self.interest_waterfall.pay(self.interest_account, PaymentSource.Interest)
                self.principal_waterfall.pay(self.principal_account, PaymentSource.Amortization)
                
                # Bump the next payment date forward.
                self.next_payment_date += self.payment_interval
            
            self.take_snapshot()
            
            self.last_simulation_date = self.simulate_until
            # Bump the next simulation date forward. Simulate at 1 month intervals.
            self.simulate_until = self.simulate_until + relativedelta(months=1)
        
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
        name = f"<RA:{self.num_reinvestment_assets} WA>"
        maturity = current_date + relativedelta(months=self.reinvestment_maturity_months)
                
        # The price of a reinvestment asset shouldn't be higher than 100%.
        price = min(self.portfolio.weighted_average_price, 1)
        coupon = self.portfolio.weighted_average_coupon
        balance = cash / price

        return Asset(name, balance, price, coupon, self.payment_frequency, 
            current_date, next_payment_date, maturity, self.cpr, self.cdr, self.recovery_rate)
        
    def calc_equity_liquidation_value(self) -> float:
        """
        Calculates the equity liquidation value of the CLO.
        """
        # We include the equity tranche interest payment which happened on the liquidation date (lastInterestPayment).
        equity_liquidation_value = self.principal_account.balance + self.interest_account.balance + \
            self.portfolio.total_dirty_market_value - self.total_debt - sum([fee.interest_accrued for fee in self.management_fees]) + \
                self.equity_tranche.last_interest_payment
            
        return equity_liquidation_value
        
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
            interest_swept                   = self.interest_swept,
            principal_swept                  = self.principal_swept,
            date                            = self.simulate_until,
            principal_reinvested             = self.principal_reinvested,
            interest_account_balance          = self.interest_account.balance,
            principal_account_balance         = self.principal_account.balance,
            equity_liquidation_value          = self.calc_equity_liquidation_value(),
            total_debt_tranches_balance        = self.total_debt,
            total_asset_balance               = self.portfolio.total_asset_balance,
        ))