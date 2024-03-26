import os
import argparse
import pandas as pd

from datetime import date
from clo_factory import CLOFactory
from results_writer import ResultsWriter


# Data
DATA_DIR = "./data"
DEALS_CSV = os.path.join(DATA_DIR, "deals.csv")
LOANS_CSV = os.path.join(DATA_DIR, "loans.csv")
TRANCHES_CSV = os.path.join(DATA_DIR, "tranches.csv")


def load_data(deal_id: str):
    deals = pd.read_csv(DEALS_CSV)
    loans = pd.read_csv(LOANS_CSV)
    tranches = pd.read_csv(TRANCHES_CSV)

    # Filter for the relevant deal.
    deals = deals[deals['deal_id'] == deal_id]
    loans = loans[loans['deal_id'] == deal_id]
    tranches = tranches[tranches['deal_id'] == deal_id]

    # Ignore equity assets.
    loans = loans[loans['type'] != 'Equity']
    # Fill NaNs.
    tranches.fillna({'margin': 0}, inplace=True)
    # Convert `deals` to a series.
    deal = deals.iloc[0]

    return deal, loans, tranches

def main():
    parser = argparse.ArgumentParser(description="Simulate CLO cashflows based on provided parameters.")
    parser.add_argument("--deal_id", required=True, type=str, help="The ID of the deal to simulate.")
    
    # Add arguments for each assumption
    parser.add_argument("--cpr", type=float, default=0.20, help="Constant Prepayment Rate (default: 0.20)")
    parser.add_argument("--cdr", type=float, default=0.01, help="Constant Default Rate (default: 0.01)")
    parser.add_argument("--recovery_rate", type=float, default=0.50, help="Recovery rate (default: 0.50)")
    parser.add_argument("--payment_frequency", type=int, default=4, help="Payment frequency (default: 4)")
    parser.add_argument("--simulation_interval", type=int, default=1, help="Simulation interval in months (default: 1)")
    parser.add_argument("--senior_management_fee", type=float, default=0.003, help="Senior management fee (default: 0.003)")
    parser.add_argument("--junior_management_fee", type=float, default=0.002, help="Junior management fee (default: 0.002)")
    parser.add_argument("--call_date", type=lambda s: date.fromisoformat(s), default=date(9999, 12, 31), help="Call date in ISO format YYYY-MM-DD (default: 9999-12-31)")
    parser.add_argument("--reinvestment_asset_maturity_months", type=int, default=72, help="Reinvestment asset maturity in months (default: 72)")
    
    args = parser.parse_args()
    args.deal_id = args.deal_id.upper()

    # Load data from disk.
    deal, loans, tranches = load_data(args.deal_id)

    print("Building CLO model...")
    factory = CLOFactory(
        deal, tranches, loans, args.cpr, args.cdr, args.recovery_rate,
        args.payment_frequency, args.simulation_interval, args.senior_management_fee, 
        args.junior_management_fee, args.call_date, args.reinvestment_asset_maturity_months
    )
    model = factory.build()
    print("> CLO model built.")

    print("Running cashflows...")
    model.simulate()
    print("> Cashflows simulated.")

    print("Writing results to disk...")
    path = ResultsWriter(model, args.deal_id).write_results()
    print(f"> Results written to '{path}'")


if __name__ == "__main__":
    main()
