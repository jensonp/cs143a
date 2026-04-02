# Graphviz Learning Heuristic Template

This note is a reusable template for deciding when a chapter explanation should gain a Graphviz figure and what kind of figure that explanation actually needs.

## 1. Goal

Add a figure only when prose is forcing the reader to reconstruct structure, time, or causality in their head. The figure is successful when it removes that reconstruction cost and makes the mechanism easier to produce from memory later.

A useful test is:

`good figure = less mental reconstruction + sharper mechanism boundaries`

If the diagram only repeats a definition, it is not doing enough work.

## 2. Selection Rule

Before drawing anything, identify what the learner is struggling to track.

- If the difficulty is `what exists at the same time`, use a `container or anatomy diagram`.
- If the difficulty is `what can happen next`, use a `state machine`.
- If the difficulty is `who is waiting for which resource`, use a `queue-flow diagram`.
- If the difficulty is `what changes over time across subsystems`, use a `lane trace`.
- If the difficulty is `who owns or cleans up whom`, use a `lifecycle or hierarchy graph`.
- If the difficulty is `where the complexity lives in two competing mechanisms`, use a `comparison diagram`.

The template decision rule is:

`learning bottleneck -> diagram type -> one visible takeaway`

Do not draw one figure that tries to answer five different questions.

## 3. Construction Rules

- Explanation first, figure second. The prose should introduce the mechanism before the figure becomes rereference material.
- Put the operative distinction in the labels, not only in surrounding prose.
- Edge labels should be causes or transitions such as `dispatch`, `wait`, `completion`, `save`, or `restore`.
- Prefer one figure per mechanism. If the figure needs a legend to be understood, it is usually too dense.
- Keep node text short enough to remain readable after markdown scaling.
- Use the same color language across a chapter so the reader learns the visual grammar once.
- Make the kernel boundary explicit when the mechanism depends on kernel mediation.
- If omitting a figure would force the reader to simulate time or ownership mentally, the figure is justified.

## 4. Audit Checklist

Use this checklist before keeping a figure in a note.

- Does the figure answer a learning bottleneck that the prose alone leaves expensive?
- Does it show mechanism rather than just terminology?
- Does each arrow have a clear causal meaning?
- Does the caption or alt text say what to notice?
- Can a reader restate the mechanism from the figure without rereading the paragraph?
- Is the figure narrow enough and legible enough for markdown preview?
- Does it avoid decorative duplication of another figure already nearby?

If two or more answers are `no`, the figure should probably be redrawn or deleted.

## 5. Chapter 3 Instantiation

For Chapter 3, the bottlenecks are dynamic rather than taxonomic, so the correct figure set is:

- `Process anatomy`: separate passive program file, active address space, live CPU context, and PCB.
- `Process state machine`: make `new`, `ready`, `running`, `waiting`, and `terminated` operational rather than mnemonic.
- `Scheduler and queues`: show why ready queues, device queues, and the three schedulers exist.
- `Context-switch trace`: show save/restore across CPU, kernel, and PCBs over time.
- `Creation and termination lifecycle`: make `fork`, `exec`, `wait`, zombie, orphan, and reaping part of one coherent protocol.
- `Communication models`: show where coordination lives in shared memory, local message passing, and client-server communication.

That set follows the template:

`dynamic process chapter -> state, flow, trace, lifecycle, comparison visuals`

## 6. Reuse Pattern

You can reuse this template chapter by chapter.

- Chapter 1 wants boundaries, entry paths, storage copies, and architecture comparison.
- Chapter 2 wants interface boundaries, system-call flow, kernel-structure comparison, and boot flow.
- Chapter 3 wants process state, queueing, save/restore, ancestry, and IPC comparison.
- Later chapters on CPU scheduling, synchronization, and virtual memory will want even more traces, state machines, and resource-ownership diagrams.

The general heuristic is:

`draw the figure at the point where the reader would otherwise have to simulate the system silently`
