# Chapters 3–4 (Consolidated Copy)

This file is a consolidated copy of the repo’s Chapter 3 and Chapter 4 mastery notes for easier sequential reading.
Canonical sources remain:

- `../chapter3-processes/README.md`
- `../chapter4-threads-and-concurrency/README.md`

---

# Chapter 3 Processes Mastery

Source: Chapter 3 of `../textbook.pdf` (Operating System Concepts, 9th ed.).

This file is the mastery note for Chapter 3.
It treats process management as kernel control over resumable computations rather than as a vocabulary list organized around UNIX examples.

If Chapter 1 established why the OS must control execution and Chapter 2 explained how programs reach the kernel, Chapter 3 explains how the kernel keeps many computations alive at once without losing track of state, ownership, or coordination.

## 1. What This File Optimizes For

The goal is not to memorize process vocabulary.
The goal is to be able to do the following without guessing:

- Explain what makes a process more than a program file.
- Explain why process states describe what the computation can do next, not what it did last.
- Explain why the PCB must exist if execution can be interrupted, blocked, or resumed.
- Trace a context switch as a save-decision-restore protocol with explicit kernel responsibilities.
- Trace creation and termination as lifecycle protocols (identity, inheritance, cleanup), not isolated API trivia.
- Explain why IPC is about preserving meaning, order, and progress, not just moving bytes.

For Chapter 3, mastery means:

- you can trace how a process is created, blocked, resumed, and cleaned up
- you can identify what state the kernel must preserve at each step
- you can explain which queues the scheduler cares about and why
- you can predict what breaks when lifecycle bookkeeping is missing
- you can connect the abstractions to scheduler code, sleep/wakeup paths, and IPC mechanisms in a real kernel

## 2. Mental Models To Know Cold

### 2.1 A Process Is Execution Plus Owned State

A program file is passive.
A process is the live execution of that program together with the machine state and kernel-managed resources that make the execution real.

### 2.2 Process State Means “What Can This Computation Do Next?”

`Ready`, `running`, `waiting`, and `terminated` are meaningful because they encode the process's current relationship to CPU service and future progress.

### 2.3 The PCB Is The Kernel’s Promise That Execution Can Resume

If a computation can be stopped and later continued, the kernel must have a durable record of identity, saved CPU context, scheduling metadata, and owned resources.

### 2.4 Scheduling Is Queue Selection Under Scarcity

The scheduler is a kernel mechanism for choosing which runnable process or thread receives CPU service next.
It operates over explicit queues while other work waits for device completion, timer expiration, or memory relief.

### 2.5 IPC Is Coordination, Not Just Data Transfer

IPC is the mechanism isolated processes use to exchange information and coordinate progress.
The difficult part is preserving ordering, ownership, meaning, and liveness across separate execution contexts.

## 3. Mastery Modules

### 3.1 A Process Is A Program In Execution Plus Owned State

**Problem**

The operating system must manage computations that are currently executing and owning resources, not just program files stored on disk.
A file on disk cannot tell the kernel which instruction is live, which registers hold state, or which resources are currently owned.

**Mechanism**

A `process` is a program in execution together with:

- the `program counter`
- CPU `registers`
- the `stack`
- the `data section`
- the `heap`
- open kernel-managed resources such as files or devices

This is why one program file can correspond to many different processes.
Each execution has different live state even when the code is identical.

**Invariants**

- A process is more than code; it includes execution state and owned resources.
- The program counter and registers must be treated as part of the process's live identity.
- Multiple processes may share program text while still being distinct computations.

**What Breaks If This Fails**

- If a process is treated as only a file, scheduling and resumption become conceptually impossible.
- If live resource ownership is ignored, cleanup and isolation lose meaning.
- If active state is confused with stored code, process creation and duplication become mysterious.

**Code Bridge**

- When reading a kernel's process descriptor, identify which fields belong to CPU state, memory state, and owned resources.

**Drills (With Answers)**

1. **Q:** Why can one executable file correspond to many processes?
**A:** The executable file is a template: code plus initial data. A process is an *instance* with its own live CPU context (PC/registers/stack), its own kernel identity (PID, scheduling state), and its own owned resources (open files, credentials, mappings). Many processes can map the same program text while remaining distinct computations because the instance state is what differentiates them.

2. **Q:** Why is the heap part of the process but not part of the program file in the same way?
**A:** The program file contains the initial image: code and static data. The heap is created and grown at runtime through allocation, demand paging, and mapping decisions, and its contents depend on the program’s execution history. The kernel must track the heap as part of the address space, but it is not a static artifact that exists “in the file” before execution.

3. **Q:** Why is a JVM process still a real process even though it hosts another runtime inside it?
**A:** Because the kernel still schedules and isolates the outer process, not the language runtime. The JVM is user-space code living inside one OS process; its threads and GC are ultimately implemented using OS threads, syscalls, and memory mappings. The presence of a runtime does not weaken the kernel’s role: the OS process remains the unit of protection, resource ownership, and kernel-resumable state.

![Supplement: passive program file, active process image, CPU context, and PCB](../graphviz/chapter3_graphviz/fig_3_1_process_image_anatomy.svg)

### 3.2 Process States Describe What The Kernel Can Do Next

#### Why This Section Exists

Once you accept that a process is a resumable computation, you immediately face a practical question: at any given instant, what is the kernel allowed to do with it?

The kernel cannot simply "run everything." CPUs are scarce, devices complete asynchronously, and processes routinely reach moments where they *cannot* make progress even if you gave them a CPU (for example, waiting for a disk block, a network packet, a child to exit, or a lock to be released). If the kernel does not represent those moments explicitly, scheduling degenerates into guesswork: the OS will waste CPU time on processes that cannot advance, or it will lose track of who should be woken when an event occurs.

Process states exist to fill that exact gap. They are not labels for what happened in the past; they are a contract about *what can happen next* and therefore which kernel mechanisms apply: dispatch, preempt, block, wake, or clean up.

#### The Object Being Introduced (Eligibility For Service + A Waiting Condition)

The object is a **state classification** that the kernel uses to partition processes into sets with different rules.

What is fixed:

- The scheduler can only choose among work that is eligible to run now.
- Devices and timers generate events asynchronously; wakeups must be tied to those events.
- Cleanup must be done even though "the process" is no longer executing.

What varies:

- Whether the process is eligible for CPU service now.
- If it is not eligible, *what exact condition* must occur for it to become eligible again.

The state model is therefore inseparable from two concrete kernel structures:

- a **ready queue** (runnable set) for processes eligible to run, and
- one or more **wait queues** keyed by the event/resource being awaited (device completion, timer, lock, child exit).

If you keep only one sentence: "state" is the kernel's way of turning progress into queue membership plus a wakeup condition.

#### Formal Definitions (Ready, Running, Waiting, Terminated)

Definition (ready): A process is ready if it is eligible to run as soon as the scheduler chooses it. It is not currently executing, but if you restored its context onto a CPU, it would make progress immediately.

Definition (running): A process is running if its execution context is currently loaded on some CPU and it is consuming CPU cycles.

Definition (waiting / blocked): A process is waiting if it is not eligible for CPU service because it is waiting for an external event or resource. The key is that "waiting" implies a *specific wakeup condition* that the kernel can test and signal.

Definition (terminated): A process is terminated when its execution is over. Importantly, termination does not mean "instantly erased." The kernel may need to preserve minimal bookkeeping (exit status, accounting) until a parent or supervisor collects it.

#### Interpretation (State Is A Kernel Promise About Scheduling And Wakeup Semantics)

The distinction between ready and waiting is what makes multiprogramming real. A waiting process is removed from CPU competition so the scheduler can give the CPU to someone who can actually execute. Meanwhile the kernel must remember *where to resume* and *why resumption is currently illegal*. That "why" is not philosophical; it is the pointer to the queue or event structure that will wake the process later.

If you forget this, you will fall into the most damaging beginner intuition: "the CPU waits for the disk." The CPU never has to wait for the disk. A process waits, and the kernel chooses other runnable work. The whole point of the state model is to ensure that "waiting" becomes an actionable kernel fact.

#### Boundary Conditions / Assumptions / Failure Modes

Assumptions you should surface explicitly:

- A blocked process has a well-defined wakeup condition (interrupt completion, lock release, timer expiry, message arrival). If the kernel cannot name the condition, it cannot wake it reliably.
- State transitions must be synchronized with queue operations. A state field that says "waiting" is meaningless if the process is still on the run queue, and vice versa.

Failure modes (these show up later as deadlocks, missed signals, and performance cliffs):

- **lost wakeup**: the event occurs, but the process is not moved back to ready because queue membership and signaling got out of sync.
- **spurious runnable**: a blocked process remains runnable and is scheduled repeatedly, wasting CPU.
- **incorrect termination protocol**: the kernel frees state too early and the parent cannot observe the child’s exit status, or frees too late and process-table resources leak.

#### Fully Worked Example: Blocked On I/O Is Not "Inactive"

Consider a process that calls `read(fd, buf, 4096)` on a disk-backed file when the data is not in cache.

1. The process starts in `running` (it is executing).
2. It issues the syscall; the kernel validates arguments and initiates disk I/O.
3. The process cannot complete the syscall until the device finishes. The kernel therefore:
   - saves the process context (so it can resume),
   - records the wait condition (this disk request completion),
   - moves the process to `waiting`, and
   - dispatches some other `ready` process.
4. Later, the disk completes and interrupts the CPU. The interrupt handler records the completion and moves the blocked process from `waiting` to `ready`.
5. Eventually, the scheduler dispatches it again; it becomes `running` and returns from the syscall.

What you should notice is the invariant pattern: progress is regulated by queues and events, not by the CPU "pausing."

#### Misconceptions (Because They Produce Wrong Debugging Instincts)

Misconception 1: "`waiting` means the process is swapped out."

- Waiting is about CPU eligibility, not memory residency. A waiting process may be resident in RAM or not; swapping is a separate scarcity mechanism. Confusing them leads to wrong performance explanations ("it was slow because it was waiting") and wrong fixes.

Misconception 2: "`ready` means it will run soon."

- Ready means eligible, not guaranteed. Under load, ready time can be long due to scheduling policy, priority, and competition. This is why response time is a queueing problem, not just a CPU-speed problem.

Misconception 3: "State transitions are just bookkeeping."

- They are enforcement. If the kernel does not enforce the rule "waiting processes do not consume CPU," the entire multiprogramming story collapses.

#### Connection To Later Material

You will reuse this state-and-queue framing everywhere:

- CPU scheduling chapters refine how the ready set is ordered and selected.
- Threading chapters refine what the schedulable entity is (process vs thread) but keep the same ready/waiting logic.
- Synchronization chapters explain why locks create waiting states and how to avoid deadlocks.
- IPC chapters explain how message arrival becomes a wakeup event and how buffering changes waiting behavior.

#### Retain / Do Not Confuse

Retain: process state is defined by CPU eligibility and explicit wakeup conditions, not by historical narration.

Do not confuse: waiting (not runnable) with swapped out (not resident), or ready (eligible) with running (currently consuming CPU).

**Problem**

Once a process exists, it does not run continuously to completion.
The kernel must classify whether it can run now, later, or never again.

**Mechanism**

The classic states are:

- `new`
- `ready`
- `running`
- `waiting`
- `terminated`

These states are operational:

- `ready` means the process could run if given a CPU
- `running` means it is using a CPU now
- `waiting` means some event must occur before it can continue
- `terminated` means execution is over and cleanup is underway or complete

The scheduler and wakeup paths depend on these distinctions.

**Invariants**

- A ready process is eligible for CPU service now.
- A waiting process cannot make progress until an event occurs.
- A running process consumes CPU; a ready one does not.
- State transitions must reflect real causality such as dispatch, block, completion, or exit.

**What Breaks If This Fails**

- If waiting and ready are confused, the kernel wastes CPU on work that cannot progress.
- If running and ready are confused, scheduling decisions lose meaning.
- If termination is treated like just another waiting state, cleanup logic becomes inconsistent.

**One Trace: basic lifecycle under scheduler control**

Read this as a “what can happen next” trace.
Each transition corresponds to a kernel-recognized cause (dispatch, block, completion, exit), and the state label is only meaningful because it constrains what the scheduler and wakeup paths are allowed to do next.
When you cover the table, do not recite labels; recite the cause that justifies each transition and the invariant it preserves (no CPU time for blocked work, no progress without dispatch).

| Step | State | Cause |
| --- | --- | --- |
| creation | `new` | process admitted |
| dispatch | `ready -> running` | scheduler selects it |
| block | `running -> waiting` | I/O request or event wait |
| wakeup | `waiting -> ready` | event completes |
| exit | `running -> terminated` | execution ends |

This is a kernel contract, not a labeling scheme.
The state names matter only because they constrain what the OS is allowed to do next: who can be scheduled, who must wait, and which event can legally re-admit the process.
If you cannot name the event that will wake a waiting process, you do not yet have an operational process model.

**Code Bridge**

- In scheduler code, ask where the process state field changes and which event justifies each transition.

**Drills (With Answers)**

1. **Q:** Why is `ready` not just “almost running”?
**A:** `Ready` means “eligible to run if scheduled,” not “already running with a delay.” The distinction matters because only `running` consumes CPU now, while `ready` competes for CPU through the scheduler. Treating them as the same erases the meaning of dispatch and makes it impossible to reason about fairness, queueing, and response time.

2. **Q:** Why is `waiting` not the same thing as “inactive”?
**A:** `Waiting` has a specific wakeup condition: some event (I/O completion, lock release, timer) must occur before progress is possible. The kernel must remember *what* the process is waiting for and place it in the right wait structure; it is paused but not gone. “Inactive” is vague; `waiting` is operationally precise.

3. **Q:** Why do state transitions need causes rather than just labels?
**A:** Because the kernel’s invariants depend on causality. A process becomes `waiting` because it cannot proceed until an event occurs; it becomes `ready` because that event happened and the kernel recorded it. If you allow arbitrary relabeling, you can schedule blocked work, lose wakeups, or clean up live processes, all of which are correctness failures.

![Supplement: process states are defined by what the process can do next](../graphviz/chapter3_graphviz/fig_3_2_process_state_machine.svg)

### 3.3 The PCB Is The Kernel’s Authoritative Record

#### Why This Section Exists

Process state labels only become real if the kernel has somewhere trustworthy to store the facts that make a process resumable: where it will resume (PC), what it will resume with (registers), what memory layout gives addresses meaning (page table root / address space), and what resources it owns (open files, credentials, pending signals).

Those facts cannot live only "in the process," because the process is precisely the thing that might be stopped, blocked, or even malicious. The kernel needs a protected, durable record that (1) survives preemption and blocking, (2) can be safely read and updated by the scheduler and other kernel subsystems, and (3) cannot be forged by user code.

That record is the PCB (or, in many real kernels, a closely related family of task/thread structures). This section exists because without a PCB-level mental model, context switches and lifecycle protocols become magic.

#### The Object Being Introduced (Kernel-Resident Records That Index Execution)

The object is a **kernel-resident descriptor** that binds together three worlds:

- the CPU world: the saved execution context that can be restored,
- the memory world: the address-space mapping that gives the context meaning,
- and the resource world: the kernel objects the process is allowed to use.

What is fixed:

- The kernel must be able to find and restore an execution context without trusting user memory.
- The kernel must be able to account and enforce policy using these records (scheduling, limits, credentials).

What varies:

- The specific fields and names across OS implementations.
- Whether the OS splits process vs thread state into separate structures (common) or combines them (also common in teaching kernels).

#### Formal Definitions (PCB, Trap Frame, Kernel Stack)

Definition (PCB): The process control block is the kernel’s authoritative record for a process, storing identity, state, pointers to memory-management structures, scheduling metadata, and references to owned resources.

Definition (trap frame): The saved CPU register snapshot created on a trap/interrupt/syscall entry so the kernel can later return to the interrupted context correctly. In many kernels, the trap frame lives on the kernel stack of the current thread/process.

Definition (kernel stack): A privileged stack used while executing kernel code on behalf of a process/thread. It is separate from the user stack, because kernel code must remain runnable even when user memory is invalid or untrusted.

The important interpretation is that "PCB contains everything" is an oversimplification. A PCB is often an index: it points to the trap frame and kernel stack, points to the address-space root, and points to tables of resources. But the PCB is the anchor that keeps those pieces coherent.

![Supplement: the PCB anchors trap frames, kernel stacks, address-space roots, and owned resources into one resumable identity](../graphviz/chapter3_graphviz/fig_3_14_pcb_trapframe_anchor.svg)

#### Boundary Conditions / Assumptions / Failure Modes

Assumptions:

- The PCB and related scheduler structures live in kernel memory and are protected from user writes. If user code can forge PCB fields, protection collapses.
- Context-save/restore protocols are correct with respect to the CPU ABI and interrupt/trap entry rules. If you save the wrong set, restore returns to nonsense.

Failure modes:

- Save/restore bugs produce corruption that is timing-sensitive: it may appear only under interrupts or heavy switching.
- Resource bookkeeping bugs leak kernel objects (file descriptors, VM mappings) or create use-after-free when a PID/descriptor is reused.
- If exit cleanup races with a parent `wait`, you get zombies that never clear or status that disappears.

#### Fully Worked Example: Timer Preemption Uses PCB + Trap Frame Together

Consider a running process A that is preempted by a timer interrupt.

