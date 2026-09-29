"""Bot que decide con el modelo Laya.

``LayaBot`` no depende de ``laya`` en tiempo de importación: recibe un objeto
``agent`` con un método ``predict(state, questions)``. Para el modelo real,
usa ``load_agent()``; para tests, basta con un doble que devuelva respuestas.

El bot construye un ``state`` en lenguaje natural (el formato que mejor
entiende Laya) y preguntas de tipo ``choice``: una para la acción y otra para
el tamaño de la subida.
"""

try:  # importado como paquete: src.game.laya_bot
    from .bot import Bot, Decision
    from .game import Action
except ImportError:  # importado plano (el directorio src/game en el path)
    from bot import Bot, Decision

    from game import Action


ACTION_INSTRUCTIONS = (
    "You are playing No-Limit Texas Hold'em. Read the table state and choose "
    "the best action for the hero. Consider pot odds, position and stack size."
)

SIZE_INSTRUCTIONS = (
    "Choose how many chips the hero should end up with in front this street "
    "when betting or raising."
)

_SUIT_NAMES = {"♠️": "spades", "♥️": "hearts", "♦️": "diamonds", "♣️": "clubs"}
_RANK_NAMES = {"A": "Ace", "K": "King", "Q": "Queen", "J": "Jack", "10": "Ten"}


def card_text(card) -> str:
    """Carta en texto legible para el modelo, p. ej. 'Ace of spades'."""
    rank = _RANK_NAMES.get(card.getRank(), card.getRank())
    suit = _SUIT_NAMES.get(card.getSuit(), card.getSuit())
    return f"{rank} of {suit}"


