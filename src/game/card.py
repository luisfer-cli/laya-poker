RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
RANK_VALUE = {rank: value for value, rank in enumerate(RANKS, start=2)}


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

    def getValue(self) -> int:
        """Valor numérico de la carta (2..14, siendo el As 14)."""
        return RANK_VALUE[self.rank]

    def __eq__(self, other):
        if not isinstance(other, Card):
            return NotImplemented
        return self.rank == other.rank and self.suit == other.suit

    def __hash__(self):
        return hash((self.rank, self.suit))

    def __repr__(self):
        return f"{self.rank}{self.suit}"
