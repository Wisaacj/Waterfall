from datetime import date
from dateutil.relativedelta import relativedelta

from . import day_counter
from .account import Account
from .interest_vehicle import InterestVehicle
from .snapshots import *


class Asset(InterestVehicle):
    """
    Class representing an Asset.
    """
    def __init__(self, figi: str, kind: str, balance: float, price: float, coupon: float, payment_frequency: int, 
        report_date: date, next_payment_date: date, maturity_date: date, cpr: float, cdr: float, recovery_rate: float):
        """
        Instantiates an asset.
        
        :param id: the asset's ISIN or reinvestment name.
        :param balance: the balance of the asset as of the report_date.
        :param price: the price of the asset as of the report_date.
        :param coupon: the coupon paid on the asset as of the report_date 
        :param payment_frequency: the number of times the asset pays per year.
        :param report_date: the date the deal report was generated on.
        :param next_payment_date: the next date the asset will pay.
        :param maturity_date: the date the asset matures
        """
        # Initialise the last_simulation_date to the report_date.
        super().__init__(balance, coupon, report_date)
        
        self.figi = figi
        self.kind = kind
        
        # Price, assumptions.
        self.price = price
        self.cpr = cpr
        self.cdr = cdr
        self.recovery_rate = recovery_rate
        
        # Dates.
        self.maturity = maturity_date
        self.report_date = report_date
        self.next_payment_date = next_payment_date
        self.payment_frequency = payment_frequency
        self.payment_interval = relativedelta(months=(12/payment_frequency))
        self.simulating_interim_period = False
        
        # Backdate the interest accrued to the amount accrued between 
        # the last payment and report dates.
        self.interest_accrued = self.calc_backdated_accrued_interest()
        
        # These are used to keep track of the flow of principal when a payment
        # date lies inbetween two simulation dates.
        self.scheduled_principal = 0
        self.defaulted_principal = 0
        self.recovered_principal = 0
        self.unscheduled_principal = 0
        
        # History of cashflows.
        self.history = []
        
        # Take a snapshot of the initial state of the asset.
        self.take_snapshot(report_date)
        
    def __str__(self) -> str:
        """
        Returns this asset's Bloomberg ID.
        """
        return self.figi
    
    def simulate(self, simulate_until: date):
        """
        Runs a simulation on the asset over the given number of months and computes the new cash flows for the period.
        
        :param simulate_until: as the name suggests.
        """
        # if simulate_until == self.last_simulation_date:
        #     return
        
        # If there is a payment date before the end of the simulation, we will instead simulate until that date
        # and then remove all money before proceeding with the following simulation period.
        while (simulate_until > self.next_payment_date or simulate_until > self.maturity):
            interim_date = self.next_payment_date if self.next_payment_date <= self.maturity else self.maturity
            
            # Simulate until the interim date.
            self.simulating_interim_period = True
            self.simulate(interim_date)
            
        # Work out the proportion of the year we are simulating over here.
        year_factor = self.calc_year_factor(simulate_until)

        # Accrue interest for this period.
        self.accrue_interest(year_factor)
        
        # The amount of prepayments and defaults during this simulation period.
        prepayments = (1 - ((1-self.cpr) ** year_factor)) * self.balance
        defaults = (1 - ((1-self.cdr) ** year_factor)) * (self.balance - prepayments)
        
        # The amount of prepayments and defaults as a proportion of the balance.
        balance = self.balance if self.balance != 0 else 1
        unscheduled_proportion = prepayments / balance
        defaulted_proportion = defaults / balance
        
        # 1) For defaults:
        # Recover some of the defaulted principal
        recovery = defaults * self.recovery_rate
        self.principal_paid += recovery
        # Defaulted assets suffer 100% loss on interest accrued on that portion (this is 
        # made explicit by incrementing interest_paid by 0)
        self.interest_paid += 0
        self.interest_accrued -= defaulted_proportion * self.interest_accrued
        
        # 2) For unscheduled principal:
        self.principal_paid += prepayments
        self.interest_paid += unscheduled_proportion * self.interest_accrued
        self.interest_accrued -= unscheduled_proportion * self.interest_accrued
        
        # 3) For remaining balances:
        self.balance -= prepayments + defaults
        
        # If we are on a payment date, run the payment process.
        if (simulate_until == self.next_payment_date):
            # Pay off the accrued interest and then reset it.
            self.interest_paid += self.interest_accrued
            self.interest_accrued = 0
            
            # Bump the next payment date forward by the payment interval.
            self.next_payment_date += self.payment_interval
        
        if (simulate_until >= self.maturity):
            # Scheduled principal is the remaining balance on maturity.
            self.scheduled_principal = self.balance
            
            # Pay off the remaining balance.
            self.principal_paid += self.balance
            self.balance = 0
            
            # Pay off any remaining accrued interest.
            self.interest_paid += self.interest_accrued
            self.interest_accrued = 0
            
            # Set maturity to be 31/12/9999 to avoid running this condition again.
            self.maturity = date(9999, 12, 31)
        
        # Finally, we must save the last date that this simulation was run until, which is the end of this simulation.
        self.last_simulation_date = simulate_until
        
        # If we are simulating until an actionDate rather than an original simulate_until,
        # we are at risk of not accurately tracking the flow of principal because we subdivide the
        # original simulation period into at least two segments, but only take a snapshot in the last segment.
        # The following variables keep track of the principal through the subdivided segments.
        self.unscheduled_principal += prepayments
        self.defaulted_principal += defaults
        self.recovered_principal += recovery

        if self.simulating_interim_period:
            self.simulating_interim_period = False 
            return
        
        self.take_snapshot(simulate_until)
        
        # Reset these variables.
        self.unscheduled_principal = 0
        self.scheduled_principal = 0
        self.defaulted_principal = 0
        self.recovered_principal = 0
        self.period_accrual = 0
    
    def sweep_interest(self, destination: Account) -> float:
        """
        Credits the destination account with the interest paid by this asset and sets it to 0.
        
        :param destination: the Account to credit with the interest.
        :return: the amount of interest swept.
        """
        amount = self.interest_paid

        if amount < 0:
            raise Exception()

        destination.credit(amount)
        self.interest_paid = 0
        
        return amount
    
    def sweep_principal(self, destination: Account) -> float:
        """
        Credits the destination account with the principal paid by this asset and sets it to 0.
        
        :param destination: the Account to credit with the interest.
        :return: the amount of principal swept.
        """
        amount = self.principal_paid
        destination.credit(amount)
        self.principal_paid = 0
        
        return amount
    
    def liquidate(self, accrual_date: date):
        # Loans trade with delayed comp (T+10), while bonds trade with lesser delayed
        # comp (T+2). That is, we continue to earn interest on loans until T+10 and
        # bonds until T+2.
        if self.kind == 'loan':
            settlement_date = day_counter.add_uk_business_days(accrual_date, 10)
        elif self.kind == 'bond':
            settlement_date = day_counter.add_uk_business_days(accrual_date, 2)
        else:
            raise ValueError(f"unknown asset kind: cannot liquidate assets of kind {self.kind}")
        
        # Accrue interest on the asset until the comp period is over.
        self.simulate(settlement_date)

        # Sell the asset into the market
        self.principal_paid += self.price * self.balance
        # The asset has been liquidated so its balance is effectively zero.        
        self.balance = 0
        
    def calc_prior_payment_date(self, comparison_date: date) -> date:
        """
        Calculates the payment date prior to a comparison date.
        
        :param comparison_date: the date you want the prior payment date to.
        :return: the prior payment date.
        """
        prior_payment_date = self.next_payment_date
        
        while prior_payment_date > comparison_date:
            prior_payment_date -= self.payment_interval
        
        return prior_payment_date
    
    def calc_backdated_accrued_interest(self) -> float:
        """
        Calculates the interest accrued between the last payment date and the report date.
        """
        year_factor = self.calc_year_factor(self.report_date, self.calc_prior_payment_date(self.report_date))
        return self.balance * year_factor * self.interest_rate

    def take_snapshot(self, simulate_until: date) -> None:
        """
        Takes a snapshot of the asset's attributes.
        
        :param simulate_until: the date marking the end of of this simulation period.
        """
        self.history.append(AssetSnapshot(
            date=simulate_until,
            balance=self.balance,
            defaulted_principal=self.defaulted_principal,
            scheduled_principal=self.scheduled_principal,
            unscheduled_principal=self.unscheduled_principal,
            principal_paid=self.principal_paid,
            interest_paid=self.interest_paid,
            interest_accrued=self.interest_accrued,
            period_accrual=self.period_accrual,
            recovered_principal=self.recovered_principal,
            interest_rate=self.coupon,
        ))
