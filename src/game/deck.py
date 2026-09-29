try:  # importado como paquete: src.game.deck
    from .card import Card
except ImportError:  # importado plano (el directorio src/game en el path)
    from card import Card

import random


class Deck:
    def __init__(self):
        self.cards = []
        self.reset()

    def reset(self):
        ranks = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
        suits = ["♠️", "♥️", "♦️", "♣️"]
        self.cards = [Card(rank, suit) for rank in ranks for suit in suits]

    def shuffle(self):
        random.shuffle(self.cards)

    def draw(self):
        if not self.cards:
            raise IndexError("No quedan cartas en el mazo")
        return self.cards.pop()

    def draw_many(self, count):
        return [self.draw() for _ in range(count)]

    def remaining(self):
        return len(self.cards)

    def __len__(self):
        return len(self.cards)

    def __repr__(self):
        return f"Deck({len(self.cards)} cartas)"
