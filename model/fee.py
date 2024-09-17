from datetime import date

from .enums import PaymentSource, WaterfallItem
from .interest_vehicle import InterestVehicle
from .snapshots import FeeSnapshot
from .account import Account


class Fee(InterestVehicle):
    """
    Class representing a fee with an interest rate and fixed component.
    """
    def __init__(self, balance: float, coupon: float, report_date: date, fee_name: WaterfallItem, fixed_expense: float = 0):
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
        self.fixed_expense = fixed_expense
        self.clo_call_date = date(9999, 12, 31)
        
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
        accrue_until = min(simulate_until, self.clo_call_date)
        year_factor = self.calc_year_factor(accrue_until)

        self.accrue(year_factor)
        self.take_snapshot(simulate_until)
        
        self.last_simulation_date = accrue_until
        self.period_accrual = 0        
    
    def accrue(self, year_factor: float):
        """
        Extends the parent class' implementation by also adding a year_factor adjusted
        fixed expense to the `interest_accrued`.
        
        :param year_factor: a period of time to accrue interst, expressed as a percentage of a year.
        """
        super().accrue_interest(year_factor)

        period_fixed_expense = year_factor * self.fixed_expense
        self.interest_accrued += period_fixed_expense
        self.period_accrual += period_fixed_expense
    
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

    def notify_of_liquidation(self, liquidation_date: date):
        """
        Notifies the fee that the CLO will be liquidated shortly.
        """
        self.clo_call_date = liquidation_date
        
    def log_payment_in_history(self, payment: float):
        """
        Sums the given payment with the amount paid in the most recent snapshot in the history
        
        :param payment: an amount to log.
        """
        self.last_snapshot.paid += payment
    
    def take_snapshot(self, as_of_date: date):
        """
        Takes a snapshot of the fee's attributes on `as_of_date`.
        
        :param as_of_date: the date the snapshot is taken on.
        """
        self.history.append(FeeSnapshot(
            date = as_of_date,
            balance = self.balance,
            period_accrual = self.period_accrual,
            accrued = self.interest_accrued
        ))


class IncentiveFee(Fee):
    """
    Class representing an incentive fee.
    """
    def __init__(self, balance: float, irr_hurdle_rate: float, diversion_rate: float, report_date: date):
        super().__init__(balance, irr_hurdle_rate, report_date, WaterfallItem.IncentiveFee)
        self.diversion_rate = diversion_rate

    @property
    def irr_hurdle_rate(self):
        """
        An alias for interest rate.
        """
        return self.interest_rate
    
    def accrue(self, year_factor: float):
        """
        Overrides the superclass implementation to increase the balance by the period accrual.
        """
        accrual = self.balance * year_factor * self.irr_hurdle_rate
        self.balance += accrual
        self.period_accrual += accrual

    def pay(self, source: Account, attribute_source: PaymentSource):
        """
        Pays an incentive fee once the balance crosses 0, at which point interest
        is diverted from the equity holders to the CLO manager.
        """
        diverted_funds = source.request_debit(source.balance)
        self.balance -= diverted_funds

        # Amount diverted from the equity distribution.
        payment = max(-self.balance, 0) * self.diversion_rate

        # Credit the residual back to the source account.
        source.credit(diverted_funds - payment)

        # Floor the balance at 0.
        self.balance = max(self.balance, 0)

        self.log_payment_in_history(payment)