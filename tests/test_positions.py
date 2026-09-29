import unittest

from src.game.positions import position_names, seat_position_names


class PositionNamesTests(unittest.TestCase):
    def test_heads_up(self):
        self.assertEqual(position_names(2), ["BTN/SB", "BB"])

    def test_3_jugadores(self):
        self.assertEqual(position_names(3), ["BTN", "SB", "BB"])

    def test_4_jugadores(self):
        self.assertEqual(position_names(4), ["BTN", "SB", "BB", "CO"])

    def test_5_jugadores(self):
        self.assertEqual(position_names(5), ["BTN", "SB", "BB", "CO", "HJ"])

    def test_6_jugadores(self):
        self.assertEqual(position_names(6), ["BTN", "SB", "BB", "CO", "HJ", "UTG"])

    def test_hay_un_nombre_por_jugador(self):
        for n in range(2, 11):
            nombres = position_names(n)
            self.assertEqual(len(nombres), n)
            self.assertEqual(len(set(nombres)), n, f"nombres repetidos con {n}")

    def test_utg_es_el_ultimo_preflop(self):
        # El último de la lista es el primero en hablar en el preflop.
        self.assertEqual(position_names(6)[-1], "UTG")
        self.assertEqual(position_names(9)[-1], "UTG")

    def test_asignacion_a_asientos(self):
        # 6 jugadores con el botón en el asiento 2.
        mapping = seat_position_names(6, button=2, small_blind=3)
        self.assertEqual(mapping[2], "BTN")
        self.assertEqual(mapping[3], "SB")
        self.assertEqual(mapping[4], "BB")
        self.assertEqual(mapping[1], "UTG")  # habla primero preflop


if __name__ == "__main__":
    unittest.main()
