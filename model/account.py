class Account:
    """
    Class representing an Account, which can be debitted and creditted.
    """
    def __init__(self, balance: float = 0) -> None:
        """
        Instantiates an Account.
        
        :param balance: the initial balance.
        """
        self.balance = balance
        
    def request_debit(self, amount: float) -> float:
        """
        Attempts to debit the specified amount from the account but will not debit more
        than the amount in the account.
        
        :param amount: specified amount to debit from the account.
        :return: the amount debited. This is the given amount if the balance permits, 
            or the account's balance otherwise.
        """
        # If we are trying to debit more from the account than there is, we set the balance
        # to 0 and return the previous balance to indicate it was the maximum amount that
        # could be debited from the account.
        if amount < 0 or self.balance < 0:
            return 0

        if amount > self.balance:
            amount_debited = self.balance
            self.balance = 0
        else:
            self.balance -= amount
            amount_debited = amount
            
        return amount_debited
    
    def credit(self, amount: float) -> float:
        """
        Credits the specified quantity to the account.
        
        :param amountToCredit: as the name implies.
        :return: the new balance.
        """
        if amount < 0:
            raise ValueError("Cannot credit a negative amount.")
        
        self.balance += amount
        return self.balance