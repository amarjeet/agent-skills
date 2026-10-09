# Formal specs for {{PROJECT_NAME}}

Spec kind: `{{SPECS_KIND}}`. Each module names the design sections it is derived from in its header.
The models abstract time and payloads; timeouts and schedules become enabled steps.

| Spec | Design sections | What it pins down |
| --- | --- | --- |
| `example` | Section / Subsection | The state machine, its invariants, the scenarios the design makes claims about |

Only the behaviour module's definitions are mapped to stories. Instance modules that bind rejected
designs hold the runs (`...Violates`) that show why they were rejected.

## Properties and their status

| Instance | Property | Result |
| --- | --- | --- |
| `Example` | `safety` | Simulated: no violation in N traces of M steps; verified to depth D |

## Running

```sh
{{SPECS_GATE}}        # typecheck, witness runs, invariant simulation, documented violations, tracker check
```
