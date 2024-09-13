import argparse
import data_source

from datetime import date
from factories import CLOFactory
from results_writer import ResultsWriter


def main():
    parser = argparse.ArgumentParser(description="Simulate CLO cashflows to maturity based on provided parameters.")
    parser.add_argument("--deal_id", required=True, type=str, help="The ID of the deal to simulate.")
    
    # Add arguments for each assumption
    parser.add_argument("--cpr", type=float, default=0.20, help="Constant Prepayment Rate (default: 0.20)")
    parser.add_argument("--cdr", type=float, default=0.01, help="Constant Default Rate (default: 0.01)")
    parser.add_argument("--recovery_rate", type=float, default=0.50, help="Recovery rate (default: 0.50)")
    parser.add_argument("--payment_frequency", type=int, default=4, help="Payment frequency (default: 4)")
    parser.add_argument("--simulation_interval", type=int, default=1, help="Simulation frequency (default: 12)")
    parser.add_argument("--reinvestment_asset_maturity_months", type=int, default=72, help="Reinvestment asset maturity in months (default: 72)")
    
    args = parser.parse_args()
    args.deal_id = args.deal_id.upper()

    # Load data from disk.
    deal, loans, tranches = data_source.load_data(args.deal_id)

    print("Building CLO model...")
    factory = CLOFactory(
        deal, tranches, loans, args.cpr, args.cdr, args.recovery_rate,
        args.payment_frequency, args.simulation_frequency, args.reinvestment_asset_maturity_months
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
