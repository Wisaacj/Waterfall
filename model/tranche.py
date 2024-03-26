from datetime import date
from dateutil.relativedelta import relativedelta

from .account import Account
from .interest_vehicle import InterestVehicle
from .snapshots import *
from .enums import *


class Tranche(InterestVehicle):
    """
    Class representing a Tranche of a structured credit security.
    """
    def __init__(
        self,
        rating: str,
        balance: float,
        coupon: float,
        report_date: date,
    ):
        """
        Instantiates a Tranche.
        
        :param rating: the seniority of the tranche.
        :param balance: the tranche's principal balance.
        :param coupon: the coupon paid on the tranche.
        :param report_date: the date the structured deal report was generated on.
        """
        super().__init__(balance, coupon)
        
        self.rating = rating
        self.initial_balance = balance
        
        self.deferred_interest = 0
        self.last_simulation_date = report_date
        
        # Take a snapshot of the initial values of the tranche's attributes.
        self.take_snapshot(report_date)
        
    def __str__(self) -> str:
        """
        Overrides the default __str__ method for this class.
        """
        return self.rating
    
    @property
    def last_interest_payment(self) -> float:
        """
        Returns the last interest payment.
        """
        return self.last_snapshot.interest_paid
    
    @property
    def last_principal_payment(self) -> float:
        """
        Returns the last principal payment.
        """
        return self.last_snapshot.principal_paid
    
    @property
    def is_equity_tranche(self) -> bool:
        """
        Returns whether the tranche is an equity tranche or not.
        """
        return self.get_waterfall_item() == WaterfallItem.Equity
    
    def simulate(self, simulate_until: date):
        """
        Simulates the tranche until the given date.
        
        :param simulate_until: as the rating suggests.
        """
        if simulate_until == self.last_simulation_date:
            return
        
        year_factor = self.calc_year_factor(simulate_until)
        self.accrue_interest(year_factor)

        self.take_snapshot(simulate_until)

        self.period_accrual = 0
        self.last_simulation_date = simulate_until
    
    def accrue_interest(self, year_factor: float):
        """
        Overrides the parent class' implementation of this method. Tranches accrue
        interest on both their balance and any deffered interest.
        
        :param year_factor: the proportion of the year to calculate interest for.
        """
        accrual = (self.balance + self.deferred_interest) * year_factor * self.interest_rate
        self.interest_accrued += accrual
        self.period_accrual += accrual
    
    def pay_interest(self, source: Account, attribute_source: PaymentSource):
        """
        Pays the accrued interest on the tranche.
        
        :param source: an Account to debit from.
        :param attribute_source: this is not used and is only here to satisfy calls from CashflowWaterfalls.
        """
        # Debit as much of the deferred interest as possible.
        deferred_paid = source.request_debit(self.deferred_interest)
        self.deferred_interest -= deferred_paid
        self.interest_paid += deferred_paid

        # Debit as much of the accrued interest as possible.        
        accrued_paid = source.request_debit(self.interest_accrued)
        self.interest_accrued -= accrued_paid
        self.interest_paid += accrued_paid
        
        # Log the interest payments in the snapshot history.
        self.last_snapshot.deferred_interest_paid += deferred_paid
        self.last_snapshot.interest_paid += deferred_paid + accrued_paid
        
        # If, after paying the interest, we still have interest left over,
        # we must add this to the deferred interest.
        if self.interest_accrued > 0:
            self.deferred_interest += self.interest_accrued
            self.last_snapshot.deferred_interest_accrued_over_period = self.interest_accrued
            self.interest_accrued = 0
    
    def pay_principal(self, source: Account, attribute_source: PaymentSource):
        """
        Pays off the tranche's principal using the source Account's balance.
        
        :param source: an Account to debit from.
        :param attribute_source: the source of principal monies to attribute the payment to.
        """        
        amount_paid = source.request_debit(self.balance)
        self.balance -= amount_paid
        self.principal_paid += amount_paid
        
        pct_principal = (amount_paid / self.initial_balance) if self.initial_balance > 0 else 0
        
        self.last_snapshot.balance = self.balance
        self.last_snapshot.principal_paid += amount_paid
        self.last_snapshot.pct_principal += pct_principal
        
        # This performs snapshot.attribute_source = pct_principal.
        setattr(self.last_snapshot, attribute_source.value, pct_principal)

    def get_waterfall_item(self, _wi = WaterfallItem):
        """
        Returns the waterfall item that the tranche rating maps onto.
        
        :param _wi: this is in the method signature to save instantiating _wi every time the method is called.
        :return: the waterfall item that maps onto this tranche.
        """
        tranche_rating_map = {
            'AAA': _wi.AAA,
            'AA': _wi.AA,
            'A': _wi.A,
            'BBB': _wi.BBB,
            'BB': _wi.BB,
            'B': _wi.B,
            'EQTY': _wi.Equity,
            'Equity': _wi.Equity
        }
        
        if self.rating not in tranche_rating_map:
            raise Exception(f"Enum exception: Tranche '{self.rating}' doesn't map onto an enum WaterfallItems.")
        
        return tranche_rating_map[self.rating]
            
    def take_snapshot(self, as_of_date: date):
        """
        Takes a snapshot of this Tranche's attributes.
        
        :param as_of_date: the date the snapshot is taken on.
        :param initial: a bool indicating whether this is the initial snapshot of the tranche's attributes or not.
        """
        snapshot = TrancheSnapshot(
            date = as_of_date,
            coupon = self.coupon,
            balance = self.balance,
            interest_accrued = self.interest_accrued,
            deferred_interest = self.deferred_interest,
            interest_accrued_over_period = self.period_accrual,
        )
        self.history.append(snapshot)