1. The timer interrupt occurs asynchronously. Hardware transfers control to the kernel and pushes/saves a register snapshot (exact details depend on the ISA).
2. The kernel entry path completes the saving protocol, producing a trap frame that is now the authoritative snapshot of A’s interrupted user context.
3. The kernel updates A’s PCB fields: it records state transition (`running -> ready`), accounts CPU time, and enqueues A on the ready queue.
4. The scheduler chooses a different runnable process B. The kernel switches "current" pointers to B’s PCB/thread record and loads B’s saved context.
5. The kernel returns from interrupt/trap using B’s trap frame, restoring registers and resuming B’s user-mode instruction stream.

Notice the division of labor: the trap frame is the raw CPU snapshot; the PCB is the durable kernel record that ties that snapshot to queues, memory mappings, and resources.

#### Misconceptions

Misconception 1: "The PCB is just for the scheduler."

- The PCB is shared infrastructure. The scheduler cares about run-queue membership and priorities, but the memory manager cares about the address-space pointer, the signal subsystem cares about pending signals, and the file subsystem cares about open-file tables. The PCB is the rendezvous point for kernel subsystems that must coordinate around one process identity.

Misconception 2: "User space could store its own context, so PCBs are optional."

- User space can store some logical state, but it cannot store the privileged facts that make resumption safe: mode bits, validated mappings, kernel object references, and unforgeable credentials. The kernel must store those.

#### Connection To Later Material

PCB reasoning is the backbone of:

- CPU scheduling (what fields the scheduler reads/writes, how queue membership is represented),
- threading (splitting process vs per-thread execution records),
- signals and cancellation (how asynchronous events attach to a target execution context),
- and IPC (how blocked state is represented and what wakeups mutate).

#### Retain / Do Not Confuse

Retain: the PCB is the kernel’s authoritative anchor for a process identity across interruption, blocking, and cleanup.

Do not confuse: the raw saved register snapshot (trap frame) with the higher-level kernel record (PCB) that ties it to scheduling and resources.

**Problem**

If a process can be interrupted, blocked, preempted, or resumed, the kernel needs durable bookkeeping that survives those transitions.

**Mechanism**

The `process control block (PCB)` stores the information needed to treat the process as a resumable execution entity.
That typically includes:

- process identity
- saved execution state
- scheduling metadata
- memory-management information
- I/O and resource metadata

The exact field names differ by OS, but the role stays constant:
the PCB is where the kernel remembers enough to resume or clean up the process correctly.

**Invariants**

- Saved execution state must be sufficient for correct resumption.
- Scheduling metadata must allow the process to be placed in the right queues.
- Resource metadata must remain consistent with what the process actually owns or references.
- The PCB is authoritative; it cannot be replaced by vague assumptions about “the running program.”

**What Breaks If This Fails**

- Without saved context, resumption is incorrect.
- Without scheduling metadata, dispatch decisions become disconnected from process reality.
- Without resource metadata, cleanup and protection break.

**Code Bridge**

- In Linux-like code, ask how identity, saved CPU context, run-queue membership, and open-resource state are represented in the task structure.

**Drills (With Answers)**

1. **Q:** Why is the PCB not just optional bookkeeping?
**A:** Because preemption and blocking make execution discontinuous. If the kernel can stop a computation and later resume it, the kernel must have an authoritative record that survives the stop. The PCB is that record: it is the kernel’s representation of the process as a resumable entity, and without it the OS cannot safely schedule, block, wake, or clean up processes.

2. **Q:** What is the minimum information a PCB must preserve for resumption?
**A:** Enough architectural and kernel state to continue the same instruction stream correctly: saved CPU context (PC, SP, registers, status flags), identity (PID), and the address-space handle (page table pointer or equivalent). In practice it also includes kernel stack/context, scheduling metadata (state, priority, run-queue links), and pointers to the process’s owned resources so invariants remain consistent after resumption.

3. **Q:** Why is resource metadata part of the PCB story instead of only CPU state?
**A:** Because a process is a resource-owning contract, not only a CPU snapshot. Open files, memory mappings, IPC endpoints, credentials, and pending signals determine what the computation is allowed to do and what it is waiting on. If you only save registers, you can “resume” into a world where ownership and protection are wrong, which breaks isolation and cleanup.

### 3.4 Threads Refine The Process Model Rather Than Replacing It

**Problem**

Modern systems often need multiple execution paths inside one application without duplicating every process-level resource.

**Mechanism**

A `thread` is an execution path inside a process.
The process remains the larger resource-owning container:

- address space
- open files
- other process-level kernel resources

Threads share those process-level resources while keeping distinct execution states.

The process/thread distinction is a distinction between two kernel responsibilities:

- the process owns the address space and protection boundary
- the thread carries one schedulable control flow through that boundary

**Invariants**

- Process and thread are not interchangeable abstractions.
- Threads inside one process share the process container.
- Distinct execution paths still require distinct execution state.

**What Breaks If This Fails**

- If threads are confused with processes, resource sharing and isolation logic become muddled.
- If process ownership is ignored, “lighter weight” execution is explained badly.
- If execution path and resource container are fused conceptually, later concurrency discussions become harder.

**Code Bridge**

- In thread-aware kernels or runtimes, ask which state belongs per-thread and which remains process-wide.

**Drills (With Answers)**

1. **Q:** Why is a thread cheaper than a full process in many systems?
**A:** Threads share the process container: address space, open files, and other resources are not duplicated. Creating and switching threads often avoids the heaviest costs of process creation (new address space, large metadata, full isolation setup) and can reduce context-switch cost (less MMU/TLB churn). The trade is that sharing increases coordination burden and failure coupling inside the process.

2. **Q:** Why does shared address space not make two threads the same execution path?
**A:** Because “execution path” is defined by control state, not only by memory. Each thread has its own PC/register set and its own stack, and the scheduler can run them independently, at different points in the code, or simultaneously on different cores. Shared memory is shared *ownership*, not shared *control flow*.

3. **Q:** Why does the process still matter after threads are introduced?
**A:** The process remains the unit of protection and resource ownership: it defines what memory is accessible, which files are open, and what privileges apply. Threads are schedulable execution contexts living inside that container. Without the process abstraction, you cannot explain isolation boundaries, address-space management, or why threads can corrupt each other’s invariants by racing on shared state.

### 3.5 Queues And Schedulers Exist Because Processes Compete For Service

**Problem**

The CPU and devices are scarce.
The kernel therefore needs explicit waiting structures and selection logic.

**Mechanism**

Processes may appear in structures such as:

- the `job queue`
- the `ready queue`
- device-specific wait queues
- swap-related holding structures when memory pressure matters

The `short-term scheduler` chooses among ready processes.
The `long-term scheduler` influences how many processes are admitted into active competition.
The `medium-term scheduler` can reduce pressure by swapping processes out and back in.

These structures exist because the kernel must represent different scarcity conditions explicitly: CPU scarcity in the ready queue, device scarcity in wait queues, and memory scarcity in swap-related structures.

**Invariants**

- Ready work and blocked work must remain distinct.
- Device waits belong in event- or device-specific queues, not the ready queue.
- Long-term admission affects the degree of multiprogramming.
- Scheduler choice must operate on a truthful representation of who can run now.

**What Breaks If This Fails**

- If everything is thrown into one queue, scheduling loses semantic meaning.
- If the ready queue contains blocked processes, CPU time is wasted.
- If admission pressure is ignored, memory and responsiveness can both degrade.

**One Trace: queue movement under normal operation**

This trace is about the operational meaning of “state.”
Queue membership is not bookkeeping trivia; it encodes which scarcity the process is currently subject to (CPU scarcity in the ready queue, device scarcity in a wait queue, memory scarcity when swapped).
When you cover the table, say why each move is allowed: dispatch consumes CPU service, block records a wait condition, completion re-admits runnable work, and swapping changes who competes under memory pressure.

| Step | Queue / State Change | Meaning |
| --- | --- | --- |
| process admitted | enters job set then ready queue | now eligible for future CPU service |
| dispatched | leaves ready queue, becomes running | CPU assigned |
| blocks on I/O | enters device wait queue | cannot use CPU productively now |
| I/O completes | leaves device wait queue, reenters ready queue | runnable again |
| swapped out under pressure | leaves active competition temporarily | memory pressure managed |

Notice that the table is really “scarcity -> bookkeeping.”
CPU scarcity is encoded by ready/running; device scarcity by wait queues; memory scarcity by swap pressure mechanisms.
Good OS structure keeps these meanings separated so one bottleneck does not destroy the semantics of scheduling and wakeup.

**Code Bridge**

- In scheduler code, identify which queue corresponds to which kind of scarcity: CPU, device, or memory.

**Drills (With Answers)**

1. **Q:** Why is a queue not just an implementation detail but part of the process model?
**A:** Because queue membership is how the kernel represents *what kind of progress is possible*. A ready queue means “eligible for CPU service now”; a device wait queue means “cannot progress until this event fires”; a swap structure means “not currently competing due to memory pressure.” If you treat queues as implementation detail, you lose the semantics that make scheduling, wakeups, and fairness explainable.

2. **Q:** Why does the long-term scheduler change system behavior even though it runs infrequently?
**A:** Admission controls the degree of multiprogramming: how many processes are actively competing for RAM and CPU. Even rare decisions change the system’s steady-state mix, which affects paging pressure, cache behavior, throughput, and interactive latency. A “too many admitted” system can thrash even if short-term scheduling is perfect.

3. **Q:** Why is a healthy process mix important for overall utilization?
**A:** Because different processes stress different resources. A mix of CPU-bound and I/O-bound work lets the OS overlap CPU execution with device latency instead of leaving one resource idle. If all work blocks on the same scarce device, the CPU can go idle; if all work is CPU-bound, devices can be underutilized and interactive response can degrade.

![Supplement: admission, dispatch, blocking, completion, and swap pressure create the queue structure](../graphviz/chapter3_graphviz/fig_3_3_scheduler_queues.svg)

### 3.6 Context Switching Is Save, Decision, And Restore

#### Why This Section Exists

The process model is only real if the kernel can *actually* stop one computation and later resume it exactly, potentially after running many other computations in between. Context switching is the mechanism that makes that promise true.

This section exists because "the scheduler chooses who runs next" is not yet an operational statement. A choice is not a physical event. It becomes physical only when the kernel performs a save-decision-restore protocol that changes what registers, stack pointer, and address-space mapping are live on the CPU. If you cannot narrate that protocol, you will not be able to reason about preemption, blocking syscalls, or later synchronization behavior under interrupts.

#### The Object Being Introduced (A Protocol With Explicit Responsibilities)

Treat a context switch as a protocol with responsibilities, not as one magical instruction.

What is fixed:

- The CPU can execute only one instruction stream at a time per core.
- Traps/interrupts create controlled kernel entry points.
- The kernel is responsible for preserving resumability and enforcing scheduling rules.

What varies:

- Which event triggered the switch (timer interrupt, I/O block, yield, higher-priority wakeup).
- Whether the switch also changes the address space (process switch) or keeps it (thread switch inside one process, later).

What conclusions it licenses:

- You can explain why "blocking" is compatible with CPU utilization: the blocked entity is saved and removed from the runnable set, and a different entity is restored.
- You can explain why context switching has overhead (and why too much preemption can reduce throughput).

#### Formal Definition (Context Switch As State Transfer)

Definition (context switch): A kernel-mediated transfer of CPU execution from one schedulable entity to another, consisting of:

1. saving enough outgoing CPU state into kernel-owned storage so the entity is resumable,
2. updating kernel scheduling/bookkeeping state to reflect the outgoing entity's new status,
3. selecting an incoming runnable entity according to scheduling policy, and
4. restoring the incoming entity's saved state (and associated memory mapping) so it becomes live on the CPU.

#### Interpretation (The Switch Is Where "Policy" Touches Hardware)

Scheduling policy lives in decision rules: priorities, fairness, deadlines, affinity. Context switching is where those rules become physical reality. The kernel turns "B should run next" into:

- B's registers and stack pointer are loaded,
- B's address space is installed (if needed),
- and the CPU returns to user mode at B's program counter.

This is why context-switch code is among the most delicate code in an OS: it is where abstract policy turns into concrete machine state.

#### Boundary Conditions / Assumptions / Failure Modes

Assumptions:

- The saved state is complete with respect to the ABI and trap entry/exit protocol.
- The kernel updates queue membership and state atomically with respect to interrupts (and later, with respect to other CPUs).

Failure modes:

- partial saves produce corruption that is hard to reproduce (depends on timing and which registers were live).
- state/queue mismatches produce lost wakeups or duplicated runnable entities.
- excessive switching produces performance collapse: even if "fair," the system spends too much time switching and too little time executing useful instructions.

#### Fully Worked Example: Blocking Syscall Switches For A Different Reason Than Timer Preemption

Compare two switches:

Timer preemption:

1. A is running; timer fires.
2. Kernel saves A, requeues it as ready.
3. Scheduler chooses B.
4. Kernel restores B and returns to user mode.

Blocking syscall:

1. A is running; A issues `read()` and the data is not ready.
2. Kernel saves A, but does **not** requeue it as ready. Instead it enqueues A on a wait queue associated with the I/O completion event and marks it waiting.
3. Scheduler chooses B from the ready queue.
4. Kernel restores B and returns to user mode.

The structural difference is the state transition. In preemption, A remains runnable; in blocking, A becomes non-runnable until a wakeup event occurs.

#### Misconceptions

Misconception 1: "A context switch always means a different process."

- Not necessarily. It can be a switch between threads inside the same process (later). The common part is saving/restoring execution context; whether the address space changes is a separate axis.

Misconception 2: "The scheduler is the switch."

- The scheduler chooses; the context switch makes that choice real. Conflating them hides where correctness obligations live (save/restore) versus where policy lives (choose).

#### Connection To Later Material

Context switching is the mechanical substrate for:

- CPU scheduling policies (the decision that triggers which restore),
- synchronization and preemption safety (what must be atomic around queue operations),
- and thread models (user threads vs kernel threads change what entities can be switched independently).

#### Retain / Do Not Confuse

Retain: switching is a protocol: save -> update state/queues -> choose -> restore.

Do not confuse: timer preemption (runnable -> runnable) with blocking (runnable -> waiting).

**Problem**

The OS must stop one computation and later resume either the same one or a different one without corrupting execution.

**Mechanism**

A `context switch` saves the outgoing process state and restores the incoming process state.
It is triggered by events such as:

- timer interrupts
- blocking I/O
- explicit yield or sleep
- wakeup and scheduler choice

The scheduler's decision only becomes real because the context switch changes which process state is live on the CPU.

Context-switch cost is kernel overhead because the switch preserves resumability and fairness rather than advancing the user program's instruction stream directly.

**Invariants**

- Outgoing state must be saved before it is overwritten.
- Incoming state must be restored consistently.
- The scheduler must choose among runnable work, not arbitrary work.
- Switching too frequently can trade responsiveness for excessive overhead.

**What Breaks If This Fails**

- Without correct saves, resumed execution is corrupted.
- Without correct restore, the wrong computation continues.
- Without a scheduler decision between save and restore, switching is meaningless.
- Without overhead awareness, fairness improvements can become performance regressions.

**One Trace: timer-driven preemption**

This is the minimal save-decision-restore loop that makes time sharing real.
The timer interrupt creates a forced kernel entry, then the kernel must (1) save enough state to resume A, (2) decide which runnable context is next, and (3) restore B so the decision becomes real.
When you rehearse it, explicitly name where the saved state lives (PCB / kernel stack) and why “choose” must occur between save and restore.

| Step | Running Process | Kernel / Scheduler | Result |
| --- | --- | --- | --- |
| slice active | process A uses CPU | timer counts down | A makes progress |
| timeout | A is interrupted | kernel regains control | preemption point reached |
| save | A stops running | A's context stored in PCB | A becomes resumable |
| choose | scheduler selects B | runnable set examined | next process chosen |
| restore | B's state loaded | kernel returns to user mode | B becomes running |

The correctness pressure here is atomicity: saving state, changing queues/state, and restoring the next context must be consistent even under interrupts and (in later chapters) multiple CPUs.
Context-switch code is small and tightly structured because it is the point where scheduling policy becomes machine state: the kernel must translate "B should run next" into B's registers, stack, and address space becoming live on the CPU.

**Code Bridge**

- In a teaching kernel, inspect the timer interrupt path and the scheduler handoff to see where save, decision, and restore each occur.

**Drills (With Answers)**

1. **Q:** Why is a context switch not itself useful work for the user computation?
**A:** Because it does not advance the user program’s instruction stream; it preserves and transfers control so *someone* can run. Saving and restoring registers, updating kernel bookkeeping, and switching stacks are overhead paid to create the illusion of concurrent progress and to enforce fairness and responsiveness. You do it to share the machine, not to compute the program’s output.

2. **Q:** What exact state must survive preemption?
**A:** The architectural CPU context needed to resume correctly: PC, SP, general registers, and status/flags (often plus FP/SIMD state). The kernel must also preserve the identity and execution container mapping: which address space to restore (page table pointer) and the kernel bookkeeping that makes the thread schedulable (state, priority, run-queue links, kernel stack). “Saved registers only” is not enough if the restored mapping and identity are wrong.

3. **Q:** Why does timer-driven preemption require both interrupt logic and scheduler logic?
**A:** Interrupt logic provides the forced entry that regains control even if the process never yields. Scheduler logic decides which runnable work should run next. Without interrupts, you cannot enforce preemption; without scheduling, you can preempt but you cannot choose a correct next owner of the CPU (or maintain fairness and responsiveness).

