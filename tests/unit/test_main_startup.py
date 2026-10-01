import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class MainStartupTests(unittest.TestCase):
    def test_import_does_not_start_runtime(self):
        tree = ast.parse((PROJECT_ROOT / "main.py").read_text(encoding="utf-8"))
        guarded_calls = []
        main_function_calls_client_run = False

        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "main":
                main_function_calls_client_run = any(
                    isinstance(child, ast.Call)
                    and (
                        (
                            isinstance(child.func, ast.Attribute)
                            and isinstance(child.func.value, ast.Name)
                            and child.func.value.id == "client"
                            and child.func.attr == "run"
                        )
                        or (
                            isinstance(child.func, ast.Name)
                            and child.func.id == "run_discord_bot"
                        )
                        or (
                            isinstance(child.func, ast.Attribute)
                            and child.func.attr == "run"
                            and isinstance(child.func.value, ast.Call)
                            and isinstance(child.func.value.func, ast.Name)
                            and child.func.value.func.id == "DiscordBot"
                        )
                    )
                    for child in ast.walk(node)
                )
            if not isinstance(node, ast.If):
                continue
            if not (
                isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name)
                and node.test.left.id == "__name__"
                and len(node.test.ops) == 1
                and isinstance(node.test.ops[0], ast.Eq)
                and len(node.test.comparators) == 1
                and isinstance(node.test.comparators[0], ast.Constant)
                and node.test.comparators[0].value == "__main__"
            ):
                continue
            guarded_calls.extend(
                child
                for child in ast.walk(node)
                if isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "main"
            )

        self.assertTrue(
            main_function_calls_client_run and guarded_calls,
            "runtime startup must be called only through the __main__ entry point",
        )


if __name__ == "__main__":
    unittest.main()
