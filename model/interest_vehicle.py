from . import settings
from .snapshots import Snapshot

from datetime import date


class InterestVehicle:
    """
    Class representing a simple financial vehicle which accrues interest.
    """
    def __init__(self, balance: float, interest_rate: float, last_simulation_date: date = None):
        """
        Instantiates an InterestVehicle.
        
        :param balance: the initial balance of the vehicle.
        :param interest_rate: the rate at which the vehicle accrues interest.
        :param last_simulation_date: the last time the vehicle was simulated.
        """
        self.balance = balance
        self.interest_rate = interest_rate
        self.last_simulation_date = last_simulation_date
        
        # Earnings can be collected (swept) by other objects.
        self.interest_paid = 0 
        self.principal_paid = 0 
        self.interest_accrued = 0
        self.period_accrual = 0
        
        self.history: list[Snapshot] = []
        
    @property
    def coupon(self):
        """
        An alias of interest rate.
        """
        return self.interest_rate
    
    @property
    def spread(self):
        """
        An alias of interest rate.
        """
        return self.interest_rate
    
    @property
    def margin(self):
        """
        An alias of interest rate.
        """
        return self.interest_rate
    
    @property
    def last_snapshot(self) -> Snapshot:
        """
        Returns the last snapshot in history. As history is list of Snapshots 
        are dataclasses, which are both mutable, thus updating this updates the underlying snapshot.
        """
        return self.history[-1]
    
    def calc_year_factor(self, to_date: date, from_date: date = None) -> float:
        """
        Calculates the proportion of a year between two dates according to some day counter.
        
        :param to_date: the end of the date interval.
        :param from_date: the start of the date interval.
        :return: the year factor.
        """
        if from_date is not None:
            return (to_date - from_date).days / settings.DCF_DENOMINATOR
        
        # If a from_date is not provided, default it to the last_simulation_date. 
        return (to_date - self.last_simulation_date).days / settings.DCF_DENOMINATOR
    
    def accrue_interest(self, yearFactor: float) -> None:
        """
        Accrues interest on the balance for a given period
        
        :param yearFactor: a period of time to accrue interest, expressed as a percentage of a year.
        """
        accrual = self.balance * yearFactor * self.interest_rate
        self.interest_accrued += accrual
        self.period_accrual += accrual