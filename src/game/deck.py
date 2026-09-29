import Card
import random


class Deck:
    def __init__(self):
        self.reset()

    def reset(self):
        ranks = ["A", "2", "3", "4", "5", "6",
                 "7", "8", "9", "10", "J", "Q", "K"]
        suits = ["♠️", "♥️", "♦️", "♣️"]
        self.cards = [
            Card(rank, suit)
            for rank in ranks
            for suit in suits
        ]

    def shuffle(self):
        random.shuffle(self.cards)

    def draw(self):
        return self.cards.pop()
