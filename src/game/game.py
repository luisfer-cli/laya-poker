"""Motor de Texas Hold'em No-Limit con las reglas oficiales.

Reglas implementadas:
  * Ciegas (pequeña y grande) y botón que rota cada mano; en heads-up el botón
    postea la ciega pequeña y actúa primero preflop, pero postflop lo hace la
    ciega grande.
  * Reparto de dos cartas por jugador en dos rondas, empezando a la izquierda
    del botón.
  * Una carta quemada (burn) antes del flop, del turn y del river.
  * Rondas de apuestas preflop, flop, turn y river; el postflop abre el juego
    el jugador a la izquierda del botón.
  * Apuesta mínima postflop = ciega grande; subida mínima = última subida
    completa.
  * All-in (incluido el all-in corto, que no reabre la apuesta a quien ya
    actuó; varios all-ins cortos que sumen una subida completa sí la reabren).
  * Botes laterales (side pots) y reparto del bote con empates.

Flujo de una mano:

    game = Game([Player("Ana", 1000), Player("Beto", 1000)], big_blind=10)
    game.start_hand()
    while game.state not in (GameState.FINISHED,):
        game.act(Action.CALL)   # actúa el jugador de turno (game.currentPlayer())
        ...
"""

try:  # importado como paquete: src.game.game
    from .deck import Deck
    from .evaluator import evaluate
    from .player import Player
    from .pot import build_side_pots
except ImportError:  # importado plano (el directorio src/game en el path)
    from deck import Deck
    from evaluator import evaluate
    from player import Player
    from pot import build_side_pots

from enum import Enum, IntEnum, auto


class GameState(Enum):
    WAITING = auto()
    PREFLOP = auto()
    FLOP = auto()
    TURN = auto()
    RIVER = auto()
    SHOWDOWN = auto()
    FINISHED = auto()


class Action(IntEnum):
    FOLD = auto()
    CHECK = auto()
    CALL = auto()
    BET = auto()
    RAISE = auto()
    ALL_IN = auto()


