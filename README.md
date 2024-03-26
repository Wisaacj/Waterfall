# Exercise

1. Create a simplified CLO cashflow model using the below data

2. Evaluate one CLO (which I will flag later when I send the data) from the perspective of a CLO Equity buyer and think about fair value you would pay

## Running the simulator
Install dependencies: 
- `pip install pandas python-dateutil`

To perform a cashflow simulation, run
- `python main.py --deal_id [DEAL_ID]`

To perform a cashflow run with a different assumption, e.g., with a higher CDR, run
- `python main.py --deal_id CADOG13 --cdr 0.03`

For additional information on all command line arguments, run
-  `python main.py --help`

Depending on your Python installation, you may need to use `python3` instead of `python`.


## Data

I will send you extracts of three files (The full files include all European deals, I will reduce the dataset and only send 10 or so)

Deal Data, consisting all (in your case 10) European CLOs, one line each with columns including deal info like: Reinvestment End Date, NAV, NAV90 (Equity NAV assuming all assets above 90 are par and all below 90 are at market value), Avg Portfolio Price, Avg Portfolio Spread etc
Tranche Data, consisting tranche information for the deals in 1 above: For each tranche, data includes: Notional, spread, other fields like MVOC etc

Loan Data, consisting of the underlying assets data of the above CLOs. This is mainly helpful to build the maturity / amortization profile of the portfolio

---

Comments from Will:
- You may notice I've renamed the column headers of the datasets (and their filenames). I did this to make parsing the datasets easier/faster for me but, with more time, I could quite easily update the program to use the headers from your internal database.
 

## Assumptions and Instructions

You can use whatever language you feel most comfortable in. Preference for Python on our side but don’t want to sacrifice speed or quality on your side. Would prefer not to use VBA

Think about time allocation and prioritize. We don’t expect you to create a full CLO cashflow model with OC Tests etc etc but a 80/20 sort of model that is good enough to produce meaningful results and play with a few assumptions

 - Assumptions it should be sensitive to: CDR, CPR, WAS, Call Date

 - You can think about reinvestments. If you think you have time to incorporate the concept of reinvestments, it would be great. If not, that could be one shortcut

You can ignore Euribor rates and just use spread excl 3mE on the asset and liability side

The idea is that your script works deal independent and that you can input any ticker of your deal dataset and that your model creates cashflows and an IRR output for that CLO and a certain price. (The actual CLO cashflow model could also be created in Excel which would require you however to link Python (or alternate language) with Excel… )