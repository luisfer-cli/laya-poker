"""Bot que decide con el modelo Laya.

``LayaBot`` no depende de ``laya`` en tiempo de importación: recibe un objeto
``agent`` con un método ``predict(state, questions)``. Para el modelo real,
usa ``load_agent()``; para tests, basta con un doble que devuelva respuestas.

El bot construye un ``state`` (texto natural o JSON según el ``Prompt``) y
preguntas de tipo ``choice``: una para la acción y otra para el tamaño.
"""

try:  # importado como paquete: src.game.laya_bot
    from .bot import Bot, Decision
    from .game import Action
    from .positions import seat_position_names
    from .prompts import Prompt
except ImportError:  # importado plano (el directorio src/game en el path)
    from bot import Bot, Decision
    from positions import seat_position_names
    from prompts import Prompt

    from game import Action


_SUIT_NAMES = {"♠️": "spades", "♥️": "hearts", "♦️": "diamonds", "♣️": "clubs"}
_RANK_NAMES = {"A": "Ace", "K": "King", "Q": "Queen", "J": "Jack", "10": "Ten"}


def card_text(card) -> str:
    """Carta en texto legible para el modelo, p. ej. 'Ace of spades'."""
    rank = _RANK_NAMES.get(card.getRank(), card.getRank())
    suit = _SUIT_NAMES.get(card.getSuit(), card.getSuit())
    return f"{rank} of {suit}"


