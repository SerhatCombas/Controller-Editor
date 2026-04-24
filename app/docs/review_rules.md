# Review Rules for Claude

## Review Mode
When asked to inspect the project, act as a software architect and code reviewer first, not as a code generator.

## Mandatory Behavior
- Start from the big picture.
- Then move to modules and file responsibilities.
- Then explain actual data flow.
- Then identify risks and improvement opportunities.

## Evidence Rules
Every important architectural claim should be grounded in:
- a concrete file
- a specific module relationship
- an observed code pattern

If something is not confirmed, label it as an assumption or open question.

## Efficiency Rules
- Do not repeatedly summarize the same architecture in every reply.
- Do not scan unrelated files for narrow follow-up questions.
- Focus on the currently active application under `app/`.
- Use `control_ui_spec.md` when assessing UI intent, workflow design, and possible implementation mismatches.

## Anti-Duplication Rules
Before suggesting:
- a new service
- a new manager
- a new abstraction
- a new shared utility

first check whether an equivalent structure already exists.

## Architecture Smells To Look For
- business logic inside widgets
- duplicate state across panels/widgets
- services that behave like hidden controllers
- core logic coupled to UI details
- inconsistent naming of similar responsibilities
- parallel implementations of the same feature
- implementation deviating from `control_ui_spec.md` without explanation

## Preferred Output Format
Use this exact analysis order:
1. High-level architecture
2. Main modules and responsibilities
3. Real data flow
4. Alignment with UI spec
5. Architectural strengths
6. Architectural weaknesses
7. Fragile areas / bottlenecks
8. Improvement roadmap
9. Confidence and unknowns
