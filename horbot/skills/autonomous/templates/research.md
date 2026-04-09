# Research Workflow

Systematic research and information gathering workflow.

## Trigger

Use when asked to research a topic, gather information, or create summaries.

## Steps

1. **Define scope** - Clarify research objectives and boundaries
2. **Search for information** - Use `web_search` to find relevant sources
3. **Fetch and analyze** - Use `web_fetch` to read detailed content
4. **Synthesize findings** - Combine information into coherent summary
5. **Create report** - Generate structured output with sources

## Example Usage

```
Research the latest trends in AI agent architectures
```

## Expected Output

- Executive summary
- Key findings with sources
- Comparison table (if applicable)
- Recommendations
- References

## Tools Used

- `web_search` - Search the web for information
- `web_fetch` - Fetch detailed content from URLs
- `read_file` - Read local documents (optional)
- `write_file` - Save research report (optional)

## Safety Notes

- Read-only by default
- Uses `readonly` permission profile
- No external API calls beyond web tools
- Respects robots.txt and rate limits
