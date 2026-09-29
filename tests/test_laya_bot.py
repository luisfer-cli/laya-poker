import unittest

from src.game import Action, Decision, Game, LayaBot, Player, create_laya_bots


class FakeAgent:
    """Doble del modelo: devuelve respuestas prefijadas y guarda lo que recibe."""

    def __init__(self, answers=None):
        self.answers = answers if answers is not None else {}
        self.calls = []

    def predict(self, state, questions):
        self.calls.append((state, questions))
        return self.answers


def new_game(count=3, chips=1000):
    players = [Player(f"P{i}", chips) for i in range(count)]
    return Game(players, small_blind=5, big_blind=10)


class LayaBotStateTests(unittest.TestCase):
    def test_contexto_incluye_lo_necesario(self):
        game = new_game(count=3)
        game.start(shuffle=False)
        bot = LayaBot(FakeAgent())

        context = bot.build_context(game)

        self.assertEqual(context["street"], "preflop")
        self.assertEqual(context["pot"], 15)
        self.assertEqual(context["to_call"], 10)  # el botón debe igualar 10
        self.assertEqual(context["board"], [])
        self.assertEqual(len(context["hero"]["hole_cards"]), 2)
        self.assertEqual(context["hero"]["position"], "button")
        self.assertEqual(len(context["players"]), 3)
        self.assertEqual(sum(1 for p in context["players"] if p["is_hero"]), 1)

    def test_estado_es_texto_natural(self):
        game = new_game(count=3)
        game.start(shuffle=False)
        bot = LayaBot(FakeAgent())

        state = bot.build_state(game)

        self.assertIsInstance(state, str)
        self.assertIn("preflop", state)
        self.assertIn("Hero", state)
        self.assertIn("Pot: 15 chips", state)
        self.assertIn("Opponents", state)

    def test_preguntas_solo_ofrecen_acciones_legales(self):
        game = new_game(count=3)
        game.start(shuffle=False)
        bot = LayaBot(FakeAgent())

        questions = bot.build_questions(game)
        criteria = questions["action"]["criteria"]

        self.assertIn("fold", criteria)
        self.assertIn("call", criteria)
        self.assertIn("raise", criteria)
        self.assertNotIn("check", criteria)  # hay una apuesta pendiente
        self.assertIn("bet_size", questions)

    def test_check_disponible_cuando_no_hay_apuesta(self):
        game = new_game(count=2)
        game.start(shuffle=False)
        game.act(Action.CALL)  # P0 iguala; le toca a la ciega grande
        bot = LayaBot(FakeAgent())

        criteria = bot.build_questions(game)["action"]["criteria"]

        self.assertIn("check", criteria)
        self.assertNotIn("call", criteria)


class LayaBotDecisionTests(unittest.TestCase):
    def setUp(self):
        self.game = new_game(count=3)
        self.game.start(shuffle=False)

    def test_elige_call(self):
        agent = FakeAgent(
            {"answers": {"action": {"choice": "call", "answer_confidence": 0.9}}}
        )
        bot = LayaBot(agent)

        decision = bot.decide(self.game)

        self.assertEqual(decision, Decision(Action.CALL))
        self.assertEqual(len(agent.calls), 1)

    def test_elige_raise_con_tamano(self):
        agent = FakeAgent(
            {
                "answers": {
                    "action": {"choice": "raise", "answer_confidence": 0.9},
                    "bet_size": {"choice": "pot"},
                }
            }
        )
        bot = LayaBot(agent)

        decision = bot.decide(self.game)

        esperado = bot._raise_sizes(self.game)["pot"][0]
        self.assertEqual(decision.action, Action.RAISE)
        self.assertEqual(decision.amount, esperado)

    def test_elige_all_in(self):
        agent = FakeAgent({"answers": {"action": {"choice": "all_in"}}})
        bot = LayaBot(agent)

        self.assertEqual(bot.decide(self.game).action, Action.ALL_IN)

    def test_acepta_respuestas_sin_envolver(self):
        agent = FakeAgent({"action": {"choice": "call", "answer_confidence": 0.9}})
        bot = LayaBot(agent)

        self.assertEqual(bot.decide(self.game).action, Action.CALL)

    def test_respuesta_desconocida_usa_fallback(self):
        agent = FakeAgent({"answers": {"action": {"choice": "bailar"}}})
        bot = LayaBot(agent)

        # Frente a una apuesta, el fallback conservador es retirarse.
        self.assertEqual(bot.decide(self.game).action, Action.FOLD)

    def test_confianza_baja_usa_fallback(self):
        agent = FakeAgent(
            {"answers": {"action": {"choice": "call", "answer_confidence": 0.2}}}
        )
        bot = LayaBot(agent, min_confidence=0.8)

        self.assertEqual(bot.decide(self.game).action, Action.FOLD)

    def test_tamano_desconocido_usa_el_minimo(self):
        agent = FakeAgent(
            {
                "answers": {
                    "action": {"choice": "raise"},
                    "bet_size": {"choice": "inventado"},
                }
            }
        )
        bot = LayaBot(agent)
        bot.decide(self.game)

        decision = bot.parse(agent.answers, self.game)
        self.assertEqual(
            decision.amount, min(a for a, _ in bot._raise_sizes(self.game).values())
        )

    def test_tamano_limitado_por_las_fichas(self):
        game = new_game(count=3, chips=30)
        game.start(shuffle=False)
        bot = LayaBot(FakeAgent())

        sizes = bot._raise_sizes(game)

        max_to = game.players[0].getChips() + game.players[0].getCurrentBet()
        amounts = [amount for amount, _ in sizes.values()]
        self.assertTrue(all(amount <= max_to for amount in amounts))
        self.assertIn(max_to, amounts)  # siempre se puede ir all-in


class LayaBotsFactoryTests(unittest.TestCase):
    def test_crea_un_bot_por_jugador(self):
        game = new_game(count=4)
        agent = FakeAgent()

        bots = create_laya_bots(game, agent)

        self.assertEqual(len(bots), 4)
        self.assertTrue(all(isinstance(b, LayaBot) for b in bots))
        self.assertEqual([b.name for b in bots], ["P0", "P1", "P2", "P3"])


if __name__ == "__main__":
    unittest.main()
