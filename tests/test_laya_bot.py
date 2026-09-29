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
        self.assertEqual(context["hero"]["position"], "BTN")
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

    def test_estado_incluye_posicion_y_contexto(self):
        game = new_game(count=6)
        game.start(shuffle=False)
        bot = LayaBot(FakeAgent())

        context = bot.build_context(game)

        # En la primera mano el botón es el asiento 0; el primero en hablar
        # preflop es el UTG (asiento 5).
        self.assertEqual(game.button, 0)
        boton = next(p for p in context["players"] if p["seat"] == game.button)
        self.assertEqual(boton["position"], "BTN")
        self.assertEqual(context["hero"]["position"], "CO")
        posiciones = {p["position"] for p in context["players"]}
        self.assertIn("UTG", posiciones)
        self.assertIn("SB", posiciones)
        self.assertIn("BB", posiciones)
        self.assertEqual(context["num_active"], 6)
        self.assertTrue(context["can_raise"])
        self.assertTrue(context["can_reraise"])  # debe igualar la ciega

        state = bot.build_state(game)
        self.assertIn("effective stack", state)
        self.assertIn("can re-raise", state)

    def test_stack_efectivo_usa_el_rival_mas_corto(self):
        game = Game(
            [Player("Ana", 1000), Player("Beto", 405), Player("Caro", 1000)],
            small_blind=5,
            big_blind=10,
        )
        game.start(shuffle=False)
        bot = LayaBot(FakeAgent())

        context = bot.build_context(game)

        # Beto (ciega pequeña) postea 5, así que le quedan 400.
        self.assertEqual(game.players[1].getChips(), 400)
        self.assertEqual(context["effective_stack"], 400)

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

    def test_all_in_por_tamano_con_stack_corto(self):
        # Con el stack efectivo pequeño (≤ 2 botes), el all-in sí es un tamaño
        # disponible; elegirlo produce un ALL_IN.
        game = new_game(count=3, chips=60)
        game.start(shuffle=False)
        agent = FakeAgent(
            {
                "answers": {
                    "action": {"choice": "raise"},
                    "bet_size": {"choice": "all_in"},
                }
            }
        )
        bot = LayaBot(agent)

        decision = bot.decide(game)

        self.assertEqual(decision.action, Action.ALL_IN)

    def test_tamano_all_in_ausente_con_stack_largo(self):
        # En un bote pequeño con stacks grandes, comprometer el stack entero no
        # es una jugada natural y no debe ofrecerse como tamaño.
        game = new_game(count=3, chips=1000)
        game.start(shuffle=False)
        bot = LayaBot(FakeAgent())

        sizes = bot._raise_sizes(game)

        self.assertNotIn("all_in", sizes)
        # Ningún tamaño ofrecido supera el stack del jugador.
        max_to = game.players[game.currentSeat()].getChips()
        for amount, _ in sizes.values():
            self.assertLessEqual(amount, max_to)

    def test_tamano_no_supera_lo_que_el_rival_puede_pagar(self):
        # Si el rival más corto tiene 300, no tiene sentido proponer tamaños
        # muy por encima de su stack.
        game = Game(
            [Player("A", 1000), Player("B", 300), Player("C", 300)],
            small_blind=5,
            big_blind=10,
        )
        game.start(shuffle=False)
        bot = LayaBot(FakeAgent())
        # Forzamos un bote grande para que el tope por bote no sea el límite.
        game.pot = 500
        game.current_bet = 0

        sizes = bot._raise_sizes(game)

        for amount, _ in sizes.values():
            self.assertLessEqual(amount, game.current_bet + 300)

    def test_all_in_no_aparece_como_accion_principal(self):
        bot = LayaBot(FakeAgent())

        criteria = bot.build_questions(self.game)["action"]["criteria"]

        self.assertNotIn("all_in", criteria)
        self.assertIn("raise", criteria)

    def test_all_in_disponible_si_no_se_puede_subir(self):
        # Alguien con muy pocas fichas solo puede ir all-in para seguir.
        game = new_game(count=3, chips=1000)
        game.start(shuffle=False)
        game.players[0].setChips(15)  # no llega a la subida mínima (a 20)
        bot = LayaBot(FakeAgent())

        criteria = bot.build_questions(game)["action"]["criteria"]

        self.assertIn("all_in", criteria)
        self.assertNotIn("raise", criteria)

    def test_prompt_legacy_si_ofrece_all_in(self):
        from src.game import get_prompt

        bot = LayaBot(FakeAgent(), prompt=get_prompt("legacy_all_in"))

        criteria = bot.build_questions(self.game)["action"]["criteria"]

        self.assertIn("all_in", criteria)

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

    def test_asigna_prompts_ciclicamente(self):
        from src.game import get_prompt

        game = new_game(count=4)
        agent = FakeAgent()
        prompts = [get_prompt("tight"), get_prompt("solid")]

        bots = create_laya_bots(game, agent, prompts=prompts)

        self.assertEqual(
            [b.prompt.name for b in bots],
            ["tight", "solid", "tight", "solid"],
        )


class PromptTests(unittest.TestCase):
    def setUp(self):
        self.game = new_game(count=3)
        self.game.start(shuffle=False)

    def test_prompt_personaliza_las_descripciones(self):
        from src.game import Prompt

        prompt = Prompt(
            name="custom",
            action_text={
                "fold": "TIRAR",
                "check": "PASAR",
                "call": "IGUALAR",
                "bet": "APOSTAR",
                "raise": "SUBIR",
                "all_in": "TODO",
            },
        )
        bot = LayaBot(FakeAgent(), prompt=prompt)

        criteria = bot.build_questions(self.game)["action"]["criteria"]

        self.assertEqual(criteria["fold"], "TIRAR")
        self.assertEqual(criteria["call"], "IGUALAR")

    def test_prompt_persona_aparece_en_el_estado(self):
        from src.game import Prompt

        prompt = Prompt(name="con-persona", persona="Eres un jugador muy tacaño.")
        bot = LayaBot(FakeAgent(), prompt=prompt)

        state = bot.build_state(self.game)

        self.assertTrue(state.startswith("Eres un jugador muy tacaño."))

    def test_prompt_json_devuelve_dict(self):
        from src.game import get_prompt

        bot = LayaBot(FakeAgent(), prompt=get_prompt("json"))

        state = bot.build_state(self.game)

        self.assertIsInstance(state, dict)
        self.assertEqual(state["street"], "preflop")


if __name__ == "__main__":
    unittest.main()
