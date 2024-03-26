from enum import Enum, auto


class WaterfallItem(Enum):
    """
    Enumerates the possible items that could be in a cashflow waterfall.
    """
    AAA = "AAA"
    AA = "AA"
    A = "A"
    BBB = "BBB"
    BB = "BB"
    B = "B"
    Equity = "Equity"
    SeniorExpensesFee = "SeniorExpensesFee"
    SeniorMgmtFee = "SeniorMgmtFee"
    JuniorMgmtFee = "JuniorMgmtFee"
    IncentiveFee = "IncentiveFee"


class PaymentSource(Enum):
    """
    Enumerates the possible sources of monies in a payment.
    """
    Interest = ""
    Amortization = "pct_amortization"