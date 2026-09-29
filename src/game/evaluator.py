"""Evaluador de manos de póker.

``evaluate(cards)`` recibe entre 5 y 7 cartas y devuelve una tupla comparable
(``score``) con la mejor mano de 5 cartas posible. Cuanto mayor es la tupla,
mejor es la mano, así que basta con usar ``max()`` o ``>`` para comparar.
"""

from collections import Counter
from enum import IntEnum


class HandCategory(IntEnum):
    HIGH_CARD = 0
    PAIR = 1
    TWO_PAIR = 2
    THREE_OF_A_KIND = 3
    STRAIGHT = 4
    FLUSH = 5
    FULL_HOUSE = 6
    FOUR_OF_A_KIND = 7
    STRAIGHT_FLUSH = 8


CATEGORY_NAMES = {
    HandCategory.HIGH_CARD: "carta alta",
    HandCategory.PAIR: "pareja",
    HandCategory.TWO_PAIR: "doble pareja",
    HandCategory.THREE_OF_A_KIND: "trío",
    HandCategory.STRAIGHT: "escalera",
    HandCategory.FLUSH: "color",
    HandCategory.FULL_HOUSE: "full",
    HandCategory.FOUR_OF_A_KIND: "póker",
    HandCategory.STRAIGHT_FLUSH: "escalera de color",
}


def _straight_high(values) -> int:
    """Devuelve la carta más alta de la mejor escalera, o 0 si no hay.

    ``values`` son valores únicos de rango. El As puede valer 1 (escalera
    'rueda': A-2-3-4-5).
    """
    unique = sorted(set(values), reverse=True)
    if 14 in unique:
        unique.append(1)
    run = 1
    for i in range(1, len(unique)):
        if unique[i] == unique[i - 1] - 1:
            run += 1
            if run >= 5:
                return unique[i] + 4
        else:
            run = 1
    return 0


def evaluate(cards):
    """Evalúa 5, 6 o 7 cartas y devuelve una tupla comparable."""
    if len(cards) < 5:
        raise ValueError("Se necesitan al menos 5 cartas para evaluar una mano")

    counts = Counter(card.getValue() for card in cards)
    trips = sorted((r for r, n in counts.items() if n == 3), reverse=True)
    pairs = sorted((r for r, n in counts.items() if n == 2), reverse=True)
    quads = sorted((r for r, n in counts.items() if n == 4), reverse=True)
    ordered = sorted(counts, reverse=True)

    # Color (y escalera de color)
    suit_counts = Counter(card.getSuit() for card in cards)
    flush_suit = next((suit for suit, n in suit_counts.items() if n >= 5), None)
    if flush_suit is not None:
        flush_values = [c.getValue() for c in cards if c.getSuit() == flush_suit]
        straight_flush = _straight_high(flush_values)
        if straight_flush:
            return (HandCategory.STRAIGHT_FLUSH, straight_flush)

    if quads:
        quad = quads[0]
        kicker = max(r for r in counts if r != quad)
        return (HandCategory.FOUR_OF_A_KIND, quad, kicker)

    if trips:
        if len(trips) >= 2:
            return (HandCategory.FULL_HOUSE, trips[0], trips[1])
        if pairs:
            return (HandCategory.FULL_HOUSE, trips[0], pairs[0])

    if flush_suit is not None:
        top5 = sorted(flush_values, reverse=True)[:5]
        return (HandCategory.FLUSH, *top5)

    straight = _straight_high(counts)
    if straight:
        return (HandCategory.STRAIGHT, straight)

    if trips:
        kickers = [r for r in ordered if r != trips[0]][:2]
        return (HandCategory.THREE_OF_A_KIND, trips[0], *kickers)

    if len(pairs) >= 2:
        hi, lo = pairs[0], pairs[1]
        kicker = max(r for r in counts if r not in (hi, lo))
        return (HandCategory.TWO_PAIR, hi, lo, kicker)

    if pairs:
        pair = pairs[0]
        kickers = [r for r in ordered if r != pair][:3]
        return (HandCategory.PAIR, pair, *kickers)

    return (HandCategory.HIGH_CARD, *ordered[:5])


def describe(score) -> str:
    """Descripción legible de un score devuelto por ``evaluate``."""
    category = HandCategory(score[0])
    return CATEGORY_NAMES[category]
