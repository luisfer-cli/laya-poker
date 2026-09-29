import unittest

from src.game import Card, Deck


class DeckTests(unittest.TestCase):
    def test_mazo_tiene_52_cartas_unicas(self):
        deck = Deck()
        self.assertEqual(len(deck), 52)
        self.assertEqual(len(set(deck.cards)), 52)

    def test_draw_reduce_el_mazo(self):
        deck = Deck()
        carta = deck.draw()
        self.assertIsInstance(carta, Card)
        self.assertEqual(len(deck), 51)

    def test_draw_many(self):
        deck = Deck()
        mano = deck.draw_many(5)
        self.assertEqual(len(mano), 5)
        self.assertEqual(len(set(mano)), 5)
        self.assertEqual(len(deck), 47)

    def test_draw_de_mazo_vacio_falla(self):
        deck = Deck()
        deck.cards = []
        with self.assertRaises(IndexError):
            deck.draw()

    def test_shuffle_conserva_las_cartas(self):
        deck = Deck()
        antes = set(deck.cards)
        deck.shuffle()
        self.assertEqual(set(deck.cards), antes)

    def test_valores_de_rango(self):
        deck = Deck()
        valores = {card.getRank(): card.getValue() for card in deck.cards}
        self.assertEqual(valores["A"], 14)
        self.assertEqual(valores["K"], 13)
        self.assertEqual(valores["2"], 2)


if __name__ == "__main__":
    unittest.main()
