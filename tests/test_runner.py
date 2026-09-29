import unittest

from runner import card_token, format_resultado, resolve_prompts
from src.game import Action, Card, Decision, Game, GameState, Player


class ResolvePromptsTests(unittest.TestCase):
    def test_asigna_ciclicamente(self):
        prompts = resolve_prompts("tight,solid", players=4)
        self.assertEqual(
            [p.name for p in prompts], ["tight", "solid", "tight", "solid"]
        )

    def test_vacio_usa_default(self):
        prompts = resolve_prompts("", players=2)
        self.assertEqual([p.name for p in prompts], ["default", "default"])

    def test_prompt_desconocido_falla_con_mensaje_claro(self):
        with self.assertRaises(SystemExit) as ctx:
            resolve_prompts("default,aggressive", players=2)
        self.assertIn("prompt desconocido", str(ctx.exception))
        self.assertIn("solid", str(ctx.exception))


class CardTokenTests(unittest.TestCase):
    def test_formato_hand_history(self):
        self.assertEqual(card_token(Card("A", "♠️")), "As")
        self.assertEqual(card_token(Card("10", "♥️")), "Th")
        self.assertEqual(card_token(Card("7", "♣️")), "7c")
        self.assertEqual(card_token(Card("K", "♦️")), "Kd")


class HistoryViewTests(unittest.TestCase):
    def _game(self):
        return Game(
            [Player("Ana", 1000), Player("Beto", 1000)], small_blind=5, big_blind=10
        )

    def test_narra_las_acciones(self):
        from runner import HistoryView

        game = self._game()
        view = HistoryView()
        game.start(shuffle=False)
        ana = game.players[0]

        # CALL sin apuesta pendiente se narra como "pasa".
        # Ana es la ciega pequeña (botón en heads-up): stack 995 tras postear.
        self.assertEqual(
            view._action_text(game, ana, Decision(Action.CHECK)), "pasa  (stack: 995)"
        )
        self.assertEqual(
            view._action_text(game, ana, Decision(Action.FOLD)), "se retira"
        )
        self.assertEqual(
            view._action_text(game, ana, Decision(Action.BET, 50)),
            "apuesta 50  (stack: 950)",
        )
        self.assertEqual(
            view._action_text(game, ana, Decision(Action.RAISE, 120)),
            "sube a 120  (stack: 880)",
        )

    def test_stack_restante_en_call_y_all_in(self):
        from runner import HistoryView

        game = self._game()
        game.start(shuffle=False)
        view = HistoryView()
        ana = game.players[0]

        # Ana (ciega pequeña) paga 5 más para igualar la ciega grande.
        self.assertEqual(
            view._action_text(game, ana, Decision(Action.CALL)),
            "paga 5  (stack: 990)",
        )
        self.assertEqual(
            view._action_text(game, ana, Decision(Action.ALL_IN)),
            "va all-in por 1000  (stack: 0)",
        )

    def test_showdown_summary(self):
        initial = [1000, 1000]
        game = self._game()
        game.start(shuffle=False)
        # Bote de 20 para Ana.
        game.players[0].setChips(1010)
        game.players[1].setChips(990)
        texto = format_resultado(game, initial)
        self.assertIn("Ana gana 10", texto)

    def test_encabezado_de_calle_incluye_el_bote(self):
        import io
        from contextlib import redirect_stdout

        from runner import HistoryView

        game = Game(
            [Player("Ana", 1000), Player("Beto", 1000), Player("Caro", 1000)],
            small_blind=5,
            big_blind=10,
        )
        view = HistoryView()
        game.start(shuffle=False)

        # Forzamos el bote como si la ronda preflop hubiera terminado.
        game.pot = 30
        game.state = GameState.FLOP
        game.community = [Card("2", "♥️"), Card("2", "♠️"), Card("A", "♥️")]

        salida = io.StringIO()
        with redirect_stdout(salida):
            view._print_street(game)

        self.assertIn("*** FLOP ***", salida.getvalue())
        self.assertIn("bote: 30", salida.getvalue())


if __name__ == "__main__":
    unittest.main()
