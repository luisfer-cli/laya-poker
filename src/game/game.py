import Deck
from enum import Enum, auto


class GameState(Enum):
    WAITING = auto()
    PREFLOP = auto()
    FLOP = auto()
    TURN = auto()
    RIVER = auto()
    SHOWDOWN = auto()
    FINISHED = auto()


class Game:
    def __init__(self, seats):
        self.deck: Deck = Deck()
        self.state = GameState.WAITING
        self.seats = seats
