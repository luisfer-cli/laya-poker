"""Perfiles de prompt para el ``LayaBot``.

Cada ``Prompt`` agrupa:
  * ``persona``: frase que se antepone al estado (rol del jugador).
  * ``action_instructions`` / ``size_instructions``: el texto de cada pregunta.
  * ``state_style``: ``"natural"`` (texto) o ``"json"`` (dict serializado).
  * ``action_text`` / ``size_text``: plantillas de las opciones.
  * ``offer_all_in_as_action``: si el all-in se ofrece como acción principal.
    Por defecto es ``False``: el all-in solo se alcanza eligiendo el tamaño
    "all_in" en la segunda pregunta, y ese tamaño solo se ofrece cuando el
    stack efectivo es pequeño (≤ 2 botes). Esto evita que compita como opción
    suelta y reduce mucho la agresividad.

Las plantillas pueden usar estos marcadores:
  * acción: ``{to_call}``, ``{min_to}``, ``{chips}``
  * tamaño: ``{amount}``
"""

from dataclasses import dataclass, field

DEFAULT_ACTION_TEXT = {
    "fold": "Fold and give up the hand.",
    "check": "Check, passing the action without betting.",
    "call": "Call {to_call} chips to stay in the hand.",
    "bet": "Open the betting for at least {min_to} chips.",
    "raise": "Raise to at least {min_to} chips.",
    "all_in": "Go all-in for {chips} chips.",
}

DEFAULT_SIZE_TEXT = {
    "minimum": "Make the minimum raise, to {amount} chips.",
    "half_pot": "Raise to about half the pot, to {amount} chips.",
    "three_quarter_pot": "Raise to about three quarters of the pot, to {amount} chips.",
    "pot": "Raise to about the size of the pot, to {amount} chips.",
    "all_in": "Go all-in, to {amount} chips.",
}

DEFAULT_ACTION_INSTRUCTIONS = (
    "You are playing No-Limit Texas Hold'em. Read the table state and choose "
    "the best action for the hero. Consider pot odds, position and stack size."
)

DEFAULT_SIZE_INSTRUCTIONS = (
    "Choose how many chips the hero should end up with in front this street "
    "when betting or raising."
)


@dataclass
class Prompt:
    name: str = "default"
    persona: str = ""
    action_instructions: str = DEFAULT_ACTION_INSTRUCTIONS
    size_instructions: str = DEFAULT_SIZE_INSTRUCTIONS
    state_style: str = "natural"
    action_text: dict = field(default_factory=lambda: dict(DEFAULT_ACTION_TEXT))
    size_text: dict = field(default_factory=lambda: dict(DEFAULT_SIZE_TEXT))
    # Si es False, el all-in no se ofrece como acción principal: solo se llega
    # a él eligiendo un tamaño all-in en la segunda consulta.
    offer_all_in_as_action: bool = False

    def action_description(self, key: str, **values) -> str:
        return self.action_text.get(key, DEFAULT_ACTION_TEXT.get(key, key)).format(
            **values
        )

    def size_description(self, key: str, **values) -> str:
        return self.size_text.get(key, DEFAULT_SIZE_TEXT.get(key, key)).format(**values)


PROMPTS = {
    "default": Prompt(
        name="default",
        offer_all_in_as_action=False,
    ),
    "neutral": Prompt(
        name="neutral",
        persona="Answer every decision with a single option.",
        offer_all_in_as_action=False,
        action_text={
            "fold": "Fold",
            "check": "Check",
            "call": "Call the bet",
            "bet": "Bet",
            "raise": "Raise",
            "all_in": "Go all-in",
        },
        size_text={
            "minimum": "Minimum raise ({amount})",
            "half_pot": "Half pot ({amount})",
            "three_quarter_pot": "Three quarters pot ({amount})",
            "pot": "Pot ({amount})",
            "all_in": "All-in ({amount})",
        },
    ),
    "tight": Prompt(
        name="tight",
        persona="You are a tight, patient and risk-averse poker player who only continues with strong hands.",
        action_instructions=(
            "You are a tight poker player. Choose the safest reasonable action for "
            "the hero. Folding to aggression and avoiding big losses is preferred."
        ),
        offer_all_in_as_action=False,
        action_text={
            "fold": "Fold, the hero is not committed to this pot.",
            "check": "Check and keep the pot small.",
            "call": "Call only if the price is good.",
            "bet": "Make a small bet with a strong hand.",
            "raise": "Raise only with a very strong hand.",
            "all_in": "Go all-in, only with a premium hand.",
        },
        size_text={
            "minimum": "Raise the minimum: {amount} chips.",
            "half_pot": "Raise to half the pot: {amount} chips.",
            "three_quarter_pot": "Raise to three quarters of the pot: {amount} chips.",
            "pot": "Raise to the size of the pot: {amount} chips.",
            "all_in": "Go all-in for {amount} chips.",
        },
    ),
    "solid": Prompt(
        name="solid",
        persona="You are a solid, disciplined winning poker player. You play a balanced strategy and avoid unnecessary risk.",
        action_instructions=(
            "You are a solid winning poker player. Choose the most profitable "
            "action for the hero. Prefer controlled bets over risking the whole "
            "stack, and fold when the hand does not justify continuing."
        ),
        offer_all_in_as_action=False,
        action_text={
            "fold": "Fold and wait for a better spot.",
            "check": "Check and control the pot.",
            "call": "Call a reasonable price to see another card.",
            "bet": "Bet a controlled amount for value or protection.",
            "raise": "Raise to a sensible size, keeping the pot manageable.",
            "all_in": "Commit the whole stack, only with a very strong hand.",
        },
        size_text={
            "minimum": "Raise the minimum: {amount} chips.",
            "half_pot": "Raise to half the pot: {amount} chips.",
            "three_quarter_pot": "Raise to three quarters of the pot: {amount} chips.",
            "pot": "Raise to the size of the pot: {amount} chips.",
            "all_in": "Commit the whole stack: {amount} chips.",
        },
    ),
    "json": Prompt(
        name="json",
        persona="",
        state_style="json",
        offer_all_in_as_action=False,
    ),
    "legacy_all_in": Prompt(
        name="legacy_all_in",
        offer_all_in_as_action=True,
    ),
}


def get_prompt(name: str) -> Prompt:
    try:
        return PROMPTS[name]
    except KeyError:
        raise ValueError(
            f"Prompt desconocido: {name!r}. Disponibles: {', '.join(PROMPTS)}"
        ) from None
