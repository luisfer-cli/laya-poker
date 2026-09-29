"""Reparto del bote, incluidos los 'side pots' cuando hay all-ins."""


class SidePot:
    def __init__(self, amount: int, eligible):
        self.amount = amount
        # Jugadores que pueden ganar este bote (no se retiraron y aportaron lo suficiente)
        self.eligible = list(eligible)

    def __repr__(self):
        nombres = ", ".join(p.getName() for p in self.eligible)
        return f"SidePot({self.amount}, [{nombres}])"


def build_side_pots(players):
    """Construye los botes a partir de lo aportado por cada jugador.

    Cada jugador tiene un atributo ``contributed`` con las fichas totales que
    puso en la mano. Los jugadores retirados aportan al bote pero nunca pueden
    ganarlo.
    """
    contributions = {player: player.contributed for player in players}
    levels = sorted({c for c in contributions.values() if c > 0})

    pots = []
    previous = 0
    for level in levels:
        players_at_level = sum(1 for c in contributions.values() if c >= level)
        amount = (level - previous) * players_at_level
        eligible = [
            player
            for player in players
            if contributions[player] >= level and player.isActive()
        ]
        pots.append(SidePot(amount, eligible))
        previous = level

    return _merge(pots)


def _merge(pots):
    """Une botes consecutivos con los mismos jugadores elegibles."""
    merged = []
    for pot in pots:
        if merged and _same_players(merged[-1].eligible, pot.eligible):
            merged[-1].amount += pot.amount
        else:
            merged.append(pot)
    return merged


def _same_players(left, right):
    return {id(p) for p in left} == {id(p) for p in right}