![Supplement: a context switch is a save-decision-restore protocol, not a mysterious jump](../graphviz/chapter3_graphviz/fig_3_4_context_switch_trace.svg)

### 3.7 Process Creation Is Controlled Duplication And Divergence

#### Why This Section Exists

Once you understand that a process is the kernel's unit of execution and ownership, "creation" becomes one of the most load-bearing mechanisms in the OS. Creation is where the kernel mints a new identity that will compete for CPU/memory/I/O, inherits (or does not inherit) access to resources, and must later be cleaned up without leaks.

This section exists because process creation is frequently taught as API trivia (`fork`, `exec`, `spawn`) when the real intellectual content is the protocol:

- identity allocation (PID + kernel records),
- inheritance rules (what carries over),
- divergence (how parent and child do different work),
- and efficiency (how creation can be cheap enough to use constantly in shells and servers).

Lecture 2's `fork`/`exec` split is the canonical way to see that "create a container" and "choose a program image" are different problems. Even on systems that offer a one-shot `spawn`, the same conceptual separation exists internally.

#### The Object Being Introduced (Lifecycle Protocol: Identity + Inheritance + Divergence)

The object here is a **creation protocol** that preserves invariants across multiple subsystems:

- scheduling: insert a new runnable entity without duplicating or losing bookkeeping,
- memory: create an address-space image that is coherent and protected,
- files: define what file descriptors and open-file descriptions are shared or duplicated,
- security: ensure the child does not accidentally inherit more authority than intended,
- cleanup: ensure every allocated object is reclaimed at termination.

What varies is the *policy* of inheritance and the *API* exposed to user space; what stays fixed is that the kernel must implement the protocol safely.

#### Formal Definitions (fork, exec, Copy-on-Write)

Definition (fork-style creation): A primitive that creates a child process whose initial execution context is a near-copy of the parent, differing in identity (PID) and return value. Divergence happens through control flow.

Definition (exec-style replacement): A primitive that replaces the current process's program image (code/data/stack layout and entry point) while preserving the process identity and selected inherited resources.

Definition (copy-on-write, COW): An optimization where parent and child initially share physical pages marked read-only; on the first write to a shared page, the kernel copies the page so the writer receives a private copy. The logical model is "copied address spaces"; the physical model is "shared until written."

![Supplement: fork can be logically copy-like while physically sharing pages via copy-on-write until a write forces a private copy](../graphviz/chapter3_graphviz/fig_3_15_fork_copy_on_write.svg)

#### Interpretation (Why Creation Is Harder Than "Run Another Program")

Creation is not "start executing some code." It is the act of creating a new execution container whose future syscalls, faults, scheduling decisions, and resource usage will be meaningful. That requires the kernel to tie together:

- a new identity (PID + PCB/task record),
- a consistent initial CPU context (where does the child begin executing?),
- an address-space mapping (what do addresses mean for this new computation?),
- and a controlled set of inherited kernel object references (files, pipes, credentials).

If you translate `fork` to "copy memory," you will miss the most important parts: kernel object inheritance rules and the existence of shared-but-mutable objects (like open-file descriptions).

#### Boundary Conditions / Assumptions / Failure Modes

Assumptions:

- The kernel can allocate and initialize a new process record under concurrency without corrupting global structures.
- Inheritance rules are explicit and enforced (close-on-exec flags, credential changes).

Failure modes:

- Incorrect inheritance can leak authority (child inherits privileged descriptors or credentials).
- Incorrect sharing semantics can cause surprising interference (shared file offsets, shared working directories).
- Over-eager deep copying can make creation too expensive; this is why COW and spawn-style APIs exist.

#### Fully Worked Example: File-Descriptor Inheritance Is About Kernel Objects, Not Integers

Suppose the parent opens a file and then forks:

1. Parent calls `open("data.log")` and receives fd=3.
2. Parent calls `fork()`.

At the user level, both processes now have an integer 3. The kernel question is what object that integer names.

In many Unix designs:

- the parent has a per-process fd table mapping `3 -> (pointer to an open-file description)`,
- `fork` duplicates the fd table entries so the child also has `3 -> same open-file description object`.

That open-file description often includes a current file offset. If it is shared, parent and child writes advance a shared offset and therefore interleave unless coordinated. This is why "inheritance" is not a casual feature; it is a semantic choice that affects ordering and correctness.

#### Misconceptions

Misconception 1: "`exec` creates a new process."

- `exec` replaces the program image inside an existing process identity. PID often stays the same; the "container" persists while its contents change.

Misconception 2: "`fork` always duplicates everything immediately."

- The logical model is "two independent processes," but the kernel can implement that with sharing (COW) and with shared kernel objects. Independence is a semantic guarantee, not an instruction that bytes must be copied now.

#### Connection To Later Material

Creation is the foundation for:

- shells and pipelines (inherit pipes, then `exec` into stages),
- server models (prefork vs thread pools),
- scheduling and accounting (new entities enter queues and resource limits),
- and security (least privilege via controlled inheritance).

#### Retain / Do Not Confuse

Retain: creation mints identity and initial bindings; divergence is a separate step (often via `exec` or control flow).

Do not confuse: copying an address space (semantic) with copying all bytes immediately (implementation).

**Problem**

Processes must be created dynamically, but creation raises questions of identity, inheritance, and independence.

**Mechanism**

When a parent creates a child, the OS must decide:

- what identity the child gets
- what resources are inherited
- whether parent and child continue concurrently
- whether the child starts as a copy of the parent image or quickly diverges to a new one

UNIX expresses this structurally with `fork()` and `exec()`:

- `fork()` duplicates the process image
- `exec()` replaces the current program image

The conceptual point is that process creation and program-image replacement are separate kernel actions, regardless of the exact API names a system uses.

**Invariants**

- Creation is not just “run another program”; it creates a new execution container.
- Parent-child ancestry and shared future behavior are not the same thing.
- Resource inheritance must be controlled or isolation becomes weak.
- Image duplication and image replacement are distinct lifecycle steps.

**What Breaks If This Fails**

- If creation and image replacement are fused conceptually, `fork/exec` becomes hard to reason about.
- If inheritance is uncontrolled, resource ownership and predictability degrade.
- If ancestry is confused with identity, process trees stop making sense.

**One Trace: fork then exec style divergence**

This trace exists to separate “new identity” from “new program image.”
`fork` (conceptually) creates a new execution container with inherited context and resources, while `exec` replaces the address-space image so the child can become a different program.
When you cover the table, force yourself to say: which aspects are inherited (files/credentials by default) and which aspect changes at `exec` (the code/data image and entry point).

| Step | Parent | Child | Kernel Meaning |
| --- | --- | --- | --- |
| before creation | running existing image | absent | one execution context exists |
| creation request | asks for child | created with inherited state | new process identity allocated |
| post-fork | continues or waits | starts as copy-like execution image | ancestry established |
| exec | may remain unchanged | image replaced | child diverges into new program |

The practical payoff is that user-space tools (shells, servers) can build pipelines by controlling inheritance (open files, pipes, credentials) and then selecting the program image via `exec`.
The kernel exports the container and replacement mechanism; user space owns the orchestration policy.

**Code Bridge**

- Inspect where the kernel copies process metadata, where it duplicates or references resources, and where `exec` replaces the address-space image.

**Drills (With Answers)**

1. **Q:** Why are `fork()` and `exec()` structurally different actions?
**A:** `fork` is about creating a new identity and execution container: a new PID, new schedulable entity, and inherited resource bindings. `exec` is about replacing the program image inside an existing container: new code/data, new entry point, potentially new address-space layout. Separating them makes the model compositional: “create a process” and “choose what it runs” are different problems.

2. **Q:** Why is parent-child ancestry not the same thing as sharing a future program image?
**A:** Ancestry is the creation relationship: who created whom, and therefore who can `wait` for whom and who inherits what initially. The future program image is a runtime choice: after `exec`, the child may run a completely different program than the parent. Confusing these leads to wrong assumptions like “child runs parent’s code forever,” which breaks reasoning about shells, pipelines, and servers.

3. **Q:** What resource decisions must the OS make during process creation?
**A:** Which open files and descriptors are inherited (and which are marked close-on-exec), what credentials/identity are inherited, what memory mappings are duplicated or shared (copy-on-write vs deep copy), what scheduling attributes apply, and how parent/child relationships are recorded. These decisions define both correctness (what the child can access) and performance (how expensive “duplication” actually is).

![Supplement: fork then exec is controlled duplication, then image replacement](../graphviz/chapter3_graphviz/fig_3_7_fork_exec_trace.svg)

### 3.8 Termination, Wait, Zombies, And Orphans

#### Why This Section Exists

"Process termination" sounds like an instantaneous event: the program ends, the process disappears. In real kernels, termination is a protocol because other processes may need to learn the outcome (exit status), resources must be reclaimed in a safe order, and parent/child relationships create obligations (who is allowed to wait for whom).

This section exists to prevent two common confusions that break later reasoning:

- mistaking a *terminated computation* for a *deleted kernel record*, and
- treating parent/child relations as narrative trivia rather than as a cleanup protocol that preserves kernel invariants and avoids leaks.

#### The Object Being Introduced (A Two-Phase Death: Execution Ends, Bookkeeping Persists)

The object here is the **termination protocol**.

What is fixed:

- The kernel must reclaim resources (address space mappings, open descriptors, kernel objects).
- The kernel must preserve the child's exit status long enough for an authorized observer (parent) to collect it.

What varies:

- which resources are reclaimed immediately versus deferred,
- which process becomes responsible when the original parent disappears (reparenting).

The key interpretive move is to separate:

1. the *end of execution* (no more instructions will run), from
2. the *end of existence as a kernel-recorded identity* (PCB entry fully removed).

The gap between (1) and (2) is exactly what "zombie" names.

#### Formal Definitions (Exit Status, Zombie, Orphan, Reparenting)

Definition (exit status): A small result code recorded by the kernel that summarizes why the process ended (normal exit code, killed by signal, etc.).

Definition (zombie): A process that has finished executing but still has a kernel record retained solely so the parent can collect its exit status and accounting. A zombie is not runnable and does not hold an address space like a live process, but it occupies a slot/entry in process bookkeeping.

Definition (orphan): A process whose parent has terminated before it did. Orphans still execute normally; the "orphan" property is about cleanup responsibility, not about whether the process is alive.

Definition (reparenting): The kernel operation that assigns an orphaned process a new parent (often `init`/PID 1) so that there is always a live process that can eventually perform the wait/cleanup handshake.

![Supplement: termination is a protocol; zombies are bookkeeping, and orphans are reparented so cleanup is guaranteed](../graphviz/chapter3_graphviz/fig_3_16_exit_zombie_reparenting.svg)

#### Interpretation (Why Zombies Are Not A Bug)

Zombies exist because "parent observes child outcome" is a real semantic promise. If the kernel deleted all traces immediately at `exit`, the parent would have no reliable way to learn whether the child succeeded, failed, or crashed. So the kernel keeps minimal identity + status until the parent executes `wait` (or equivalent) to acknowledge it.

This is the OS version of a handshake: the child reports "I'm done" and the parent eventually acknowledges "I have received your status," after which the kernel can reclaim the final record.

#### Boundary Conditions / Assumptions / Failure Modes

Assumptions:

- Only authorized parents (or supervisors) may collect a child's status; otherwise status becomes an information leak.
- The kernel must prevent PID reuse from confusing observers (a late `wait` must not collect status from a different process that reused the PID).

Failure modes:

- If parents never `wait`, zombies accumulate and exhaust process-table resources (leak of identities/bookkeeping).
- If the kernel deletes status too early, parents lose correctness (cannot determine child result).
- If reparenting is absent, orphans can become uncollectable, causing leaks or broken semantics.

#### Fully Worked Example: Zombie Lifecycle As A Wait-Handshaking Problem

1. Child calls `exit(0)` (or crashes).
2. Kernel marks child as terminated, reclaims most resources (address space, many kernel objects), but retains:
   - PID and minimal process record,
   - exit status and accounting.
3. Child is now a zombie: not runnable, but still present as a kernel record.
4. Parent later calls `waitpid(child_pid, &status, ...)`.
5. Kernel copies out the exit status to the parent and then removes the final zombie record. Only now is the identity fully reclaimed.

The general lesson is: zombies are a consequence of a *useful contract* (observable child outcome), and the cure is not "delete zombies" but "complete the wait handshake."

#### Misconceptions

Misconception 1: "A zombie is a running process consuming CPU."

- A zombie is not runnable. It is a bookkeeping entry waiting for the parent’s acknowledgment.

Misconception 2: "An orphan is dead."

- An orphan is alive; it has simply lost its original parent. It continues executing and will still exit normally later.

Misconception 3: "Reparenting is optional sugar."

- Reparenting is the kernel guaranteeing that cleanup responsibility is always assigned so process-table resources do not leak permanently.

#### Connection To Later Material

Termination protocol details matter later for:

- shells and job control (`wait` semantics, pipelines),
- threading (what it means for one thread to exit vs the whole process to exit),
- and security (who can observe process outcomes and when).

#### Retain / Do Not Confuse

Retain: termination is a protocol; zombies are a deliberate interim state for status collection; orphans are reparented to preserve cleanup.

Do not confuse: "no longer executing" with "no longer represented in kernel bookkeeping."

**Problem**

Ending execution is not the same thing as instantly deleting every trace of the process.

**Mechanism**

Termination is a protocol:

1. execution ends
2. the process reports status, often through `exit`
3. some resources are reclaimed
4. the parent may later collect status with `wait`
5. final bookkeeping is removed

A `zombie` is a terminated process whose final status has not yet been collected.
An `orphan` is a child whose original parent has disappeared first.
On UNIX-like systems, orphans are typically reparented so someone can still collect status later.

Concretely, this “someone” is usually `init` (PID 1):
the kernel creates `init` at boot time, and it sits at the root of the process tree.
When a parent dies before its child, the kernel reassigns the child’s parent pointer to `init` so there is always a live process responsible for eventual status collection and cleanup protocol completion.

**Invariants**

- Exit status may need to outlive execution itself.
- Parent-child relationships matter to cleanup.
- A zombie is not still computing; it is lingering bookkeeping.
- An orphan is not necessarily dead; it has only lost its original parent.

**What Breaks If This Fails**

- If exit status vanishes too early, parents cannot observe child outcome correctly.
- If dead entries never clear, process-table resources leak.
- If orphan handling is absent, cleanup responsibility becomes ambiguous.

**One Trace: exit to final cleanup**

Termination is a lifecycle protocol, not an instant erase.
The key structural reason for the “zombie” phase is that the parent may need to observe outcome (exit status, resource usage) after the child has already stopped executing.
When you cover the table, identify what remains after exit (a small kernel record) and what must already be gone (CPU execution, most resources).

| Step | Process State | Kernel Meaning |
| --- | --- | --- |
| execution ends | child stops running | status becomes final |
| zombie phase | not executing, table entry retained | parent may still collect outcome |
| parent waits | status retrieved | final cleanup authorized |
| removal | table entry deleted | lifecycle complete |

This is why zombies consume process-table space despite doing no computation: the kernel is preserving observability, not execution.
The final deletion boundary is `wait`, which turns process cleanup into an explicit, ordered protocol step instead of an implicit side effect of “stopping.”

**Code Bridge**

- Look for where exit status is stored, where wait consumes it, and where the final table entry is removed.

**Drills (With Answers)**

1. **Q:** Why is a zombie not just “a dead process” in the most naive sense?
**A:** A zombie is dead in the sense that it no longer executes and cannot be scheduled. But it still has a kernel table entry because its exit status (and possibly accounting info) must remain observable to the parent. It is “lingering bookkeeping,” not “lingering computation,” and that distinction matters for resource leaks and lifecycle correctness.

2. **Q:** Why are zombie and orphan different failure or lifecycle outcomes?
**A:** Zombie means “child terminated first; parent has not reaped status yet.” Orphan means “parent disappeared first; child may still be running or may later exit.” They have different fixes and invariants: zombies are cleaned by `wait` (or reaping), while orphans require reassignment of cleanup responsibility (reparenting) so someone can eventually observe and reap status.

3. **Q:** Why does final cleanup often happen after execution has already ended?
**A:** Because cleanup is coordinated with observation. The kernel cannot discard all traces if the parent has a right to collect outcome, and the parent may not call `wait` immediately. The OS therefore splits “stop executing” from “reclaim the final record,” ensuring both correctness (status observable) and bounded resource reclamation (eventually reaped).

![Supplement: exit preserves status via a zombie phase until wait authorizes final cleanup](../graphviz/chapter3_graphviz/fig_3_8_exit_wait_trace.svg)

![Supplement: process creation and termination form one lifecycle, including zombies and orphans](../graphviz/chapter3_graphviz/fig_3_5_process_lifecycle_relations.svg)

![Supplement: when a parent dies, the kernel reparents the child to init (PID 1) so cleanup responsibility remains well-defined](../graphviz/chapter3_graphviz/fig_3_9_init_reparenting.svg)

### 3.9 IPC Exists Because Isolation Alone Is Not Enough

**Problem**

Many useful systems are built from cooperating processes rather than one giant execution context.

**Mechanism**

Processes may cooperate for:

- information sharing
- speedup
- modularity
- convenience

That requires `interprocess communication (IPC)`.
The two foundational models are:

- `shared memory`
- `message passing`

The producer-consumer pattern matters here because it shows that shared data without synchronization or protocol is not enough.

