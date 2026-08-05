# Requirement interview and design-contract policy

Use one adaptive flow for new projects and new features. Scope size changes the depth, not the workflow.

## Start from evidence

1. Preserve the user's original words with `start_requirement_discovery`.
2. For an existing project, search the code graph, relevant modules, prior contract decisions, and current behavior before asking anything.
3. Classify the requirement profile automatically:
   - `product`: new project, user-visible feature, commercial behavior.
   - `internal`: refactor, maintenance, developer workflow.
   - `defect`: wrong current behavior with an expected outcome.
4. Assess risk automatically. The user never chooses a model, branch, worktree, or question profile.

## Ask adaptively

- Ask only when the answer can change the product outcome, acceptance criteria, constraints, or recommended solution.
- Ask one question at a time during discovery. Persist it with `update_requirement_discovery`; never keep two open questions.
- Skip information already present in the request, code, project map, prior decisions, or earlier answers.
- Challenge vague terms such as “smart”, “complete”, “fast”, or “commercial ready” by asking for observable behavior.
- Name hidden assumptions and restate the strongest interpretation: `I understand you want X in situation Y, not Z. Is that accurate?`
- Do not interrogate mechanically. Different stages need different depth:
  - Greenfield product: problem, real user and scenario, current workaround, desired behavior, constraints, acceptance, protected principles.
  - Existing feature: verified current behavior, user-visible change, business rules, compatibility, acceptance, non-goals.
  - Internal work: current bottleneck, desired engineering outcome, boundaries, rollback, protected behavior.
  - Defect: reproducible symptom, expected behavior, affected scenario, evidence, protected behavior.

## When the user does not know

Do not return an expert decision to a beginner. Inspect the project, research when authorized, reason from the stated goal, and present two or three concrete beginner-facing options with a recommendation. Ask only if the remaining choice changes user experience, scope, business rules, privacy/data, an external contract, cost, or an expensive-to-reverse direction.

## Complete discovery

Use `update_requirement_discovery` to maintain the single structured contract. Call `finalize_requirement_discovery` only when its profile reports no missing dimensions and no question is open. This moves the item to solution design; it does not authorize code.

## Select the best solution

- Do not default to an MVP, full platform, rewrite, or existing architecture.
- For a simple and dominant solution, one approach is acceptable.
- For nontrivial work, compare at least two meaningfully different approaches. Evaluate requirement fit, user experience, effort, risk, existing-code reuse, reversibility, and long-term cost.
- A fast or minimal approach may be included when relevant, but it is not mandatory and receives no automatic preference.
- Call `record_solution_design` with one recommendation, its requirement-based reason, and honest confidence.
- If no decision signal remains and confidence is high, allow Guardian to select the recommendation automatically.
- If a material decision signal or low confidence remains, persist one decision question and stop. Explain the stakes, show the recommendation, and wait for the user. Record the answer with `record_solution_decision`, including when the user rejects the recommendation.

## Keep one document

Treat `get_design_contract` as the single source of truth. It contains:

- immutable original request;
- clarified problem, goal, stakeholders, scenarios, and verified current state;
- functional and quality requirements, constraints, preferences, and assumptions;
- acceptance criteria, non-goals, and protected behavior;
- approaches considered, recommendation, selected approach, and decision log;
- document-review scores and findings.

Do not create independent product, spec, architecture, and execution documents that can drift. Render human, project-map, and implementation views from this same contract. Use the artifact URI in downstream task handoffs.

## Review and hand off

Before implementation, review the contract from fresh context on five dimensions: completeness, consistency, clarity, scope, and feasibility. Record the result with `review_design_contract`.

- Fix discoverable factual or technical gaps without asking the user.
- Return material intent ambiguity to one requirement question.
- Return implementation or consistency findings to solution design.
- Pass only with every dimension at least 7/10, no open question or decision, and a selected approach.

Only after the contract passes may planning record `completed/ready`, an execution worktree bind, scope lock, and implementation begin. If implementation reality conflicts with the selected design, call `reopen_design_contract`, preserve its revision lineage, redesign and review it, and ask only when the change crosses the same user-decision boundary. Planning from the superseded revision cannot authorize execution.
