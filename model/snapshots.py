"""
Snapshots of model attributes.

These classes are wrapped in 'dataclass', which makes them function somewhat like
a Struct in C, but the resulting object is mutable and can have default values.
"""
from datetime import date
from dataclasses import dataclass


@dataclass
class Snapshot:
    """Represents a snapshot of an object's attributes."""
    date: date


@dataclass
class CLOSnapshot(Snapshot):
    """Represents a snapshot of a CLO."""
    equity_liquidation_value: float = 0
    total_debt_tranches_balance: float = 0
    total_asset_balance: float = 0
    interest_swept: float = 0
    interest_account_balance: float = 0
    principal_swept: float = 0
    principal_account_balance: float = 0
    principal_reinvested: float = 0

    
@dataclass
class AssetSnapshot(Snapshot):
    """Represents a snapshot of an Asset."""
    balance: float
    principal_paid: float
    interest_paid: float
    scheduled_principal: float
    unscheduled_principal: float
    defaulted_principal: float
    recovered_principal: float
    period_accrual: float
    interest_accrued: float
    interest_rate: float
    
    
@dataclass
class TrancheSnapshot(Snapshot):
    """Represents a snapshot of a Tranche."""
    balance: float = 0
    interest_paid: float = 0
    interest_accrued: float = 0
    interest_accrued_over_period: float = 0
    deferred_interest: float = 0
    deferred_interest_paid: float = 0
    deferred_interest_accrued_over_period: float = 0
    principal_paid: float = 0
    pct_principal: float = 0
    pct_amortization: float = 0
    coupon: float = 0
    
    
@dataclass
class FeeSnapshot(Snapshot):
    """Represents a snapshot of a Fee."""
    balance: float
    period_accrual: float = 0
    accrued: float = 0
    paid: float = 0