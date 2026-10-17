---
name: codex-review
description: Guidance using the Codex CLI
disable-model-invocation: true
---

Use the Codex CLI to perform a plan or code review:

codex exec \
  --sandbox read-only \
  --model <gpt-6-astra | gpt-5.6-sol>
  -c model_reasoning_effort="<low|medium|high|xhigh>" \
  "$thermo-nuclear-code-review <your prompt> | <plan review prompt>"

Use thinking levels and models judiciously:
gpt-6-astra: frontier model, extremely good at finding bugs and hard to spot issues. excellent planner and architectural guide.
sol: good for quick checks, code reviews for low-to-medium complexity stuff

For thinkings levels use your best judgement.
