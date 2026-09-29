import unittest

from src.game import Action, Card, Game, GameState, HandCategory, Player, evaluate


def c(text):
    return Card(text[:-1], text[-1])


def jugadores(ficheros):
    return [Player(f"P{i}", fichas) for i, fichas in enumerate(ficheros)]


def stack_deck(game, orden):
    """Prepara el mazo para que las cartas salgan en ``orden`` (pop desde el final)."""
    game.deck.cards = list(reversed(orden))


class GameSetupTests(unittest.TestCase):
    def test_reparte_dos_cartas_y_cobra_ciegas(self):
        game = Game(jugadores([1000, 1000, 1000]), small_blind=5, big_blind=10)
        game.start(shuffle=False)

        self.assertEqual(game.state, GameState.PREFLOP)
        for player in game.players:
            self.assertEqual(len(player.getHand()), 2)
        self.assertEqual(game.pot, 15)
        # Botón en el asiento 0, ciegas en 1 y 2.
        self.assertEqual(game.button, 0)
        self.assertEqual(game.small_blind_seat, 1)
        self.assertEqual(game.big_blind_seat, 2)
        self.assertEqual(game.players[1].getCurrentBet(), 5)
        self.assertEqual(game.players[2].getCurrentBet(), 10)
        self.assertEqual(len(game.deck), 52 - 6)

    def test_ciegas_en_heads_up(self):
        game = Game(jugadores([1000, 1000]), small_blind=5, big_blind=10)
        game.start(shuffle=False)
        # En heads-up el botón pone la ciega pequeña.
        self.assertEqual(game.button, game.small_blind_seat)
        self.assertEqual(game.big_blind_seat, 1)

    def test_fold_gana_el_bote_sin_showdown(self):
        game = Game(jugadores([1000, 1000, 1000]), small_blind=5, big_blind=10)
        game.start(shuffle=False)

        game.act(Action.FOLD)  # P0 (botón)
        game.act(Action.FOLD)  # P1 (ciega pequeña)

        self.assertEqual(game.state, GameState.FINISHED)
        self.assertEqual(game.players[2].getChips(), 1005)  # 1000 - 10 + 15
        self.assertEqual(game.players[1].getChips(), 995)
        self.assertEqual(game.players[0].getChips(), 1000)
        self.assertEqual(game.pot, 0)

    def test_pasar_cuando_hay_apuesta_falla(self):
        game = Game(jugadores([1000, 1000, 1000]), small_blind=5, big_blind=10)
        game.start(shuffle=False)
        # P0 tiene que igualar los 10 de la ciega grande.
        with self.assertRaises(ValueError):
            game.act(Action.CHECK)

    def test_subida_minima(self):
        game = Game(jugadores([1000, 1000, 1000]), small_blind=5, big_blind=10)
        game.start(shuffle=False)
        with self.assertRaises(ValueError):
            game.act(Action.RAISE, 15)  # sube solo 5, mínimo 10
        game.act(Action.RAISE, 20)  # válida
        self.assertEqual(game.current_bet, 20)
        self.assertEqual(game.min_raise, 10)


class GameFlowTests(unittest.TestCase):
    def test_avanza_por_las_calles(self):
        game = Game(jugadores([1000, 1000]), small_blind=5, big_blind=10)
        game.start(shuffle=False)

        game.act(Action.CALL)  # P0 (botón/ciega pequeña) iguala
        self.assertEqual(game.state, GameState.PREFLOP)
        game.act(Action.CHECK)  # P1 comprueba

        self.assertEqual(game.state, GameState.FLOP)
        self.assertEqual(len(game.community), 3)

        # Postflop actúa primero el asiento a la izquierda del botón.
        self.assertIs(game.currentPlayer(), game.players[1])
        game.act(Action.CHECK)
        game.act(Action.CHECK)
        self.assertEqual(game.state, GameState.TURN)
        self.assertEqual(len(game.community), 4)

        game.act(Action.CHECK)
        game.act(Action.CHECK)
        self.assertEqual(game.state, GameState.RIVER)
        self.assertEqual(len(game.community), 5)

        game.act(Action.CHECK)
        game.act(Action.CHECK)
        self.assertEqual(game.state, GameState.FINISHED)

    def test_all_in_reabre_la_accion_a_quien_ya_actuo(self):
        game = Game(jugadores([1000, 1000, 1000, 1000]), small_blind=5, big_blind=10)
        game.start(shuffle=False)

        # Preflop actúan P3, P0, P1 y luego P2.
        game.act(Action.CALL)  # P3
        game.act(Action.CALL)  # P0
        game.act(Action.CALL)  # P1
        self.assertEqual([game.players[i].getName() for i in game.to_act], ["P2"])

        game.act(Action.ALL_IN)  # P2, el último

        # Los tres que ya habían igualado deben volver a responder.
        self.assertEqual(
            [game.players[i].getName() for i in game.to_act], ["P3", "P0", "P1"]
        )

    def test_all_in_corto_no_reabre_la_accion(self):
        game = Game(jugadores([1000, 1000, 1000]), small_blind=5, big_blind=10)
        game.start(shuffle=False)

        # P0 es la ciega pequeña: con 105 fichas, "subir a 100" es su all-in.
        game.players[0].setChips(100)
        game.act(Action.RAISE, 100)
        self.assertTrue(game.players[0].isAllIn())
        self.assertEqual(game.current_bet, 100)
        self.assertEqual([game.players[i].getName() for i in game.to_act], ["P1", "P2"])

        # P1 (aún sin actuar) va all-in corto: 155, sube 55 < 100.
        game.players[1].setChips(150)
        game.act(Action.ALL_IN)
        self.assertEqual(game.current_bet, 155)

        # P2 (ciega grande) debe responder; P0 ya está all-in, así que no actúa,
        # pero el all-in corto tampoco reabre la subida a nadie más.
        self.assertEqual([game.players[i].getName() for i in game.to_act], ["P2"])

    def test_jugador_que_aporta_menos_de_una_ciega_queda_all_in(self):
        # P0 es el botón, P1 la ciega pequeña con solo 3 fichas y P2 la grande.
        game = Game(jugadores([1000, 3, 1000]), small_blind=5, big_blind=10)
        game.start(shuffle=False)

        corto = game.players[1]
        self.assertTrue(corto.isAllIn())  # no llega ni a la ciega pequeña
        self.assertEqual(corto.getChips(), 0)
        self.assertEqual(corto.getCurrentBet(), 3)
        self.assertEqual(game.pot, 3 + 10)
        # Aun estando all-in, los demás siguen pudiendo actuar.
        self.assertTrue(game.to_act)


