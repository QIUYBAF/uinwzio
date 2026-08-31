# CODEX_HANDOFF_TEMPLATE

> Purpose: bridge a ChatGPT cloud project into a Codex/local execution session without relying on shared chat history.
> Rule: this file must be self-contained. Codex should be able to start work after reading only this file plus the referenced project files.

## 0. Identity
- Project ID: <CT/SW/OP-xx>
- Project name: <name>
- Handoff version: <YYYY-MM-DD HH:mm>
- Source: ChatGPT cloud project
- Target: Codex/local desktop execution
- Current status: ACTIVE / PAUSED / QA / RELEASE

## 1. One-sentence mission
<What this project is trying to achieve.>

## 2. Why this project exists
- Audience/user value:
- Core experience/result:
- What must remain recognizable across iterations:

## 3. Immutable constraints (DO NOT BREAK)
These are established project invariants. Do not change them merely because another implementation seems cleaner.
1. <visual / narrative / technical invariant>
2. <style / architecture / naming invariant>
3. <compatibility / output invariant>

If a constraint seems genuinely harmful, do not silently replace it. Record the conflict and propose a change separately.

## 4. Current project state
### Completed
- <done item>

### Working / verified baseline
- <what currently works and should be preserved>

### Known problems
- <problem + evidence>

### Current ACTIVE version
- <single active version / branch / folder>

### Current NEXT
- <exactly one next task>

## 5. This Codex session: objective
Complete the following task in this session:

<clear task statement>

Priority order:
1. <must>
2. <should>
3. <nice to have>

Do not broaden scope unless required to finish the objective.

## 6. Inputs and locations
### Local
- <path>

### GitHub
- Repository: <owner/repo>
- Relevant path/branch: <path>

### Google Drive
- <folder/file reference>

### Library / reference material
- <project home / style guide / notes>

If a referenced asset is missing, first search the listed canonical location. Do not create duplicate substitute assets unless necessary.

## 7. Execution instructions
1. Read PROJECT_HOME / project rules first.
2. Inspect the existing implementation before changing anything.
3. Preserve verified working parts.
4. Make the smallest coherent change that satisfies the objective.
5. Test/preview the result where possible.
6. Fix regressions introduced by this session.
7. Do not create parallel “final/final2/latest/new” versions. Maintain one ACTIVE output.

## 8. Acceptance criteria
The task is complete only when:
- [ ] <observable criterion>
- [ ] <observable criterion>
- [ ] Existing verified behavior still works.
- [ ] Output is placed in the canonical location.
- [ ] No unnecessary duplicate versions are left behind.

## 9. Output protocol
At the end, report only:
1. RESULT — what was completed.
2. CHANGED — files/components changed.
3. TEST — what was actually tested and result.
4. OPEN — remaining known issues, if any.
5. NEXT — one recommended next action.
6. SYNC_BACK — concise facts ChatGPT cloud must know to update PROJECT_HOME.

If code was changed, commit/push it to the canonical repository when authorized and appropriate. If a large binary deliverable was produced, place it in the canonical Drive ACTIVE/delivery folder rather than GitHub.

## 10. Stop conditions
Stop and report instead of guessing if:
- a required canonical input cannot be found;
- continuing would destroy or replace a verified baseline;
- the task requires a major design decision not specified here;
- an external credential/permission is genuinely required.

Otherwise, make reasonable implementation decisions independently and continue.
