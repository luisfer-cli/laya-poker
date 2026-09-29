import unittest

from src.game import Player, build_side_pots


def jugador(nombre, contributed, folded=False):
    player = Player(nombre, 0)
    player.contributed = contributed
    player.setFolded(folded)
    return player


class SidePotTests(unittest.TestCase):
    def test_bote_unico_sin_all_in(self):
        a = jugador("A", 100)
        b = jugador("B", 100)
        pots = build_side_pots([a, b])
        self.assertEqual(len(pots), 1)
        self.assertEqual(pots[0].amount, 200)
        self.assertCountEqual(pots[0].eligible, [a, b])

    def test_side_pot_con_all_in_desigual(self):
        a = jugador("A", 100)
        b = jugador("B", 50)
        c = jugador("C", 100)
        pots = build_side_pots([a, b, c])

        self.assertEqual(len(pots), 2)
        # Bote principal: 50 de cada uno.
        self.assertEqual(pots[0].amount, 150)
        self.assertCountEqual(pots[0].eligible, [a, b, c])
        # Bote lateral: solo A y C pueden igualar los 100.
        self.assertEqual(pots[1].amount, 100)
        self.assertCountEqual(pots[1].eligible, [a, c])

    def test_jugador_retirado_aporta_pero_no_opta(self):
        a = jugador("A", 100)
        b = jugador("B", 100, folded=True)
        pots = build_side_pots([a, b])
        self.assertEqual(pots[0].amount, 200)
        self.assertEqual(pots[0].eligible, [a])

    def test_sin_aportes_no_hay_botes(self):
        a = jugador("A", 0)
        b = jugador("B", 0)
        self.assertEqual(build_side_pots([a, b]), [])


if __name__ == "__main__":
    unittest.main()
