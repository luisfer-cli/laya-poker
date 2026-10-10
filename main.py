"""CLI para jugar Texas Hold'em contra bots de Laya."""

import argparse
import random

from src.game import (
    Action,
    Bot,
    BotEngine,
    Decision,
    Game,
    LayaBot,
    Player,
    get_prompt,
    load_agent,
)
from src.game.prompts import PROMPTS

NAMES = [
    "Tú",
    "Laya-1",
    "Laya-2",
    "Laya-3",
    "Laya-4",
    "Laya-5",
    "Laya-6",
    "Laya-7",
]
SUITS = {"♠️": "s", "♥️": "h", "♦️": "d", "♣️": "c"}
RANKS = {"10": "T"}


def card(card):
    rank = RANKS.get(card.getRank(), card.getRank())
    suit = SUITS.get(card.getSuit(), card.getSuit())
    return f"{rank}{suit}"


def cards(cards_):
    return " ".join(card(c) for c in cards_) or "-"


class HumanBot(Bot):
    def decide(self, game):
        player = game.currentPlayer()
        print_table(game)
        print(f"Tus cartas: {cards(player.getHand())}")
        print("Acciones: fold/f, check/x, call/c, bet/b N, raise/r N, allin/a")
        while True:
            try:
                text = input("> ").strip().lower().replace("-", "_")
            except EOFError:
                text = "fold"
            decision = parse_human_action(text, game)
            if decision:
                return decision
            print("Acción inválida.")


def parse_human_action(text, game):
    player = game.currentPlayer()
    to_call = max(0, game.current_bet - player.getCurrentBet())
    parts = text.split()
    cmd = parts[0] if parts else ""

    if cmd in ("f", "fold"):
        return Decision(Action.FOLD)
    if cmd in ("x", "check") and to_call == 0:
        return Decision(Action.CHECK)
    if cmd in ("c", "call") and to_call > 0:
        return Decision(Action.CALL)
    if cmd in ("a", "allin", "all_in", "all-in") and player.getChips() > 0:
        return Decision(Action.ALL_IN)
    if cmd in ("b", "bet", "r", "raise") and len(parts) == 2:
        try:
            amount = int(parts[1])
        except ValueError:
            return None
        action = Action.BET if game.current_bet == 0 else Action.RAISE
        if amount > game.current_bet and amount <= player.getChips() + player.getCurrentBet():
            return Decision(action, amount)
    return None


def print_table(game):
    print("\n" + "-" * 58)
    print(
        f"Mano {game.hand_number} | {game.state.name} | "
        f"bote {game.pot} | board {cards(game.community)}"
    )
    for i, p in enumerate(game.players):
        mark = "<-" if i == game.currentSeat() else "  "
        status = "fold" if p.isFolded() else "all-in" if p.isAllIn() else ""
        print(f"{mark} {p.getName():<8} stack={p.getChips():<5} apuesta={p.getCurrentBet():<5} {status}")
    player = game.currentPlayer()
    print(f"Por pagar: {max(0, game.current_bet - player.getCurrentBet())}")


def on_action(game, event):
    p = game.players[event["seat"]]
    action = event["action"]
    amount = f" {action.amount}" if action.amount else ""
    print(f"{p.getName()}: {action.action.name.lower()}{amount} (stack {p.getChips()}, bote {game.pot})")


def resolve_prompts(spec, count):
    names = [n.strip() for n in spec.split(",") if n.strip()] or ["solid"]
    try:
        prompts = [get_prompt(name) for name in names]
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    return [prompts[i % len(prompts)] for i in range(count)]


def parse_args():
    p = argparse.ArgumentParser(description="Juega poker Texas Hold'em contra bots Laya.")
    p.add_argument("--players", type=int, default=4, help="jugadores totales, incluyéndote")
    p.add_argument("--chips", type=int, default=1000)
    p.add_argument("--small-blind", type=int, default=5)
    p.add_argument("--big-blind", type=int, default=10)
    p.add_argument("--hands", type=int, default=1)
    p.add_argument("--model", default="convaiinnovations/laya")
    p.add_argument("--prompts", default="solid", help=f"prompts de bots: {', '.join(PROMPTS)}")
    p.add_argument("--min-confidence", type=float, default=0.0)
    p.add_argument("--seed", type=int)
    p.add_argument("--list-prompts", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    if args.list_prompts:
        print("\n".join(PROMPTS))
        return
    if not 2 <= args.players <= len(NAMES):
        raise SystemExit(f"--players debe estar entre 2 y {len(NAMES)}")
    if args.seed is not None:
        random.seed(args.seed)

    players = [Player(NAMES[i], args.chips) for i in range(args.players)]
    game = Game(players, small_blind=args.small_blind, big_blind=args.big_blind)

    print("Cargando Laya...")
    agent = load_agent(args.model)
    prompts = resolve_prompts(args.prompts, args.players - 1)
    bots = [HumanBot("Tú")] + [
        LayaBot(
            agent,
            name=players[i + 1].getName(),
            prompt=prompts[i],
            min_confidence=args.min_confidence,
        )
        for i in range(args.players - 1)
    ]
    engine = BotEngine(game, bots, on_action=lambda event: on_action(game, event))

    for _ in range(args.hands):
        if sum(p.getChips() > 0 for p in players) < 2:
            break
        initial = [p.getChips() for p in players]
        engine.play_hand()
        print("\nShowdown")
        print(f"Board: {cards(game.community)}")
        for p in players:
            delta = p.getChips() - initial[players.index(p)]
            print(f"{p.getName():<8} {cards(p.getHand())} stack={p.getChips()} ({delta:+d})")


if __name__ == "__main__":
    main()
