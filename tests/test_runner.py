import unittest

from runner import resolve_prompts


class ResolvePromptsTests(unittest.TestCase):
    def test_asigna_ciclicamente(self):
        prompts = resolve_prompts("tight,solid", players=4)
        self.assertEqual(
            [p.name for p in prompts], ["tight", "solid", "tight", "solid"]
        )

    def test_vacio_usa_default(self):
        prompts = resolve_prompts("", players=2)
        self.assertEqual([p.name for p in prompts], ["default", "default"])

    def test_prompt_desconocido_falla_con_mensaje_claro(self):
        with self.assertRaises(SystemExit) as ctx:
            resolve_prompts("default,aggressive", players=2)
        self.assertIn("prompt desconocido", str(ctx.exception))
        self.assertIn("solid", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