**Invariants**

- Cooperation requires a disciplined communication mechanism.
- Shared data also requires agreement on timing, ownership, and interpretation.
- Communication is about preserving structured meaning, not only byte movement.

**What Breaks If This Fails**

- If decomposition occurs without IPC, modular structure becomes behaviorally useless.
- If processes share data without protocol, races and inconsistent interpretation appear.
- If message boundaries are unclear, coordination logic becomes fragile.

**Code Bridge**

- In OS labs, identify where the kernel sets up the communication channel and where user processes must enforce the higher-level protocol themselves.

**Drills (With Answers)**

1. **Q:** Why is IPC necessary even on one machine?
**A:** Because processes are isolated by design. If you split a system into multiple processes for modularity, fault containment, or privilege separation, those processes still need to exchange information and coordinate progress. IPC is the disciplined way to cooperate without dissolving isolation by “just sharing everything.”

2. **Q:** Why is the producer-consumer problem about coordination as much as data storage?
**A:** Because the correctness hazard is not “where do we put bytes,” but “when is an item valid,” “who owns the slot,” and “what ordering and capacity guarantees exist.” Without a protocol, the consumer can read uninitialized/stale data or miss updates, and the producer can overwrite unread items. Producer-consumer is the minimal model that forces you to reason about visibility, atomicity, and bounded capacity.

3. **Q:** Why is modularity one of the strongest reasons to allow process cooperation?
**A:** Modular decomposition lets you isolate failures, restart components, and limit privilege (a service can run with only the rights it needs). IPC is the mechanism that lets those separately protected components coordinate without erasing their boundaries. Without IPC, modularity gives you isolated programs rather than cooperating system components.

### 3.10 Shared Memory And Message Passing Move Complexity To Different Places

**Problem**

Once processes cooperate, the main design question becomes where the complexity lives: in the kernel-mediated boundary or in shared-state discipline between peers.

**Mechanism**

In `shared memory`, the kernel establishes and protects the shared region.
After setup, the communicating processes exchange data through loads and stores to that region, and user-space synchronization becomes responsible for correctness.

In `message passing`, the OS or runtime remains involved in each send and receive operation.
That keeps the communication boundary explicit, but it adds mediation cost to each exchange.

The responsibility split is:

`shared memory -> the kernel sets up the region once; the processes own repeated synchronization and ordering`

`message passing -> the system mediates each exchange; the channel semantics stay explicit at send/receive time`

**Invariants**

- Shared memory reduces repeated kernel mediation but does not remove the need for coordination.
- Message passing makes communication events explicit.
- Neither model is universally superior; the best choice depends on locality, performance goals, and synchronization complexity.

**What Breaks If This Fails**

- If shared memory is treated as free communication, races and stale assumptions appear.
- If message passing is treated as only a distributed-systems mechanism, local IPC design becomes harder to read.
- If the location of coordination work is ignored, performance tradeoffs are misunderstood.

**One Trace: producer-consumer via shared memory**

Shared memory makes the data path cheap, but it makes the protocol path your responsibility.
The important step is `publish`: you must establish an ordering rule that makes “data is in the slot” become true *before* “the slot is marked valid” becomes visible to the consumer (and vice versa for release).
When you cover this table, say what synchronization primitive you would use to enforce those orderings (mutex+cond, semaphores, atomics), and what breaks if `publish` is not atomic with respect to the consumer's checks.

| Step | Producer | Shared Buffer | Consumer |
| --- | --- | --- | --- |
| produce | creates item | empty or has space | waiting or doing other work |
| publish | writes item and updates shared protocol state | now contains valid data | not yet consumed |
| consume | idle or producing other data | holds readable item | reads item only when protocol says valid |
| release | may continue producing | slot becomes reusable | signals or records consumption |

A fast mental check after reproducing this trace is to name the invariant you fear most: overwriting unread data, consuming unpublished data, or losing a wakeup.
Shared memory buys performance by removing per-exchange mediation, so you must “pay back” that missing mediation with explicit ordering and synchronization rules.

**Code Bridge**

- In shared-memory examples, identify which parts the kernel set up once and which parts the processes must coordinate repeatedly.

**Drills (With Answers)**

1. **Q:** Why can shared memory be faster and still be harder to get right?
**A:** It is faster because communication becomes loads/stores after setup, avoiding per-exchange syscalls and copies. It is harder because correctness now depends on synchronization and memory-ordering discipline between peers: you must prevent races, preserve invariants, and ensure visibility ordering across cores. The kernel stops mediating each exchange, so the application must supply the protocol.

2. **Q:** Why does message passing shift some complexity back into the OS or runtime?
**A:** Because each send/receive becomes an explicit mediated event: the system may buffer, block, queue, route, and wake threads. That adds overhead, but it can simplify application correctness because there is less shared mutable state and the communication boundary is explicit. Complexity moves from “shared memory discipline” to “channel semantics and scheduling behavior.”

3. **Q:** Where does synchronization responsibility live in each model?
**A:** In shared memory, most synchronization responsibility lives in the communicating processes (locks/atomics/conditions) because the kernel is not involved per exchange. In message passing, some synchronization is embedded in the mechanism (blocking send/receive, buffering capacity, ordered delivery), but higher-level protocol responsibility still remains in user space (what a message means, when to retry, how to handle timeouts/failures).

### 3.11 Naming, Blocking, And Buffering Determine How Message Passing Behaves

**Problem**

Message passing is not one single mechanism.
Its behavior depends on who names whom, whether calls block, and how much buffering exists.

**Mechanism**

Message passing can vary along several axes:

- `direct` versus `indirect` communication
- `blocking` versus `nonblocking` send and receive
- `zero-capacity`, `bounded-capacity`, or `unbounded-capacity` channels

These choices determine whether communication behaves more like rendezvous, queued delivery, or asynchronous event exchange.

**Invariants**

- Naming rules determine how tightly sender and receiver are coupled.
- Blocking rules determine whether control waits for communication success immediately.
- Buffer capacity determines when backpressure appears.

**What Breaks If This Fails**

- If direct and indirect communication are confused, addressing and ownership assumptions become wrong.
- If blocking semantics are ignored, liveness bugs become likely.
- If buffering assumptions are wrong, senders or receivers may stall unexpectedly.

**Code Bridge**

- In any IPC API, ask three questions first: who names the peer, who can block, and where can messages accumulate?

**Drills (With Answers)**

1. **Q:** Why does a zero-capacity channel behave like a rendezvous?
**A:** With zero buffering, a send cannot “deposit” a message and leave. The send must wait until a receiver is present to take the message immediately, which couples the two parties in time. This is a synchronization event as much as a data transfer.

2. **Q:** Why is indirect communication structurally looser than direct communication?
**A:** Direct communication names the peer explicitly, coupling sender and receiver identities. Indirect communication targets a mailbox/port/channel, so senders and receivers can change independently as long as they agree on the mailbox identity and semantics. This decoupling is powerful, but it also raises questions about ownership, access control, and message routing policy.

3. **Q:** Why does bounded buffering create backpressure?
**A:** Because when the buffer fills, senders must either block, fail, or drop messages. That pressure forces producers to slow down or coordinate with consumers, preventing unbounded memory growth. Bounded buffering turns “capacity” into a correctness and performance property, not just a storage detail.

### 3.12 Client-Server, Sockets, RPC, And Pipes Extend IPC Across Larger Boundaries

**Problem**

Once communication crosses subsystem or machine boundaries, the communicating processes still need explicit rules for naming, ordering, failure handling, and interpretation rather than raw byte exchange alone.

**Mechanism**

`Sockets` expose communication endpoints.
`RPC` raises the abstraction level so communication resembles a procedure call.
`Pipes` support ordered byte-stream communication, often for related local processes.

These mechanisms are all IPC forms or IPC-derived abstraction layers.
The main difference is the boundary they cross and how much protocol structure they provide above raw transport.

The difficult issues remain the same:

- naming
- data representation
- synchronization
- failure handling
- protection

**Invariants**

- Local and remote communication still require structured agreement on meaning.
- RPC depends on packaging and reconstructing data correctly across endpoints.
- Pipes, sockets, and RPC differ in abstraction level more than in fundamental purpose.

**What Breaks If This Fails**

- If sockets are treated as only networking trivia, the underlying IPC model is obscured.
- If RPC is treated as magic, marshalling and failure modes become invisible.
- If pipes are treated as equivalent to all other IPC, their ordered-stream assumptions get overgeneralized.

**One Trace: request/reply over message-oriented IPC**

This is the generic client-server coordination pattern.
The channel/kernel/runtime mediates delivery (and often buffering and wakeups), while the server supplies the service semantics; the reply makes the request meaningful to the caller as an atomic-looking operation.
When you cover the table, explicitly state where a client could block (on send, on reply), where buffering could hide latency, and what ordering assumptions the server relies on to interpret requests correctly.

| Step | Client | Kernel / Runtime | Server |
| --- | --- | --- | --- |
| request formed | prepares operation and args | channel exists or is created | waiting |
| send | issues send or call | mediates delivery | receives request |
| service | waits for reply or continues | may buffer, schedule, or route | performs work |
| reply | receives result | returns message or reply | sends outcome |

Treat this as a protocol with explicit blocking points and buffering policies, not as “bytes moved.”
If you cannot point to where correlation (which reply matches which request) and failure/timeout handling belong, you will build systems that are fast in the happy path but brittle in the real world.

**Code Bridge**

- In sockets or RPC code, ask where naming ends, where marshalling begins, and where failure or timeout becomes visible to the caller.

**Drills (With Answers)**

1. **Q:** Why is RPC conceptually an IPC mechanism with a higher-level interface?
**A:** RPC is still request/reply message passing, but it hides message framing behind a procedure-call illusion. It adds marshaling/unmarshaling, naming/binding, and failure/timeout handling conventions. The core IPC problem remains: you are coordinating two execution contexts across a boundary while preserving meaning, order, and progress.

2. **Q:** Why do sockets still need a protocol above raw bytes?
**A:** A socket gives you a byte stream (or datagrams), not structured meaning. Applications must define framing, message boundaries (if needed), request identifiers, and semantic contracts (what a sequence of bytes represents). Without a protocol, you can transmit bytes successfully and still have a broken system because the receiver cannot interpret, order, or validate them consistently.

3. **Q:** Why is the local-versus-remote distinction less important than many students first assume?
**A:** Remote communication adds latency and partial failure, but the conceptual problems begin locally: naming, buffering, blocking, ordering, backpressure, and interpretation. If you cannot design correct local IPC, “networking” will not rescue you. RPC and sockets are IPC pushed across a larger boundary; they amplify existing coordination issues rather than replacing them with a new category of problems.

![Supplement: communication models differ mainly in where coordination and mediation live](../graphviz/chapter3_graphviz/fig_3_6_communication_models.svg)

### 3.13 Concrete IPC On POSIX: Shared Memory, Pipes, Sockets

This chapter optimizes for mental models, but Lecture 2 also expects you to recognize a few canonical POSIX shapes.
Treat these as “minimal API traces” that anchor the abstractions in concrete mechanisms.

Why this section exists: the earlier IPC modules explain *models* (shared memory vs message passing), but real systems force you to reason about where the boundary is drawn in actual code.
POSIX mechanisms are not important because you will memorize their signatures; they are important because they embody the same conceptual splits the whole chapter relies on:

- “setup once, then communicate cheaply” (shared memory)
- “stream bytes through a kernel-managed conduit” (pipes)
- “name endpoints and speak a protocol over a transport” (sockets)

If you can explain *why* each mechanism looks the way it does, the API details become learnable rather than arbitrary.

#### 3.13.1 POSIX Shared Memory: `shm_open` + `ftruncate` + `mmap`

Shared memory has two phases:

1. kernel-mediated setup (name a segment, size it, map it)
2. user-space loads/stores plus synchronization (Chapter 5)

In POSIX-style APIs, the setup often looks like:

```c
int shm_fd = shm_open(name, O_CREAT | O_RDWR, 0666);
ftruncate(shm_fd, 4096);
void *addr = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, shm_fd, 0);
```

After `mmap`, the “send/receive” path is just memory reads/writes.
That is why shared memory can be fast and also why it demands correct synchronization discipline.

![Supplement: POSIX shared memory is setup once (open/size/map), then communicate via loads/stores plus synchronization](../graphviz/chapter3_graphviz/fig_3_10_posix_shm_flow.svg)

Interpretation: `shm_open` and `mmap` are not “communication operations” in the same sense as `send/receive`.
They establish a shared *place* where communication can happen.
After that, the OS is no longer mediating each exchange, which is why shared memory shifts the burden onto the program: you must define what each byte means, when it is valid, and how readers and writers synchronize visibility.
Chapter 5 exists largely to teach how to do that without races and without burning CPU.

#### 3.13.2 Pipes: Ordinary vs Named

Pipes are an IPC mechanism optimized for *ordered byte-stream* communication.

- `ordinary pipe` (anonymous): typically used between parent/child; unidirectional; created with `pipe()` and inherited across `fork()`
- `named pipe` (FIFO): has a filesystem name; can be used without a parent-child relationship; often treated as bidirectional at the “who can open it” level even though each open endpoint is still read-only or write-only

The ordinary-pipe control pattern is:

```c
int fd[2];
pipe(fd);
pid_t pid = fork();
if (pid > 0) {           // parent: producer
  close(fd[0]);          // close read end
  write(fd[1], msg, len);
  close(fd[1]);
} else {                 // child: consumer
  close(fd[1]);          // close write end
  read(fd[0], buf, n);
  close(fd[0]);
}
```

![Supplement: ordinary pipes are typically parent-child and unidirectional; named pipes decouple processes via a filesystem name](../graphviz/chapter3_graphviz/fig_3_11_pipes_types.svg)

Interpretation: the key semantic feature of pipes is not “they pass bytes,” but “they impose an ordering and a blocking rule.”
A read from a pipe can block until data exists; a write can block until buffer space exists; and end-of-file is expressed structurally by **closing** the write end so readers can conclude “no more bytes will ever arrive.”
That is why the `close()` calls in the sketch are not cleanup trivia; they are part of the communication protocol.

**Worked Example: Why `ls | wc -l` Is A Process + Pipe + Descriptor-Rewiring Story**

Shell pipelines look like “one command feeds another,” but the OS truth is: *two processes* cooperate through a pipe whose ends are installed into standard streams.
A minimal trace (names vary across OSes, but the structure is stable):

1. The shell creates a pipe: two file descriptors exist, one for reading and one for writing.
2. The shell forks twice to create two children.
3. In the left child (`ls`), the shell duplicates the pipe write end onto `stdout` (fd 1), then closes both original pipe fds, then `exec`s `ls`.
4. In the right child (`wc -l`), the shell duplicates the pipe read end onto `stdin` (fd 0), then closes both original pipe fds, then `exec`s `wc`.
5. The parent closes its copies of the pipe fds, so it does not accidentally keep the pipe alive.

Now the programs are ordinary user-space code:
`ls` writes to fd 1, `wc` reads from fd 0.
The only reason “fd 1 means pipe” is because the parent rewired the descriptor table before `exec`.

![Supplement: a shell pipeline is pipe() + fork() + dup2() + close() + exec(); EOF depends on closing the write end](../graphviz/chapter3_graphviz/fig_3_13_pipe_pipeline_trace.svg)

Misconception to avoid: “pipes are bidirectional because data can flow between processes.”
An ordinary pipe is fundamentally one-directional at the byte-stream level; full-duplex patterns use two pipes (or a socketpair) for two directions.

#### 3.13.3 Sockets: Addressing As `IP:port` and Common Port Conventions

A socket endpoint is commonly named as `IP:port`.

- Ports below `1024` are traditionally “well-known” ports used by standard services.
- `127.0.0.1` is the loopback address: it refers to “this same machine.”
- The transport flavor changes semantics: TCP (connection-oriented stream) versus UDP (connectionless datagrams), plus multicast patterns.

The “client shape” for a TCP socket typically looks like:

```c
int sockfd = socket(AF_INET, SOCK_STREAM, 0);
connect(sockfd, (struct sockaddr *)&addr, sizeof(addr));
read(sockfd, buf, n);
close(sockfd);
```

![Supplement: sockets are named endpoints (IP:port); loopback and well-known ports are conventions that shape real systems](../graphviz/chapter3_graphviz/fig_3_12_socket_addressing.svg)

Interpretation: sockets add two things that pipes do not emphasize:

1. **naming and binding**: “which peer do I mean?” becomes explicit as an address/port
2. **protocol**: once you have a byte stream (TCP) or datagrams (UDP), you still must define message boundaries, requests vs replies, and failure handling

The reason sockets and pipes both show up in this chapter is that they solve the same core problem (structured communication between isolated execution contexts), but they sit on different boundaries: pipes are usually local and ancestry-friendly; sockets generalize the naming and can cross machines.

## 4. Canonical Traces To Reproduce From Memory

Do not merely read these.
Cover the tables and reproduce the lifecycle or handoff from memory.

### 4.1 Ready To Running To Waiting To Ready

This is the minimal scheduler-visible lifecycle loop.
When you reproduce it, say what *event* causes each transition and what it implies about future progress: `ready` competes for CPU, `running` consumes CPU, `waiting` cannot progress until a specific event occurs.

| Step | State | Cause |
| --- | --- | --- |
| admitted | `ready` | process is eligible for CPU service |
| dispatched | `running` | scheduler selects it |
| blocks | `waiting` | needs I/O or event |
| completion | `ready` | event occurs and wakeup happens |

