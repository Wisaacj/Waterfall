from datetime import date
from pyxirr import DayCount

from .account import Account
from .interest_vehicle import InterestVehicle
from .snapshots import *
from .enums import *
from .forward_rate_curve import ForwardRateCurve


class Tranche(InterestVehicle):
    """
    Class representing a Tranche of a structured credit security.
    """
    def __init__(
        self,
        rating: str,
        balance: float,
        margin: float,
        initial_coupon: float,
        report_date: date,
        is_fixed_rate: bool = False,
        forward_rate_curve: ForwardRateCurve = None,
        day_count: DayCount = DayCount.ACT_360,
    ):
        """
        Instantiates a Tranche.
        
        :param rating: the seniority of the tranche.
        :param balance: the tranche's principal balance.
        :param margin: the margin above an index rate paid on the tranche.
        :param report_date: the date the structured deal report was generated on.
        """
        super().__init__(balance, initial_coupon, report_date, day_count)
        
        self.rating = rating
        self.initial_balance = balance
        self.is_fixed_rate = is_fixed_rate
        self.forward_rate_curve = forward_rate_curve
        self.margin = margin
        
        self.deferred_interest = 0
        self.clo_call_date = date(9999, 12, 31)
        
        # NOTE: This is incorrect. We need to backdate accrued interest on the tranche 
        # like we do the in assets & then take a snapshot. This takes a snapshot *before*
        # we backdate the accrued interest.
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
        return self.rating == 'Equity'
    
    def simulate(self, simulate_until: date):
        """
        Simulates the tranche until the given date.
        
        :param simulate_until: as the rating suggests.
        """
        accrue_until = min(simulate_until, self.clo_call_date)
        year_factor = self.calc_year_factor(accrue_until)
        self.accrue_interest(year_factor)

        self.take_snapshot(simulate_until)

        self.period_accrual = 0
        self.last_simulation_date = accrue_until

    def notify_of_liquidation(self, liquidation_date: date):
        """
        Notifies the tranche that the CLO will be liquidated shortly.
        """
        self.clo_call_date = liquidation_date

    def update_coupon(self, fixing_date: date):
        """
        Updates the coupon rate for floating rate tranches.

        This method updates the coupon rate of the tranche if it's a floating rate tranche.
        For fixed rate tranches, this method does nothing.

        :param fixing_date: The date used to determine the new base rate.

        Note:
        - For floating rate tranches, the new coupon is calculated as the sum of:
          1. The forward rate obtained from the forward_rate_curve for the given fixing_date
          2. The tranche's margin
        - For fixed rate tranches, the coupon remains unchanged
        """
        if not self.is_fixed_rate:
            base_rate = self.forward_rate_curve.get_rate(fixing_date)
            self.interest_rate = base_rate + self.margin
    
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
            
    def take_snapshot(self, as_of_date: date):
        """
        Takes a snapshot of this Tranche's attributes.
        
        :param as_of_date: the date the snapshot is taken on.
        :param initial: a bool indicating whether this is the initial snapshot of the tranche's attributes or not.
        """
        snapshot = TrancheSnapshot(
            date = as_of_date,
            coupon = self.interest_rate,
            balance = self.balance,
            interest_accrued = self.interest_accrued,
            deferred_interest = self.deferred_interest,
            interest_accrued_over_period = self.period_accrual,
        )
        self.history.append(snapshot)