class ShowdownTests(unittest.TestCase):
    def test_showdown_reparte_el_bote_al_mejor(self):
        game = Game(jugadores([1000, 1000]), small_blind=5, big_blind=10)
        stack_deck(
            game,
            [
                c("As"),
                c("Ks"),  # P0, P1 (1ª carta)
                c("Ah"),
                c("Kh"),  # P0, P1 (2ª carta)
                c("2c"),
                c("3d"),
                c("4h"),  # flop
                c("5s"),  # turn
                c("7c"),  # river
            ],
        )
        game.start(shuffle=False)

        game.act(Action.CALL)  # P0 iguala la ciega
        game.act(Action.CHECK)  # P1
        game.act(Action.CHECK)
        game.act(Action.CHECK)  # flop
        game.act(Action.CHECK)
        game.act(Action.CHECK)  # turn
        game.act(Action.CHECK)
        game.act(Action.CHECK)  # river -> showdown

        self.assertEqual(game.state, GameState.FINISHED)
        # P0 gana con pareja de ases; el bote era 20.
        self.assertEqual(game.players[0].getChips(), 1010)
        self.assertEqual(game.players[1].getChips(), 990)

    def test_side_pots_con_all_in(self):
        game = Game(jugadores([100, 50, 200]), small_blind=5, big_blind=10)
        stack_deck(
            game,
            [
                c("As"),
                c("Ks"),
                c("Qs"),  # 1ª carta
                c("Ah"),
                c("Kh"),
                c("Qh"),  # 2ª carta
                c("2c"),
                c("7d"),
                c("9h"),  # flop
                c("Js"),  # turn
                c("4c"),  # river
            ],
        )
        game.start(shuffle=False)

        game.act(Action.ALL_IN)  # P0 (botón) va all-in con 100
        game.act(Action.ALL_IN)  # P1 (ciega pequeña) all-in con 50
        game.act(Action.CALL)  # P2 (ciega grande) iguala los 100

        self.assertEqual(game.state, GameState.FINISHED)
        self.assertEqual(len(game.community), 5)
        # P0 gana con pareja de ases el bote principal y el lateral.
        score = evaluate(game.players[0].getHand() + game.community)
        self.assertEqual(score[0], HandCategory.PAIR)
        self.assertEqual(game.players[0].getChips(), 250)
        self.assertEqual(game.players[1].getChips(), 0)
        self.assertEqual(game.players[2].getChips(), 100)
        # No se pierden fichas por el camino.
        self.assertEqual(sum(p.getChips() for p in game.players), 350)


class EngineTests(unittest.TestCase):
    def test_el_boton_rota_entre_manos(self):
        players = jugadores([1000, 1000, 1000, 1000])
        game = Game(players, small_blind=5, big_blind=10)
        game.start(shuffle=False)
        self.assertEqual(game.button, 0)

        for _ in range(3):  # todos se retiran menos la ciega grande
            game.act(Action.FOLD)
        self.assertEqual(game.state, GameState.FINISHED)

        game.start(shuffle=False)
        self.assertEqual(game.button, 1)

    def test_jugador_sin_fichas_no_recibe_cartas(self):
        players = [Player("A", 1000), Player("B", 0), Player("C", 1000)]
        game = Game(players, small_blind=5, big_blind=10)
        game.start(shuffle=False)

        self.assertTrue(players[1].isFolded())
        self.assertEqual(players[1].getHand(), [])
        # Solo quedan dos jugadores activos: ciegas de heads-up.
        self.assertEqual(game.small_blind_seat, game.button)
        self.assertEqual(game.players[0].getCurrentBet(), 5)
        self.assertEqual(game.players[2].getCurrentBet(), 10)

    def test_bote_empatado_se_reparte(self):
        game = Game(jugadores([1000, 1000]), small_blind=5, big_blind=10)
        stack_deck(
            game,
            [
                c("2c"),
                c("2h"),
                c("3d"),
                c("3s"),
                c("As"),
                c("Kd"),
                c("Qh"),
                c("Jc"),
                c("10s"),  # el board da escalera al cielo a los dos
            ],
        )
        game.start(shuffle=False)
        game.act(Action.CALL)
        game.act(Action.CHECK)
        for _ in range(3):  # flop, turn y river con checks
            game.act(Action.CHECK)
            game.act(Action.CHECK)

        self.assertEqual(game.state, GameState.FINISHED)
        self.assertEqual(game.players[0].getChips(), 1000)
        self.assertEqual(game.players[1].getChips(), 1000)


if __name__ == "__main__":
    unittest.main()
