# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Install dependencies (requires `pipenv`):
```
pipenv install --dev
```

Run all tests:
```
pipenv run tests
```

Run a single test module (e.g. `tests/engine.py`):
```
PYTHONPATH=$(pwd)/lib python -m unittest -v tests.engine
```

Run tests with coverage:
```
pipenv run tests-coverage
```

Build the distribution:
```
make build
```

Build documentation:
```
make docs
```

Launch the interactive debug REPL:
```
PYTHONPATH=$(pwd)/lib python -m rule_engine.debug_repl
```

## Architecture

This is a Python library that implements a lightweight expression language for matching arbitrary Python objects. The public API surface is small: `Rule`, `Context`, `DataType`, resolver functions, and error classes — all re-exported from `lib/rule_engine/__init__.py`.

**Evaluation pipeline:**

1. `Rule(text, context)` — Entry point. Calls `Parser.parse()` to turn the expression string into an AST statement node.
2. `parser/` — Uses PLY (lex + yacc). `base.py` is the `ParserBase` class; `parser/` contains the grammar rules and utilities. `parsetab.py` is a generated PLY parse table (do not edit).
3. `ast.py` — AST node hierarchy. Every node has an `evaluate(thing)` method. Literal nodes also have `result_type` for static type checking at parse time.
4. `engine.py` — Contains `Rule`, `Context`, and `_AttributeResolver`. The `Context` object controls: symbol resolution (via `resolver` callback, defaulting to `resolve_item` for dicts), type resolution (via `type_resolver`), regex flags, default timezone, and decimal context. Thread safety is handled by `_ThreadLocalStorage` keyed on `threading.local()`.
5. `types.py` — Defines `DataType` (UNDEFINED, NULL, BOOLEAN, FLOAT, STRING, BYTES, DATETIME, TIMEDELTA, ARRAY, SET, MAPPING, FUNCTION) and type compatibility/coercion helpers.
6. `errors.py` — Exception hierarchy rooted at `EngineError`.
7. `builtins.py` — Built-in symbols available in every rule (e.g. `re_groups` after a regex match).
8. `suggestions.py` — "Did you mean?" logic for `SymbolResolutionError`.

**Key design points:**

- The library source is under `lib/` (not the project root), so `PYTHONPATH` must include `lib/` when running outside of an installed package.
- `DataType` instances double as both type tags and type definitions; `DataType.is_definition()` and `DataType.from_value()` are used throughout.
- Compound types (`ARRAY`, `SET`, `MAPPING`, `FUNCTION`) are parameterized: `DataType.ARRAY(DataType.STRING)` creates a typed array definition.
- Attribute access on values (e.g. `name.length`, `dt.year`) is handled by `_AttributeResolver` in `engine.py`, which dispatches based on the runtime type of the object.
- `Context` is designed to be thread-safe and reusable across many `Rule` evaluations.
