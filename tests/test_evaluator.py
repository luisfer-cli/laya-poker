import unittest
from itertools import pairwise

from src.game import Card, HandCategory, describe, evaluate


def c(text):
    """Crea una carta desde texto, p. ej. 'As' -> As de picas, '10h' -> 10 de corazones."""
    return Card(text[:-1], text[-1])


class EvaluatorTests(unittest.TestCase):
    def test_royal_flush(self):
        score = evaluate([c("As"), c("Ks"), c("Qs"), c("Js"), c("10s")])
        self.assertEqual(score[0], HandCategory.STRAIGHT_FLUSH)
        self.assertEqual(score[1], 14)
        self.assertEqual(describe(score), "escalera de color")

    def test_orden_de_categorias(self):
        manos = [
            [c("As"), c("Kd"), c("Qh"), c("Js"), c("9c")],  # carta alta
            [c("As"), c("Ad"), c("Qh"), c("Js"), c("9c")],  # pareja
            [c("As"), c("Ad"), c("Qh"), c("Qs"), c("9c")],  # doble pareja
            [c("As"), c("Ad"), c("Ah"), c("Qs"), c("9c")],  # trío
            [c("9s"), c("8d"), c("7h"), c("6s"), c("5c")],  # escalera
            [c("As"), c("9s"), c("7s"), c("5s"), c("3s")],  # color
            [c("As"), c("Ad"), c("Ah"), c("Qs"), c("Qc")],  # full
            [c("As"), c("Ad"), c("Ah"), c("Ac"), c("9c")],  # póker
            [c("9s"), c("8s"), c("7s"), c("6s"), c("5s")],  # escalera de color
        ]
        scores = [evaluate(mano) for mano in manos]
        for peor, mejor in pairwise(scores):
            self.assertLess(peor, mejor)

    def test_rueda_es_la_escalera_mas_baja(self):
        rueda = evaluate([c("As"), c("2d"), c("3h"), c("4s"), c("5c")])
        seis_alta = evaluate([c("2s"), c("3d"), c("4h"), c("5s"), c("6c")])
        self.assertEqual(rueda[0], HandCategory.STRAIGHT)
        self.assertEqual(rueda[1], 5)
        self.assertLess(rueda, seis_alta)

    def test_mejor_mano_entre_siete(self):
        # Con 7 cartas hay color a picas, no la simple pareja.
        cartas = [
            c("As"),
            c("9s"),
            c("7s"),
            c("5s"),
            c("3s"),
            c("Kd"),
            c("Kh"),
        ]
        score = evaluate(cartas)
        self.assertEqual(score[0], HandCategory.FLUSH)
        self.assertEqual(score[1], 14)

    def test_desempate_por_kicker(self):
        as_con_kicker_alto = evaluate([c("As"), c("Ad"), c("Kh"), c("Qd"), c("Jc")])
        as_con_kicker_bajo = evaluate([c("As"), c("Ad"), c("9h"), c("8d"), c("7c")])
        self.assertGreater(as_con_kicker_alto, as_con_kicker_bajo)

    def test_full_usa_el_mejor_trio_y_la_mejor_pareja(self):
        # Trío de ases con doble pareja de reyes: el full es A-A-A-K-K.
        score = evaluate(
            [c("As"), c("Ad"), c("Ah"), c("Ks"), c("Kd"), c("Kc"), c("2h")]
        )
        self.assertEqual(score, (HandCategory.FULL_HOUSE, 14, 13))

    def test_menos_de_cinco_cartas_es_error(self):
        with self.assertRaises(ValueError):
            evaluate([c("As"), c("Kd"), c("Qh"), c("Js")])


if __name__ == "__main__":
    unittest.main()
