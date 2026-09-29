"""Runner CLI para ver jugar a los bots de Laya.

Dos vistas:

  * ``--view thoughts``: muestra el "pensamiento" del modelo en cada decisión
    (el estado que recibe, la acción elegida, la confianza y las probabilidades).
  * ``--view history``: narra la mano como un historial real de póker
    (estilo PokerStars), sin nada interno del modelo.

Ejemplos:
    python runner.py --view thoughts --players 4 --prompts default,solid,tight
    python runner.py --view history --hands 3 --pause
    python runner.py --list-prompts
"""

import argparse
import json
import random
import time

from src.game import (
    PROMPTS,
    Action,
    BotEngine,
    Game,
    GameState,
    LayaBot,
    Player,
    get_prompt,
    load_agent,
)
from src.game.export import HandRecorder, hand_positions, write_hands

NOMBRES = ["Ana", "Beto", "Caro", "Dani", "Eva", "Fran", "Gil", "Hugo"]

SUIT_LETTER = {"♠️": "s", "♥️": "h", "♦️": "d", "♣️": "c"}
RANK_LETTER = {"10": "T"}


def card_token(card):
    """Carta en formato compacto tipo hand history: ``As``, ``Th``, ``7c``."""
    rank = RANK_LETTER.get(card.getRank(), card.getRank())
    return f"{rank}{SUIT_LETTER.get(card.getSuit(), card.getSuit())}"


def plural(n, singular, plural_):
    return singular if n == 1 else plural_


# --------------------------------------------------------------------------- vistas
class ThoughtsView:
    """Traza de depuración: qué ve y qué decide el modelo."""

    nombre = "thoughts"

    def __init__(self, show_state=False):
        self.show_state = show_state
        self._last_board = None

    def hand_start(self, game, prompts):
        self._last_board = None
        print()
        print("=" * 62)
        print(
            f"Mano {game.hand_number} | botón: {game.players[game.button].getName()} "
            f"| ciegas {game.small_blind}/{game.big_blind}"
        )
        print("=" * 62)
        for i, player in enumerate(game.players):
            cartas = " ".join(str(c) for c in player.getHand()) or "-"
            print(
                f"  P{i} {player.getName():<8} [{cartas:<12}] {player.getChips():>6} "
                f"chips   prompt={prompts[i].name}"
            )

    def decision(self, bot, game, state, result, decision):
        board = " ".join(str(c) for c in game.community)
        if board != self._last_board:
            print(f"\n  [board] {board or '(vacío)'}")
            self._last_board = board

        if self.show_state:
            texto = (
                state
                if isinstance(state, str)
                else json.dumps(state, ensure_ascii=False)
            )
            print(f"    estado: {texto}")

        answers = result.get("answers", {}) if isinstance(result, dict) else {}
        answer = answers.get("action", {}) if isinstance(answers, dict) else {}
        probs = answer.get("probabilities")
        conf = answer.get("answer_confidence")
        probs_txt = (
            " ".join(f"{k}={v:.2f}" for k, v in probs.items())
            if isinstance(probs, dict)
            else ""
        )
        print(
            f"  {game.state.name:<7} {bot.name:<8} {decision!s:<22} "
            f"<- '{answer.get('choice')}' conf={conf}  {probs_txt}"
        )

    def hand_end(self, game, initial_chips, summary=None):
        print(f"\n  [board] {' '.join(str(c) for c in game.community) or '(vacío)'}")
        if summary:
            print(f"  {summary}")
        for i, player in enumerate(game.players):
            delta = player.getChips() - initial_chips[i]
            signo = f"{delta:+d}" if delta else "0"
            marca = " FOLD" if player.isFolded() else ""
            print(
                f"    P{i} {player.getName():<8} {player.getChips():>6} chips "
                f"({signo}){marca}"
            )

    def summary(self, players, prompts, per_player):
        print()
        print("=" * 62)
        print("Resumen")
        print("=" * 62)
        for i, player in enumerate(players):
            acciones = ", ".join(f"{k}:{v}" for k, v in per_player[i].items()) or "-"
            print(
                f"  P{i} {player.getName():<8} prompt={prompts[i].name:<11} "
                f"{player.getChips():>6} chips   [{acciones}]"
            )


