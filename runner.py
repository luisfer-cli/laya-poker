"""Runner CLI para ver jugar a los bots de Laya.

Ejemplos:
    python runner.py
    python runner.py --players 4 --prompts default,neutral,tight,aggressive
    python runner.py --hands 3 --pause --show-state
    python runner.py --list-prompts

Cada jugador puede usar un prompt distinto (``--prompts``), así se comparan
estilos en la misma mesa. Los prompts disponibles están en ``src/game/prompts.py``.
"""

import argparse
import json
import random
import time

from src.game import (
    PROMPTS,
    BotEngine,
    Game,
    GameState,
    LayaBot,
    Player,
    get_prompt,
    load_agent,
)

NOMBRES = ["Ana", "Beto", "Caro", "Dani", "Eva", "Fran", "Gil", "Hugo"]


class TablePrinter:
    def __init__(self, show_state=False, pause=False, delay=0.0):
        self.show_state = show_state
        self.pause = pause
        self.delay = delay
        self._last_board = None

    def print_hand_start(self, game, prompts):
        self._last_board = None
        print()
        print("=" * 62)
        print(
            f"Mano {game.hand_number} | botón: {game.players[game.button].getName()} "
            f"| ciegas {game.small_blind}/{game.big_blind}"
        )
        print("=" * 62)
        for i, player in enumerate(game.players):
            estado = "out" if player.isFolded() else "in"
            cartas = " ".join(str(c) for c in player.getHand()) or "-"
            print(
                f"  P{i} {player.getName():<8} [{cartas:<12}] {player.getChips():>6} "
                f"chips   prompt={prompts[i].name} ({estado})"
            )

    def print_decision(self, bot, game, state, result, decision):
        seat = game.currentSeat()
        if seat is not None:
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

        if self.pause:
            self._wait()
        elif self.delay:
            time.sleep(self.delay)

    def _wait(self):
        try:
            input("    [Enter para seguir] ")
        except EOFError:
            pass

    def print_hand_end(self, game, initial_chips):
        print(f"\n  [board] {' '.join(str(c) for c in game.community) or '(vacío)'}")
        print("  Resultado:")
        for i, player in enumerate(game.players):
            delta = player.getChips() - initial_chips[i]
            signo = f"{delta:+d}" if delta else "0"
            print(
                f"    P{i} {player.getName():<8} {player.getChips():>6} chips "
                f"({signo}) {'FOLD' if player.isFolded() else ''}"
            )

    def print_summary(self, players, prompts, per_player):
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


class TracingBot(LayaBot):
    """``LayaBot`` que avisa al runner de cada decisión para poder trazar."""

    def __init__(self, *args, printer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.printer = printer

    def decide(self, game):
        state = self.build_state(game)
        questions = self.build_questions(game)
        result = self.agent.predict(state, questions)
        decision = self.parse(result, game)
        self.printer.print_decision(self, game, state, result, decision)
        return decision


def parse_args():
    parser = argparse.ArgumentParser(
        description="Ve jugar a los bots de Laya y compara prompts."
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
        "--show-state", action="store_true", help="imprime el estado que ve el modelo"
    )
    parser.add_argument(
        "--list-prompts", action="store_true", help="lista los prompts y sale"
    )
    return parser.parse_args()


def list_prompts():
    print("Prompts disponibles:")
    for name, prompt in PROMPTS.items():
        persona = prompt.persona or "(sin persona)"
        print(f"  - {name:<11} estilo={prompt.state_style:<7} {persona}")


def resolve_prompts(spec, players):
    nombres = [n.strip() for n in spec.split(",") if n.strip()]
    if not nombres:
        nombres = ["default"]
    prompts = [get_prompt(n) for n in nombres]
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

    print("Cargando el modelo Laya... (puede tardar la primera vez)")
    agent = load_agent(args.model)

    printer = TablePrinter(
        show_state=args.show_state, pause=args.pause, delay=args.delay
    )

    bots = []
    for i, player in enumerate(game.players):
        bots.append(
            TracingBot(
                agent,
                name=player.getName(),
                min_confidence=args.min_confidence,
                prompt=prompts[i],
                printer=printer,
            )
        )

    engine = BotEngine(game, bots)
    per_player = [{} for _ in players]

    for _ in range(args.hands):
        if sum(1 for p in players if p.getChips() > 0) < 2:
            print("\nSolo queda un jugador con fichas. Fin de la partida.")
            break

        initial_chips = [p.getChips() for p in players]
        game.start_hand()
        if game.state == GameState.FINISHED:
            print("\nNo hay suficientes jugadores para repartir.")
            break

        printer.print_hand_start(game, prompts)
        engine.play_current_hand()
        printer.print_hand_end(game, initial_chips)

        # Solo cuenta las acciones de la mano recién jugada.
        for hand_no, seat, action, _ in engine.history:
            if hand_no == game.hand_number:
                per_player[seat][action.name] = per_player[seat].get(action.name, 0) + 1

        total = sum(p.getChips() for p in players)
        assert total == args.players * args.chips, "¡las fichas no cuadran!"

    printer.print_summary(players, prompts, per_player)


if __name__ == "__main__":
    main()
