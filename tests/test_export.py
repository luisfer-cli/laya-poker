import json
import tempfile
import unittest

from src.game import Action, Game, Player
from src.game.export import HandRecorder, hand_positions, write_hands


def new_game(stacks=(1000, 1000, 1000)):
    players = [Player(f"P{i}", chips) for i, chips in enumerate(stacks)]
    return Game(players, small_blind=5, big_blind=10)


def fake_decision(action, amount=0):
    from src.game import Decision

    return Decision(action, amount)


def feed(recorder, game, seat, action, amount=0, state_before=None):
    before = state_before if state_before is not None else game.state
    game.act(action, amount)
    recorder.on_action(
        {
            "hand_number": game.hand_number,
            "seat": seat,
            "state_before": before,
            "action": fake_decision(action, amount),
            "stack_after": game.players[seat].getChips(),
            "pot_after": game.pot,
        }
    )


class HandRecorderTests(unittest.TestCase):
    def test_bote_de_los_eventos_cuadra_con_el_real(self):
        game = new_game()
        game.start(shuffle=False)
        rec = HandRecorder(game, hand_positions(game))
        rec.begin([1000, 1000, 1000], game.button)

        # Preflop, flop, turn y river con apuestas.
        for seat, action, amount in [
            (0, Action.CALL, 0),
            (1, Action.RAISE, 20),
            (2, Action.FOLD, 0),
            (0, Action.CALL, 0),
            (1, Action.BET, 50),
            (0, Action.CALL, 0),
        ]:
            feed(rec, game, seat, action, amount)

        data = rec.to_dict()
        bote_real = sum(p.contributed for p in game.players)
        self.assertEqual(data["events"][-1]["pot_after"], bote_real)

    def test_las_ciegas_se_registran(self):
        game = new_game()
        game.start(shuffle=False)
        rec = HandRecorder(game, hand_positions(game))
        rec.begin([1000, 1000, 1000], game.button)

        ciegas = [e for e in rec.events if e["type"] == "post_blind"]
        self.assertEqual(len(ciegas), 2)
        self.assertEqual(ciegas[0]["blind"], "small")
        self.assertEqual(ciegas[0]["amount"], 5)
        self.assertEqual(ciegas[1]["blind"], "big")
        self.assertEqual(ciegas[1]["amount"], 10)
        self.assertEqual(ciegas[-1]["pot_after"], 15)

    def test_deal_lleva_el_bote_al_abrir_la_calle(self):
        game = new_game()
        game.start(shuffle=False)
        rec = HandRecorder(game, hand_positions(game))
        rec.begin([1000, 1000, 1000], game.button)

        for seat, action, amount in [
            (0, Action.CALL, 0),
            (1, Action.CALL, 0),
            (2, Action.CHECK, 0),
        ]:
            feed(rec, game, seat, action, amount)

        deal = next(e for e in rec.to_dict()["events"] if e["type"] == "deal")
        self.assertEqual(deal["street"], "flop")
        self.assertEqual(len(deal["cards"]), 3)
        self.assertEqual(deal["pot_after"], 30)  # 10 de cada jugador

    def test_estructura_de_la_mano(self):
        game = new_game()
        game.start(shuffle=False)
        rec = HandRecorder(game, hand_positions(game))
        rec.begin([1000, 1000, 1000], game.button)
        feed(rec, game, 0, Action.FOLD)
        feed(rec, game, 1, Action.FOLD)

        data = rec.to_dict()
        self.assertEqual(data["hand_id"], 1)
        self.assertEqual(data["blinds"], {"small": 5, "big": 10})
        self.assertEqual(len(data["seats"]), 3)
        self.assertIn("hole_cards", data["seats"][0])
        self.assertIn("result", data)
        self.assertEqual(data["result"]["total_pot"], 15)

    def test_showdown_incluye_las_manos(self):
        game = new_game((1000, 1000))
        game.start(shuffle=False)
        rec = HandRecorder(game, hand_positions(game))
        rec.begin([1000, 1000], game.button)

        feed(rec, game, 0, Action.CALL)
        feed(rec, game, 1, Action.CHECK)
        for _ in range(3):
            feed(rec, game, 1, Action.CHECK)
            feed(rec, game, 0, Action.CHECK)

        data = rec.to_dict()
        showdown = next(e for e in data["events"] if e["type"] == "showdown")
        self.assertEqual(len(showdown["hands"]), 2)
        self.assertIn("best_hand", showdown["hands"][0])


class WriteHandsTests(unittest.TestCase):
    def test_escribe_json_valido(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
            path = fh.name
        write_hands(path, [{"hand_id": 1}])
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data, [{"hand_id": 1}])


if __name__ == "__main__":
    unittest.main()
