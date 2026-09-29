"""Motor de bots: conecta el juego con políticas de decisión.

Un ``Bot`` es cualquier objeto con ``decide(game) -> Decision``. El
``BotEngine`` recorre la mano y va preguntando al bot del jugador de turno.

La lógica específica de Laya vive en ``laya_bot.LayaBot``, para que este
módulo (y los tests) no dependan de torch ni del modelo.
"""

from dataclasses import dataclass

try:  # importado como paquete: src.game.bot
    from .game import Action, GameState
except ImportError:  # importado plano (el directorio src/game en el path)
    from game import Action, GameState


@dataclass
class Decision:
    """Lo que decide un bot: una acción y, si aplica, el importe (total a poner)."""

    action: Action
    amount: int = 0

    def __repr__(self):
        if self.action in (Action.BET, Action.RAISE):
            return f"Decision({self.action.name}, {self.amount})"
        return f"Decision({self.action.name})"


class Bot:
    def __init__(self, name: str = "Bot"):
        self.name = name

    def decide(self, game) -> Decision:
        raise NotImplementedError("Cada bot debe implementar decide(game)")

    def __repr__(self):
        return f"{type(self).__name__}({self.name!r})"


class FunctionBot(Bot):
    """Bot a partir de una función. Útil para tests.

    La función recibe el ``Game`` y devuelve un ``Decision`` o una tupla
    ``(Action, amount)``.
    """

    def __init__(self, fn, name: str = "Bot"):
        super().__init__(name)
        self._fn = fn

    def decide(self, game) -> Decision:
        result = self._fn(game)
        if isinstance(result, Decision):
            return result
        action, amount = result
        return Decision(action, amount)


class BotEngine:
    """Pregunta a cada bot y aplica sus decisiones hasta acabar la mano."""

    def __init__(self, game, bots, max_steps: int = 1000):
        if len(bots) != game.seats:
            raise ValueError(
                f"Se esperaban {game.seats} bots, se recibieron {len(bots)}"
            )
        self.game = game
        self.bots = list(bots)
        self.max_steps = max_steps
        self.history: list = []

    def play_hand(self):
        self.game.start_hand()
        return self.play_current_hand()

    def play_current_hand(self):
        """Juega una mano ya repartida (no llama a ``start_hand``)."""
        game = self.game
        steps = 0

        while game.state != GameState.FINISHED:
            if steps >= self.max_steps:
                raise RuntimeError("La mano no terminó: ¿algún bot no actúa?")
            seat = game.currentSeat()
            if seat is None:
                raise RuntimeError("No hay jugador al que actuar")

            decision = self._ask(self.bots[seat], game)
            self._apply(seat, decision)
            steps += 1

        return game

    def play_hands(self, count: int):
        """Juega varias manos. Se detiene si quedan menos de dos jugadores con fichas."""
        played = 0
        for _ in range(count):
            if sum(1 for p in self.game.players if p.getChips() > 0) < 2:
                break
            self.play_hand()
            played += 1
        return played

    # ------------------------------------------------------------------ interno
    def _ask(self, bot, game) -> Decision:
        try:
            decision = bot.decide(game)
        except Exception:  # noqa: BLE001 - un bot roto no debe colgar la partida
            decision = None
        if not isinstance(decision, Decision):
            decision = self._safe_action(game)
        return decision

    def _apply(self, seat, decision: Decision):
        game = self.game
        applied = decision
        try:
            game.act(decision.action, decision.amount)
        except (ValueError, RuntimeError):
            applied = self._safe_action(game)
            game.act(applied.action, applied.amount)
        self.history.append((game.hand_number, seat, applied.action, applied.amount))

    def _safe_action(self, game) -> Decision:
        """Acción conservadora cuando un bot falla o devuelve algo ilegal."""
        seat = game.currentSeat()
        player = game.players[seat]
        to_call = game.current_bet - player.getCurrentBet()
        if to_call == 0:
            return Decision(Action.CHECK)
        return Decision(Action.FOLD)
