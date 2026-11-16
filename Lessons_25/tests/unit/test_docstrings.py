"""Страж документації: кожен view (клас, функція, метод) має docstring."""

import ast
from pathlib import Path

import pytest
from django.conf import settings

VIEW_FILES = ["catalog/views.py", "catalog/async_views.py", "orders/views.py", "accounts/views.py", "config/health.py"]


def documented_objects(path):
    tree = ast.parse(Path(settings.BASE_DIR, path).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield f"{path}: {node.name}", node
            if isinstance(node, ast.ClassDef):
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        yield f"{path}: {node.name}.{sub.name}", sub


@pytest.mark.parametrize("path", VIEW_FILES)
def test_every_view_object_has_a_docstring(path):
    # Generated with AI, reviewed and modified
    missing = [name for name, node in documented_objects(path) if not ast.get_docstring(node)]
    assert missing == []


@pytest.mark.parametrize("path", ["catalog/views.py", "orders/views.py", "accounts/views.py"])
def test_public_view_functions_document_args_and_returns(path):
    # Generated with AI, reviewed and modified
    # Функції-views (не методи) з параметрами мають описувати Args/Returns у єдиному форматі.
    tree = ast.parse(Path(settings.BASE_DIR, path).read_text(encoding="utf-8"))
    weak = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_") and len(node.args.args) > 1:
            doc = ast.get_docstring(node) or ""
            if "Args:" not in doc or "Returns:" not in doc:
                weak.append(node.name)
    assert weak == [], f"додайте Args/Returns: {weak}"
