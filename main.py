"""Punto de entrada para probar el reparto de cartas.

Uso:
    python main.py                    # un reparto de ejemplo + validaciones
    python main.py --repartos 5000    # además, comprueba aleatoriedad

El programa construye una partida, reparte las cartas y verifica que:
  * cada jugador recibe exactamente 2 cartas,
  * no hay cartas repetidas entre las manos,
  * al mazo le quedan 52 - 2 * jugadores cartas,
  * (opcional) en muchos repartos salen las 52 cartas y el mazo está barajado.
"""

import argparse
from collections import Counter

from src.game import Game, Player


def carta_a_texto(card):
    return f"{card.getRank()}{card.getSuit()}"


def validar_partida(partida, num_jugadores):
    """Devuelve la lista de errores encontrados en un reparto."""
    errores = []

    todas = []
    for i, jugador in enumerate(partida.players, start=1):
        mano = jugador.getHand()
        if len(mano) != 2:
            errores.append(f"El jugador {i} tiene {len(mano)} cartas (se esperaban 2)")
        todas.extend(mano)

    if len(todas) != 2 * num_jugadores:
        errores.append(f"Se repartieron {len(todas)} cartas en total")

    repetidas = [
        f"{rank}{suit}"
        for (rank, suit), veces in Counter(
            (c.getRank(), c.getSuit()) for c in todas
        ).items()
        if veces > 1
    ]
    if repetidas:
        errores.append(f"Hay cartas repetidas: {', '.join(repetidas)}")

    restantes = len(partida.deck.cards)
    esperadas = 52 - 2 * num_jugadores
    if restantes != esperadas:
        errores.append(
            f"Quedan {restantes} cartas en el mazo (se esperaban {esperadas})"
        )

    return errores


def repartir_de_ejemplo(num_jugadores):
    """Hace un reparto y lo muestra por pantalla. Devuelve los errores."""
    jugadores = [Player(f"Jugador {i + 1}", 1000) for i in range(num_jugadores)]
    partida = Game(jugadores)
    partida.start()

    print("=" * 46)
    print(f"Reparto de ejemplo ({num_jugadores} jugadores)")
    print("=" * 46)
    print(f"Estado: {partida.state.name} | Asientos: {partida.seats}")
    for i, jugador in enumerate(partida.players, start=1):
        mano = "  ".join(carta_a_texto(c) for c in jugador.getHand())
        print(f"  {jugador.getName():<12} {mano}")
    print(f"\nCartas restantes en el mazo: {len(partida.deck.cards)}")

    errores = validar_partida(partida, num_jugadores)
    if errores:
        print("\n[FALLO] Se encontraron problemas en el reparto:")
        for error in errores:
            print(f"  - {error}")
    else:
        print("\n[OK] El reparto es correcto (2 cartas por jugador, sin repetidas).")

    return errores


def probar_aleatoriedad(num_jugadores, repartos):
    """Repite muchos repartos y resume frecuencias y fallos."""
    print("\n" + "=" * 46)
    print(f"Comprobando {repartos} repartos...")
    print("=" * 46)

    frecuencias = Counter()
    total_errores = 0

    for _ in range(repartos):
        jugadores = [Player(f"Jugador {i + 1}", 1000) for i in range(num_jugadores)]
        partida = Game(jugadores)
        partida.start()

        if validar_partida(partida, num_jugadores):
            total_errores += 1

        for jugador in partida.players:
            for card in jugador.getHand():
                frecuencias[carta_a_texto(card)] += 1

    print(f"Repartos con errores: {total_errores}/{repartos}")
    print(f"Cartas distintas repartidas: {len(frecuencias)}/52")

    if len(frecuencias) != 52:
        faltan = 52 - len(frecuencias)
        print(
            f"[AVISO] Faltan {faltan} cartas por aparecer; puede que el mazo no se baraje."
        )

    esperado = repartos * num_jugadores * 2 / 52
    minimo = min(frecuencias.values())
    maximo = max(frecuencias.values())
    print(f"Frecuencia esperada por carta: ~{esperado:.0f}")
    print(f"Frecuencia observada: min={minimo}, max={maximo}")

    return total_errores, frecuencias


def main():
    parser = argparse.ArgumentParser(
        description="Prueba el reparto de cartas del poker."
    )
    parser.add_argument(
        "--jugadores", type=int, default=4, help="número de jugadores (por defecto 4)"
    )
    parser.add_argument(
        "--repartos",
        type=int,
        default=0,
        help="si es mayor que 0, repite ese número de repartos para comprobar aleatoriedad",
    )
    args = parser.parse_args()

    if args.jugadores < 1 or args.jugadores > 26:
        parser.error("--jugadores debe estar entre 1 y 26 (52 cartas / 2 por jugador)")

    repartir_de_ejemplo(args.jugadores)

    if args.repartos > 0:
        probar_aleatoriedad(args.jugadores, args.repartos)


if __name__ == "__main__":
    main()


# --- Ejemplo antiguo de Laya (no relacionado con el reparto) ---
# import laya
#
# agent = laya.load("convaiinnovations/laya")
#
# state = {
#     "subject": "Error en producción",
#     "body": "La API devuelve 500 y varios usuarios están afectados."
# }
#
# questions = {
#     "priority": {
#         "type": "choice",
#         "instructions": "¿Qué prioridad debería tener este incidente?",
#         "criteria": {
#             "low": "Problema menor sin impacto importante",
#             "medium": "Impacto limitado",
#             "high": "Servicio o usuarios seriamente afectados"
#         }
#     },
#     "escalate": {
#         "type": "noul",
#         "instructions": "¿Este incidente debería escalarse?"
#     }
# }
#
# result = agent.predict(state, questions)
#
# print(result)
