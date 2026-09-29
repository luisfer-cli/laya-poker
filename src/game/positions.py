"""Nombres de posición de póker según el número de jugadores.

Se asignan contando **hacia atrás** desde el botón: las posiciones más tardías
(con ventaja) están junto al botón y las más tempranas al final.

    BTN  CO  HJ  MP, MP+1, ...  UTG  UTG+1, ...

Reglas:
* ``BTN`` (button), ``SB`` (small blind) y ``BB`` (big blind) son fijas.
* En 3 jugadores solo hay ``BTN``/``SB``/``BB``.
* En 4 jugadores el que no es ciego es ``CO``.
* Los huecos entre la ciega grande y el botón se reparten entre ``UTG+n``,
  ``MP``, ``HJ`` y ``CO``.
* En heads-up (2 jugadores) el botón pone la ciega pequeña: ``BTN/SB``.
"""

_HEADS_UP = ["BTN/SB", "BB"]


def position_names(num_players: int):
    """Lista de nombres de posición indexada por el anillo desde el botón.

    El índice 0 es el botón; 1, la ciega pequeña; 2, la ciega grande.
    """
    if num_players < 2:
        raise ValueError("Se necesitan al menos 2 jugadores")
    if num_players == 2:
        return list(_HEADS_UP)

    # Posiciones tardías, de la más cercana al botón hacia fuera.
    tardias = ["CO", "HJ"]
    num_late = min(len(tardias), max(0, num_players - 3))
    num_early = max(0, num_players - 3 - num_late)

    # Posiciones tempranas: de UTG (habla primero) hacia dentro.
    #   early=1 -> [UTG]
    #   early=2 -> [UTG, UTG+1]
    #   early=3 -> [UTG, UTG+1, MP]
    #   early>3 -> [UTG, UTG+1, MP, UTG+2, UTG+3, ...]
    tempranas = []
    for i in range(num_early):
        if i == 0:
            tempranas.append("UTG")
        elif i == 1:
            tempranas.append("UTG+1")
        elif i == 2:
            tempranas.append("MP")
        else:
            tempranas.append(f"UTG+{i - 1}")

    # La lista va del botón hacia atrás: primero las tardías y luego las
    # tempranas en orden inverso, de modo que UTG (la primera en hablar)
    # quede siempre al final.
    names = ["BTN", "SB", "BB"]
    names += [tardias[i] for i in range(num_late)]
    names += list(reversed(tempranas))
    return names


def seat_position_names(seats: int, button: int, small_blind: int):
    """Nombres de posición para cada asiento concreto."""
    nuts = position_names(seats)
    return {(button + offset) % seats: name for offset, name in enumerate(nuts)}
