# Project Setup Workflow

Initialize a new project with standard structure and configuration.

## Trigger

Use when asked to create a new project, set up a development environment, or initialize a codebase.

## Steps

1. **Analyze requirements** - Understand project type and needs
2. **Create directory structure** - Set up standard project layout
3. **Generate configuration files** - Create config files for the project type
4. **Initialize dependencies** - Set up package management
5. **Create documentation** - Add README and basic docs

## Example Usage

```
Set up a new Python project with FastAPI and pytest
```

## Expected Output

- Project directory structure
- Configuration files (pyproject.toml, .gitignore, etc.)
- Basic documentation
- Test setup

## Tools Used

- `list_dir` - Check existing structure
- `write_file` - Create files
- `edit_file` - Modify configuration
- `exec` - Run initialization commands (requires confirmation)

## Safety Notes

- Uses `coding` permission profile
- Requires confirmation for `exec` commands
- Creates files in workspace only