Say the *cause* out loud: dispatch, block, completion.
If you can’t name the event, you’ll confuse “waiting” with “not scheduled,” and you will misreason about hangs, idle CPUs, and why wakeups exist as explicit kernel mechanisms.

### 4.2 Timer-Driven Preemption And Context Switch

Reproduce this as a protocol, not as a “jump.”
The kernel regains control, saves outgoing state so it is resumable, chooses among runnable contexts, and restores the chosen one so the decision becomes execution.

| Step | Outgoing Process | Kernel | Incoming Process |
| --- | --- | --- | --- |
| before timeout | running | timer armed | ready |
| interrupt | interrupted | regains control | still waiting in ready set |
| save and choose | stopped temporarily | stores outgoing context and selects next | chosen |
| restore | not running | loads chosen context | now running |

Rehearse the order as an invariant: regain control -> save -> choose -> restore -> return.
The most common mistake is imagining a context switch as “just jump to another program”; in reality it is a state protocol plus kernel bookkeeping that preserves resumability and fairness.

### 4.3 Fork Then Exec Style Split

Say out loud what changes at each stage.
After creation, there is a new identity and inherited bindings; after `exec`, the program image changes while the identity (the process container) persists.

| Step | Parent | Child |
| --- | --- | --- |
| before split | existing execution | absent |
| after creation | continues or waits | begins with inherited execution context |
| after exec | may remain same program | image replaced with new program |

The two-phase story is the mastery point: inheritance first, then image replacement.
Practice naming one inherited binding (e.g., file descriptors) and one replaced component (code/data image) every time you reproduce this trace.

### 4.4 Exit To Zombie To Wait To Cleanup

This trace exists to prove that “done executing” and “done existing” are different.
The zombie phase is the record that allows the parent to observe outcome; `wait` is the authorization to remove that final record.

| Step | Child | Parent | Kernel |
| --- | --- | --- | --- |
| exit | execution ends | may still be running | status preserved |
| zombie phase | not executing | has not waited yet | table entry retained |
| wait | inactive | collects status | authorizes cleanup |
| cleanup | fully removed | receives outcome | bookkeeping ends |

When you reproduce this, explicitly state why the zombie exists (status/accounting observability) and what event ends it (`wait`).
That turns “zombie” from folklore into a concrete protocol step.

### 4.5 Shared-Memory Producer / Consumer Coordination

When you reproduce this trace, emphasize the protocol state, not just the buffer.
The buffer being in shared memory does not make it safe; correctness depends on “publish before consume” ordering and on preventing overwrite of unread data.

| Step | Producer | Buffer | Consumer |
| --- | --- | --- | --- |
| create item | ready to publish | has free slot | not yet reading |
| publish | writes and updates protocol state | contains valid data | can now consume |
| consume | may continue or wait | item removed or slot freed | reads only when valid |

Your recitation should mention the ordering constraint: publish-before-visible and release-after-consume.
If you can name a concrete primitive that enforces it (mutex+cond, semaphores, atomics with fences), you are reasoning about mechanisms rather than only repeating a pattern.

### 4.6 Message-Passing Request / Reply

This is the smallest client-server message pattern.
Track where buffering and blocking can occur, and where ordering assumptions live (channel guarantees vs server protocol).

| Step | Sender | Channel / Kernel | Receiver |
| --- | --- | --- | --- |
| request | forms message | idle or ready | waiting |
| send | issues operation | buffers or routes | not yet handling |
| delivery | waiting or continuing | makes message visible | receives |
| reply | waits or receives response | routes result | returns outcome |

Here the key variable is channel semantics: buffered versus rendezvous, blocking versus nonblocking, and what ordering guarantee the channel actually provides.
Practice stating one deadlock scenario under blocking rendezvous and one overload scenario under bounded buffering; those are the real failure modes behind the abstraction.

## 5. Key Questions (Answered)

1. **Q:** Why is a process conceptually closer to a resumable contract with the kernel than to a file on disk?
**A:** Because the defining feature of a process is that the kernel agrees to treat it as a schedulable, interruptible, and resumable computation with owned resources. That “contract” includes identity, protection, scheduling eligibility, and cleanup obligations. A file on disk is passive; it does not contain the live execution context or resource bindings that must survive preemption and blocking.

2. **Q:** Why do process states describe future possibilities rather than past history?
**A:** Because the state is used to decide what the kernel is allowed to do next. `Ready` means “can run if scheduled,” `waiting` means “cannot run until an event happens,” and `terminated` means “should not run again.” Past history can influence *policy* (e.g., priority), but state exists to encode immediate admissible transitions for scheduling and wakeup correctness.

3. **Q:** Why is the PCB the kernel's authoritative record instead of just a convenient cache?
**A:** Because after preemption, the CPU register file no longer contains the process’s state, and user memory may not be trusted or even resident. The kernel must have a canonical, protected record to resume the exact computation and to enforce ownership and protection consistently. If the PCB were “just a cache,” correctness would be optional; in reality, resumability and cleanup depend on it.

4. **Q:** Why does the scheduler need queues that distinguish CPU scarcity from device scarcity?
**A:** Because “ready to compete for CPU” and “blocked on an external event” are fundamentally different scarcity conditions. CPU scarcity is resolved by selecting among runnable work; device scarcity is resolved by waiting for completion and waking the right blocked work. Mixing them destroys meaning: you either waste CPU scheduling blocked work or you lose wakeup structure that preserves liveness.

5. **Q:** Why is a context switch best understood as a protocol rather than as a single event?
**A:** Because it has an order that must be correct: save outgoing state before it is clobbered, make a scheduling decision based on truthful runnable state, then restore incoming state consistently. The protocol also includes bookkeeping updates (state fields, queue membership, accounting) that must remain atomic with respect to interrupts and concurrent CPUs. Treating it as “one event” hides the invariants that prevent corruption and lost wakeups.

6. **Q:** Why does `fork` plus `exec` teach more about process structure than either call in isolation?
**A:** Together they expose the two major axes of process structure: identity/inheritance (process container) and program image (what code/data is executed). `fork` teaches what it means to create a new container with inherited bindings; `exec` teaches that the container can persist while the program image is replaced. This separation is the conceptual core: “create a process” and “choose the program” are different problems.

7. **Q:** Why can a terminated process still need a table entry?
**A:** Because outcome is an observable part of the lifecycle. The parent may need exit status and accounting information after the child has stopped executing, and the kernel must preserve that information until it is collected. The “zombie” table entry is the minimal record that preserves correctness without preserving execution.

8. **Q:** Why are zombie and orphan fundamentally different lifecycle outcomes?
**A:** Zombie is “child ended; parent hasn’t reaped status,” so the fix is to collect status (`wait`) and reclaim the final record. Orphan is “parent ended first,” so the fix is to reassign cleanup responsibility (reparenting) while the child may still execute. They arise from opposite orderings of parent/child termination and therefore imply different invariants and recovery actions.

9. **Q:** Why is IPC about preserving meaning and order rather than just transferring bytes?
**A:** Because coordination fails even when bytes move perfectly if peers disagree about interpretation, boundaries, or ordering. IPC must preserve protocol meaning: which operation is requested, which reply corresponds, what ordering is guaranteed, and what happens on delay or failure. “Bytes delivered” is a transport property; “system behaves correctly” requires semantic agreement.

10. **Q:** Why does shared memory reduce some kernel work while increasing application responsibility?
**A:** After the kernel creates the shared region, the processes exchange data through loads and stores to that region instead of through a mediated send/receive on every handoff. That avoids per-message syscalls and can be very fast. But because the kernel no longer validates each exchange, the application must enforce synchronization, visibility ordering, and invariants like “do not overwrite unread data.” Less kernel mediation means more protocol responsibility in user space.

11. **Q:** Why do blocking semantics and buffering rules materially change IPC behavior?
**A:** They determine liveness and backpressure. A zero-capacity channel turns communication into a rendezvous, forcing timing coupling; bounded buffers create backpressure when full; nonblocking operations shift coordination to polling/retry logic. These rules change not only performance but also which bugs are possible (deadlocks, starvation, dropped messages).

12. **Q:** Why are sockets and RPC best understood as IPC across a larger boundary rather than as unrelated networking trivia?
**A:** Because they solve the same core problem as local IPC: structured communication between isolated execution contexts. The larger boundary adds latency, addressing, and partial failure, but the fundamental questions remain: naming, buffering, ordering, interpretation, and progress. Seeing sockets/RPC as IPC helps you reason uniformly about coordination rather than memorizing “networking features.”

## 6. Suggested Bridge Into Real Kernels

If you later study a teaching kernel or Linux-like codebase, a good Chapter 3 reading order is:

1. process descriptor / PCB representation
2. scheduler loop and ready-queue logic
3. sleep and wakeup paths
4. timer interrupt to context-switch handoff
5. fork/exec and exit/wait paths
6. local IPC or pipe implementation

Conceptual anchors to look for:

- where process identity is stored
- where runnable versus blocked state is encoded
- where save and restore happen during a switch
- where exit status survives after execution ends
- where IPC setup is done by the kernel and where higher-level protocol is left to processes

If you later study browsers, runtimes, or servers, ask the same Chapter 3 questions again.
The examples get more complex.
The process-control problems do not.

## 7. How To Use This File

If you are short on time:

- Read `## 2. Mental Models To Know Cold` once.
- Reproduce the traces in `## 4. Canonical Traces To Reproduce From Memory`.

Use this file when:

- you want Chapter 3 to read as kernel management of live state rather than as a vocabulary review
- you want to reason about process lifecycle, scheduling, and IPC without hiding behind API trivia
- you want a mental model strong enough to read process or scheduler code later

Read it slowly.
Reproduce the traces from memory.
If the chapter feels easy, try explaining one lifecycle bug, one scheduling bug, and one IPC bug purely in terms of state, ownership, and coordination.

---

# Chapter 4 Threads and Concurrency Mastery

Source: Chapter 4 of `../textbook.pdf` (Operating System Concepts, 9th ed.).

This file is the mastery note for Chapter 4.
It treats threading as a control-boundary and scheduling design choice, not as a language feature.

If Chapter 3 taught you how the kernel tracks *one* execution container, Chapter 4 teaches how the kernel and runtime track *many* execution paths inside that container, and how multicore turns “concurrency” into real parallel hazards.

## 1. What This File Optimizes For

The goal is not to memorize thread API calls.
The goal is to be able to do the following without guessing:

- Distinguish what is shared between threads and what remains per-thread state.
- Predict when “one thread blocks” implies “the whole process blocks” (and when it does not).
- Explain why multicore turns concurrency into real parallel correctness hazards and performance cliffs.
- Choose when to create threads explicitly versus using implicit threading (pools, tasks, fork-join).
- Compare M:1, 1:1, and M:N threading models by blocking behavior, overhead, and achievable parallelism.
- Explain why fork/exec, signals, and cancellation become lifecycle and protocol problems in multithreaded programs.

For Chapter 4, mastery means:

- you can trace what happens when a thread blocks, cancels, exits, or joins
- you can predict how a threading model changes parallelism and failure modes
- you can reason about speedup limits and performance cliffs on multicore
- you can connect the abstractions to real scheduler and runtime code later

## 2. Mental Models To Know Cold

### 2.1 A Thread Is a Schedulable Execution Context

A thread is the schedulable control-flow object:
program counter, registers, stack, and the scheduling identity needed to run.

A process is the resource-owning container:
address space, open files, and other resources that persist across context switches.

Chapter 4 depends on keeping those responsibilities separate: the process owns resources, while each thread carries one execution path through them.

### 2.2 Concurrency Is Structure; Parallelism Is Physics

Concurrency: you *structure* the program so multiple activities can make progress.
Parallelism: the machine *actually runs* multiple activities at the same time.

You can have concurrency without parallelism (single core).
You cannot have safe parallelism without correct concurrency structure (multicore).

Related terms from Lecture 2 that are easy to mix up:

- `multiprocessing`: the machine has multiple CPUs/cores
- `multiprogramming`: the OS keeps multiple jobs/processes in memory so the CPU stays busy
- `multithreading`: one process has multiple threads of execution

### 2.3 The Threading Model Is Mostly About What Blocks

If the kernel schedules only *one* kernel execution entity for the whole process, then a blocking system call blocks *everyone* in the process.
If the kernel schedules multiple kernel threads, then one thread can block while others keep running.

Most tradeoffs between user-level threads, kernel threads, and the many-to-one / one-to-one / many-to-many models reduce to one boundary question: which execution entities can the kernel see, schedule, block, and wake independently?

### 2.4 “More Threads” Is Not Automatically “More Speed”

Threads create two new costs:

- coordination cost: locks, atomic operations, ordering constraints
- runtime cost: creation, context switches, cache effects, scheduling overhead

On multicore, a “correct” program can still become slow because contention forces threads to wait on each other.

### 2.5 Implicit Threading Is Admission Control

Explicit threading is letting the programmer create execution contexts directly.
Implicit threading is the system providing a higher-level unit of work (tasks) and controlling how many threads actually run at once.

Thread pools, fork-join frameworks, OpenMP, and GCD exist because unbounded thread creation overwhelms memory, the scheduler, and shared resources.

## 3. Mastery Modules

### 3.1 Process vs Thread: Resource Container vs Execution Context

**Problem**

A modern program needs multiple flows of control (UI + I/O + background work, multiple client requests, pipelines).
Spawning a full process per activity is expensive and makes sharing state awkward.

**Mechanism**

A `process` is the resource-owning container:

- address space (code, data, heap, mapped files)
- open files and sockets
- permissions and identities

A `thread` is a schedulable execution context inside that container:

- program counter + registers
- stack (per-thread call frames)
- thread-local storage

Threads share the process’s address space and resources by default.
That sharing is the performance advantage and the correctness hazard.

**Invariants**

- A process may have multiple threads, but one address space.
- Threads share memory; therefore, one thread's writes can become another thread's observations and must be treated as communication.
- Per-thread stacks must not overlap; shared heap data must be synchronized by design.

**What Breaks If This Fails**

- If you assume stacks are shared, you mis-explain correctness (“how did my local variable change?”).
- If you assume heap data is private, you create races by accident.
- If you assume files are per-thread, you mis-handle I/O ordering and close semantics.

**Code Bridge**

- In POSIX, identify what `pthread_create` must allocate (stack + thread metadata) versus what already exists (address space).
- In Linux-like kernels, notice that “threads” often look like “tasks that share an address space.”

**Drills (With Answers)**

1. **Q:** Name three kinds of state that are per-thread and three that are shared across threads.
**A:** Per-thread examples: (1) registers/PC (the live control state), (2) the stack (call frames and locals), (3) TLS and per-thread scheduler identity/state. Shared examples: (1) the address space contents (heap/global data), (2) process-wide open file table/descriptor namespace, (3) process credentials and many kernel-owned resources attached to the process container. The exact list varies by OS, but “control flow state is per-thread; ownership/protection state is mostly per-process” is the invariant.

2. **Q:** Why does “shared address space” make communication cheap but correctness hard?
**A:** Cheap because threads can exchange data through plain loads and stores with no per-message kernel mediation or copying. Hard because those same memory operations can interleave across threads: one thread can observe another thread's partial update, overwrite a value, or read data before the required ordering is established. Shared memory removes an explicit boundary, so the program must create its own correctness boundary with locks, atomics, and protocols.

3. **Q:** If one thread calls `close(fd)`, what must other threads assume about that file descriptor?
**A:** They must assume it can become invalid immediately and can even be *reused* for a different file/socket shortly after. Continuing to use it without coordination can cause EBADF at best and incorrect I/O to the wrong underlying object at worst (if the number is reused). Correct designs either synchronize close/use, duplicate file descriptors for independent lifetimes, or use higher-level ownership rules to prevent “use-after-close.”

In many OS texts and kernels, the per-thread kernel bookkeeping is described as a `thread control block (TCB)`:
the record that stores each thread’s private execution context (PC/registers/stack pointer + scheduling metadata).
The key “Lecture 2” mental split is simply: shared process container state versus private per-thread execution state.

![Supplement: threads share process resources but keep distinct execution context](../graphviz/chapter4_graphviz/fig_4_1_process_threads_container.svg)

![Supplement: thread state divides into process-shared state and per-thread state (TCB)](../graphviz/chapter4_graphviz/fig_4_4_thread_shared_private_state.svg)

### 3.1.1 Why Thread Switching Can Be Cheaper Than Process Switching

Lecture 2 makes a concrete performance claim: switching between two threads in the *same* process does not require “memory-management work” in the same way a process switch does.
Here is the first-principles reason.

**Mechanism**

Every context switch must save and restore a schedulable execution context (PC/registers/stack pointers).
But a **process switch** typically also changes the *address space* (the page-table root or equivalent), which implies:

- the meaning of virtual addresses changes
- cached translations (TLB entries) may be invalidated or require tagging rules
- caches and memory locality may suffer because the working set shifts to a different address space

A **thread switch within one process** still switches registers/stack, but it usually keeps the same address space, so the expensive “change what addresses mean” work is reduced.

![Supplement: thread switch vs process switch differs mainly by whether the address space/page-table root changes (TLB/cache effects)](../graphviz/chapter4_graphviz/fig_4_7_thread_vs_process_switch_cost.svg)

### 3.2 Why Threads Exist (And What They Cost)

#### Why This Section Exists

