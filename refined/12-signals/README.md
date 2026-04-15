# Signals and Signal Handling

## Why This Topic Has to Appear

Once you understand processes, threads, interrupts, traps, and system calls, one question becomes unavoidable: **how does the operating system notify a process that something important has happened?** A process may need to be told that the user pressed `Ctrl-C`, that a child terminated, that a timer expired, that it attempted an illegal memory access, or that another process deliberately requested its attention. The process cannot poll for every such event without wasting CPU time, and the kernel cannot simply overwrite the process’s ordinary control flow without a disciplined mechanism. That mechanism is **signals**.

Signals matter because they are the process-level notification path for asynchronous events in Unix-like systems. They connect kernel-detected events and interprocess requests to user-visible process behavior. Without them, later topics such as child reaping, timer-driven behavior, terminal control, abnormal termination, and process supervision stay fragmented.

This topic therefore fills a specific gap: interrupts explain how hardware gets the CPU’s attention, traps explain how the current instruction stream enters the kernel, but signals explain how the kernel later informs a process that an event must be handled at the process level.

## The Object Being Introduced

A signal is a **kernel-mediated notification** attached to a process. Its job is to represent an event that matters to the target process and to force the question: what should happen to that process now?

What is fixed is that signals are OS-defined event notifications with specific meanings and default actions. What varies is:
- which signal was generated,
- what caused it,
- which process it is delivered to,
- whether the signal is blocked, pending, ignored, handled, or takes its default action.

## Formal Definition

A **signal** is an operating-system notification delivered to a process to indicate that a particular event has occurred and that some predefined or user-defined action must now be considered.

## Interpretation

In plain technical English, a signal is the kernel saying, "this process needs to know that something happened." The most important minimal model is:

1. a signal is **generated** by some event,
2. the signal is **delivered** to a process,
3. the signal is **handled** either by a default action or a user-defined handler.

That three-step structure is the backbone of this topic.

## Signal Generation

Signal generation is the kernel-side recognition that some event maps to a signal for a target process.

Common causes include:
- terminal or user actions,
- kernel-detected faults,
- timers,
- child state changes,
- and explicit requests from other processes.

Generation is not yet the same as delivery. It means the kernel has recognized that a signal now matters.

## Signal Delivery

Signal delivery is the point at which the kernel presents the signal to the target process so that the process's configured action can take effect.

A signal may exist as pending before it is delivered. Delivery depends on the process's state and signal-masking rules.

The important distinction is:
- **generated** means the event has been recognized,
- **delivered** means the process is now being made to observe the signal's effect.

## Signal Handling

Handling is the action taken once the signal becomes effective.

A signal may use:
- a **default action**, or
- a **user-defined handler**.

Default actions include behaviors such as terminating, stopping, or continuing the process, depending on the signal.

A user-defined handler lets the process replace the default action for certain signals. But this customization is not unlimited.

## Deep Trace: Signal Lifecycle

Suppose a process is running, and an event occurs that should matter to it. The kernel first recognizes the event and determines which signal class corresponds to that event. At that moment the signal is generated. The signal is now conceptually pending for the target process, but the process has not necessarily observed it yet. The kernel then checks whether the signal is currently blocked or otherwise deferred by the process's signal mask and state. If the signal is not deliverable yet, it remains pending. If it is deliverable, the kernel next checks what action is configured for that signal in the target process: default action or user-defined handler. If the action is the default, the kernel applies that default process-level consequence, such as termination or stopping. If a user-defined handler exists and the signal is one that may be overridden, the kernel arranges later process control flow so that the handler executes in user space under the process's ordinary authority. The key conceptual sequence is therefore not "event means handler instantly runs." The key conceptual sequence is: event recognized, signal generated, delivery conditions checked, action selected, process-visible consequence applied.

## Non-Overridable Signals

Lecture 2 requires one hard boundary to be made explicit:

- `SIGKILL`
- `SIGSTOP`

These cannot be overridden.

That restriction is not a minor API quirk. It preserves the operating system's final authority to terminate or stop a process when necessary.

## Signals vs Interrupts vs Traps

An **interrupt** is a hardware/kernel-facing event that gets the CPU's attention.

A **trap** is a synchronous kernel entry caused by the current instruction stream.

A **signal** is a process-facing notification used by the kernel to tell a process that an event matters to it.

They may appear in one causal chain, but they are not the same object.

## Worked Example: Child Termination Notification

Suppose process P creates child C. Later, C terminates.

The child's termination is a kernel-visible lifecycle event. The kernel then generates the appropriate child-state-change signal for P. That signal may later be delivered according to the system's rules. The parent may use the signal information together with `wait`-style logic to learn that the child changed state and to collect termination status.

This example shows that signals are not only about killing processes. They are also part of lifecycle notification and supervision.

## Worked Example: User Interrupts a Foreground Program

Suppose a user sends an interrupt request from the terminal to a foreground process.

The terminal subsystem causes the kernel to generate the corresponding signal for that process. The signal is then delivered. If the process has an allowed user-defined handler, that handler runs. Otherwise, the default action applies.

This example shows that signals are one of the ways the user environment and kernel can influence process control flow asynchronously.

## Boundary Conditions and Failure Modes

- Generation is not delivery.
- Delivery is not handling.
- Not every signal may be overridden.
- A blocked process is not outside signal logic.
- Default handling is real behavior, not a placeholder.

## Common Misconceptions

Do not confuse:
- signal with interrupt,
- delivery with generation,
- default handling with "nothing happened,"
- user-defined handler with kernel-mode code,
- overridable signals with the kernel's non-negotiable control signals.

## How This Connects Forward

Signals connect directly to:
- process lifecycle,
- job control,
- terminal interaction,
- timers,
- exceptions and fault consequences,
- and process supervision.

## Retain / Do Not Confuse

Retain:
- signals are process-level notifications,
- the right minimal model is generated -> delivered -> handled,
- handling may be default or user-defined,
- `SIGKILL` and `SIGSTOP` cannot be overridden.

Do not confuse:
- signals with interrupts,
- generation with delivery,
- delivery with immediate handler execution in every case.
