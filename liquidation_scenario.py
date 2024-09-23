import argparse
import data_source

from pathlib import Path
from datetime import date
from factories import CLOFactory
from results_writer import ResultsWriter
from dateutil.relativedelta import relativedelta


def main():
    parser = argparse.ArgumentParser(description="Simulate interest accrued on a portfolio of assets underlying a CLO.")
    parser.add_argument("--deal_id", required=True, type=str, help="The ID of the deal to simulate.")
    parser.add_argument("--accrual_date", required=True, type=lambda s: date.fromisoformat(s),  help="Accrual date in ISO format YYYY-MM-DD (default: 9999-12-31)")
    parser.add_argument("--liquidation_date", required=True, type=lambda s: date.fromisoformat(s), help="Liquidation date in ISO format YYYY-MM-DD (default: 9999-12-31)")

    # Add arguments for each assumption
    parser.add_argument("--cpr", type=float, default=0.0, help="Constant Prepayment Rate (default: 0.0)")
    parser.add_argument("--cdr", type=float, default=0.0, help="Constant Default Rate (default: 0.0)")
    parser.add_argument("--recovery_rate", type=float, default=1.0, help="Recovery rate (default: 1.0)")    
    parser.add_argument("--payment_frequency", type=int, default=4, help="Payment frequency (default: 4)")
    parser.add_argument("--simulation_frequency", type=int, default=12, help="Simulation frequency (default: 12)")
    parser.add_argument("--reinvestment_asset_maturity_months", type=int, default=72, help="Reinvestment asset maturity in months (default: 72)")
    parser.add_argument("--output_path", type=Path, default=Path("outputs"), help="Path to save the output files (default: ./outputs)")

    args = parser.parse_args()

    deal_id = args.deal_id.upper()
    accrual_date = args.accrual_date
    liquidation_date = args.liquidation_date

    print(f"\nLoading deal, tranche, & loan data for {deal_id} from disk...")
    deal, loans, tranches = data_source.load_deal_data(deal_id)
    print(f"    > Loaded deal data")

    print(f"\nLoading forward rate curves from US Oracle DB...")
    forward_curves = data_source.load_latest_forward_curves()
    print(f"    > Loaded rate curves")

    print(f"Building model of {deal_id}...")
    factory = CLOFactory(
        deal, tranches, loans, args.cpr, args.cdr, args.recovery_rate,
        args.payment_frequency, args.simulation_frequency, args.reinvestment_asset_maturity_months
    )
    model = factory.build()
    print("    > Model built")

    print(f"Running scenario: Selling portfolio on {accrual_date} and liquidating {deal_id} on {liquidation_date}...")
    model.liquidate(accrual_date, liquidation_date)
    print("    > Scenario simulation complete")
    
    print("Writing results to disk...")
    path = ResultsWriter(model, args.deal_id, args.output_path).write_results()
    print(f"    > Results written to '{path}'\n")


def debug():
    deal_id = "SCULE7"
    accrual_date = date.today() + relativedelta(days=14)
    liquidation_date = date(2024, 10, 15)

    print(f"\nLoading deal, tranche, & loan data for {deal_id} from disk...")
    deal, loans, tranches = data_source.load_deal_data(deal_id)
    print(f"    > Loaded deal data")

    print(f"\nLoading the latest forward-rate curves from your DB (US Oracle)...")
    forward_curves = data_source.load_latest_forward_curves()
    print(f"    > Loaded rate curves")

    print(f"Building a model of {deal_id}...")
    factory = CLOFactory(deal, tranches, loans, forward_curves, 0, 0, 1, 4, 12, 72)
    model = factory.build()
    print("    > Model built")

    print(f"Running scenario: Selling portfolio on {accrual_date} and liquidating {deal_id} on {liquidation_date}...")
    model.liquidate(accrual_date, liquidation_date)
    print("    > Scenario simulation complete")
    
    print("Writing results to disk...")
    path = ResultsWriter(model, deal_id).write_results()
    print(f"    > Results written to '{path}'\n")


if __name__ == "__main__":
    debug()