class HistoryView:
    """Narración de la mano en formato de historial real de póker."""

    nombre = "history"

    def __init__(self, show_cards=False):
        self.show_cards = show_cards
        self._street = None
        self._board_len = 0
        self._last_aggressor = None

    def hand_start(self, game, prompts):
        self._street = None
        self._board_len = 0
        self._last_aggressor = None
        print()
        print("=" * 62)
        print(f"Mano #{game.hand_number}  ciegas {game.small_blind}/{game.big_blind}")
        print(f"Botón: {game.players[game.button].getName()}")
        for i, player in enumerate(game.players):
            cartas = ""
            if self.show_cards:
                mano = " ".join(card_token(c) for c in player.getHand())
                cartas = f"  [{mano}]"
            print(
                f"  {player.getName():<8} asiento {i}  "
                f"stack {player.getChips()}{cartas}"
            )
        print("-" * 62)
        print("*** CARTAS REPARTIDAS ***")
        print(f"(bote inicial: {game.pot})")

    def decision(self, bot, game, state, result, decision):
        # Cambio de calle: imprimimos el encabezado correspondiente.
        self._print_street(game)
        print(f"{bot.name}: {self._action_text(game, bot, decision)}")

    def _print_street(self, game):
        if game.state != self._street:
            self._street = game.state
            if game.state == GameState.FLOP:
                print(
                    f"\n*** FLOP *** [{' '.join(card_token(c) for c in game.community)}]"
                    f"  (bote: {game.pot})"
                )
            elif game.state == GameState.TURN:
                print(
                    f"\n*** TURN *** [{' '.join(card_token(c) for c in game.community)}]"
                    f"  (bote: {game.pot})"
                )
            elif game.state == GameState.RIVER:
                print(
                    f"\n*** RIVER *** [{' '.join(card_token(c) for c in game.community)}]"
                    f"  (bote: {game.pot})"
                )

    def _action_text(self, game, bot, decision):
        """Narra la acción e incluye el stack restante tras aplicarla.

        La decisión se narra antes de que el motor la aplique, así que el
        stack posterior se calcula aquí a partir de la propia acción.
        """
        action = decision.action
        player = game.players[game.currentSeat()]
        chips = player.getChips()
        bet = player.getCurrentBet()
        to_call = max(0, game.current_bet - bet)

        if action == Action.FOLD:
            return "se retira"
        if action == Action.CHECK:
            return self._con_stack("pasa", chips)
        if action == Action.CALL:
            if to_call == 0:
                return self._con_stack("pasa", chips)
            return self._con_stack(f"paga {to_call}", chips - to_call)
        if action == Action.BET:
            nuevo = max(0, chips - (decision.amount - bet))
            return self._con_stack(f"apuesta {decision.amount}", nuevo)
        if action == Action.RAISE:
            nuevo = max(0, chips - (decision.amount - bet))
            return self._con_stack(f"sube a {decision.amount}", nuevo)
        if action == Action.ALL_IN:
            total = chips + bet
            return self._con_stack(f"va all-in por {total}", 0)
        return str(action)

    @staticmethod
    def _con_stack(texto, stack):
        return f"{texto}  (stack: {stack})"

    def hand_end(self, game, initial_chips, summary=None):
        board = " ".join(card_token(c) for c in game.community)
        if board:
            print(f"\nBoard final [{board}]")
        bote_final = sum(p.contributed for p in game.players)
        print(f"Bote disputado: {bote_final}")
        if summary:
            print(summary)
        print("*** RESUMEN ***")
        for i, player in enumerate(game.players):
            delta = player.getChips() - initial_chips[i]
            signo = f"{delta:+d}" if delta else "0"
            print(f"  {player.getName():<8} {player.getChips():>6} chips ({signo})")

    def summary(self, players, prompts, per_player):
        return  # El historial no necesita el resumen de acciones.


