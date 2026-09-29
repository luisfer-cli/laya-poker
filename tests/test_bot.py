import unittest

from src.game import (
    Action,
    BotEngine,
    Decision,
    FunctionBot,
    Game,
    GameState,
    Player,
)


def new_game(chips=1000, count=3):
    players = [Player(f"P{i}", chips) for i in range(count)]
    return Game(players, small_blind=5, big_blind=10)


class FunctionBotTests(unittest.TestCase):
    def test_devuelve_decision(self):
        bot = FunctionBot(lambda game: Decision(Action.CHECK))
        game = new_game(count=2)
        game.start(shuffle=False)
        self.assertEqual(bot.decide(game).action, Action.CHECK)

    def test_acepta_tupla(self):
        bot = FunctionBot(lambda game: (Action.CALL, 0))
        game = new_game(count=2)
        game.start(shuffle=False)
        self.assertEqual(bot.decide(game).action, Action.CALL)


class BotEngineTests(unittest.TestCase):
    def test_juega_la_mano_y_conserva_fichas(self):
        game = new_game()
        bots = [FunctionBot(lambda g: (Action.CALL, 0)) for _ in game.players]
        engine = BotEngine(game, bots)

        engine.play_hand()

        self.assertEqual(game.state, GameState.FINISHED)
        self.assertEqual(sum(p.getChips() for p in game.players), 3000)
        self.assertTrue(engine.history)

    def test_recupera_accion_ilegal_con_una_segura(self):
        game = new_game()
        # Todos intentan CHECK incluso cuando hay una apuesta pendiente (ilegal).
        bots = [FunctionBot(lambda g: Decision(Action.CHECK)) for _ in game.players]
        engine = BotEngine(game, bots)

        engine.play_hand()

        self.assertEqual(game.state, GameState.FINISHED)
        # El motor los convirtió en FOLD (acción segura) y avisó en el historial.
        acciones = [entry[2] for entry in engine.history]
        self.assertIn(Action.FOLD, acciones)
        self.assertEqual(sum(p.getChips() for p in game.players), 3000)

    def test_bot_roto_no_cuelga_la_partida(self):
        def explota(game):
            raise RuntimeError("boom")

        game = new_game()
        bots = [FunctionBot(explota) for _ in game.players]
        engine = BotEngine(game, bots)

        engine.play_hand()

        self.assertEqual(game.state, GameState.FINISHED)
        self.assertEqual(sum(p.getChips() for p in game.players), 3000)

    def test_numero_de_bots_incorrecto(self):
        game = new_game(count=3)
        with self.assertRaises(ValueError):
            BotEngine(game, [FunctionBot(lambda g: Decision(Action.FOLD))])

    def test_play_hands(self):
        game = new_game()
        bots = [FunctionBot(lambda g: (Action.CALL, 0)) for _ in game.players]
        engine = BotEngine(game, bots)

        jugadas = engine.play_hands(3)

        self.assertEqual(jugadas, 3)
        self.assertGreaterEqual(len(engine.history), 3)


if __name__ == "__main__":
    unittest.main()
