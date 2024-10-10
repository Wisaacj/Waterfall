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
    SeniorExpensesFee = "Senior Expenses Fee"
    SeniorMgmtFee = "Senior Mgmt Fee"
    JuniorMgmtFee = "Junior Mgmt Fee"
    IncentiveFee = "Incentive Fee"


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

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_string(cls, value: str) -> "AssetKind":
        try:
            return AssetKind(value.lower())
        except ValueError:
            raise ValueError(f"'{value}' is not a valid AssetKind")


class AssetType(Enum):
    """
    Enumerates the possible types of assets.
    """
    FloatingRate = "floating"
    FixedRate = "fixed"


class LiquidationType(Enum):
    """
    Enumerates the possible types of liquidation.
    """
    MARKET = "market"
    NAV90 = "nav90"
    OVERRIDE = "override"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_string(cls, value: str) -> "LiquidationType":
        try:
            return LiquidationType(value.lower())
        except ValueError:
            raise ValueError(f"'{value}' is not a valid LiquidationType")
