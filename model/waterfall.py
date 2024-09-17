from typing import Any, Callable

from .account import Account
from .enums import PaymentSource, WaterfallItem


class CashflowWaterfall:
    """
    Class representing a cashflow waterfall.
    """
    def __init__(self, waterfall: dict[WaterfallItem, Callable[[Account, PaymentSource], Any]], order: list[WaterfallItem]):
        """
        Instantiates a cashflow waterfall.
        
        :param waterfall: the waterfall consisting of objects and their payment methods.
        :param order: the order in which the waterfall should be run.
        """
        self.waterfall = waterfall
        self.order = order
        
    def pay(self, source: Account, attribute_source: PaymentSource):
        """
        Pays the given account down the waterfall.
        
        :param source: an Account to debit from.
        :param attribute_source: the source of monies to attribute the payment to.
        :return: a bool indicating whether the transaction was successful or not.
        """
        for item in self.order:
            self.waterfall[item](source, attribute_source)