import ast
from pathlib import Path
from typing import Any, Generator

import jinja2
from inline_snapshot import snapshot
from jinja2.ext import debug

from . import templates

loader = jinja2.FileSystemLoader(templates.TEMPLATES_DIR)
env = jinja2.Environment(
    extensions=[debug],
    undefined=jinja2.StrictUndefined,
    autoescape=True,
    loader=loader,
)
debug_global = {"DEBUG": True}


def test_hyphen_path_to_underscore_stem_should_extract_stem():
    inputs = ["index", "/index", "/index.html", "/accounts/4/index.html"]
    outputs = [templates.hyphen_path_to_underscore_stem(input) for input in inputs]
    assert outputs == snapshot(["index", "index", "index", "index"])


def test_hyphen_path_to_underscore_stem_should_convert_hyphens_to_underscores():
    inputs = [
        "/sold-items.html",
        "/accounts/4/privacy-settings.html",
        "/system-accounts/4/privacy-settings.html",
    ]
    outputs = [templates.hyphen_path_to_underscore_stem(input) for input in inputs]
    assert outputs == snapshot(["sold_items", "privacy_settings", "privacy_settings"])


def test_templates_and_corresponding_macros_have_the_same_name():
    for name in loader.list_templates():
        module = env.get_template(name, globals=debug_global.copy()).module
        expected_macro_name = templates.hyphen_path_to_underscore_stem(name)
        err_msg = f'{name} has no macro named "{expected_macro_name}"'
        assert expected_macro_name in dir(module), err_msg
        macro = getattr(module, expected_macro_name)
        assert isinstance(macro, jinja2.runtime.Macro)
        assert expected_macro_name == macro.name


def test_macro_argument_names_and_function_parameter_names_match():
    def func_defs(
        tree: ast.Module,
    ) -> Generator[ast.FunctionDef | ast.AsyncFunctionDef, Any, None]:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(
                node, ast.AsyncFunctionDef
            ):
                yield node

    def macro_template_decorated_func_defs(
        tree: ast.Module,
    ) -> Generator[tuple[list[str], ast.FunctionDef | ast.AsyncFunctionDef], Any, None]:
        for func_def in func_defs(tree):
            for dec in func_def.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue

                func = dec.func
                if (
                    isinstance(func, ast.Name)
                    and func.id == templates.macro_template.__name__
                ):
                    assert isinstance(dec.args[0], ast.Constant)
                    assert isinstance(dec.args[0].value, str)
                    name = dec.args[0].value
                    module = env.get_template(name, globals=debug_global.copy()).module
                    macro_name = templates.hyphen_path_to_underscore_stem(name)
                    macro: jinja2.runtime.Macro = getattr(module, macro_name)
                    yield macro.arguments, func_def

    tree = ast.parse(Path(templates.__file__).read_bytes())
    for macro_args, func_def in macro_template_decorated_func_defs(tree):
        # print(f"\n[{func_def.name}(...)]")
        for i, (macro_arg, func_arg) in enumerate(zip(macro_args, func_def.args.args)):
            # print(i, (macro_arg, func_arg.arg))
            err_msg = f"The macro argument and function parameter do not match at {i}: {macro_arg} != {func_arg.arg}"
            assert macro_arg == func_arg.arg, err_msg