# --------------------------------------------------------------------------- bot
class TracingBot(LayaBot):
    """``LayaBot`` que avisa a la vista de cada decisión."""

    def __init__(self, *args, view=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.view = view

    def decide(self, game):
        state = self.build_state(game)
        questions = self.build_questions(game)
        result = self.agent.predict(state, questions)
        decision = self.parse(result, game)
        self.view.decision(self, game, state, result, decision)
        return decision


def build_views(args):
    if args.view == "thoughts":
        return ThoughtsView(show_state=args.show_state)
    return HistoryView(show_cards=args.show_cards)


def format_resultado(game, initial_chips):
    """Frase tipo 'Ana gana 320 del bote principal'."""
    ganadores = []
    for i, player in enumerate(game.players):
        delta = player.getChips() - initial_chips[i]
        if delta > 0:
            ganadores.append((player.getName(), delta))
    if not ganadores:
        return "La mano termina sin ganador claro."
    partes = [f"{nombre} gana {monto}" for nombre, monto in ganadores]
    return " y ".join(partes) + "."


# --------------------------------------------------------------------------- args
def parse_args():
    parser = argparse.ArgumentParser(
        description="Ve jugar a los bots de Laya: su razonamiento o la mano como partida real."
    )
    parser.add_argument(
        "--view",
        choices=["thoughts", "history"],
        default="thoughts",
        help="thoughts: traza del modelo (por defecto); history: narración tipo partida real",
    )
    parser.add_argument("--players", type=int, default=4, help="número de jugadores")
    parser.add_argument("--chips", type=int, default=1000, help="fichas iniciales")
    parser.add_argument("--small-blind", type=int, default=5)
    parser.add_argument("--big-blind", type=int, default=10)
    parser.add_argument("--hands", type=int, default=1, help="manos a jugar")
    parser.add_argument(
        "--prompts",
        default="default",
        help=f"prompts por jugador, separados por coma (disponibles: {', '.join(PROMPTS)})",
    )
    parser.add_argument("--min-confidence", type=float, default=0.0)
    parser.add_argument("--model", default="convaiinnovations/laya")
    parser.add_argument("--seed", type=int, default=None, help="semilla del reparto")
    parser.add_argument(
        "--pause", action="store_true", help="Enter antes de cada acción"
    )
    parser.add_argument(
        "--delay", type=float, default=0.0, help="segundos entre acciones"
    )
    parser.add_argument(
        "--show-state",
        action="store_true",
        help="(vista thoughts) imprime el estado que ve el modelo",
    )
    parser.add_argument(
        "--show-cards",
        action="store_true",
        help="(vista history) muestra las cartas de cada jugador al repartir",
    )
    parser.add_argument(
        "--list-prompts", action="store_true", help="lista los prompts y sale"
    )
    parser.add_argument(
        "--export",
        default=None,
        metavar="ARCHIVO.json",
        help="exporta las manos jugadas a un JSON para animarlas",
    )
    return parser.parse_args()


def list_prompts():
    print("Prompts disponibles:")
    for name, prompt in PROMPTS.items():
        persona = prompt.persona or "(sin persona)"
        print(f"  - {name:<13} estilo={prompt.state_style:<7} {persona}")


def resolve_prompts(spec, players):
    nombres = [n.strip() for n in spec.split(",") if n.strip()]
    if not nombres:
        nombres = ["default"]

    prompts = []
    for nombre in nombres:
        try:
            prompts.append(get_prompt(nombre))
        except ValueError:
            disponibles = ", ".join(PROMPTS)
            raise SystemExit(
                f"Error: prompt desconocido {nombre!r}.\n"
                f"Disponibles: {disponibles}\n"
                f"Usa --list-prompts para ver la descripción de cada uno."
            ) from None
    return [prompts[i % len(prompts)] for i in range(players)]


def main():
    args = parse_args()

    if args.list_prompts:
        list_prompts()
        return

    if args.seed is not None:
        random.seed(args.seed)

    if args.players < 2:
        raise SystemExit("Se necesitan al menos 2 jugadores")

    prompts = resolve_prompts(args.prompts, args.players)
    players = [
        Player(NOMBRES[i] if i < len(NOMBRES) else f"P{i}", args.chips)
        for i in range(args.players)
    ]
    game = Game(players, small_blind=args.small_blind, big_blind=args.big_blind)

    view = build_views(args)

    print("Cargando el modelo Laya... (puede tardar la primera vez)")
    agent = load_agent(args.model)

    bots = []
    for i, player in enumerate(game.players):
        bots.append(
            TracingBot(
                agent,
                name=player.getName(),
                min_confidence=args.min_confidence,
                prompt=prompts[i],
                view=view,
            )
        )

    engine = BotEngine(game, bots)
    per_player = [{} for _ in players]
    exported = []

    for _ in range(args.hands):
        if sum(1 for p in players if p.getChips() > 0) < 2:
            print("\nSolo queda un jugador con fichas. Fin de la partida.")
            break

        initial_chips = [p.getChips() for p in players]
        game.start_hand()
        if game.state == GameState.FINISHED:
            print("\nNo hay suficientes jugadores para repartir.")
            break

        recorder = None
        if args.export:
            recorder = HandRecorder(game, positions=hand_positions(game))
            recorder.begin(initial_chips, game.button)
            engine.on_action = recorder.on_action

        view.hand_start(game, prompts)
        engine.play_current_hand()

        if recorder is not None:
            exported.append(recorder.to_dict())

        summary = format_resultado(game, initial_chips)
        view.hand_end(game, initial_chips, summary=summary)

        if args.pause:
            _wait()
        elif args.delay:
            time.sleep(args.delay)

        for hand_no, seat, action, _ in engine.history:
            if hand_no == game.hand_number:
                per_player[seat][action.name] = per_player[seat].get(action.name, 0) + 1

        total = sum(p.getChips() for p in players)
        assert total == args.players * args.chips, "¡las fichas no cuadran!"

    view.summary(players, prompts, per_player)

    if args.export:
        write_hands(args.export, exported)
        print(f"\nManos exportadas a {args.export} ({len(exported)}).")


def _wait():
    try:
        input("[Enter para seguir] ")
    except EOFError:
        pass


if __name__ == "__main__":
    main()
