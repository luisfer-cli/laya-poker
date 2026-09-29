class Card:
    def __init__(self, rank: str, suit: str):
        self.rank: str = rank
        self.suit: str = suit

    def getRank(self):
        return self.rank

    def setRank(self, rank: str):
        self.rank: str = rank

    def getSuit(self):
        return self.suit

    def setSuit(self, suit: str):
        self.suit: str = suit