class Game:
    def __init__(
        self, players: list[Player], small_blind: int = 5, big_blind: int = 10
    ):
        self.players: list[Player] = players
        self.seats = len(players)
        self.deck = Deck()
        self.state = GameState.WAITING

        self.small_blind = small_blind
        self.big_blind = big_blind

        self.button = self.seats - 1  # se avanza al empezar la primera mano
        self.small_blind_seat = None
        self.big_blind_seat = None

        self.community: list = []
        self.pot = 0
        self.current_bet = 0
        self.min_raise = big_blind
        # Apuesta en la última subida completa y tamaño de esa subida, para
        # calcular el mínimo de re-subida y si los all-ins cortos reabren.
        self.last_full_bet = big_blind
        self.last_full_raise = big_blind
        self.to_act: list[int] = []
        self.hand_number = 0

    # ------------------------------------------------------------------ setup
    def start(self, shuffle: bool = True):
        """Alias de ``start_hand`` (compatibilidad)."""
        return self.start_hand(shuffle=shuffle)

    def start_hand(self, shuffle: bool = True):
        if shuffle:
            self.deck.reset()
            self.deck.shuffle()

        self.hand_number += 1
        self.community = []
        self.pot = 0
        self.current_bet = 0
        self.min_raise = self.big_blind
        self.last_full_bet = self.big_blind
        self.last_full_raise = self.big_blind

        for player in self.players:
            player.resetForHand()

        # Los jugadores sin fichas no participan.
        for player in self.players:
            if player.getChips() <= 0:
                player.setFolded(True)

        ocupados = [i for i, p in enumerate(self.players) if p.isActive()]
        if len(ocupados) < 2:
            self.state = GameState.FINISHED
            return

        # Reparte dos cartas a cada jugador, una ronda de una carta a la vez
        # empezando por el jugador a la izquierda del botón (que aún es el de
        # la mano anterior; el botón se mueve después, pero el efecto es el
        # mismo: se reparte en el sentido de las agujas del reloj).
        reparto = self._order_from(self._next_seat(self.button, lambda i: True))
        reparto = [i for i in reparto if self.players[i].isActive()]
        for _ in range(2):
            for i in reparto:
                self.players[i].getHand().append(self.deck.draw())

        # Mueve el botón al siguiente jugador con fichas.
        self.button = self._next_seat(self.button, lambda i: self.players[i].isActive())
        self._post_blinds()

        self.state = GameState.PREFLOP
        first = self._next_seat(self.big_blind_seat, self._can_act)
        self.to_act = self._open_betting(first)

        if not self.to_act:
            self._finish_betting()

    # ------------------------------------------------------------------ turnos
    def currentSeat(self):
        """Índice del jugador al que le toca actuar, o None."""
        return self.to_act[0] if self.to_act else None

    def currentPlayer(self):
        seat = self.currentSeat()
        return None if seat is None else self.players[seat]

    def act(self, action, amount: int = 0):
        """Aplica una acción del jugador de turno.

        ``amount`` es, para BET/RAISE, el total al que sube la apuesta en esta
        calle (no el incremento).
        """
        if self.state in (GameState.WAITING, GameState.SHOWDOWN, GameState.FINISHED):
            raise RuntimeError("La mano no está en curso")
        if not self.to_act:
            raise RuntimeError("No hay jugador al que le toque actuar")

        idx = self.to_act[0]
        player = self.players[idx]
        to_call = max(0, self.current_bet - player.getCurrentBet())

        aggressive = False
        reopen = True

        if action == Action.FOLD:
            player.setFolded(True)

        elif action == Action.CHECK:
            if to_call != 0:
                raise ValueError("No puedes pasar: hay una apuesta pendiente")

        elif action == Action.CALL:
            self._commit(player, to_call)

        elif action in (Action.BET, Action.RAISE):
            if to_call == 0 and self.current_bet > 0 and action == Action.BET:
                raise ValueError("No puedes apostar: ya hay una apuesta, usa RAISE")
            if amount <= self.current_bet:
                raise ValueError("La subida debe superar la apuesta actual")

            raise_size = amount - self.current_bet
            alcanzable = player.getChips() + player.getCurrentBet()
            if raise_size < self.min_raise and amount < alcanzable:
                raise ValueError(
                    f"La subida mínima es {self.min_raise} (subir a "
                    f"{self.current_bet + self.min_raise})"
                )

            add = amount - player.getCurrentBet()
            if add > player.getChips():
                raise ValueError("No tienes fichas suficientes, usa ALL_IN")
            self._commit(player, add)
            self.current_bet = amount
            aggressive = True
            # Subir menos del mínimo solo es legal cuando es un all-in; en ese
            # caso no reabre la apuesta a quien ya actuó en esta calle.
            reopen = raise_size >= self.min_raise
            if reopen:
                self.last_full_bet = amount
                self.last_full_raise = raise_size
                self.min_raise = raise_size
            else:
                self.min_raise = self.last_full_raise

        elif action == Action.ALL_IN:
            add = player.getChips()
            self._commit(player, add)
            if player.getCurrentBet() > self.current_bet:
                # Los all-ins cortos reabren si, entre todos, superan la apuesta
                # anterior en al menos el tamaño de la última subida completa.
                reopen = (
                    player.getCurrentBet() - self.last_full_bet >= self.last_full_raise
                )
                if reopen:
                    self.last_full_raise = player.getCurrentBet() - self.last_full_bet
                    self.last_full_bet = player.getCurrentBet()
                    self.min_raise = self.last_full_raise
                else:
                    self.min_raise = self.last_full_raise
                self.current_bet = player.getCurrentBet()
                aggressive = True

        else:
            raise ValueError(f"Acción desconocida: {action}")

        self._register_action(idx, player, aggressive, reopen)

    def _register_action(self, idx, player, aggressive, reopen=True):
        if idx in self.to_act:
            self.to_act.remove(idx)

        activos = [i for i, p in enumerate(self.players) if p.isActive()]
        if len(activos) == 1:
            self._award_uncontested(activos[0])
            return

        if aggressive:
            # Tras una subida que reabre, todos los que aún pueden actuar deben
            # responder, en orden a partir del asiento siguiente al que subió.
            if reopen:
                first = self._next_seat(idx, self._can_act)
                self.to_act = [i for i in self._order_from(first) if i != idx]
            else:
                # All-in corto: no reabre la apuesta. Solo deben responder los
                # que aún no habían igualado la apuesta actual y no han
                # actuado todavía en esta calle; quien ya actuó solo puede
                # igualar o retirarse, así que se le deja en la cola solo si
                # le falta por poner.
                pendientes = [
                    i
                    for i in range(self.seats)
                    if i != idx
                    and self._can_act(i)
                    and self.players[i].getCurrentBet() < self.current_bet
                    and i in self.to_act
                ]
                if pendientes:
                    first = self._next_seat(
                        idx,
                        lambda i: i in pendientes,
                    )
                    self.to_act = [
                        i for i in self._order_from(first) if i in pendientes
                    ]
                else:
                    self.to_act = []

        if not self.to_act:
            self._finish_betting()

    # ------------------------------------------------------------------ calles
    def _finish_betting(self):
        while self.state not in (GameState.SHOWDOWN, GameState.FINISHED):
            self._advance_street()
            if self.to_act:
                return

    def _advance_street(self):
        if self.state == GameState.PREFLOP:
            self._burn()
            self._deal_community(3)
            self.state = GameState.FLOP
        elif self.state == GameState.FLOP:
            self._burn()
            self._deal_community(1)
            self.state = GameState.TURN
        elif self.state == GameState.TURN:
            self._burn()
            self._deal_community(1)
            self.state = GameState.RIVER
        elif self.state == GameState.RIVER:
            self.showdown()
            return
        else:
            return

        self.current_bet = 0
        # La apuesta mínima postflop es la ciega grande.
        self.min_raise = self.big_blind
        self.last_full_bet = self.big_blind
        self.last_full_raise = self.big_blind
        for player in self.players:
            player.setCurrentBet(0)
        first = self._next_seat(self.button, self._can_act)
        self.to_act = self._open_betting(first)

    def _open_betting(self, first):
        """Abre ronda solo si hay al menos dos jugadores que puedan actuar."""
        pueden = [i for i in range(self.seats) if self._can_act(i)]
        if len(pueden) < 2:
            return []
        return self._order_from(first)

    def _burn(self):
        """Quema una carta antes de repartir las comunitarias (regla oficial)."""
        if len(self.deck) > 0:
            self.deck.draw()

    def _deal_community(self, count):
        self.community.extend(self.deck.draw_many(count))

    # ---------------------------------------------------------------- showdown
    def showdown(self):
        self.state = GameState.SHOWDOWN
        pots = build_side_pots(self.players)

        for pot in pots:
            if not pot.eligible:
                continue
            scores = [
                (evaluate(player.getHand() + self.community), player)
                for player in pot.eligible
            ]
            best = max(score for score, _ in scores)
            winners = [player for score, player in scores if score == best]
            share, remainder = divmod(pot.amount, len(winners))
            for position, winner in enumerate(winners):
                extra = 1 if position < remainder else 0
                winner.setChips(winner.getChips() + share + extra)

        self.pot = 0
        self.state = GameState.FINISHED

    def _award_uncontested(self, winner_index):
        winner = self.players[winner_index]
        winner.setChips(winner.getChips() + self.pot)
        self.pot = 0
        self.state = GameState.FINISHED

    # ------------------------------------------------------------------ helper
    def _commit(self, player, amount):
        amount = max(0, min(amount, player.getChips()))
        player.setChips(player.getChips() - amount)
        player.setCurrentBet(player.getCurrentBet() + amount)
        player.contributed += amount
        self.pot += amount
        # Si pagó todo lo que le quedaba, ya no puede actuar en esta mano.
        if player.getChips() == 0:
            player.setAllIn(True)
        return amount

    def _can_act(self, index):
        return self.players[index].canAct()

    def _next_seat(self, start, predicate):
        for step in range(1, self.seats + 1):
            i = (start + step) % self.seats
            if predicate(i):
                return i
        return start

    def _order_from(self, first):
        order = []
        i = first
        for _ in range(self.seats):
            if self._can_act(i):
                order.append(i)
            i = (i + 1) % self.seats
        return order

    # ------------------------------------------------------------------ ciegas
    def _post_blinds(self):
        if len([p for p in self.players if p.isActive()]) == 2:
            self.small_blind_seat = self.button
        else:
            self.small_blind_seat = self._next_seat(
                self.button, lambda i: self.players[i].isActive()
            )
        self.big_blind_seat = self._next_seat(
            self.small_blind_seat, lambda i: self.players[i].isActive()
        )

        self._commit(self.players[self.small_blind_seat], self.small_blind)
        self._commit(self.players[self.big_blind_seat], self.big_blind)
        self.current_bet = max(
            self.players[self.small_blind_seat].getCurrentBet(),
            self.players[self.big_blind_seat].getCurrentBet(),
        )
        self.min_raise = self.big_blind
        self.last_full_bet = self.big_blind
        self.last_full_raise = self.big_blind

    def __repr__(self):
        return f"Game({self.seats} jugadores, {self.state.name})"
