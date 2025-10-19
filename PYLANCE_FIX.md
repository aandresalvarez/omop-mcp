# Fixing Pylance Import Errors in VS Code

## What Was Done

I've created configuration files to help VS Code's Pylance find all installed packages:

1. **`.vscode/settings.json`** - VS Code workspace settings
2. **`.vscode/extensions.json`** - Recommended extensions
3. **`pyrightconfig.json`** - Pylance/Pyright configuration

## Steps to Fix Import Errors

### 1. Reload VS Code Window
**This is the most important step!**

Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux) and select:
```
Developer: Reload Window
```

This will reload VS Code with the new configuration files.

### 2. Select Python Interpreter

After reloading, you may need to explicitly select the Python interpreter:

1. Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
2. Type: `Python: Select Interpreter`
3. Choose: `Python 3.12.X ('.venv': venv) ./venv/bin/python`

### 3. Verify the Fix

After reloading, the import errors should disappear. You can verify by:

1. Opening any Python file (e.g., `src/omop_mcp/server.py`)
2. Checking that imports like `import structlog` no longer show errors
3. Looking at the bottom-left of VS Code - it should show `Python 3.12.X ('.venv': venv)`

## What These Files Do

### `.vscode/settings.json`
- Points VS Code to the virtual environment at `.venv/bin/python`
- Configures Pylance to search in `src/` and the venv's site-packages
- Sets up formatting, linting, and testing preferences
- Enables automatic code formatting on save

### `pyrightconfig.json`
- Tells Pylance/Pyright where to find Python files (`src`, `tests`)
- Specifies the virtual environment location
- Configures type checking behavior
- Reduces noise from type checking warnings

### `.vscode/extensions.json`
- Recommends useful VS Code extensions:
  - `ms-python.python` - Python language support
  - `ms-python.vscode-pylance` - Fast Python intellisense
  - `ms-python.debugpy` - Python debugger
  - `charliermarsh.ruff` - Fast Python linter

## All Packages Are Installed

I verified that all required packages are installed in the virtual environment:

```bash
✓ duckdb (1.4.1)
✓ google-cloud-bigquery (3.38.0)
✓ pytest (8.4.2)
✓ snowflake-connector-python (4.0.0)
✓ structlog (25.4.0)
✓ uvicorn (0.38.0)
✓ pyjwt (2.10.1)
✓ mcp (1.18.0)
✓ pydantic-ai (1.1.0)
```

## Troubleshooting

If errors persist after reloading:

### Option 1: Restart Pylance Language Server
1. Press `Cmd+Shift+P` / `Ctrl+Shift+P`
2. Type: `Python: Restart Language Server`
3. Press Enter

### Option 2: Clear VS Code Cache
1. Close VS Code completely
2. Delete: `~/Library/Application Support/Code/User/workspaceStorage/` (Mac)
3. Reopen VS Code

### Option 3: Reinstall Packages
```bash
uv sync --all-extras
```

## Expected Result

After following these steps, you should see:
- ✅ No red underlines on imports
- ✅ Full autocomplete for all packages
- ✅ Hover tooltips showing function signatures
- ✅ "Go to Definition" working for all imports
- ✅ Bottom-left shows: `Python 3.12.X ('.venv': venv)`

## Notes

- The virtual environment is managed by `uv`, not standard `pip`
- All packages are already installed and working (tests pass!)
- The errors are only Pylance configuration issues, not actual code problems
- The configuration files are now committed to git for future use
