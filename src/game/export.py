"""Exporta manos a JSON para animarlas desde otro software.

El formato es una lista de manos; cada mano contiene:

  * ``hand_id``, ``blinds``, ``button_seat``
  * ``seats``: jugadores con asiento, nombre, posición, stack y cartas.
  * ``events``: lista ordenada de eventos de la mano. Cada evento lleva
    ``street`` y el ``pot`` acumulado **después** del evento.
  * ``result``: ganadores y bote total.

Tipos de evento:
  * ``post_blind``: ciegas al empezar la mano.
  * ``deal``: cartas comunitarias que salen en una calle.
  * ``action``: fold / check / call / bet / raise / all_in, con el importe
    total puesto por el jugador en esa acción y su stack restante.
  * ``showdown``: manos que ligó cada jugador vivo.
"""

import json

from .evaluator import describe, evaluate
from .game import GameState
from .positions import seat_position_names


def _card(card):
    return str(card)


def _street_name(state):
    return {
        GameState.PREFLOP: "preflop",
        GameState.FLOP: "flop",
        GameState.TURN: "turn",
        GameState.RIVER: "river",
        GameState.SHOWDOWN: "showdown",
    }.get(state, "finished")


class HandRecorder:
    """Recoge los eventos de una mano y la serializa a JSON.

    Se conecta al ``BotEngine`` con ``on_action`` y se inicializa con
    ``begin`` tras repartir. El bote de cada evento se calcula sumando los
    aportes registrados, para que sea consistente aunque el hook se llame
    después de aplicar la acción.
    """

    def __init__(self, game, positions=None):
        self.game = game
        self.positions = positions or {}
        self.events = []
        self.initial_stacks = []
        self.button_seat = None
        self._pot = 0
        self._street = None
        self._board_len = 0
        # Aportes acumulados por asiento ya contabilizados en el bote.
        self._contribuido = {}

    def begin(self, initial_stacks, button_seat):
        """Registra el estado inicial y las ciegas ya posteadas."""
        self.initial_stacks = list(initial_stacks)
        self.button_seat = button_seat
        game = self.game
        self._street = _street_name(game.state)
        self._board_len = 0
        self._pot = 0
        # Las ciegas ya están en juego: las contamos como aportadas.
        self._contribuido = {i: game.players[i].contributed for i in range(game.seats)}

        for seat, blind in (
            (game.small_blind_seat, "small"),
            (game.big_blind_seat, "big"),
        ):
            aportado = game.players[seat].getCurrentBet()
            self._pot += aportado
            self.events.append(
                {
                    "type": "post_blind",
                    "street": "preflop",
                    "seat": seat,
                    "blind": blind,
                    "amount": aportado,
                    "stack_after": game.players[seat].getChips(),
                    "pot_after": self._pot,
                }
            )

    # ------------------------------------------------------------------ hook
    def on_action(self, event):
        """Callback conectado a ``BotEngine(on_action=...)``.

        El incremento del bote se calcula con ``player.contributed``, que el
        motor solo acumula y nunca reinicia dentro de la mano. Así es correcto
        aunque la acción cierre la calle y el motor reinicie las apuestas.
        """
        street = _street_name(event["state_before"])
        game = self.game

        if street != self._street:
            self._record_deal(street)

        decision = event["action"]
        seat = event["seat"]
        player = game.players[seat]
        anterior = self._contribuido.get(seat, 0)
        incremento = max(0, player.contributed - anterior)
        self._contribuido[seat] = player.contributed
        self._pot += incremento
        self.events.append(
            {
                "type": "action",
                "street": street,
                "seat": seat,
                "action": decision.action.name.lower(),
                "amount": decision.amount,
                "bet_increment": incremento,
                "stack_after": player.getChips(),
                "pot_after": self._pot,
            }
        )

    def _record_deal(self, street):
        game = self.game
        nuevas = game.community[self._board_len :]
        self._board_len = len(game.community)
        self._street = street
        if nuevas:
            self.events.append(
                {
                    "type": "deal",
                    "street": street,
                    "cards": [_card(c) for c in nuevas],
                    "pot_after": self._pot,
                }
            )

    def to_dict(self):
        game = self.game
        # Puede haber cartas comunitarias repartidas tras la última acción
        # (por ejemplo, si la mano termina en esa calle).
        if len(game.community) > self._board_len:
            self._record_deal(_street_name(game.state))
        events = list(self.events)

        vivos = [p for p in game.players if p.isActive()]
        if len(vivos) >= 2 and game.community:
            manos = []
            for i, p in enumerate(game.players):
                if not p.isActive():
                    continue
                score = evaluate(p.getHand() + game.community)
                manos.append(
                    {"seat": i, "best_hand": describe(score), "score": list(score)}
                )
            events.append(
                {
                    "type": "showdown",
                    "street": "showdown",
                    "community_cards": [_card(c) for c in game.community],
                    "hands": manos,
                    "pot_after": sum(p.contributed for p in game.players),
                }
            )

        return {
            "hand_id": game.hand_number,
            "blinds": {"small": game.small_blind, "big": game.big_blind},
            "button_seat": self.button_seat,
            "seats": [
                {
                    "seat": i,
                    "name": p.getName(),
                    "position": self.positions.get(i, "?"),
                    "initial_stack": self.initial_stacks[i],
                    "hole_cards": [_card(c) for c in p.getHand()],
                    "folded": p.isFolded(),
                    "all_in": p.isAllIn(),
                }
                for i, p in enumerate(game.players)
            ],
            "community_cards": [_card(c) for c in game.community],
            "events": events,
            "result": {
                "total_pot": sum(p.contributed for p in game.players),
                "players": [
                    {
                        "seat": i,
                        "stack_after": p.getChips(),
                        "net": p.getChips() - self.initial_stacks[i],
                        "folded": p.isFolded(),
                    }
                    for i, p in enumerate(game.players)
                ],
            },
        }


def hand_positions(game):
    """Posiciones por asiento para la mano en curso."""
    if game.small_blind_seat is None:
        return {}
    return seat_position_names(game.seats, game.button, game.small_blind_seat)


def write_hands(path, hands):
    """Escribe la lista de manos en un JSON."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(hands, fh, ensure_ascii=False, indent=2)
