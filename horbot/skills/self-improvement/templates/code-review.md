# Code Review Template

Use this template to systematically review generated code.

## Review Checklist

### 1. Code Quality

- [ ] **Readability** - Code is easy to understand
- [ ] **Naming** - Variables and functions have clear names
- [ ] **Structure** - Code is well-organized and modular
- [ ] **Comments** - Complex logic is documented
- [ ] **Consistency** - Follows project coding standards

### 2. Functionality

- [ ] **Correctness** - Code does what it's supposed to do
- [ ] **Edge Cases** - Handles boundary conditions
- [ ] **Error Handling** - Errors are caught and handled properly
- [ ] **Input Validation** - Inputs are validated
- [ ] **Output Verification** - Outputs are correct

### 3. Performance

- [ ] **Efficiency** - No unnecessary computations
- [ ] **Resource Usage** - Memory and CPU usage is optimal
- [ ] **Database Queries** - Queries are optimized
- [ ] **Caching** - Appropriate use of caching
- [ ] **Scalability** - Code can handle increased load

### 4. Security

- [ ] **Input Sanitization** - User inputs are sanitized
- [ ] **Authentication** - Proper authentication checks
- [ ] **Authorization** - Proper authorization checks
- [ ] **Data Protection** - Sensitive data is protected
- [ ] **Vulnerabilities** - No known security vulnerabilities

### 5. Testing

- [ ] **Unit Tests** - Unit tests are written
- [ ] **Integration Tests** - Integration tests are written
- [ ] **Test Coverage** - Adequate test coverage
- [ ] **Edge Case Tests** - Edge cases are tested
- [ ] **Error Scenario Tests** - Error scenarios are tested

### 6. Maintainability

- [ ] **Modularity** - Code is modular
- [ ] **Reusability** - Code is reusable
- [ ] **Extensibility** - Code is easy to extend
- [ ] **Documentation** - Code is documented
- [ ] **Dependencies** - Dependencies are minimal and necessary

## Review Process

### Step 1: Initial Scan

Quickly scan the code to understand:

- Overall structure
- Main functionality
- Key components

### Step 2: Detailed Review

Go through the checklist systematically:

1. Review code quality
2. Verify functionality
3. Check performance
4. Assess security
5. Evaluate testing
6. Consider maintainability

### Step 3: Identify Issues

For each issue found:

1. Describe the issue
2. Explain the impact
3. Suggest a solution
4. Prioritize (high/medium/low)

### Step 4: Document Findings

Create a review report:

```markdown
## Code Review Report

**File**: [filename]
**Reviewer**: AI Self-Review
**Date**: [date]

### Issues Found

#### Issue 1: [Issue Title]
- **Priority**: High/Medium/Low
- **Category**: Code Quality/Functionality/Performance/Security/Testing/Maintainability
- **Description**: [Description]
- **Impact**: [Impact]
- **Solution**: [Suggested solution]

### Recommendations

1. [Recommendation 1]
2. [Recommendation 2]

### Positive Findings

1. [Positive finding 1]
2. [Positive finding 2]
```

## Improvement Actions

After review, create improvement actions:

### Immediate Actions (High Priority)

- [ ] [Action 1]
- [ ] [Action 2]

### Short-term Actions (Medium Priority)

- [ ] [Action 1]
- [ ] [Action 2]

### Long-term Actions (Low Priority)

- [ ] [Action 1]
- [ ] [Action 2]

## Review Metrics

Track review metrics:

- **Issues Found**: [count]
- **Critical Issues**: [count]
- **Improvements Applied**: [count]
- **Time Saved**: [estimate]
- **Quality Score**: [score]

## Follow-up

After implementing improvements:

1. Re-review the code
2. Verify improvements
3. Update documentation
4. Record learnings
