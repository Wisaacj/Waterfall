from datetime import date

from .tranche import Tranche
from .account import Account
from .enums import PaymentSource


class EquityTranche(Tranche):
    """
    Class repesenting an equity tranche of a structured credit security.
    """
    def __init__(self, balance: float, report_date: date):
        """
        Instantiates an EquityTranche.
        
        :param balance: the balance of the tranche as of the report_date.
        :param report_date: the date the deal report was generated on.
        """
        super().__init__('Equity', balance, margin=0, initial_coupon=0, report_date=report_date)
                
    def pay_interest(self, source: Account, attribute_source: PaymentSource):
        """
        As this is the equity tranche, we want to empty the source account: it is entitled
        to all residual monies.
        
        :param source: an Account to debit from.
        :param attribute_source: this is not used and is only here to satisfy calls from CashflowWaterfalls.
        """        
        # Debit the entire account.
        amount_earned = source.request_debit(source.balance)
        self.interest_paid += amount_earned
        
        # Log the payment.
        self.last_snapshot.interest_paid += amount_earned
    
    def pay_principal(self, source: Account, attribute_source: PaymentSource):
        """
        As this is the equity tranche, we want to empty the source principal account EVEN
        after all the principal in the equity tranche has been paid off. It collects all
        residual monies.
        
        :param source: an Account to debit from.
        :param attribute_source: this is not used and is only here to satisfy calls from CashflowWaterfalls.
        """
        # Debit the entire account.
        amount_paid = source.request_debit(source.balance) 
        self.balance -= amount_paid
        self.balance = max(self.balance, 0) # Balance can't be below 0.
        
        # Log the payment.
        self.last_snapshot.principal_paid += amount_paid
        self.last_snapshot.balance -= amount_paid
        