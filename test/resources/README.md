# Test Resources

`test_resource_cases.py` collects every `TEST_*` directory under this tree that has both `sources/` and `outputs/`.

## Layout

- `module/`: integration cases for a whole versioned module. Use this when a module contains multiple top-level element kinds, such as class, function, and variable exports together.
- `class/`: cases for top-level class exports compiled by the class compiler. Subdirectories can group class-specific behavior such as `attr`, `constructor`, `inheritance`, or `sync`.
- `function/`: cases for top-level function exports compiled by the function compiler.
- `variable/`: cases for top-level variable exports compiled by the variable compiler.

## Naming

Leaf test case directories use `TEST_xx_yyy`.

- `xx`: two-digit index within the parent directory.
- `yyy`: a short description, or `basic` if no clearer short name exists.

Examples:

```bash
pytest --target_dir=module/TEST_01_mixed
pytest --target_dir=class/constructor/TEST_01_basic
pytest --target_dir=function/TEST_01_dispatch
pytest --target_dir=variable/TEST_01_value
```

## Entrypoint Comment

Every `sources/main.py` starts with a Japanese comment explaining what the program is intended to verify. Keep this comment up to date when changing a case.

## Compiled Output

Pytest writes the latest compiled program for each case into `compiled/` under the case directory. The directory is deleted and recreated on each run so it only contains the latest result.

`compiled/metadata.json` records test metadata such as start/end time, compile status, execution status, actual output, and exception details when compilation or execution fails.

Optional per-case settings can be written in `test.json`:

```json
{
  "version_selection_strategy": "latest",
  "expect_compile_error": "Import spec"
}
```
