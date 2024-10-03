import argparse
import common_args
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
    parser = common_args.add_clo_assumptions(parser)

    args = parser.parse_args()

    deal_id = args.deal_id.upper()
    accrual_date = args.accrual_date
    liquidation_date = args.liquidation_date

    print(f"\nLoading deal, tranche, & loan data for {deal_id} from disk...")
    deal, loans, tranches = data_source.load_deal(deal_id)
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

    print(f"Running scenario: Selling portfolio on {accrual_date} and liquidating {deal_id} on {liquidation_date}...")
    model.liquidate(accrual_date, liquidation_date)
    print("    > Scenario simulation complete")
    
    print(f"Writing results for {deal_id} to disk...")
    writer = ResultsWriter(model, deal_id, args.output_path)
    if args.output_asset_cashflows:
        writer.include_assets()
    path = writer.include_tranches().write()
    print(f"    > Results written to '{path}'\n")


def debug():
    deal_id = "SCULE7"
    accrual_date = date(2024, 9, 16) + relativedelta(days=14) # date.today() + relativedelta(days=14)
    liquidation_date = date(2024, 10, 15)

    print(f"\nLoading deal, tranche, & loan data for {deal_id} from disk...")
    deal, loans, tranches = data_source.load_deal(deal_id)
    print(f"    > Loaded deal data")

    print(f"Loading the latest forward-rate curves from DB (US Oracle)...")
    forward_curves = data_source.load_latest_forward_curves()
    print(f"    > Loaded rate curves")

    print(f"Building a model of {deal_id}...")
    factory = CLOFactory(deal, tranches, loans, forward_curves, 0, 0, 0, 0, 1, 4, 12, 72)
    model = factory.build()
    print("    > Model built")

    print(f"Running scenario: Selling portfolio on {accrual_date} and liquidating {deal_id} on {liquidation_date}...")
    model.liquidate(accrual_date, liquidation_date)
    print("    > Scenario simulation complete")
    
    print("Writing results to disk...")
    path = ResultsWriter(model, deal_id)\
        .include_tranches()\
        .include_assets()\
        .write()
    print(f"    > Results written to '{path}'\n")


if __name__ == "__main__":
    main()