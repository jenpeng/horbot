---
name: self-improvement
description: Enable AI to autonomously improve its capabilities, optimize code, analyze errors, and enhance performance. Use when AI needs to review its own work, learn from mistakes, or optimize its responses.
always: false
---

# Self-Improvement Skill

Enable the AI to autonomously improve its capabilities, learn from experience, and optimize its performance.

## Capabilities

When this skill is active, the AI can:

1. **Code Review & Optimization** - Review and improve its own generated code
2. **Capability Assessment** - Evaluate its strengths and limitations
3. **Error Analysis** - Learn from mistakes and avoid repetition
4. **Performance Optimization** - Enhance response quality and speed
5. **Learning Suggestions** - Identify areas for improvement

## Usage

The AI can invoke this skill in the following scenarios:

### 1. Code Review

When the AI completes a coding task, it can:

- Review the code for best practices
- Identify potential improvements
- Check for security vulnerabilities
- Optimize performance

### 2. Error Analysis

When errors occur, the AI can:

- Analyze the root cause
- Document the error pattern
- Create prevention strategies
- Update its knowledge base

### 3. Capability Assessment

Periodically, the AI can:

- Evaluate its current capabilities
- Identify knowledge gaps
- Create learning plans
- Track improvement progress

### 4. Performance Optimization

The AI can optimize its:

- Response accuracy
- Task completion rate
- Error reduction
- User satisfaction

## Templates

This skill provides the following templates:

### Code Review Template

Location: `templates/code-review.md`

Use this template to systematically review generated code.

### Capability Assessment Template

Location: `templates/capability-assessment.md`

Use this template to assess current capabilities and identify improvement areas.

### Learning Plan Template

Location: `templates/learning-plan.md`

Use this template to create structured learning plans.

## Best Practices

1. **Regular Self-Review** - Review work after completing significant tasks
2. **Error Documentation** - Document errors and solutions for future reference
3. **Incremental Improvement** - Focus on small, measurable improvements
4. **User Feedback Integration** - Incorporate user feedback into improvement plans
5. **Knowledge Sharing** - Share learnings through documentation

## Improvement Process

The self-improvement process follows these steps:

1. **Identify** - Recognize areas that need improvement
2. **Analyze** - Understand the root cause and impact
3. **Plan** - Create a structured improvement plan
4. **Implement** - Execute the improvement plan
5. **Verify** - Measure the effectiveness of improvements
6. **Document** - Record learnings for future reference

## Safety Considerations

- Always verify improvements before applying them
- Maintain backward compatibility
- Document all changes
- Test thoroughly before deployment
- Keep backup of previous versions

## Integration with Other Skills

This skill works well with:

- **autonomous** - For automated improvement cycles
- **memory** - To store improvement history in hierarchical context
- **github** - To track improvements via version control

## Integration with Hierarchical Context

This skill is integrated with the hierarchical context management system for persistent improvement tracking:

### Improvement History Storage

Improvement logs are automatically stored in the hierarchical context system:

- **L0 (Current Session)**: Active improvement tasks and ongoing reviews
- **L1 (Recent)**: Recent improvements and lessons learned (default storage)
- **L2 (Long-term)**: Consolidated improvement patterns and best practices

### Retrieving Past Improvements

You can search past improvements from the hierarchical context:

```python
# Search for past improvements
results = memory_store.search_memories(
    query="code review authentication",
    levels=["L1", "L2"],
    max_results=10
)
```

### Benefits of Hierarchical Storage

1. **Persistent Learning** - Improvements are preserved across sessions
2. **Contextual Retrieval** - Find relevant past improvements when needed
3. **Pattern Recognition** - Identify recurring issues and solutions
4. **Knowledge Building** - Build a knowledge base of best practices

## Example Scenarios

### Scenario 1: Code Review After Feature Implementation

```
AI: I've completed the authentication feature. Let me review it using the self-improvement skill.

[Uses code-review template]
- Checked for security vulnerabilities ✓
- Verified error handling ✓
- Optimized database queries ✓
- Improved code readability ✓

Result: 3 improvements identified and applied.
```

### Scenario 2: Error Pattern Analysis

```
AI: I've encountered similar errors in the last 3 tasks. Let me analyze the pattern.

[Uses capability-assessment template]
- Identified common error source: incorrect API usage
- Created prevention strategy: API validation checklist
- Updated knowledge base with correct usage patterns

Result: Error prevention strategy implemented.
```

### Scenario 3: Performance Optimization

```
AI: My response time has increased. Let me optimize my performance.

[Uses learning-plan template]
- Analyzed response patterns
- Identified bottlenecks
- Created optimization plan
- Implemented improvements

Result: Response time reduced by 30%.
```

## Metrics

Track improvement progress with these metrics:

- **Code Quality Score** - Based on review findings
- **Error Rate** - Number of errors per task
- **Task Completion Rate** - Successful completions vs attempts
- **User Satisfaction** - Based on feedback
- **Response Accuracy** - Correctness of responses

## Limitations

- Cannot modify core system files
- Requires user confirmation for significant changes
- Limited to available tools and resources
- Must maintain system stability
- Cannot access external resources without permission

## Configuration

Enable in your `config.json`:

```json
{
  "self_improvement": {
    "enabled": true,
    "auto_review": true,
    "review_frequency": "after_task",
    "metrics_tracking": true,
    "improvement_log": "workspace/.improvements/log.jsonl"
  }
}
```

## Improvement Log

All improvements are logged to `workspace/.improvements/log.jsonl`:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "type": "code_review",
  "area": "authentication",
  "improvements": ["added input validation", "improved error handling"],
  "impact": "reduced errors by 40%"
}
```