class LayaBot(Bot):
    def __init__(
        self,
        agent,
        name: str = "Laya",
        min_confidence: float = 0.0,
        prompt: Prompt | None = None,
    ):
        super().__init__(name)
        self.agent = agent
        self.min_confidence = min_confidence
        self.prompt = prompt or Prompt()

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
        to_call = max(0, game.current_bet - player.getCurrentBet())
        positions = seat_position_names(game.seats, game.button, game.small_blind_seat)

        activos = [p for p in game.players if p.isActive()]
        rivales = [p for p in activos if p is not player]
        # Stack efectivo: lo máximo que se puede poner en juego contra el rival
        # más corto que siga en la mano.
        stack_efectivo = min([player.getChips()] + [p.getChips() for p in rivales])
        max_to = player.getChips() + player.getCurrentBet()
        min_to = game.current_bet + game.min_raise

        return {
            "game": "No-Limit Texas Hold'em",
            "street": game.state.name.lower(),
            "hand_number": game.hand_number,
            "pot": game.pot,
            "pot_bb": round(game.pot / game.big_blind, 1),
            "board": [card_text(card) for card in game.community],
            "to_call": to_call,
            "to_call_bb": round(to_call / game.big_blind, 2),
            "min_raise_to": min_to,
            "max_raise_to": max_to,
            "can_raise": player.getChips() > 0 and max_to >= min_to,
            "can_reraise": to_call > 0 and player.getChips() > to_call,
            "effective_stack": stack_efectivo,
            "num_active": len(activos),
            "hero": {
                "seat": seat,
                "name": player.getName(),
                "position": positions.get(seat, "middle position"),
                "chips": player.getChips(),
                "hole_cards": [card_text(card) for card in player.getHand()],
                "current_bet": player.getCurrentBet(),
                "to_call": to_call,
            },
            "players": [
                {
                    "seat": i,
                    "name": p.getName(),
                    "position": positions.get(i, "?"),
                    "chips": p.getChips(),
                    "current_bet": p.getCurrentBet(),
                    "folded": p.isFolded(),
                    "all_in": p.isAllIn(),
                    "is_hero": i == seat,
                }
                for i, p in enumerate(game.players)
            ],
        }

    def build_state(self, game):
        """Situación para el modelo, en texto natural o JSON según el prompt."""
        ctx = self.build_context(game)

        if self.prompt.state_style == "json":
            data = dict(ctx)
            if self.prompt.persona:
                data["persona"] = self.prompt.persona
            return data

        hero = ctx["hero"]
        board = ", ".join(ctx["board"]) if ctx["board"] else "none"

        rivals = []
        for p in ctx["players"]:
            if p["is_hero"]:
                continue
            status = "folded" if p["folded"] else "all-in" if p["all_in"] else "in hand"
            rivals.append(
                f"{p['name']} ({p['position']}, {status}, {p['chips']} chips, "
                f"bet {p['current_bet']})"
            )

        limites = []
        if ctx["can_raise"]:
            limites.append(f"smallest legal raise is to {ctx['min_raise_to']}")
        if ctx["can_reraise"]:
            limites.append("hero can re-raise")
        limites_txt = (" Hero options: " + ", ".join(limites) + ".") if limites else ""

        state = (
            f"No-Limit Texas Hold'em, {ctx['street']}, {ctx['num_active']} players in the hand. "
            f"Hero is {hero['name']} on the {hero['position']} with "
            f"{', '.join(hero['hole_cards'])}. "
            f"Board: {board}. "
            f"Pot: {ctx['pot']} chips ({ctx['pot_bb']} big blinds). "
            f"Hero must call {ctx['to_call']} chips to stay in the hand. "
            f"Hero stack: {hero['chips']} chips, effective stack vs shortest rival: "
            f"{ctx['effective_stack']} chips.{limites_txt} "
            f"Opponents: {'; '.join(rivals)}."
        )
        if self.prompt.persona:
            state = f"{self.prompt.persona} {state}"
        return state

    def build_questions(self, game) -> dict:
        legal = self._legal_actions(game)
        questions = {
            "action": {
                "type": "choice",
                "instructions": self.prompt.action_instructions,
                "criteria": {key: desc for key, (_, desc) in legal.items()},
            }
        }

        sizes = self._raise_sizes(game)
        if sizes:
            questions["bet_size"] = {
                "type": "choice",
                "instructions": self.prompt.size_instructions,
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
        to_call = max(0, game.current_bet - player.getCurrentBet())
        max_to = player.getChips() + player.getCurrentBet()
        min_to = game.current_bet + game.min_raise
        values = {"to_call": to_call, "min_to": min_to, "chips": player.getChips()}

        options = {
            "fold": (Action.FOLD, self.prompt.action_description("fold", **values))
        }

        if to_call == 0:
            options["check"] = (
                Action.CHECK,
                self.prompt.action_description("check", **values),
            )
        else:
            options["call"] = (
                Action.CALL,
                self.prompt.action_description("call", **values),
            )

        if player.getChips() > 0 and max_to >= min_to:
            if game.current_bet == 0:
                options["bet"] = (
                    Action.BET,
                    self.prompt.action_description("bet", **values),
                )
            else:
                options["raise"] = (
                    Action.RAISE,
                    self.prompt.action_description("raise", **values),
                )

        if player.getChips() > 0:
            options["all_in"] = (
                Action.ALL_IN,
                self.prompt.action_description("all_in", **values),
            )

        return options

    def _raise_sizes(self, game):
        """dict: clave -> (importe, descripción) con tamaños de subida legales."""
        seat = game.currentSeat()
        player = game.players[seat]
        to_call = max(0, game.current_bet - player.getCurrentBet())
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
            sizes[key] = (amount, self.prompt.size_description(key, amount=amount))
        return sizes

    def _fallback(self, game) -> Decision:
        seat = game.currentSeat()
        player = game.players[seat]
        to_call = max(0, game.current_bet - player.getCurrentBet())
        if to_call == 0:
            return Decision(Action.CHECK)
        return Decision(Action.FOLD)


def load_agent(model: str = "convaiinnovations/laya", **kwargs):
    """Carga el modelo real de Laya (importa torch bajo demanda)."""
    try:
        import laya
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise RuntimeError(
            "El paquete 'laya' no está instalado. Añádelo con 'pip install laya'."
        ) from exc
    return laya.load(model, **kwargs)


def create_laya_bots(game, agent, prompts=None, **kwargs):
    """Un ``LayaBot`` por asiento.

    ``prompts`` puede ser un ``Prompt`` o una lista; si es una lista se asigna
    cíclicamente a los asientos, para comparar prompts en la misma mesa.
    """
    if prompts is None:
        prompts = [Prompt()]
    elif isinstance(prompts, Prompt):
        prompts = [prompts]

    bots = []
    for i, player in enumerate(game.players):
        prompt = prompts[i % len(prompts)]
        bots.append(LayaBot(agent, name=player.getName(), prompt=prompt, **kwargs))
    return bots