Chapter 3 made "one process" feel like a coherent unit: one container that can be created, scheduled, blocked, and cleaned up. The moment you build real applications, that unit is too coarse. A single process often needs multiple independent flows of control:

- a UI loop that must stay responsive,
- background I/O and parsing,
- multiple client requests in a server,
- timeouts, retries, and periodic maintenance work.

If you attempt to express all of that as one sequential control flow, you either waste time (waiting for I/O) or you write an event-driven program that manually simulates concurrency and becomes difficult to reason about. Threads exist to provide a first-class OS/runtime object for "another flow of control" without forcing you to duplicate the entire process container.

This section exists to make the *trade* explicit: threads buy you cheap sharing and parallelism, but they also turn shared memory into a correctness surface that your program must defend.

#### The Object Being Introduced (A New Place In The Design Where Invariants Can Break)

Threads introduce a new object in your mental model:

- **a shared address space** used by multiple independent instruction streams.

That means memory is no longer just "my program's data." It becomes a communication medium between threads. Any invariant that involves shared data must now hold across *all possible interleavings* of thread steps.

What is fixed:

- The OS/runtime may schedule threads in any order (preemption).
- On multicore, threads may run simultaneously (true parallelism).

What varies:

- which interleaving actually occurs on a given run (timing-dependent),
- and which shared objects are touched by which threads.

The conclusion this licenses is the most important one for a serious student:

Correctness is not "my intended order." Correctness is "every permitted schedule preserves the invariant."

#### Formal Definitions (Interleaving, Data Race, Critical Section)

Definition (interleaving): A particular ordering of the steps of multiple threads. On one core, concurrency means the OS interleaves steps; on many cores, interleavings happen in real time as well.

Definition (data race): Two threads access the same memory location concurrently, at least one access is a write, and there is no synchronization that orders the accesses. Data races produce undefined or unintuitive results because the language/runtime/hardware are not required to provide a coherent "single order" of operations.

Definition (critical section): A region of code that accesses shared state in a way that must not be interleaved with other critical sections on the same state, or the shared invariant can be violated. Critical sections are protected by synchronization mechanisms (locks, atomics, condition variables) introduced in later chapters.

![Supplement: the same code can be correct sequentially and incorrect under interleavings; races are about schedules, not about intent](../graphviz/chapter4_graphviz/fig_4_9_race_interleaving_increment.svg)

#### Boundary Conditions / Assumptions / Failure Modes

Assumptions:

- The scheduler is allowed to preempt at "inconvenient" points, including between any two instructions that are not protected by the kernel or runtime.
- Many operations you think of as "one action" are multi-step at the machine level (for example, `x++` is a read, an add, and a write).

Failure modes:

