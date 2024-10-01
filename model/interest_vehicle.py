import pyxirr

from datetime import date
from pyxirr import DayCount
from .snapshots import Snapshot


class InterestVehicle:
    """
    Class representing a simple financial vehicle which accrues interest.
    """
    def __init__(self, balance: float, interest_rate: float, 
                 last_simulation_date: date = None, day_count: DayCount = DayCount.ACT_360):
        """
        Instantiates an InterestVehicle.
        
        :param balance: the initial balance of the vehicle.
        :param interest_rate: the rate at which the vehicle accrues interest.
        :param last_simulation_date: the last time the vehicle was simulated.
        """
        self.balance = balance
        self.interest_rate = interest_rate
        self.last_simulation_date = last_simulation_date
        self.day_count = day_count
        
        # Earnings can be collected (swept) by other objects.
        self.interest_paid = 0 
        self.principal_paid = 0 
        self.interest_accrued = 0
        self.period_accrual = 0
        
        self.history: list[Snapshot] = []
    
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
            return pyxirr.year_fraction(from_date, to_date, self.day_count)
        
        # If a from_date is not provided, default it to the last_simulation_date.
        return pyxirr.year_fraction(self.last_simulation_date, to_date, self.day_count)
    
    def accrue_interest(self, year_factor: float) -> None:
        """
        Accrues interest on the balance for a given period
        
        :param year_factor: a period of time to accrue interest, expressed as a percentage of a year.
        """
        accrual = self.balance * year_factor * self.interest_rate
        self.interest_accrued += accrual
        self.period_accrual += accrual

    def irr(self, purchase_price: float) -> float:
        """
        Calculates the IRR of the vehicle.
        
        :param purchase_price: the price at which the vehicle was purchased.
        :return: the IRR of the vehicle.
        """
        orig_balance = self.history[0].balance
        purchase_cost = -1 * (purchase_price * orig_balance)
        cashflows = [snapshot.interest_paid + snapshot.principal_paid 
                     for snapshot in self.history]
        cashflows[0] += purchase_cost
        dates = [snapshot.date for snapshot in self.history]

        return pyxirr.xirr(dates, cashflows)
