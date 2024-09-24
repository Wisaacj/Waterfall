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


class AssetKind(Enum):
    """
    Enumerates the possible kinds of assets.
    """
    Loan = "loan"
    Bond = "bond"

    @classmethod
    def from_string(cls, value: str) -> "AssetKind":
        if value.lower() == "loan":
            return cls.Loan
        elif value.lower() == "bond":
            return cls.Bond
        else:
            raise ValueError(f"Invalid asset kind: {value}")


class AssetType(Enum):
    """
    Enumerates the possible types of assets.
    """
    FloatingRate = "floating"
    FixedRate = "fixed"