- lost updates (two increments become one),
- stale reads (one thread never observes another's write in the expected order),
- deadlocks (threads wait in a cycle once you add locks),
- and "Heisenbugs" where debugging output changes timing and hides the issue.

#### Fully Worked Example: The Smallest Lost-Update Race

Shared variable `x = 0`. Two threads each execute `x = x + 1`.

A possible interleaving:

1. T1 reads x (gets 0)
2. T2 reads x (gets 0)
3. T1 writes x (writes 1)
4. T2 writes x (writes 1)

Final value is 1, even though "two increments happened." Nothing supernatural occurred; the increments were not atomic, and there was no synchronization to force ordering. The general pattern is what you should retain: invariants fail when a multi-step update is interleaved with another multi-step update on the same shared state.

#### Misconceptions

Misconception 1: "If I don't see the bug, it isn't there."

- Races are schedule-dependent. A program can be wrong and still appear to work on light load, on one core, or under one timing regime.

Misconception 2: "I/O is the only reason for threads."

- I/O overlap is one motivation, but multicore parallelism and responsiveness are equally fundamental. Threads are the unit the kernel can schedule on multiple CPUs.

#### Connection To Later Material

This section is the conceptual doorway into synchronization:

- Chapter 5 will provide the mechanisms (mutexes, semaphores, monitors) that make critical sections enforceable and give you disciplined ways to avoid races and deadlocks.
- Later scheduling material will explain how the OS's choices amplify or reduce contention and how thread counts interact with run queues and cache locality.

#### Retain / Do Not Confuse

Retain: threads make memory shared by default; shared memory is communication; correctness requires invariants across all interleavings.

Do not confuse: "it usually runs fine" with "it is correct."

**Problem**

Programs want to overlap I/O with computation, stay responsive, and exploit multicore.
A single sequential control flow forces unnecessary waiting.

**Mechanism**

Classic motivations for multithreading:

- `responsiveness`: one thread can keep the UI/reactor alive while another blocks
- `resource sharing`: sharing memory is simpler than IPC for tightly coupled work
- `economy`: threads are typically cheaper than processes (less state to create/switch)
- `scalability`: threads are the unit that can map onto multiple cores

The cost is that shared memory becomes a correctness surface the program must defend.
Adding threads creates more possible interleavings, so the program becomes responsible for preserving invariants across those interleavings.

**Invariants**

- Shared invariants must hold across all possible interleavings, not just the “intended order.”
- Performance and correctness are linked: contention is both a speed problem and a design smell.

**What Breaks If This Fails**

- Races: wrong values, lost updates, stale reads.
- Deadlocks: progress stops because threads wait on each other in a cycle.
- Heisenbugs: timing-sensitive failures that vanish under debugging.

**Code Bridge**

- In a server, identify which data is per-request (safe to keep thread-local) and which data is global (requires synchronization).

**Drills (With Answers)**

1. **Q:** Why can a single bug in a shared invariant produce “rare” failures instead of consistent failures?
**A:** Because the bug is triggered by a specific interleaving, not by deterministic single-thread logic. Most schedules may “accidentally” avoid the harmful ordering, especially on light load or on a single core. As load, core count, or timing changes, the probability of the bad interleaving rises, which is why races often look like “rare, spooky failures.”

2. **Q:** What is one example where responsiveness improves but throughput worsens after adding threads?
**A:** A UI or request handler that spawns background threads can remain responsive, but overall throughput can drop if threads contend on a lock, thrash caches, or spend time context-switching instead of computing. Another classic case is “thread per request” under load: latency for early requests may improve, but as concurrency explodes, the scheduler overhead and memory pressure reduce total completed work per second.

3. **Q:** What is the most common place you accidentally share data in a threaded program?
**A:** Anything that looks “global” or reusable: shared caches, singletons, static variables, shared queues, and shared buffers reused across requests. File descriptors and sockets are also frequently shared implicitly (because they are process-scoped). The failure mode is usually not “I meant to share”; it is “I forgot this object outlives one thread and is touched by another.”

### 3.3 Multicore Programming: Turning Concurrency Into Parallel Work

#### Why This Section Exists

Threads by themselves only give you *the possibility* of concurrent structure. Multicore hardware turns that possibility into a new kind of correctness and performance environment: now two threads can genuinely run at the same time and genuinely contend on shared memory and shared kernel structures.

This section exists for two reasons:

1. to ground speedup expectations (Amdahl's Law is not a slogan; it's a boundary on what is achievable), and
2. to surface the hidden physics of shared-memory machines (caches, coherence traffic, false sharing) that can make a "more parallel" design slower.

#### The Object Being Introduced (Where Time Goes On Multicore)

On multicore, time is spent in several places that single-thread mental models ignore:

- doing useful work (the part you want),
- waiting for locks or queues (contention),
- waiting for memory or coherence (latency and traffic),
- and paying runtime overhead (scheduling, context switching, thread management).

If you want a portable mental model, treat "serial fraction" as:

"everything that is effectively serialized by design, including contended critical sections and communication bottlenecks."

#### Boundary Conditions / Assumptions / Failure Modes

Assumptions:

- Cache coherence exists, but it has a cost: writes must become visible to other cores, and that visibility requires coordination.
- Memory bandwidth is finite; adding cores can saturate it.

Failure modes:

- lock convoying: many threads wait on one lock, causing long tail latency,
- false sharing: threads update different variables that happen to share a cache line, forcing unnecessary coherence traffic,
- and load imbalance: cores idle because work distribution is uneven.

![Supplement: false sharing is a performance bug caused by cache-line granularity, not by semantic sharing](../graphviz/chapter4_graphviz/fig_4_10_false_sharing_cacheline.svg)

#### Misconceptions

Misconception 1: "If the code is parallel, it will scale."

- Parallel structure is necessary but not sufficient. Contention, memory traffic, and imbalance can dominate.

Misconception 2: "Coherence makes shared memory free."

- Coherence makes shared memory *possible*, not free. The cost is paid in invalidations, cache-line bouncing, and sometimes global ordering constraints.

**Problem**

Multicore provides hardware parallelism, but most work is not parallelizable without restructuring.
Even after restructuring, speedup is limited by serial sections and coordination overhead.

**Mechanism**

Two common decompositions:

- `task parallelism`: different tasks run in parallel (request handling, pipeline stages)
- `data parallelism`: the same operation runs over different data partitions

The simplest bound is `Amdahl’s Law`:

If fraction `S` is serial and fraction `1-S` is perfectly parallel, then with `N` cores:

`speedup <= 1 / (S + (1-S)/N)`

The formula describes an ideal upper bound.
Real systems run below that bound because locks, cache misses, queueing, and communication add extra serialized or contended work.

**Invariants**

- Serial sections and contended critical sections cap speedup.
- Work must be balanced; idle cores are wasted parallelism.
- Communication and coordination are work too.

**What Breaks If This Fails**

- If a single lock guards “everything,” multicore becomes “fast waiting.”
- If tasks are unbalanced, one thread becomes the bottleneck and others idle.
- If shared-memory access patterns are poor, cache coherence traffic dominates.

**One Trace: Amdahl bound**

Assume `S = 0.10` (10% serial).

Read this table as a warning about *where* your speedup goes.
The serial fraction (including contended locks, single-threaded subsystems, and unavoidable sequential work) is a hard cap: as `N` grows, the parallel portion shrinks in marginal value and the serial portion dominates.
When you apply this in real systems, treat “serial fraction” as “everything that is effectively serialized by design,” not just one obvious loop.

| Cores N | Ideal bound | Interpretation |
| --- | --- | --- |
| 1 | 1.0x | baseline |
| 2 | `1 / (0.10 + 0.90/2) = 1.82x` | not 2x because serial work remains |
| 4 | `1 / (0.10 + 0.90/4) = 3.08x` | diminishing returns |
| 16 | `1 / (0.10 + 0.90/16) = 6.40x` | even 16 cores cannot exceed 10x |

Use these numbers as a debugging compass, not as a performance guarantee.
If you cannot point to what is acting as “serial fraction” in your system (a lock, a queue, a single-threaded subsystem, I/O serialization), adding cores will mostly add waiting.

**Code Bridge**

- In a real system, find the “serial fraction” by locating shared locks, shared queues, or single-threaded subsystems.

**Drills (With Answers)**

1. **Q:** Why can removing one contended lock outperform adding more cores?
**A:** A contended lock turns large regions of work into an effectively serial section, increasing the serial fraction `S` that caps speedup. Adding cores cannot break a serialization bottleneck; it can only add more threads waiting on it. Removing or narrowing the lock reduces the serialized region, lowers `S`, and can unlock real parallel speedup that additional hardware alone cannot deliver.

2. **Q:** What’s the difference between “parallelizable work exists” and “parallel speedup is achieved”?
**A:** Parallelizable work exists when the algorithm can be decomposed into independent pieces. Speedup is achieved only when the runtime execution actually keeps cores busy with low overhead: balanced work distribution, minimal contention, good locality, and bounded coordination cost. Many programs have parallelizable work on paper but fail to speed up due to synchronization, cache coherence, or imbalance.

3. **Q:** Name one performance cliff that appears only after moving from 1 core to many cores.
**A:** Cache-coherence and contention cliffs. For example, a single shared counter or queue that is fine on one core can become a coherence hot spot on many cores, causing massive cache-line bouncing. False sharing (independent variables on the same cache line) is another classic multicore-only cliff: logic is correct, but performance collapses as cores fight over coherence ownership.

### 3.4 User Threads vs Kernel Threads: Who Schedules What?

#### Why This Section Exists

Once you accept that threads are the schedulable unit of control flow, a design choice appears immediately:

"Are threads *real* entities the kernel schedules, or are they a user-space illusion created by a runtime library?"

This is not an implementation detail. It determines which events can stop one thread without stopping others, whether threads can run on multiple cores at the same time, and who is responsible for saving/restoring state when a thread yields or blocks.

The entire user-vs-kernel thread discussion is about one boundary:

Which execution entities can the kernel see, preempt, block, and wake independently?

![Supplement: kernel visibility determines blocking behavior; if the kernel sees only one entity, a blocking syscall blocks the whole process](../graphviz/chapter4_graphviz/fig_4_11_kernel_visibility_blocking.svg)

#### The Object Being Introduced (Visibility + Blocking Semantics)

The object is the mapping between:

- **user-level threads** (what the program/runtimes think are threads), and
- **kernel schedulable entities** (what the OS can schedule and block).

What is fixed:

- The kernel can only schedule and block what it knows exists.
- A user-space scheduler can only run when the process is running in user mode.

What varies:

- whether a thread switch is a user-space function call (cheap) or a kernel-mediated context switch (more expensive),
- and whether a blocking system call blocks one thread or the entire process.

#### Formal Definitions (User-Level Thread, Kernel Thread)

Definition (user-level thread): A thread implemented and scheduled in user space by a runtime library. The kernel may see only one kernel thread representing the whole process, while the runtime multiplexes many user threads on top of it.

Definition (kernel thread): A schedulable entity the kernel knows about and schedules directly. Kernel threads can be blocked and woken independently by kernel events (I/O completion, timers) and can run simultaneously on multiple cores.

#### Interpretation (What A Blocking Syscall Really Means)

The critical fact is: the kernel does not "block a user thread." It blocks a kernel-visible execution entity. If that entity represents the entire process (M:1), then a blocking syscall stops all user-level threads because the kernel has no idea they exist. If the kernel sees multiple threads (1:1 or M:N), then a blocking syscall can stop only the calling thread while others continue.

This is why the lecture framing "the threading model is mostly about what blocks" is not a slogan. It is literally how the boundary behaves when the process crosses into privileged code.

#### Boundary Conditions / Assumptions / Failure Modes

Assumptions:

- User-level threading requires cooperation: either explicit yields or runtime-managed safe points. If a user thread runs forever without yielding and the kernel sees only one entity, the runtime cannot schedule other user threads.
- Kernel-level threading requires kernel support and per-thread bookkeeping (TCB), so thread creation and switching costs are higher.

Failure modes:

- M:1 can collapse under blocking I/O: one thread blocks and everything stops.
- User-level scheduling can break under multicore: if the kernel sees only one entity, you cannot achieve true parallel execution within one process.

#### Fully Worked Example: Why M:1 Looks Great Until It Touches The Kernel

Consider a process with two user-level threads:

- T1 computes.
- T2 issues a blocking `read()` on a socket.

Under M:1:

1. The kernel schedules one kernel thread for the process.
2. The runtime switches between T1 and T2 in user space quickly.
3. When T2 executes `read()`, the process enters the kernel.
4. The kernel blocks the *kernel thread* waiting for the socket.
5. Now T1 cannot run, because the runtime cannot run while the whole process is blocked in the kernel.

Under 1:1:

1. T1 and T2 are kernel threads.
2. T2 blocks in `read()`; kernel marks T2 waiting.
3. T1 remains runnable and continues.

Same program, different semantics, because the kernel's visibility changed.

#### Misconceptions

Misconception 1: "User threads are always better because switches are cheaper."

- Cheaper switching is real, but if the kernel cannot block/wake threads independently, real workloads that block (I/O, page faults, locks) can suffer catastrophic loss of concurrency.

Misconception 2: "Kernel threads always mean better performance."

- Kernel threads enable parallelism and independent blocking, but they also increase overhead and contention in kernel scheduling structures. The right design depends on workload, core count, and blocking behavior.

#### Connection To Later Material

This section sets up:

- multithreading model comparison (M:1, 1:1, M:N) as boundary placement,
- scheduling and wakeup behavior in later chapters,
- and synchronization correctness (what can be preempted, when, and by whom).

#### Retain / Do Not Confuse

Retain: the kernel schedules kernel-visible entities; user-level threads are an abstraction layered on top.

Do not confuse: "thread exists in my program" with "thread exists to the kernel."

**Problem**

We want many threads, but involving the kernel in every thread operation can be expensive.
If the kernel does not know about threads, the runtime must simulate concurrency.

**Mechanism**

`User-level threads`:
the threading library creates and schedules threads in user space.

`Kernel threads`:
the kernel schedules threads directly; blocking, preemption, and multicore execution are handled naturally by the kernel.

User-level threading libraries are often (at least conceptually) `cooperative`:
user threads may be scheduled non-preemptively relative to each other, and a switch happens only when a thread `yield()`s or performs an operation that returns control to the runtime.
This is the core reason M:1 can look great in microbenchmarks (fast user-space switching) and still fail badly under real blocking and multicore demands.

The key distinction is what happens on a blocking system call:

- if the kernel thinks there is only one execution entity, it blocks the whole process
- if the kernel schedules multiple threads, it blocks only the calling thread

**Invariants**

- The kernel schedules kernel-visible entities, not “language abstractions.”
- A user-level scheduler can only run when it has CPU; it cannot run while the whole process is blocked in the kernel.

**What Breaks If This Fails**

- In a pure user-thread model, one blocking system call can freeze all threads.
- Preemption and fairness can degrade if the runtime lacks good signals from the kernel.

**One Trace: one thread blocks on I/O**

Use this table to reason about “who can run next” when one thread blocks.
If the kernel sees only one schedulable entity for the process, then a blocking syscall parks that entity and all user-level threads stall; if the kernel schedules threads, only the calling thread sleeps.
When you memorize it, focus on the kernel-visible schedulable unit, because that alone determines blocking behavior.

| Model | Thread A does blocking `read()` | Thread B outcome |
| --- | --- | --- |
| user threads, kernel sees 1 entity | process enters kernel and sleeps | B cannot run |
| kernel threads (1:1 or M:N with kernel support) | only A sleeps | B can keep running |

The table is why “cheap user threads” can still be an expensive design mistake: the kernel cannot schedule what it cannot see.
Reason about blocking by naming the kernel-visible schedulable unit first; everything else follows.

**Worked Example: Two “Green Threads,” One Blocking `read()`, And A Frozen Server**

Imagine an application runtime that implements user-level threads (M:1) inside one process.
Thread A handles a request that needs to read from a socket.
Thread B handles a different request that is ready to compute and respond.

What the program *wants* is: “A can wait on I/O while B continues.”
What the OS *actually sees* is: “this process has one kernel-visible thread, and it is about to block.”

Step by step:

1. The runtime schedules A and A issues a blocking `read()` syscall.
2. The kernel puts the *only* kernel-visible thread to sleep on the socket’s wait queue.
3. Because the process has no runnable kernel thread, the runtime is not executing, so it cannot run B even though B is “runnable” in the runtime’s own bookkeeping.
4. The process becomes runnable again only after an interrupt/event makes the socket readable and the kernel wakes the sleeping kernel thread.
5. Only then does user space regain CPU time and the runtime can pick either A (to complete the read) or B (to run other work).

This is the concrete meaning of “one blocks, all block.”
The failure is not that the runtime is stupid; it is that the runtime cannot schedule what the kernel has parked.
To get the intended behavior you need either (a) kernel threads the kernel can block independently (1:1), or (b) nonblocking/async I/O so the kernel never parks the only execution resource, or (c) an M:N design with kernel cooperation so blocked kernel threads can be replaced with runnable ones.

![Supplement: in M:1, a blocking syscall can park the only kernel-visible execution resource; the runtime cannot run other user threads until the kernel wakes it](../graphviz/chapter4_graphviz/fig_4_8_m1_blocking_timeline.svg)

Misconception to avoid: “user-level threads are just like kernel threads but cheaper.”
They can be cheaper for creation and user-space switching, but they are not equivalent in the presence of blocking syscalls and preemption, because the kernel is still the authority over which execution contexts may run.

**Code Bridge**

- In POSIX, identify which calls are “cancellation points” or likely to block, then reason about how that interacts with the model.

**Drills (With Answers)**

1. **Q:** Why is “fast thread creation” not enough to make user-only threads a good idea?
**A:** Because the failure mode is not creation cost; it is blocking and preemption. If the kernel schedules only one entity, any blocking system call blocks the whole process, and the user-level scheduler cannot run to “switch threads” while blocked. You also lose true multicore parallelism because the kernel can run only one kernel-visible entity at a time.

2. **Q:** What new cost appears when the kernel schedules many threads directly?
**A:** Kernel-visible threads consume kernel resources: per-thread kernel stacks/metadata, scheduler run-queue operations, and more context switches under oversubscription. More runnable threads also increase contention on scheduling and synchronization paths. You gain correct blocking and true parallelism, but you pay in memory footprint and scheduling overhead if you create too many.

3. **Q:** How can a runtime avoid blocking the entire process in the presence of blocking I/O?
**A:** By ensuring blocking I/O does not park the only kernel-visible execution entity. Options include using kernel threads (1:1), using nonblocking or async I/O so user threads do not enter a blocking sleep, or using an M:N model with kernel cooperation so the runtime can remap user threads onto kernel threads that remain runnable. The key is: preserve at least one runnable kernel-visible entity when one thread blocks.

### 3.5 Multithreading Models: Many-to-One, One-to-One, Many-to-Many

#### Why This Section Exists

The user-vs-kernel thread distinction (previous section) tells you that "thread" can mean two different things: a language/runtime abstraction and a kernel scheduling entity. Multithreading models exist to specify how those two layers are mapped.

This section exists because the mapping is where the biggest practical tradeoffs live:

- Whether blocking stops one thread or the whole process.
- Whether the program can actually use multiple cores at once.
- Whether "create many threads" explodes kernel overhead.

If you treat M:1 / 1:1 / M:N as taxonomy trivia, you miss that this is a boundary placement decision: it decides how much concurrency logic lives in user space versus how much the kernel enforces.

#### The Object Being Introduced (A Mapping From User Threads To Kernel Execution Resources)

The object is a mapping:

`(user threads)  ->  (kernel-visible execution entities)`

What is fixed:

- The kernel schedules only kernel-visible entities.
- Blocking syscalls block kernel-visible entities.

What varies:

- how many kernel entities exist relative to user threads,
- and how the runtime learns about kernel blocking/resumption events (needed for M:N).

The right way to read each model is: "what happens to progress if one user thread blocks in the kernel?"

#### Formal Definitions (M:1, 1:1, M:N)

Definition (M:1): Many user threads are multiplexed onto one kernel thread. Fast user-space switching is possible, but blocking and multicore parallelism are constrained by the single kernel execution resource.

Definition (1:1): Each user thread corresponds to a kernel thread. Blocking and multicore parallelism behave naturally, but large thread counts create kernel overhead (stacks, scheduling, bookkeeping).

Definition (M:N): Many user threads are multiplexed over N kernel threads (N can be less than, equal to, or greater than number of cores). This aims to combine cheap user-level scheduling with enough kernel resources to avoid whole-process blocking and to use multicore. It typically requires kernel-runtime coordination to handle blocking correctly.

#### Fully Worked Example: Same Server, Different Model, Different Failure Mode

Imagine a server that handles requests by:

1. parsing a request (CPU work),
2. reading from disk/network (blocking I/O),
3. updating shared in-memory state (synchronization),
4. replying (I/O).

Under M:1:

- If any request thread blocks in I/O, the whole process may block because the one kernel thread is asleep. Throughput collapses under real I/O waits unless you use nonblocking/asynchronous I/O and keep the kernel thread runnable.

Under 1:1:

- One request thread can block while others continue. But if you create a thread per request under heavy load, you may oversubscribe CPUs and thrash: too many stacks, too much context switching, and severe cache contention.

Under M:N:

- Some threads can block without stopping the whole process because other kernel threads remain runnable. But correctness depends on coordination: the runtime must know when a kernel thread has blocked so it can schedule other user threads onto remaining runnable kernel threads.

The transfer lesson: the model you choose moves waiting between layers. If you do not explicitly manage waiting, the system will still wait, but in a less controllable place (kernel scheduler thrash, or whole-process blocking).

#### Misconceptions

Misconception 1: "M:N is always best because it combines the advantages."

- M:N is a goal, not a free lunch. It is complex and depends on kernel cooperation. Poor coordination can produce subtle stalls and priority inversions that are harder to debug than 1:1.

Misconception 2: "1:1 means unlimited threads are fine."

- 1:1 makes blocking semantics clean, but the kernel still has finite resources. Past some point, adding threads mostly adds overhead and contention.

#### Connection To Later Material

This model discussion becomes practical in:

- implicit threading (pools and tasks are often "M tasks to N kernel threads"),
- scheduling (oversubscription and run-queue behavior),
- and synchronization (contention costs dominate when there are too many runnable threads).

#### Retain / Do Not Confuse

Retain: M:1 cannot do true multicore parallelism and is vulnerable to whole-process blocking.

Retain: 1:1 has clean semantics but can thrash under high thread counts.

Do not confuse: concurrency (many user threads) with parallelism (many kernel threads running on many cores).

**Problem**

We want the cheapness of user threads and the correctness/performance of kernel scheduling.
Different systems choose different mappings between user threads and kernel threads.

**Mechanism**

- `many-to-one (M:1)`: many user threads mapped to one kernel thread
- `one-to-one (1:1)`: each user thread mapped to a kernel thread
- `many-to-many (M:N)`: many user threads multiplexed over a smaller or equal set of kernel threads

Many-to-many often relies on kernel support to coordinate scheduling decisions between the runtime and the kernel (e.g., scheduler activations / upcalls).
Historically, systems like Solaris 2 are often cited as a “hybrid” approach that implements both user-level and kernel-supported threads.

**Invariants**

- True multicore parallelism requires at least as many kernel threads as cores you want to occupy.
- Blocking behavior is defined by kernel-visible entities.
- M:N is only practical when the runtime and kernel can coordinate.

**What Breaks If This Fails**

- M:1 fails to exploit multicore and suffers from “one blocks, all block.”
- 1:1 can suffer from high overhead if you create huge numbers of threads.
- M:N can be complex and fragile if the runtime can’t learn when kernel threads block or resume.

**Code Bridge**

- When you read a runtime later, ask: is it mapping tasks to kernel threads directly, or does it maintain its own user-level scheduler?

**Drills (With Answers)**

1. **Q:** Why does M:1 fundamentally prevent parallelism on multicore?
**A:** Because all user threads are multiplexed onto one kernel thread. The kernel can schedule that one kernel thread on only one core at a time, so even if your user-level scheduler time-slices among user threads, you cannot occupy multiple cores simultaneously. Concurrency exists (interleaving), but parallelism is impossible.

2. **Q:** Why can 1:1 become a memory and scheduling problem with “thread per request”?
**A:** Each thread typically has a sizable stack and kernel bookkeeping, so thousands of threads become a memory-pressure problem. Oversubscription also turns into a scheduling problem: the kernel spends time context-switching and managing run queues rather than executing useful work, and caches thrash as many thread working sets compete. Throughput can fall even though you “added parallelism.”

3. **Q:** What kernel signal would a user-level scheduler want to know about blocked kernel threads?
**A:** It would want to know when a kernel thread blocks and when it becomes runnable again, so it can remap user threads and avoid stalling the runtime. Historically this appears as scheduler activations / upcalls or other kernel-to-runtime notifications: “this execution resource is now unavailable/available.” Without such signals, M:N becomes fragile because the runtime cannot make correct scheduling decisions under blocking.

![Supplement: threading models differ mainly in parallelism, blocking behavior, and overhead](../graphviz/chapter4_graphviz/fig_4_2_threading_models_comparison.svg)

![Supplement: cooperative user-level scheduling switches at yield/boundaries; kernel threads can be preempted independently](../graphviz/chapter4_graphviz/fig_4_5_user_threads_yield.svg)

### 3.6 Thread Libraries: API vs Implementation

**Problem**

Programs need a portable interface for creating and coordinating threads, but different OSes implement threads differently.

**Mechanism**

Thread libraries typically provide:

- create/start
- join (wait for completion) or detach (no join expected)
- mutual exclusion and condition synchronization primitives (bridges to Chapter 5)
- per-thread storage

Common examples in the textbook:
`Pthreads`, `Windows`, and `Java` threads.

The important question is not which library name appears in the textbook.
The important question is which lifecycle and synchronization semantics the library promises and which kernel machinery it relies on to keep those promises.

**Invariants**

- Join is a lifecycle protocol: “I will wait and reap the thread’s outcome.”
- Detach is a cleanup protocol: “no join; free resources when done.”
- Thread identity and lifetime must be tracked reliably or resources leak.

**What Breaks If This Fails**

- If joins are missed, thread resources accumulate (leaks).
- If detach/join semantics are mixed incorrectly, you can double-free or lose completion information.

**Code Bridge**

- On Linux-like systems, follow `pthread_create` into the kernel boundary it uses (often `clone`-like).
- On JVMs, ask where threads become OS threads and where green-thread scheduling might occur (implementation-dependent).

**Drills (With Answers)**

1. **Q:** Why does “join” feel like `wait()` from Chapter 3?
**A:** Because it is the thread lifecycle analog of reaping: “wait until the child finishes, then reclaim its resources and (often) retrieve its outcome.” Like `wait`, join is about coordinating termination and cleanup so resources are reclaimed deterministically. The conceptual pattern is the same: completion information may need to outlive execution.

2. **Q:** What’s one reason a thread library might avoid “create a kernel thread every time”?
**A:** Creation overhead and resource pressure. Spawning kernel threads repeatedly can allocate stacks, kernel objects, and scheduling state, and it can create bursty load and cache disruption. Pools and task schedulers amortize this by reusing threads, bounding runnable concurrency, and smoothing demand.

3. **Q:** What lifecycle invariant does detach enforce?
**A:** Detach enforces “no join will occur,” so the system is allowed (and required) to reclaim thread resources automatically at termination. It prevents leaks caused by forgotten joins, but it also means you cannot later synchronize on that thread’s completion via join. The invariant is a clear ownership rule for cleanup responsibility.

### 3.7 Implicit Threading: Pools, Tasks, and Fork-Join

**Problem**

If every request creates a new thread, the system can spend more time creating and scheduling threads than doing useful work.

**Mechanism**

Implicit threading approaches include:

- `thread pools`: a fixed or bounded set of worker threads pulls tasks from a queue
- `fork-join` / task frameworks: programmers express parallel structure, runtime schedules tasks
- `OpenMP`: compiler directives produce parallel regions and tasks
- `Grand Central Dispatch (GCD)`: queues of blocks/tasks scheduled onto a pool (macOS/iOS)

The unifying idea is that the runtime accepts units of work but controls how many kernel-schedulable execution contexts compete at once.

**Invariants**

- The system must bound runnable threads to avoid thrashing.
- Work submission must not become a single contended bottleneck.
- Task execution must preserve the program’s ordering and memory invariants.

**What Breaks If This Fails**

- Unbounded thread creation causes memory pressure and scheduler overload.
- A single global queue can become a hot lock.

**One Trace: thread pool request handling**

This is the admission-control story in four moves.
A pool turns unbounded demand (“requests arrive arbitrarily”) into bounded runnable concurrency (“only this many workers contend for CPU at once”), trading some queueing delay for stability.
When you cover this table, be explicit about where backpressure lives: the queue is the pressure valve that prevents the scheduler and memory system from being overloaded by unlimited thread creation.

| Step | Component | Meaning |
| --- | --- | --- |
| submit | producer enqueues work item | request becomes schedulable work |
| pick up | worker thread dequeues | thread pool controls concurrency |
| execute | worker runs handler | useful work happens |
| respond | worker completes and returns | thread reused for next task |

The queue is the intentional backpressure surface.
If you delete the queue by spawning unbounded threads, you do not eliminate waiting; you push it into the scheduler and memory system as thrash, which is harder to control and often worse for tail latency.

**Code Bridge**

- In servers, look for “accept loop + work queue + worker threads” as the structural signature of a pool.

**Drills (With Answers)**

1. **Q:** Why is a thread pool an OS-level performance and stability mechanism, not just a style choice?
**A:** Because it bounds the number of runnable kernel threads that compete for CPU, memory, and locks. Without that bound, the OS scheduler and memory system can be overwhelmed (too many stacks, too many context switches, too much contention), causing throughput collapse and extreme tail latency. A pool is therefore an admission-control layer that shapes load into something the kernel can schedule predictably.

2. **Q:** What’s the difference between “tasks” and “threads” in a fork-join framework?
**A:** A task is a unit of work; a thread is an execution resource (a schedulable context with a stack and registers). Fork-join frameworks create many tasks but run them on a bounded set of threads, using work-stealing or queues to balance load. This separation is the key: you can express abundant parallel structure without creating abundant OS threads.

3. **Q:** Why can a bounded pool reduce tail latency even if it reduces peak parallelism?
**A:** Because unlimited parallelism under load often creates contention and scheduling thrash that makes the slowest requests extremely slow. Bounding concurrency reduces lock contention, cache churn, and run-queue overload, which can make per-request service time more predictable. Tail latency is often dominated by overload behaviors, and pools prevent those overload pathologies.

![Supplement: thread pools convert unbounded demand into bounded runnable work](../graphviz/chapter4_graphviz/fig_4_3_thread_pool_flow.svg)

### 3.8 Threading Issues: Fork/Exec, Signals, Cancellation, TLS

#### Why This Section Exists

Threads turn many OS operations into protocols. In a single-threaded process, `fork`, signals, and `exit` have relatively straightforward meanings: there is one control flow, so "the process does X" is unambiguous.

In a multithreaded process, that unambiguity disappears:

- If the process forks, do we duplicate *all* threads, or only one? What happens to locks held by threads that do not exist in the child?
- If a signal arrives, which thread should run the handler? What if different threads mask different signals?
- If a thread is canceled, how do we ensure it does not leave shared invariants broken (locks held, partially updated state)?

This section exists because these are exactly the places where a "working" multithreaded program becomes fragile or insecure if the protocols are not understood.

#### The Object Being Introduced (Asynchronous Events + Shared Invariants)

The shared object across fork/signals/cancellation is the same:

Asynchrony introduces actions that can occur "in the middle" of your program's intended sequence.

Fork introduces a whole new process that inherits state that may have been mid-update.
Signals inject a handler at an arbitrary point.
Cancellation stops a thread at a point the original code did not intend to stop.

Your only defense is to design explicit invariants and define safe points: places where the runtime/OS is allowed to inject or stop control without leaving shared state inconsistent.

![Supplement: deferred cancellation stops at cancellation points and runs cleanup to preserve invariants (locks/resources released)](../graphviz/chapter4_graphviz/fig_4_12_cancellation_cleanup_protocol.svg)

#### Boundary Conditions / Assumptions / Failure Modes

Assumptions:

- "Stop a thread" is dangerous unless you know which invariants it is currently responsible for.
- Fork semantics typically assume single-threaded execution in the child immediately after fork (only the calling thread continues) to avoid duplicating complex runtime state.

Failure modes:

- deadlocks after fork: the child inherits locks as "held" but the owning threads do not exist, so progress is impossible.
- inconsistent shared state after async cancellation: a thread is canceled while holding a lock or mid-update.
- signal handler races: handler touches shared state without synchronization, creating a race from an unexpected direction.

#### Retain / Do Not Confuse

Retain: these are protocol problems because they involve asynchronous control interacting with shared invariants.

Do not confuse: "process-level event" (signal delivered to the process) with "thread-level execution" (some specific thread will run the handler).

**Problem**

Once a process has multiple threads, the OS and runtime must decide which thread receives a signal, what state survives `fork`, and at which boundary a thread may stop safely.

**Mechanism**

Key issue clusters:

- `fork` / `exec` in a multithreaded process:
  - a common rule is “after `fork`, only the calling thread exists in the child”
  - `exec` replaces the process image, so thread structure is rebuilt in the new program
- `signals`:
  - some signals are process-directed; the runtime/OS must pick a thread to deliver to
  - per-thread masks control which thread may receive which signals
- `cancellation`:
  - `asynchronous` cancellation stops immediately (dangerous)
  - `deferred` cancellation stops at defined cancellation points (safer)
  - cleanup handlers must release locks and resources
- `thread-local storage (TLS)`:
  - per-thread copies of data that would otherwise be shared and race-prone

**Invariants**

- After `fork` in a multithreaded program, the child must not assume locks are in a clean state.
- Cancellation must not leave shared invariants broken (e.g., a lock held forever).
- Signal handlers must be written with reentrancy and safety constraints in mind.

**What Breaks If This Fails**

- Fork + locks can deadlock: the child inherits lock state but not the threads that could release it.
- Async cancellation can corrupt invariants mid-critical-section.
- Signals delivered to an unexpected thread can violate assumptions and cause inconsistent state.

**One Trace: deferred cancellation**

Deferred cancellation is “stop, but only at a safe boundary.”
The cancel request is not the termination; termination happens at a cancellation point where the thread can run cleanup code to release locks and restore invariants.
When you cover this table, the mastery check is: can you name which invariants would be destroyed by asynchronous cancellation at each stage?

| Step | Canceler | Target thread | Meaning |
| --- | --- | --- | --- |
| request | sends cancel request | continues running | cancellation is pending |
| reach point | - | hits cancellation point | safe stop location |
| cleanup | - | runs cleanup handlers | invariants restored |
| termination | - | exits | join/detach protocol completes |

The distinction between “request cancel” and “terminate” is the point: safe cancellation is not immediate; it is deferred to a boundary where invariants can be restored.
If you cannot name what cleanup must happen (release which locks, free which resources), you cannot safely use cancellation.

**One Trace: UNIX signal lifecycle (baseline)**

Signals are the OS-visible “something happened” notifications.
The baseline lifecycle is: generate -> deliver to process -> handle (default or user-defined).
Multithreading complicates only the delivery choice (which thread runs the handler), not the existence of the lifecycle itself.

| Phase | OS / kernel | Process / runtime meaning |
| --- | --- | --- |
| generate | event occurs (fault, timer, child exit, user send) | a signal becomes pending |
| deliver | kernel selects a target thread (subject to masks) | handler will run at a safe boundary |
| handle | default action or user-defined handler executes | process may continue, stop, or terminate |

![Supplement: signal handling is generate -> deliver -> handle (default or user-defined); multithreading mainly changes delivery choice](../graphviz/chapter4_graphviz/fig_4_6_signal_lifecycle.svg)

**Code Bridge**

- In POSIX, find cancellation points in blocking calls and identify what cleanup must happen to preserve invariants.

**Drills (With Answers)**

1. **Q:** Why is “only the calling thread remains after fork” a safety choice?
**A:** Because `fork` copies the process image, including lock states, but it does not copy other threads in a way that guarantees consistent invariants in the child. The child could inherit a mutex as “locked” by a thread that no longer exists, creating immediate deadlock or invariant corruption. Restricting the child to one thread minimizes the inconsistent-state surface and encourages the safe pattern: `fork` then immediately `exec`.

2. **Q:** Why is deferred cancellation safer than asynchronous cancellation?
**A:** Deferred cancellation stops a thread only at defined safe points, where it can run cleanup handlers and release shared resources. Asynchronous cancellation can terminate in the middle of a critical section, leaving locks held, partially updated data structures, and broken invariants that other threads depend on. Safety comes from choosing a stop boundary that preserves global correctness.

3. **Q:** Name one use of TLS that reduces synchronization needs.
**A:** Per-thread scratch buffers (formatting, parsing, temporary storage) are a common TLS use: each thread has its own buffer, so there is no shared mutable object to lock. Thread-local error state (like `errno`-style patterns) is another. TLS reduces sharing pressure, but it does not solve synchronization for truly shared data structures or invariants that must be global.

### 3.9 Operating-System Examples: What “Thread” Means In Practice

**Problem**

The word “thread” is stable, but OS implementations choose different internal representations and policies.

**Mechanism**

Practical anchors:

- Many modern general-purpose OSes implement a mostly `1:1` model in practice.
- The implementation detail that matters is: does the kernel schedule the thread independently, and can different threads truly run at once on different cores?

**Invariants**

- If the kernel schedules it, it has a kernel identity and kernel-saved context.
- If it shares an address space, it shares the memory invariants of that process.

**What Breaks If This Fails**

- If you confuse user-level tasks with kernel-scheduled threads, you mispredict blocking, fairness, and parallelism behavior.

**Code Bridge**

- In Linux-like kernels: search for task structures, clone/fork variants, and scheduler run queues.

**Drills (With Answers)**

1. **Q:** If your runtime uses tasks, what is the kernel actually scheduling?
**A:** Kernel-visible threads (OS threads / kernel threads). Tasks are multiplexed in user space onto that bounded set of threads, so the kernel only sees the underlying schedulable entities. This is why task schedulers exist: you can have millions of tasks while the kernel schedules dozens of threads.

2. **Q:** How would you detect “M:1 behavior” in performance symptoms?
**A:** You would see limited core utilization (often one core pegged) even when there is abundant “logical concurrency,” and you would see “one blocks, all stall” behavior when any task performs a blocking system call. Latency spikes under blocking I/O are a tell, as is an inability to scale throughput with additional cores despite having many user-level threads/tasks.

3. **Q:** Why is thread representation a kernel data-structure choice that can change performance?
**A:** Because the scheduler’s hot path is largely data-structure operations: run-queue management, wakeups, priority updates, load balancing, and context save/restore metadata. Layout affects cache locality, contention, and the cost of common operations. A representation that is correct but lock-heavy or cache-unfriendly can dominate runtime cost even if the application logic is efficient.

## 4. Canonical Traces To Reproduce From Memory

Do not merely read these.
Cover the tables and reproduce the sequence from memory.

### 4.1 Create -> Run -> Exit -> Join

This is the minimal thread lifecycle protocol.
When you reproduce it, separate the *control* events (start running, stop running) from the *cleanup* events (status recorded, resources reclaimed).
Join is not “waiting because you feel like it”; it is the reaping step that makes lifecycle resources deterministic.

| Step | Parent thread | Child thread | Kernel / runtime meaning |
| --- | --- | --- | --- |
| create | requests new thread | allocated with new stack/context | new schedulable context exists |
| run | continues | executes entry function | concurrent execution begins |
| exit | may keep running | returns/exits | completion status recorded |
| join | waits for child | already done or finishes | resources reclaimed deterministically |

The lifecycle does not end at `exit`; it ends when resources are reclaimed (join/detach).
This is why leaked joins or detached threads can become real resource leaks and stability bugs even when “the work is done.”

### 4.2 Blocking System Call Under Different Models

This table is the core of “what blocks” reasoning.
To master it, you must be able to say which schedulable entity the kernel sees, because that alone determines whether blocking parks one thread or the entire process.

| Model | Blocking call effect | Who can still run? |
| --- | --- | --- |
| M:1 user threads | blocks entire process | nobody in that process |
| 1:1 kernel threads | blocks only that thread | other threads in same process |
| M:N (with kernel support) | blocks one kernel thread | other kernel threads, runtime may remap |

Practice this as a single question: what does the kernel schedule?
If the kernel schedules one entity, blocking sleeps the whole process; if it schedules many, blocking is localized and the process can still make progress through other runnable threads.

### 4.3 Thread Pool Request Path

Reproduce this as “demand shaping.”
The pool bounds runnable concurrency and uses a queue to absorb bursts, preventing overload collapse in the scheduler and memory subsystem.

| Step | Producer | Queue | Worker |
| --- | --- | --- | --- |
| submit | creates work item | enqueued | idle |
| schedule | - | item visible | dequeues |
| execute | waits or continues | item consumed | runs handler |
| reuse | - | queue remains | worker returns to idle |

Mentally separate “arrival burst” from “runnable burst.”
Thread pools trade queueing delay for bounded runnable concurrency, which prevents scheduler overload and makes service time more predictable under load.

### 4.4 Parallel Speedup Bound (Amdahl)

This is the “compute the cap, then go hunt the serial fraction” trace.
When you reproduce it, explicitly name what counts as serial in real code (contended locks, single-threaded queues, I/O serialization), not only “a loop that can’t be parallelized.”

| Step | Quantity | Meaning |
| --- | --- | --- |
| identify serial fraction | `S` | part that cannot be parallelized |
| choose cores | `N` | hardware parallelism |
| compute bound | `1/(S + (1-S)/N)` | maximum ideal speedup |
| interpret | diminishing returns | more cores help less as N grows |

This is why performance work so often becomes “reduce contention” work.
In practice, shrinking the effective serial fraction usually means narrowing critical sections, sharding queues, improving locality, or redesigning a single shared bottleneck.

### 4.5 Fork In A Multithreaded Process -> Exec

This trace exists because `fork` is not “copy the whole process and keep going” in a multithreaded world.
After `fork`, the child has one thread but inherits memory and lock state, so it must treat the inherited state as potentially inconsistent until `exec` replaces the image.

| Step | Parent (many threads) | Child after fork | After exec |
| --- | --- | --- | --- |
| fork issued | one thread calls fork | only calling thread exists | - |
| post-fork | parent continues | child must assume locks may be inconsistent | - |
| exec | optional | replaces image | new program defines new threading |

The safety rule is: `fork` gives the child inherited memory and lock state, but it does not give the child the other threads that made that state consistent.
The standard mitigation is “fork then exec quickly,” minimizing the amount of code the child runs in a potentially inconsistent lock state.

### 4.6 Deferred Cancellation With Cleanup

This is the “request, then stop safely” protocol.
Cancellation is safe only if it happens at a boundary where cleanup can restore shared invariants (locks released, resources freed, protocol state consistent).

| Step | Canceler | Target | Invariant preserved |
| --- | --- | --- | --- |
| request cancel | sets pending flag | continues | state not torn mid-critical-section |
| cancellation point | - | checks pending | safe stop boundary |
| cleanup | - | releases locks/frees resources | shared invariants restored |
| termination | - | exits | lifecycle reaped by join/detach |

Treat cancellation as a two-part mechanism: a request flag and a safe stopping boundary.
The cancellation point is the boundary where the target thread can run cleanup code and release shared resources; without that boundary, cancellation can leave shared state corrupted.

## 5. Key Questions (Answered)

1. **Q:** Why is “threads share memory” both the main performance advantage and the main correctness risk?
**A:** The advantage is that one thread can make data visible to another through plain memory operations with no per-exchange kernel mediation or copying. The risk is that those same operations can interleave and reorder: one thread can observe partial updates, overwrite shared state, or read data before the required ordering is established. Shared memory removes an explicit communication boundary, so correctness requires the program to reintroduce one with locks, atomics, and protocols.

2. **Q:** Why does “what blocks” explain most threading-model tradeoffs?
**A:** Because blocking reveals where scheduling responsibility actually lies. If the kernel sees one schedulable entity for the whole process, one blocking syscall parks that entity and all user-level threads stall with it. If the kernel schedules multiple threads independently, only the calling thread sleeps and the others can keep making progress. Most threading-model tradeoffs reduce to this boundary: which execution entities can the kernel block and wake independently?

3. **Q:** Why can adding cores reduce performance when contention grows?
**A:** More cores can increase contention on shared locks and data, turning “parallel work” into “parallel waiting.” Coherence traffic and lock handoff can dominate, and oversubscription can increase context switching and cache thrash. Past a point, adding cores increases coordination work faster than it increases useful work.

4. **Q:** Why is a thread pool an admission-control mechanism, not only an efficiency trick?
**A:** Because it bounds how many kernel-schedulable threads compete for CPU and memory at one time. Without that bound, thread-per-request can explode stack memory, scheduler overhead, and lock contention, producing throughput collapse and extreme tail latency. A pool moves excess demand into an explicit queue, so waiting happens in a controlled admission structure instead of as uncontrolled runnable-thread growth.

5. **Q:** Why does 1:1 threading make blocking behavior easy to reason about but sometimes expensive?
**A:** Easy because each user thread maps to a kernel-scheduled entity, so “thread blocks” means “that thread sleeps” in a straightforward way, and multicore parallelism is natural. Expensive because kernel threads cost memory and scheduling overhead, and large numbers of threads create oversubscription, run-queue contention, and cache thrash. 1:1 shifts complexity from “model ambiguity” to “resource scaling.”

6. **Q:** Why is M:N hard to implement without kernel cooperation?
**A:** Because the runtime must know when its kernel execution resources block or resume to make correct scheduling decisions for user threads. Without kernel-to-runtime signals (upcalls/activations), the runtime can believe it has runnable capacity while all kernel threads are sleeping, causing stalls and unfairness. Cooperation is needed to align user scheduling with kernel blocking and preemption realities.

7. **Q:** Why does fork in a multithreaded process require special rules?
**A:** Because the child inherits memory and lock state but does not inherit a consistent “snapshot” of other threads’ progress. Locks can be held by threads that no longer exist in the child, leaving invariants permanently broken. Special rules (only calling thread exists; fork-then-exec patterns) reduce the inconsistent-state surface and restore a clean execution image quickly.

8. **Q:** Why is asynchronous cancellation dangerous even if it seems convenient?
**A:** Because it can terminate a thread in the middle of a critical section or while holding a lock, leaving shared invariants broken. Other threads may then deadlock or read partially updated state. Convenience is “stop now”; safety requires “stop at a point where cleanup can restore invariants.”

9. **Q:** Why do signals become a policy problem (who receives) in multithreaded programs?
**A:** Because some signals target the process as a whole rather than a specific thread, so the OS or runtime must choose which eligible thread will run the handler. Different threads may have different masks, lock states, and reentrancy risks, so that choice changes which invariants can be touched safely. Signal delivery is therefore not only a delivery mechanism; it is also a policy decision about which thread should take responsibility for the event.

10. **Q:** Why does TLS reduce synchronization pressure, and what does it not solve?
**A:** TLS reduces sharing by giving each thread its own instance of otherwise-global state (scratch buffers, per-thread error state), eliminating the need to lock that state. It does not solve synchronization for truly shared resources and invariants: shared queues, shared caches, shared file descriptors, and shared protocol state still require coordination. TLS is a tool for shrinking the shared surface, not erasing it.

11. **Q:** What is one concrete way that cache coherence can dominate multicore performance?
**A:** A shared hot variable (like a global counter or a lock-protected queue head) can cause a cache line to bounce between cores on every update. The program remains correct, but performance collapses because cores spend time on coherence traffic rather than on computation. False sharing is a particularly nasty version: independent variables on the same cache line create coherence storms even though logic never “shares” the variables intentionally.

12. **Q:** If a parallel program is correct, why might it still be nondeterministic in timing and output order?
**A:** Correctness often permits multiple valid interleavings. The OS scheduler, core timing, and cache effects can change which thread runs first and when, so timing and output order (logs, response ordering) can vary even when invariants are preserved. Determinism requires stronger constraints than correctness (explicit ordering), and those constraints often cost performance.

## 6. Suggested Bridge Into Real Kernels

If you later study Linux-like kernels and runtimes, a good Chapter 4 reading order is:

1. user thread API entry (`pthread_create`, join/detach) to kernel boundary
2. kernel thread/task creation (`clone`-like) and what is shared vs copied
3. scheduler runnable-queue logic for threads
4. blocking I/O path and wakeups (how sleeping threads resume)
5. cancellation, signals, and per-thread masks/TLS machinery

Conceptual anchors to look for:

- where a new stack is allocated and mapped
- where “thread identity” is stored in kernel structures
- where blocking sleeps, wakeups, and run-queue operations happen
- where the runtime bounds concurrency (pool size, queues, backpressure)

## 7. How To Use This File

If you are short on time:

- Read `## 2. Mental Models To Know Cold` once.
- Reproduce the traces in `## 4. Canonical Traces To Reproduce From Memory`.

If you want Chapter 4 to become reasoning skill:

- Work the `## 3. Mastery Modules` slowly: problem -> mechanism -> invariants -> failure modes.
- Do the drills without looking.
- Practice the canonical traces until you can reproduce them from memory and explain *why each step exists*.
