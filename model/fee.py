from datetime import date

from .enums import PaymentSource, WaterfallItem
from .interest_vehicle import InterestVehicle
from .snapshots import FeeSnapshot
from .account import Account


class Fee(InterestVehicle):
    """
    Class representing a fee with an interest rate and fixed component.
    """
    def __init__(self, balance: float, coupon: float, report_date: date, fee_name: WaterfallItem):
        """
        Instantiates a Fee.
        
        :param balance: the fee's initial balance.
        :param coupon: the rate at which the fee accrues interest.
        :param report_date: the date the deal report was generated on.
        :param fee_name: the type of fee.
        :param fixedExpense: an optional annual fixed expense.
        """
        super().__init__(balance, coupon, report_date)
        
        self.name = fee_name.value
        
        # Take a snapshot of the inital values of the fee's attributes.
        self.take_snapshot(report_date)
        
    def __str__(self) -> str:
        """Returns the fee's type."""
        return self.name
    
    def simulate(self, simulate_until: date):
        """
        Simulates from the last simulation date until the given date.
        
        :param simulate_until: as the name suggests.
        """
        if simulate_until == self.last_simulation_date: 
            return      
        
        self.accrue(self.calc_year_factor(simulate_until))
        self.take_snapshot(simulate_until)
        
        self.last_simulation_date = simulate_until
        self.period_accrual = 0        
    
    def accrue(self, yearFactor: float):
        """
        Extends the parent class' implementation by also adding a yearFactor adjusted
        fixed expense to the `interest_accrued`.
        
        :param yearFactor: a period of time to accrue interst, expressed as a percentage of a year.
        """
        super().accrue_interest(yearFactor)
    
    def pay(self, source: Account, attribute_source: PaymentSource):
        """
        Attempts to pay the amount accrued on the fee.
        
        :param source: an interest account to debit from.
        :param attribute_source: this is not used and is only here to satisfy calls from CashflowWaterfalls.
        """
        amount_paid = source.request_debit(self.interest_accrued)
        self.interest_accrued -= amount_paid
        self.interest_paid += amount_paid
        
        self.log_payment_in_history(amount_paid)
        
    def log_payment_in_history(self, payment: float):
        """
        Sums the given payment with the amount paid in the most recent snapshot in the history
        
        :param payment: an amount to log.
        """
        self.last_snapshot.paid += payment
    
    def take_snapshot(self, asOfDate: date):
        """
        Takes a snapshot of the fee's attributes on `asOfDate`.
        
        :param asOfDate: the date the snapshot is taken on.
        """
        self.history.append(FeeSnapshot(
            date = asOfDate,
            balance = self.balance,
            period_accrual = self.period_accrual,
            accrued = self.interest_accrued
        ))