class LayaBot(Bot):
    def __init__(self, agent, name: str = "Laya", min_confidence: float = 0.0):
        super().__init__(name)
        self.agent = agent
        self.min_confidence = min_confidence

    # ------------------------------------------------------------- decisión
    def decide(self, game) -> Decision:
        state = self.build_state(game)
        questions = self.build_questions(game)
        result = self.agent.predict(state, questions)
        return self.parse(result, game)

    # --------------------------------------------------------------- estado
    def build_context(self, game) -> dict:
        """Datos estructurados de la situación (para depurar y testear)."""
        seat = game.currentSeat()
        player = game.players[seat]
        to_call = game.current_bet - player.getCurrentBet()

        return {
            "game": "No-Limit Texas Hold'em",
            "street": game.state.name.lower(),
            "hand_number": game.hand_number,
            "pot": game.pot,
            "board": [card_text(card) for card in game.community],
            "to_call": to_call,
            "min_raise_to": game.current_bet + game.min_raise,
            "hero": {
                "seat": seat,
                "name": player.getName(),
                "position": self._position(game, seat),
                "chips": player.getChips(),
                "hole_cards": [card_text(card) for card in player.getHand()],
                "current_bet": player.getCurrentBet(),
                "to_call": to_call,
            },
            "players": [
                {
                    "seat": i,
                    "name": p.getName(),
                    "chips": p.getChips(),
                    "current_bet": p.getCurrentBet(),
                    "folded": p.isFolded(),
                    "all_in": p.isAllIn(),
                    "is_hero": i == seat,
                }
                for i, p in enumerate(game.players)
            ],
        }

    def build_state(self, game) -> str:
        """Situation en lenguaje natural, el formato que mejor entiende Laya."""
        ctx = self.build_context(game)
        hero = ctx["hero"]
        board = ", ".join(ctx["board"]) if ctx["board"] else "none"

        rivals = []
        for p in ctx["players"]:
            if p["is_hero"]:
                continue
            status = "folded" if p["folded"] else "all-in" if p["all_in"] else "in hand"
            rivals.append(
                f"{p['name']} ({status}, {p['chips']} chips, bet {p['current_bet']})"
            )

        return (
            f"No-Limit Texas Hold'em, {ctx['street']}. "
            f"Hero is {hero['name']} on the {hero['position']} with "
            f"{', '.join(hero['hole_cards'])}. "
            f"Board: {board}. "
            f"Pot: {ctx['pot']} chips. Hero must call {ctx['to_call']} chips "
            f"(minimum raise to {ctx['min_raise_to']}). "
            f"Hero stack: {hero['chips']} chips. "
            f"Opponents: {'; '.join(rivals)}."
        )

    def build_questions(self, game) -> dict:
        legal = self._legal_actions(game)
        questions = {
            "action": {
                "type": "choice",
                "instructions": ACTION_INSTRUCTIONS,
                "criteria": {key: desc for key, (_, desc) in legal.items()},
            }
        }

        sizes = self._raise_sizes(game)
        if sizes:
            questions["bet_size"] = {
                "type": "choice",
                "instructions": SIZE_INSTRUCTIONS,
                "criteria": {key: desc for key, (_, desc) in sizes.items()},
            }
        return questions

    # ---------------------------------------------------------------- parseo
    def parse(self, result, game) -> Decision:
        # Laya envuelve las respuestas en {"answers": {...}}; también aceptamos
        # el diccionario de respuestas directamente.
        if not isinstance(result, dict):
            answers = {}
        elif isinstance(result.get("answers"), dict):
            answers = result["answers"]
        else:
            answers = result

        legal = self._legal_actions(game)
        answer = answers.get("action")
        key = answer.get("choice") if isinstance(answer, dict) else None

        if key not in legal:
            return self._fallback(game)

        confidence = answer.get("answer_confidence", answer.get("confidence"))
        if (
            self.min_confidence
            and confidence is not None
            and confidence < self.min_confidence
        ):
            return self._fallback(game)

        action = legal[key][0]
        if action in (Action.BET, Action.RAISE):
            amount = self._chosen_raise(game, answers)
            return Decision(action, int(amount))
        return Decision(action)

    def _chosen_raise(self, game, answers) -> int:
        sizes = self._raise_sizes(game)
        if not sizes:
            return game.current_bet + game.min_raise

        size_answer = answers.get("bet_size")
        size_key = size_answer.get("choice") if isinstance(size_answer, dict) else None
        if size_key in sizes:
            return sizes[size_key][0]

        # Si el modelo no eligió tamaño, usa el mínimo legal.
        return min(amount for amount, _ in sizes.values())

    # ----------------------------------------------------------- reglas/legal
    def _legal_actions(self, game):
        """dict: clave -> (Action, descripción) con las acciones legales."""
        seat = game.currentSeat()
        player = game.players[seat]
        to_call = game.current_bet - player.getCurrentBet()
        max_to = player.getChips() + player.getCurrentBet()
        min_to = game.current_bet + game.min_raise

        options = {"fold": (Action.FOLD, "Fold and give up the hand.")}

        if to_call == 0:
            options["check"] = (
                Action.CHECK,
                "Check, passing the action without betting.",
            )
        else:
            options["call"] = (
                Action.CALL,
                f"Call {to_call} chips to stay in the hand.",
            )

        if player.getChips() > 0 and max_to >= min_to:
            if game.current_bet == 0:
                options["bet"] = (
                    Action.BET,
                    f"Open the betting for at least {min_to} chips.",
                )
            else:
                options["raise"] = (Action.RAISE, f"Raise to at least {min_to} chips.")

        if player.getChips() > 0:
            options["all_in"] = (
                Action.ALL_IN,
                f"Go all-in for {player.getChips()} chips.",
            )

        return options

    def _raise_sizes(self, game):
        """dict: clave -> (importe, descripción) con tamaños de subida legales."""
        seat = game.currentSeat()
        player = game.players[seat]
        to_call = game.current_bet - player.getCurrentBet()
        max_to = player.getChips() + player.getCurrentBet()
        min_to = game.current_bet + game.min_raise

        if player.getChips() <= 0 or max_to < min_to:
            return {}

        pot_after_call = game.pot + to_call
        raw = {
            "minimum": min_to,
            "half_pot": game.current_bet + round(0.5 * pot_after_call),
            "three_quarter_pot": game.current_bet + round(0.75 * pot_after_call),
            "pot": game.current_bet + pot_after_call,
            "all_in": max_to,
        }

        sizes = {}
        seen = set()
        for key, amount in raw.items():
            amount = max(min_to, min(int(amount), max_to))
            if amount in seen:
                continue
            seen.add(amount)
            sizes[key] = (amount, f"Make it {amount} chips.")
        return sizes

    def _fallback(self, game) -> Decision:
        seat = game.currentSeat()
        player = game.players[seat]
        to_call = game.current_bet - player.getCurrentBet()
        if to_call == 0:
            return Decision(Action.CHECK)
        return Decision(Action.FOLD)

    def _position(self, game, seat) -> str:
        if seat == game.button:
            return "button"
        if seat == game.small_blind_seat:
            return "small blind"
        if seat == game.big_blind_seat:
            return "big blind"
        return "middle position"


def load_agent(model: str = "convaiinnovations/laya", **kwargs):
    """Carga el modelo real de Laya (importa torch bajo demanda)."""
    try:
        import laya
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise RuntimeError(
            "El paquete 'laya' no está instalado. Añádelo con 'pip install laya'."
        ) from exc
    return laya.load(model, **kwargs)


def create_laya_bots(game, agent, **kwargs):
    """Un ``LayaBot`` por asiento, usando el mismo agente."""
    return [LayaBot(agent, name=player.getName(), **kwargs) for player in game.players]
