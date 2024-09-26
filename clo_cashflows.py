import argparse
import data_source

from pathlib import Path
from factories import CLOFactory
from results_writer import ResultsWriter


def main():
    parser = argparse.ArgumentParser(description="Simulate CLO cashflows to maturity based on provided assumptions.")
    parser.add_argument("--deal_id", required=True, type=str, help="The ID of the deal to simulate.")
    
    # Add arguments for each assumption
    parser.add_argument("--cpr", type=float, default=0.20, help="Constant Prepayment Rate (default: 0.20)")
    parser.add_argument("--cpr_lockout_months", type=int, default=0, help="Number of months to lock out CPR (default: 0)")
    parser.add_argument("--cdr", type=float, default=0.01, help="Constant Default Rate (default: 0.01)")
    parser.add_argument("--cdr_lockout_months", type=int, default=0, help="Number of months to lock out CDR (default: 0)")
    parser.add_argument("--recovery_rate", type=float, default=0.50, help="Recovery rate (default: 0.50)")
    parser.add_argument("--payment_frequency", type=int, default=4, help="Payment frequency (default: 4)")
    parser.add_argument("--simulation_frequency", type=int, default=12, help="Simulation frequency (default: 12)")
    parser.add_argument("--rp_extension_months", type=int, default=0, help="Reinvestment period extension in months (default: 0)")
    parser.add_argument("--reinvestment_asset_maturity_months", type=int, default=72, help="Reinvestment asset maturity in months (default: 72)")
    parser.add_argument("--output_path", type=Path, default=Path("outputs"), help="Path to save the output files (default: ./outputs)")
    parser.add_argument("--output_asset_cashflows", type=bool, default=True, help="Output asset cashflows to CSV (default: True)")
    
    args = parser.parse_args()
    deal_id = args.deal_id.upper()

    print(f"\nLoading deal, tranche, & loan data for {deal_id} from disk...")
    deal, loans, tranches = data_source.load_deal_data(deal_id)
    print(f"    > Loaded deal data")

    print(f"Loading the latest forward-rate curves from DB (US Oracle)...")
    forward_curves = data_source.load_latest_forward_curves()
    print(f"    > Loaded rate curves")

    print(f"Building a model of {deal_id}...")
    factory = CLOFactory(
        deal, tranches, loans, forward_curves, args.cpr, args.cdr, 
        args.cpr_lockout_months, args.cdr_lockout_months, args.recovery_rate,
        args.payment_frequency, args.simulation_frequency, args.reinvestment_asset_maturity_months,
        args.rp_extension_months
    )
    model = factory.build()
    print("    > Model built")

    print(f"Running scenario: Simulating cashflows for {deal_id} to maturity...")
    model.simulate()
    print("    > Cashflows simulated")

    path = ResultsWriter(model, args.deal_id, args.output_path).write_tranche_cashflows()
    print(f"    > Tranche cashflows written to '{path}'")

    if args.output_asset_cashflows:
        path = ResultsWriter(model, args.deal_id, args.output_path).write_asset_cashflows()
        print(f"    > Asset cashflows written to '{path}'\n")


if __name__ == "__main__":
    main()
