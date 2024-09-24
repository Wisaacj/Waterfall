from datetime import date
from dateutil.relativedelta import relativedelta

from . import day_counter
from .account import Account
from .interest_vehicle import InterestVehicle
from .snapshots import AssetSnapshot
from .forward_rate_curve import ForwardRateCurve
from .enums import AssetKind


class Asset(InterestVehicle):
    """
    Class representing an Asset.
    """

    def __init__(self, 
                 figi: str, 
                 asset_kind: AssetKind,
                 balance: float, 
                 price: float, 
                 spread: float, 
                 initial_coupon: float,
                 payment_frequency: int,
                 report_date: date, 
                 next_payment_date: date, 
                 maturity_date: date,
                 cpr_lockout_end_date: date,
                 cdr_lockout_end_date: date,
                 cpr: float, 
                 cdr: float, 
                 recovery_rate: float,
                 forward_rate_curve: ForwardRateCurve,
                 is_floating_rate: bool):
        """
        Instantiates an asset.

        :param figi: the asset's BBG ID or reinvestment name.
        :param balance: the balance of the asset as of the report_date.
        :param price: the price of the asset as of the report_date.
        :param spread: the spread paid on the asset over the base rate
        :param payment_frequency: the number of times the asset pays per year.
        :param report_date: the date the deal report was generated on.
        :param next_payment_date: the next date the asset will pay.
        :param maturity_date: the date the asset matures
        """
        # Initialise the last simulation date to report date.
        super().__init__(balance, initial_coupon, report_date)

        self.figi = figi
        self.spread = spread
        self.asset_kind = asset_kind
        self.forward_rate_curve = forward_rate_curve
        self.is_floating_rate = is_floating_rate

        # Price, assumptions.
        self.price = price
        self.cpr = cpr
        self.cdr = cdr
        self.recovery_rate = recovery_rate

        # Dates.
        self.maturity = maturity_date
        self.report_date = report_date
        self.next_payment_date = next_payment_date
        self.settlement_date = date(9999, 12, 31)
        """When the asset is sold and settled."""
        self.cpr_lockout_end_date = cpr_lockout_end_date
        self.cdr_lockout_end_date = cdr_lockout_end_date

        self.payment_frequency = payment_frequency
        self.payment_interval = relativedelta(months=(12/payment_frequency))

        self.simulating_interim_period = False

        # Backdate the interest accrued to the amount accrued between
        # the last payment and report dates.
        self.interest_accrued = self.calc_backdated_accrued_interest()

        # These are used to keep track of the flow of principal when a payment
        # date lies inbetween two simulation dates.
        self.scheduled_principal = 0
        self.defaulted_principal = 0
        self.recovered_principal = 0
        self.unscheduled_principal = 0

        # History of cashflows.
        self.history = []

        # Take a snapshot of the initial state of the asset.
        self.take_snapshot(report_date)

    def __str__(self) -> str:
        """
        Returns this asset's Bloomberg ID.
        """
        return self.figi

    def simulate(self, simulate_until: date):
        """
        Runs a simulation on the asset over the given number of months and computes the new cash flows for the period.

        :param simulate_until: as the name suggests.
        """
        # if simulate_until == self.last_simulation_date:
        #     return

        # If there is a payment date before the end of the simulation, we will instead simulate until that date
        # and then remove all money before proceeding with the following simulation period.
        while (simulate_until > self.next_payment_date or simulate_until > self.maturity):
            interim_date = self.next_payment_date if self.next_payment_date <= self.maturity else self.maturity

            # Simulate until the interim date.
            self.simulating_interim_period = True
            self.simulate(interim_date)

        # Work out the proportion of the year we are simulating over here.
        accrue_until = min(simulate_until, self.settlement_date)
        year_factor = self.calc_year_factor(accrue_until)

        # Accrue interest for this period.
        self.accrue_interest(year_factor)

        # Calculate effective CPR and CDR for the period.
        effective_cpr = self.effective_cpr(accrue_until)
        effective_cdr = self.effective_cdr(accrue_until)

        # The amount of prepayments and defaults during this simulation period.
        prepayments = (1 - ((1-effective_cpr) ** year_factor)) * self.balance
        defaults = (1 - ((1-effective_cdr) ** year_factor)) * \
            (self.balance - prepayments)

        # The amount of prepayments and defaults as a proportion of the balance.
        balance = self.balance if self.balance != 0 else 1
        unscheduled_proportion = prepayments / balance
        defaulted_proportion = defaults / balance

        # 1) For defaults:
        # Recover some of the defaulted principal
        recovery = defaults * self.recovery_rate
        self.principal_paid += recovery
        # Defaulted assets suffer 100% loss on interest accrued on that portion (this is
        # made explicit by incrementing interest_paid by 0)
        self.interest_paid += 0
        self.interest_accrued -= defaulted_proportion * self.interest_accrued

        # 2) For unscheduled principal:
        self.principal_paid += prepayments
        self.interest_paid += unscheduled_proportion * self.interest_accrued
        self.interest_accrued -= unscheduled_proportion * self.interest_accrued

        # 3) For remaining balances:
        self.balance -= prepayments + defaults

        on_payment_date = simulate_until == self.next_payment_date # TODO: simulate_until >= self.next_payment_date + 8 business days
        asset_matured = simulate_until >= self.maturity
        asset_settled = simulate_until >= self.settlement_date

        # If we are on a payment date, run the payment process.
        if on_payment_date:
            # Pay off the accrued interest and then reset it.
            self.interest_paid += self.interest_accrued
            self.interest_accrued = 0

            # Fix coupon for the next accrual period.
            self.update_coupon(simulate_until)

            # Bump the next payment date forward by the payment interval.
            self.next_payment_date += self.payment_interval

        if asset_matured:
            # Scheduled principal is the remaining balance on maturity.
            self.scheduled_principal = self.balance

            # Pay off the remaining balance.
            self.principal_paid += self.balance
            self.balance = 0

            # Pay off any remaining accrued interest.
            self.interest_paid += self.interest_accrued
            self.interest_accrued = 0

            # Set maturity to be 31/12/9999 to avoid running this condition again.
            self.maturity = date(9999, 12, 31)

        # Asset is sold or portfolio is liquidated.
        if asset_settled:
            # Sell the asset into the market today.
            proceeds = self.price * self.balance

            self.principal_paid += proceeds
            self.unscheduled_principal += proceeds

            # Set the balance to 0 once the asset has sold and settled.
            self.balance = 0

        # Finally, we must save the last date that this simulation was run until.
        self.last_simulation_date = accrue_until

        # If we are simulating until an interm_date rather than an original simulate_until,
        # we are at risk of not accurately tracking the flow of principal because we subdivide the
        # original simulation period into at least two segments, but only take a snapshot in the last segment.
        # The following variables keep track of the principal through the subdivided segments.
        self.unscheduled_principal += prepayments
        self.defaulted_principal += defaults
        self.recovered_principal += recovery

        if self.simulating_interim_period:
            self.simulating_interim_period = False
            return

        self.take_snapshot(simulate_until)

        # Reset these variables.
        self.unscheduled_principal = 0
        self.scheduled_principal = 0
        self.defaulted_principal = 0
        self.recovered_principal = 0
        self.period_accrual = 0

    def effective_cpr(self, as_of: date) -> float:
        """
        Calculates the effective CPR based on the lockout period.
        
        :param as_of: The current date of the simulation.
        :return: The effective CPR.
        """
        if as_of > self.cpr_lockout_end_date:
            return self.cpr
        else:
            return 0
        
    def effective_cdr(self, as_of: date) -> float:
        """
        Calculates the effective CDR based on the lockout period.
        
        :param as_of: The current date of the simulation.
        :return: The effective CDR.
        """
        if as_of > self.cdr_lockout_end_date:
            return self.cdr
        else:
            return 0

    def liquidate(self, accrual_date: date):
        """
        Liquidates the asset by trading it in the market on the accrual date. The 
        settlement date then depends on the asset kind.

        :param accrual_date: The date of the accrual.
        """
        if self.asset_kind == AssetKind.Loan:
            # Loans trade with delayed comp (T+10). That is, they continue to earn
            # interest until T+10.
            self.settlement_date = day_counter.add_uk_business_days(
                accrual_date, 10)
        elif self.asset_kind == AssetKind.Bond:
            # Bonds trade with delayed comp (T+2). That is, they continue to earn 
            # interest until T+2.
            self.settlement_date = day_counter.add_uk_business_days(
                accrual_date, 2)
        else:
            raise ValueError(f"invalid asset kind: {self.asset_kind}")
    
    def update_coupon(self, fixing_date: date):
        """
        Updates the coupon rate for floating rate assets.

        This method updates the coupon rate of the asset if it's a floating rate asset.
        For fixed rate assets, this method does nothing.

        :param fixing_date: The date used to determine the new base rate.

        Note:
        - For floating rate asset, the new coupon is calculated as the sum of:
          1. The forward rate obtained from the forward_rate_curve for the given fixing_date
          2. The asset's spread
        - For fixed rate assets, the coupon remains unchanged
        """
        if self.is_floating_rate:
            base_rate = self.forward_rate_curve.get_rate(fixing_date)
            self.interest_rate = base_rate + self.spread

    def sweep_interest(self, destination: Account) -> float:
        """
        Credits the destination account with the interest paid by this asset and sets it to 0.

        :param destination: the Account to credit with the interest.
        :return: the amount of interest swept.
        """
        amount = self.interest_paid
        destination.credit(amount)
        self.interest_paid = 0

        return amount

    def sweep_principal(self, destination: Account) -> float:
        """
        Credits the destination account with the principal paid by this asset and sets it to 0.

        :param destination: the Account to credit with the interest.
        :return: the amount of principal swept.
        """
        amount = self.principal_paid
        destination.credit(amount)
        self.principal_paid = 0

        return amount

    def calc_prior_payment_date(self, comparison_date: date) -> date:
        """
        Calculates the payment date prior to a comparison date.

        :param comparison_date: the date you want the prior payment date to.
        :return: the prior payment date.
        """
        prior_payment_date = self.next_payment_date

        while prior_payment_date > comparison_date:
            prior_payment_date -= self.payment_interval

        return prior_payment_date

    def calc_backdated_accrued_interest(self) -> float:
        """
        Calculates the interest accrued between the last payment date and the report date.
        """
        year_factor = self.calc_year_factor(
            self.report_date, self.calc_prior_payment_date(self.report_date))
        return self.balance * year_factor * self.interest_rate

    def take_snapshot(self, as_of: date) -> None:
        """
        Takes a snapshot of the asset's attributes.

        :param as_of: the date marking the end of of this simulation period.
        """
        self.history.append(AssetSnapshot(
            date=as_of,
            balance=self.balance,
            defaulted_principal=self.defaulted_principal,
            scheduled_principal=self.scheduled_principal,
            unscheduled_principal=self.unscheduled_principal,
            principal_paid=self.principal_paid,
            interest_paid=self.interest_paid,
            interest_accrued=self.interest_accrued,
            period_accrual=self.period_accrual,
            recovered_principal=self.recovered_principal,
            interest_rate=self.interest_rate,
        ))
