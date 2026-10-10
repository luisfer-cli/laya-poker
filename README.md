# Laya Poker CLI

CLI para jugar Texas Hold'em contra bots que deciden con [Laya](https://github.com/ConvAIInnovations/laya).

## Requisitos

- Python 3.11+
- Dependencias:

```bash
pip install -r requirements.txt
```

## Jugar

```bash
python main.py --players 4 --hands 3
```

Acciones durante tu turno:

- `fold` / `f`
- `check` / `x`
- `call` / `c`
- `bet N` / `b N`
- `raise N` / `r N`
- `allin` / `a`

Opciones útiles:

```bash
python main.py \
  --players 4 \
  --chips 1000 \
  --small-blind 5 \
  --big-blind 10 \
  --hands 5 \
  --prompts solid,tight \
  --model convaiinnovations/laya
```

## Tests

```bash
python -m unittest
```
