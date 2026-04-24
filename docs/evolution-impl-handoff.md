# PWV Evolution JSON Implementation Handoff

Current branch: `feature/evolution-spec-design`

Current WIP commit: `c2df622 WIP: evolution json access correspondence`

Repository: `/home/satsuki_k/Research/pwv-with-multi-version-objects`

## Summary

Implemented the first PoC step for replacing `modules.json` with `_mv_mapping/evolution.json`.

The new direction is:

- `modules.json` is no longer used as the migration spec.
- `_mv_mapping/evolution.json` is the main input for semantic evolution specs.
- Top-level kinds are conceptually `import`, `function`, `variable`, and `class`.
- `import` is stored as module metadata under `imports`.
- `function` / `variable` / `class` are stored under semantic `entities`.
- `entities` are keyed by semantic entity id, not public API name.
- Public names are derived from `entities.*.versions.*.name`.
- The same public name may refer to different semantic entities in different versions.
- The same semantic entity may change name and kind across versions.
- `state.sync` is accepted and preserved conceptually, but full sync-function integration is not implemented yet.
- State sync is constrained to state that can be kept inside generated proxy/wrapper objects.
- Python top-level name rebinding is not tracked.

## JSON Shape

Example:

```json
{
  "modules": {
    "sample": {
      "versions": [1, 2],
      "imports": {
        "1": ["import os"],
        "2": ["from math import sqrt"]
      },
      "entities": {
        "position": {
          "state": {"sync": "required"},
          "versions": {
            "1": {"kind": "variable", "name": "x"},
            "2": {"kind": "function", "name": "y"}
          }
        },
        "point": {
          "state": {"sync": "none"},
          "versions": {
            "1": {"kind": "class", "name": "Point"},
            "2": {"kind": "class", "name": "PolarPoint"}
          }
        }
      }
    }
  }
}
```

`state.sync` currently supports `none` and `required`. If omitted, docs specify `none`.

`identity` is intentionally not exposed in JSON. The compiler/runtime should infer whether a proxy, wrapper, or access facade is needed from the kind composition.

## Implementation Changes

Core data path:

- `src/mv_compiler/compiler/scanner.py`
  - Reads `_mv_mapping/evolution.json`.
  - Stores parsed modules under `PROJECT_EVOLUTION_SPECS_KEY`.
  - Does not read `modules.json`.
  - Ignores old `modules.json` when collecting other JSON files.
  - Adds a fallback inference path for old fixtures without `evolution.json`: infer same-name entities and import union from source AST.

- `src/mv_compiler/compiler/common/util/constants.py`
  - Replaced `PROJECT_MODULE_MAPPINGS_KEY` with `PROJECT_EVOLUTION_SPECS_KEY`.

- `src/mv_compiler/compiler/project.py`
  - Passes each module's evolution spec to `transform_versioned_module`.

- `src/mv_compiler/compiler/module/compiler.py`
  - Normalizes semantic entities into internal mappings.
  - Splits same-kind/same-entity names into the existing generation path.
  - Sends mixed-kind or public-name-collision cases to a new generic access facade.
  - Adds generated `MVOAccess` runtime for top-level mixed access cases.
  - Supports import union from `evolution.json`.
  - Uses derived mapped names to avoid copying conflicting latest definitions.

Version fallback:

- `src/mv_compiler/compiler/elements/function/compiler.py`
  - Slow-path function dispatch now chooses latest callable candidate first.

- `src/mv_compiler/compiler/elements/class_/dispatch.py`
  - Method slow-path dispatch now chooses latest callable candidate first.

- `src/mv_compiler/compiler/elements/class_/builder/stub_method_generator.py`
  - Consistent-signature `AttributeError` fallback now switches to latest available version.

Docs:

- `README.md`
  - Updated input format section to `evolution.json`.

- `docs/versioned_modules.md`
  - Rewritten around semantic entities and access correspondence.

- `docs/roadmap.md`
  - Updated priorities for `state.sync`, attribute-level access, class support, rebinding diagnostics, and package/import handling.

Tests:

- `test/test_module_mapping.py`
  - Reworked unit tests to write `evolution.json`.
  - Added tests for renamed entities, latest callable fallback, public name referring to different entities by version, kind-changing entity using `MVOAccess`, and import union.

- Added fixture:
  - `test/resources/features/versioned_module/TEST_01_basic/sources/_mv_mapping/evolution.json`
  - This preserves the old fixture's intent where `PLAIN` stays latest-only/unmapped while `THRESHOLD`, `Point`, and `label` are versioned.

## Verification

Full test suite passed before the WIP commit:

```bash
pytest -q
```

Result:

```text
36 passed
```

## Important Current Semantics

For same-kind and same semantic entity:

- Existing generators are reused.
- Function/class/variable name changes are allowed via `versions`.
- Variable entities default into `VersionedValue`.

For mixed-kind or public-name collision:

- Compiler emits `MVOAccess`.
- `MVOAccess.get()` reads current-version candidate if present.
- `MVOAccess.__call__()` calls current-version candidate if callable.
- If current candidate is not callable, it falls back to latest callable candidate.
- `MVOAccess.set()` updates the currently resolved candidate's stored value.

Known oddity from current test:

- In `test_kind_change_entity_uses_access_facade`, public `y` refers to the whole semantic entity, so default continuity strategy starts at v1 and `y(5)` currently resolves through the entity facade in a way that still needs research refinement.

## Remaining Design / Implementation Work

High priority:

- Connect `state.sync = required` to actual sync-function lookup and hook points.
- Decide sync function naming: semantic entity id based vs class/source-name based.
- Implement attribute-level access correspondence.
- Clarify kind-changing entity operation semantics, especially whether a public name introduced only in v2 should start at v2 or still expose full entity continuity.

Medium priority:

- Improve diagnostics for invalid `evolution.json`.
- Decide whether AST inference fallback should stay or whether explicit `evolution.json` should become mandatory.
- Remove or migrate old `modules.json` fixtures once tests no longer rely on fallback.
- Add tests for package module keys with `evolution.json`.

Low priority:

- Detect top-level rebinding that bypasses generated proxies.
- Extend class support for decorators, properties, class/static methods, class attributes, and inner classes.
