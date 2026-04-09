# Code Review Workflow

Automate code review process for pull requests or code changes.

## Trigger

Use when asked to review code, analyze pull requests, or check code quality.

## Steps

1. **Read changed files** - Use `read_file` to load the files to review
2. **Analyze code structure** - Check for patterns, complexity, and organization
3. **Check for issues** - Look for bugs, security issues, and code smells
4. **Generate report** - Create a structured review summary

## Example Usage

```
Review the authentication module in src/auth/
```

## Expected Output

- Code quality score
- List of issues found
- Recommendations for improvement
- Security considerations

## Tools Used

- `read_file` - Read source files
- `list_dir` - List directory contents
- `web_search` - Search for best practices (optional)

## Safety Notes

- Read-only operation by default
- Uses `readonly` permission profile
- No code modifications without explicit approval
