---
name: self-improvement
description: Review completed work, analyze mistakes, identify repeatable improvements, and turn validated lessons into memory or reusable skills. Use after substantial tasks, failures, or review-heavy work.
always: false
enabled: true
---

# Self-Improvement

Use this skill after meaningful work, not after trivial replies.

## Primary Goals

1. Review what was just done
2. Identify concrete weaknesses or risks
3. Extract reusable tactics
4. Persist only the learnings that deserve to survive

## When To Use

- after completing a non-trivial coding or debugging task
- after a failure, retry loop, or wrong assumption
- after a review that uncovered repeatable issues
- when a workflow feels reusable enough to become a skill

Skip it for one-off small answers with no reusable pattern.

## How It Fits The Current Memory Framework

Use the current Horbot memory layout, not ad-hoc logs:

- durable facts and lasting rules go to `L2/MEMORY.md`
- recent outcomes and concise summaries go to `L1/HISTORY.md`
- reusable tactics and corrected assumptions go to `L1/REFLECTION.md`

If the completed work forms a repeatable workflow, Horbot may also distill it into a user skill under the current agent's skills directory.

## Recommended Workflow

### 1. Review

Use the templates in `templates/` when helpful:

- `templates/code-review.md`
- `templates/capability-assessment.md`
- `templates/learning-plan.md`

Focus on concrete evidence from the work that just happened.

### 2. Classify The Learning

- durable project truth -> `MEMORY.md`
- recent progress or outcome -> `HISTORY.md`
- reusable tactic / lesson learned -> `REFLECTION.md`
- repeatable operating procedure -> candidate skill

### 3. Validate Before Persisting

Only persist learnings that are:

- specific
- evidence-backed
- reusable
- safe to keep

Do not preserve vague self-praise, unverified guesses, or secrets.

## Relation To Automatic Skill Distillation

Horbot can run a background skill review after successful tool-backed work.

That mechanism works best when:

- the task used real tools
- the result contains a concrete procedure or checklist
- the final output clearly describes the steps that worked

When the workflow is reusable, the system may:

1. create or update a skill
2. record the reusable tactic in reflection/history
3. make that workflow available for later sessions

## Guardrails

- prefer small, high-signal learnings over long reports
- do not create a new skill for project-specific or one-off work
- avoid duplicating existing skills when an update is enough
- verify important improvements before treating them as durable knowledge
- keep backward compatibility and user intent in mind
