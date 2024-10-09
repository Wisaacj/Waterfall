import argparse
from pathlib import Path


def add_clo_assumptions(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """
    Adds arguments for the CLO assumptions.
    """
    parser.add_argument("--cpr", type=float, default=0.20, help="Constant Prepayment Rate (default: 0.20)")
    parser.add_argument("--cpr_lockout_months", type=int, default=0, help="Number of months to lock out CPR (default: 0)")
    parser.add_argument("--cdr", type=float, default=0.01, help="Constant Default Rate (default: 0.01)")
    parser.add_argument("--cdr_lockout_months", type=int, default=0, help="Number of months to lock out CDR (default: 0)")
    parser.add_argument("--recovery_rate", type=float, default=0.50, help="Recovery rate (default: 0.50)")
    parser.add_argument("--payment_frequency", type=int, default=4, help="Payment frequency (default: 4)")
    parser.add_argument("--simulation_frequency", type=int, default=12, help="Simulation frequency (default: 12)")
    parser.add_argument("--rp_extension_months", type=int, default=0, help="Reinvestment period extension in months (default: 0)")
    parser.add_argument("--wal_limit_years", type=int, default=6, help="WAL limit in years (default: 6)")
    parser.add_argument("--reinvestment_maturity_months", type=int, default=72, help="Reinvestment asset maturity in months (default: 72)")
    parser.add_argument("--output_path", type=Path, default=Path("outputs"), help="Path to save the output files (default: ./outputs)")
    parser.add_argument("--output_asset_cashflows", type=bool, default=True, help="Output asset cashflows to CSV (default: True)")
    parser.add_argument("--verbosity", type=int, default=0, help="Verbosity level (0: silent, 1: verbose)")
    return parser