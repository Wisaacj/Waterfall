import argparse
import data_source
import common_args
import pandas as pd

from tqdm import tqdm
from factories import CLOFactory


def universe_irrs(args: argparse.Namespace) -> pd.DataFrame:
    # Load Napier holdings into memory.
    napier_holdings = data_source.load_napier_holdings()
    # Only consider deals we own equity in (for the time being).
    napier_holdings = napier_holdings[napier_holdings["orig_rtg"] == "Equity"]
    
    irrs = {}
    for deal_id in tqdm(napier_holdings["intex_id"].unique(), desc="Processing deals"):
        irrs[deal_id] = {}
        try:
            irr = deal_irrs(deal_id, args)
            irrs[deal_id]["irr"] = irr
        except Exception as e:
            print(f"Error processing deal {deal_id}: {e}")
            irrs[deal_id]["error"] = str(e)

    irrs_df = pd.DataFrame(irrs).T
    
    # Print summary statistics.
    print(f"Mean IRR: {irrs_df['irr'].mean():.2%}")
    print(f"Median IRR: {irrs_df['irr'].median():.2%}")
    print(f"Minimum IRR: {irrs_df['irr'].min():.2%}")
    print(f"Maximum IRR: {irrs_df['irr'].max():.2%}")

    # Print success rate.
    success_rate = (len(irrs) - sum(1 for irr in irrs.values() if 'error' in irr)) / len(irrs)
    print(f"Success rate: {len(irrs) - sum(1 for irr in irrs.values() if 'error' in irr)} / {len(irrs)} ({success_rate:.2%})")
    # Print a count of the number of deals with an error.
    print(f"Number of deals with an error: {sum(1 for irr in irrs.values() if 'error' in irr)}")
    
    return irrs_df


def deal_irrs(deal_id: str, args: argparse.Namespace) -> float:
    deal, loans, tranches = data_source.load_deal(deal_id)
    deal_holdings = data_source.load_deal_holdings(deal_id)
    forward_curves = data_source.load_latest_forward_curves()

    factory = CLOFactory(
        deal, tranches, loans, forward_curves, args.cpr, args.cdr, 
        args.cpr_lockout_months, args.cdr_lockout_months, args.recovery_rate,
        args.payment_frequency, args.simulation_frequency, args.rp_extension_months,
        args.reinvestment_maturity_months, args.wal_limit_years
    )
    model = factory.build()
    model.simulate()

    equity_holdings = deal_holdings[deal_holdings['orig_rtg'] == 'Equity']
    equity_purchase_price = equity_holdings['costprice'].mean() / 100
    equity_irr = model.equity_tranche.irr(equity_purchase_price)

    return equity_irr


def main():
    parser = argparse.ArgumentParser(description="Simulate the IRRs of a universe of deals.")
    parser = common_args.add_clo_assumptions(parser)
    args = parser.parse_args()

    irrs_df = universe_irrs(args)
    irrs_df.to_excel("outputs/Universe IRRs.xlsx")

if __name__ == "__main__":
    main()