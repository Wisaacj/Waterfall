import argparse

from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from datetime import date
from model.enums import LiquidationType


@dataclass
class Arguments:
    cpr: float
    cdr: float
    cpr_lockout_months: int
    cdr_lockout_months: int
    recovery_rate: float
    payment_frequency: int
    simulation_frequency: int
    rp_extension_months: int
    reinvestment_maturity_months: int
    wal_limit_years: float
    output_path: Path
    output_asset_cashflows: bool
    liquidation_type: LiquidationType
    use_top_down_defaults: bool
    deal_id: Optional[str] = None
    accrual_date: Optional[date] = None
    liquidation_date: Optional[date] = None


class CLOArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._add_clo_arguments()

    def into(self) -> Arguments:
        return Arguments(**vars(self.parse_args()))
    
    def add_deal_id_argument(self):
        self.add_argument("--deal_id", required=True, type=str, help="The ID of the deal to simulate.")

    def _add_clo_arguments(self):
        self.add_argument("--cpr", type=float, default=0.20, help="Constant Prepayment Rate (default: 0.20)")
        self.add_argument("--cdr", type=float, default=0.02, help="Constant Default Rate (default: 0.02)")
        self.add_argument("--cpr_lockout_months", type=int, default=0, help="Number of months to lock out CPR (default: 0)")
        self.add_argument("--cdr_lockout_months", type=int, default=0, help="Number of months to lock out CDR (default: 0)")
        self.add_argument("--recovery_rate", type=float, default=0.70, help="Recovery rate (default: 0.70)")
        self.add_argument("--payment_frequency", type=int, default=4, help="Payment frequency (default: 4)")
        self.add_argument("--simulation_frequency", type=int, default=12, help="Simulation frequency (default: 12)")
        self.add_argument("--rp_extension_months", type=int, default=0, help="Reinvestment period extension in months (default: 0)")
        self.add_argument("--reinvestment_maturity_months", type=int, default=72, help="Reinvestment asset maturity in months (default: 72)")
        self.add_argument("--wal_limit_years", type=int, default=6, help="WAL limit in years (default: 6)")
        self.add_argument("--output_path", type=Path, default=Path("outputs"), help="Path to save the output files (default: ./outputs)")
        self.add_argument("--output_asset_cashflows", type=bool, default=True, help="Output asset cashflows to CSV (default: True)")
        self.add_argument("--liquidation_type", type=LiquidationType, choices=list(LiquidationType), default=LiquidationType.NAV90, help="Type of liquidation pricing to use (default: NAV)")
        self.add_argument("--use_top_down_defaults", action="store_true", help="Use top-down defaults (default: False)")
