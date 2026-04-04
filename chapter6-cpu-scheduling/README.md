# Chapter 6 CPU Scheduling Mastery

Source: Chapter 6 of `textbook.pdf` (Operating System Concepts, 9th ed.).

This file is the mastery note for Chapter 6.
It is written to make CPU scheduling feel like a control problem under scarcity, not like “memorize FCFS/SJF/RR.”

If Chapter 4 explained threads and Chapter 5 explained correctness under interleavings, Chapter 6 explains how the system decides *who runs next*, how preemption is enforced, and why “performance” is always a trade between latency, throughput, and fairness.

## 1. What This File Optimizes For

The goal is not to memorize algorithm names.
The goal is to be able to do the following without guessing:

- State what the scheduler is optimizing in a given context (response time, throughput, fairness, deadlines).
- Explain why preemption requires both a timer and a correct context-switch protocol.
- Compare algorithms by explicit tradeoffs: starvation risk, overhead, and predictability.
- Explain why multicore scheduling becomes a locality-versus-balance problem.
- Compute waiting/turnaround/response from a schedule and use those metrics to compare policies.

For Chapter 6, mastery means:

- you can trace a scheduling decision from “interrupt happens” to “new thread runs”
- you can compute metrics from a schedule and explain what they imply
- you can predict failure modes (starvation, convoy effect, thrashing, cache migration)
- you can connect algorithm ideas to kernel mechanisms (run queues, wakeups, migration)

## 2. Mental Models To Know Cold

### 2.1 Scheduling Is Queue Selection Under Constraints

The scheduler is not a magic optimizer.
It selects from the runnable set under constraints:

- limited CPUs
- context-switch overhead
- fairness expectations
- latency targets
- sometimes deadlines

The most important anchor is always:
what is the unit being scheduled, and what counts as “runnable”.

### 2.2 Preemption Is a Control Loop

Preemption is not “stop and switch.”
It is a loop:

1. timer interrupt (or a higher-priority event) forces kernel control
2. kernel saves outgoing context
3. scheduler chooses next runnable entity
4. dispatcher restores context and returns to user mode

If any part of that loop is missing, the system is not preemptive in the strong sense.

### 2.3 Metrics Are About Distributions, Not Just Averages

Average waiting time can improve while tail latency becomes worse.
Interactive systems care about response time and jitter.
Batch systems care about throughput and turnaround.

A scheduler is a policy decision about which pain you accept.

### 2.4 “CPU Burst” Is the Right Primitive

Scheduling decisions happen between bursts of CPU execution.
I/O-bound work tends to have short CPU bursts; CPU-bound work tends to have long bursts.

Most scheduling heuristics are attempts to favor the kind of bursts you care about:
short bursts for responsiveness, long bursts for throughput.

### 2.5 Multicore Adds Locality as a First-Class Constraint

On one CPU, you mainly choose an order.
On many CPUs, you also choose where work runs.

Migration can improve balance, but it can destroy cache locality.
A good multiprocessor scheduler is always trading balance against affinity.

### 2.6 Real-Time Is “Meet Deadlines,” Not “Have Good Averages”

Real-time scheduling is defined by timeliness constraints.
“The average response time was good” is irrelevant if a deadline was missed.

## 3. Mastery Modules

### 3.1 The Scheduling Stack: Ready Set, Run Queue, Dispatcher

**Problem**

The OS must share CPU time among many runnable computations while preserving the illusion of progress.
If it cannot regain control and switch correctly, fairness and responsiveness collapse.

**Mechanism**

Core pieces:

- `ready set`: runnable work that could use the CPU now
- `run queue(s)`: data structures that represent the ready set
- `scheduler`: chooses the next runnable entity (policy + mechanism)
- `dispatcher`: performs the context switch and returns to user mode

The scheduling unit might be a process or a thread, but the structure is the same:
save outgoing, choose incoming, restore incoming.

**Invariants**

- The runnable set must represent reality (blocked work must not be considered runnable).
- The context switch must save enough state to resume correctly.
- The kernel must regain control periodically (timer) or on events (I/O completion, faults).

**What Breaks If This Fails**

- Without periodic regain of control, one CPU hog can starve others.
- Without correct save/restore, execution resumes corrupted.
- Without truthful runnable accounting, the scheduler becomes either unfair or wasteful.

**One Trace: event-driven scheduling loop**

This is the smallest “scheduler is real” trace.
Scheduling decisions only exist because the kernel regains control, updates runnable truth, chooses from the run queue, and then performs a context switch that makes the decision become execution.
When you cover this table, force yourself to point to where the runnable set changes (wakeup/admission) versus where policy is applied (selection).

| Step | Trigger | Kernel action | Meaning |
| --- | --- | --- | --- |
| 1 | timer or I/O completion | interrupt enters kernel | kernel regains control |
| 2 | make runnable / update queues | wakeup enqueues runnable work | ready set changes |
| 3 | select next | scheduler chooses from run queue | policy applied |
| 4 | switch | dispatcher saves/restores context | decision becomes real |
| 5 | return | kernel returns to user mode | chosen thread runs |

The table is intentionally minimal because the scheduler’s job is structurally minimal: regain control, maintain runnable truth, choose, and switch.
If you can map each row to a concrete code path (interrupt handler, wakeup, `schedule()`, context switch), scheduling stops being “an algorithm” and becomes an operating-system control loop.

**Code Bridge**

- Find: timer interrupt path, `schedule()`-like function, run-queue structure, context-switch assembly.

**Drills (With Answers)**

1. **Q:** Why must the scheduler be able to trust “runnable” vs “blocked” classification?
**A:** Because scheduling is selection among work that can actually use the CPU. If blocked threads sit in the runnable set, the scheduler wastes CPU time dispatching work that cannot progress (or spins in the kernel discovering it). If runnable threads are misclassified as blocked, they can starve even though resources are available. Runnable truth is the foundation on which fairness, throughput, and responsiveness are built.

2. **Q:** What minimum CPU state must be saved to resume execution correctly?
**A:** The architectural context needed to continue the same instruction stream: PC, SP, general registers, and status/flags (often including FP/SIMD state). The scheduler must also preserve the execution container mapping (address-space / page table pointer) and kernel bookkeeping so the thread can be placed back into queues correctly. In practice “resume correctly” is both an architectural requirement (registers) and a kernel-identity requirement (which address space and scheduling entity this is).

3. **Q:** Why is the dispatcher separate from the policy logic in many OS designs?
**A:** Because the dispatcher is a low-level mechanism (often architecture-specific assembly) that saves/restores state and returns to user mode, while policy is the decision rule for which runnable entity to choose. Separating them keeps the hard-to-verify, machine-dependent code small and stable, while allowing policy to evolve (priorities, fairness heuristics) without rewriting context-switch machinery. It is a concrete instance of mechanism/policy separation.

### 3.2 Scheduling Criteria: What “Good” Means

**Problem**

You cannot optimize all goals simultaneously.
Different workloads demand different success criteria.

**Mechanism**

Common criteria (be precise about definitions):

- `CPU utilization`: fraction of time CPU is doing useful work
- `throughput`: completed jobs per unit time
- `turnaround time`: completion time minus arrival time
- `waiting time`: time spent in the ready queue(s) (not running)
- `response time`: time from arrival to first CPU service (first run)

Response time is the interactive metric.
Turnaround time is the batch metric.
Throughput is the system metric.

**Invariants**

- Metrics must be computed from the schedule, not assumed.
- One metric can improve while another worsens; that is not a bug, it is the tradeoff.

**What Breaks If This Fails**

- If you optimize throughput while users care about response time, the system feels “hung.”
- If you optimize response time at all costs, throughput may collapse under overhead.

**One Trace: compute metrics from a schedule**

Given arrival at `t=0`, completion at `t=C`, first run at `t=R`, and total CPU burst `B`:

- turnaround = `C - 0`
- response = `R - 0`
- waiting = `turnaround - B` (for a single CPU burst workload)

**Code Bridge**

- When you benchmark, decide which metric you are actually measuring (mean vs tail, steady-state vs cold-start).

**Drills (With Answers)**

1. **Q:** Why can a scheduler improve average waiting time while worsening response time?
**A:** Because those metrics measure different things. A policy like SJF/SRTF can reduce total waiting by favoring short bursts, but it can still delay the *first* CPU service of newly arrived interactive work if the system is busy or if the policy batches decisions in a way that hurts “time to first run.” Optimizing total waiting for the whole run is not the same as optimizing how quickly something becomes responsive to a user.

2. **Q:** In a time-sharing system, which metric is the “feel” metric?
**A:** Response time. Humans mostly perceive “how quickly the system reacts to me,” which is time from request arrival to first service, not total completion time.

3. **Q:** Why is tail latency often more important than average latency?
**A:** Because users and systems experience worst-case stalls: the one request that takes 10x longer dominates perceived quality and often triggers timeouts. Averages can look fine while the tail is disastrous (starvation, convoys, lock contention). Scheduling policies are often judged by boundedness and predictability, not only by mean values.

### 3.3 Preemptive vs Nonpreemptive Scheduling (And Why the Timer Matters)

**Problem**

If the system waits for a thread to yield voluntarily, fairness and responsiveness are not guaranteed.

**Mechanism**

`Nonpreemptive` scheduling:
the running thread keeps the CPU until it blocks, exits, or yields.

`Preemptive` scheduling:
the kernel can interrupt the running thread and switch to another runnable one.

Preemption requires:

- a `timer` to force kernel entry even if user code never yields
- a correct save/choose/restore protocol
- careful protection of kernel critical sections (you cannot preempt in the middle of breaking invariants)

![Supplement: preemption is a control loop that becomes real only via context switch](../chapter6_graphviz/fig_6_2_preemption_control_loop.svg)

**Invariants**

- Preemption points must not violate kernel invariants (locks held, partial updates).
- The timer must be reliable enough that no thread can run forever unobserved.

**What Breaks If This Fails**

- Without preemption, interactive latency becomes unbounded under CPU hogs.
- If you preempt in unsafe kernel regions, the kernel corrupts itself.

**One Trace: timer-driven preemption**

This trace is the enforcement loop: regain control even if the running thread is selfish or buggy.
The timer is the forcing function; the scheduler provides the decision; the dispatcher makes the decision real.
When you cover the table, explicitly separate (1) control regain, (2) state preservation, and (3) policy choice.

| Step | Running thread | Kernel | Result |
| --- | --- | --- | --- |
| slice active | thread A runs | timer counts down | A progresses |
| interrupt | A interrupted | kernel regains control | preemption point |
| save | A stopped | A context saved | A resumable |
| choose | scheduler runs | next selected | policy applied |
| restore | B context restored | return to user mode | B runs |

This is the same save-decision-restore protocol as Chapter 3, now viewed from the CPU-scheduling lens.
The subtle safety constraint is that preemption cannot occur at arbitrary points inside the kernel; the OS must define safe preemption points so invariants are not torn mid-update.

**Code Bridge**

- Look for: tick handler, reschedule flag, and the place the kernel decides to switch before returning to user mode.

**Drills (With Answers)**

1. **Q:** Why does preemption require a timer and not only “yield calls”?
**A:** Yield is voluntary and therefore not enforceable. A buggy or selfish thread can never yield, monopolizing the CPU and destroying fairness and responsiveness. A privileged timer creates a bounded point where the kernel regains control regardless of user cooperation, which is necessary for both fairness and system safety.

2. **Q:** Why does preemptive scheduling interact with synchronization correctness (Chapter 5)?
**A:** Because preemption changes interleavings: a thread can be interrupted while holding locks or while data structures are mid-update. The kernel must prevent preemption at unsafe points (or design critical sections to tolerate it) to preserve invariants. At the application level, preemption amplifies race windows and makes correct lock/condition protocols essential for liveness and correctness.

3. **Q:** What does “context switch overhead” mean in a performance model?
**A:** It is CPU time spent saving/restoring state, updating scheduler bookkeeping, and losing locality (cache/TLB disruption) rather than executing user work. The overhead increases with switch frequency and with the amount of architectural state that must be saved (register sets, SIMD state). Scheduling can improve fairness but still reduce throughput if overhead dominates.

### 3.4 Core Algorithms: FCFS, SJF/SRTF, and Round Robin

**Problem**

Given a set of runnable jobs, in what order should the CPU serve them?

**Mechanism**

Three core families:

- `FCFS`: first come, first served
  - simple, but can cause convoy effects when long jobs arrive early
- `SJF`: shortest job first (or shortest CPU burst first)
  - minimizes average waiting time *if* burst lengths are known or well-predicted
- `SRTF`: shortest remaining time first (preemptive SJF)
  - improves responsiveness for short jobs but can increase switching
- `RR`: round robin with time quantum `q`
  - balances response time and fairness for time-sharing

The important variables are not the names.
They are:

- how the ready set is ordered
- whether preemption occurs
- what the quantum is

![Supplement: same workload, different schedules (FCFS vs SJF vs RR)](../chapter6_graphviz/fig_6_1_gantt_algorithm_comparison.svg)

**Invariants**

- RR’s quantum must be chosen relative to context-switch cost.
- SJF/SRTF require prediction; perfect knowledge is a teaching assumption.
- Any algorithm can starve a job if its admission rules allow permanent disadvantage.

**What Breaks If This Fails**

- Too-small quantum: system spends time switching instead of working.
- Too-large quantum: RR degenerates into FCFS in “feel.”
- Pure SRTF can starve long jobs if short jobs keep arriving.

**One Trace: choosing a quantum**

This is the “one knob that changes the character of RR” table.
Quantum selection controls how often you pay context-switch overhead versus how quickly interactive work gets a turn.
When you cover it, relate `q` to two concrete costs: (1) context switch cost, and (2) typical CPU burst length for interactive work.

| If quantum q is… | Then… | Symptom |
| --- | --- | --- |
| very small | more preemptions | high overhead, cache churn |
| very large | less preemption | poor interactivity |
| comparable to typical burst | balanced | acceptable response + throughput |

Quantum selection is where policy meets machine cost.
If `q` is smaller than typical bursts, you buy responsiveness; if it is smaller than context-switch cost, you buy thrash.

**Code Bridge**

- In real schedulers, look for: timeslice accounting, vruntime/weighting, and heuristics for interactive tasks.

**Drills (With Answers)**

1. **Q:** Why is SJF “optimal” only under the strong assumption that bursts are known?
**A:** The classic proof assumes you can sort jobs by true future CPU burst length. Real systems do not know future bursts; they estimate based on history, which can be wrong. If estimates are wrong, SJF can make bad choices (misclassify a long job as short), losing the optimality property and sometimes hurting responsiveness or fairness. “Optimal” here is a statement about an idealized model, not a guarantee in production workloads.

2. **Q:** What is the convoy effect, and why does FCFS trigger it?
**A:** The convoy effect is when a long CPU-bound job at the front causes many short or I/O-bound jobs to line up behind it, increasing their waiting time and harming device utilization. FCFS triggers it because it preserves arrival order regardless of burst length, so one long job can dominate the CPU for a long interval. In interactive systems, convoys feel like “the system is stuck behind one slow thing.”

3. **Q:** How does RR trade off response time against overhead?
**A:** Smaller quanta give more frequent turns, improving response time because jobs begin running sooner and more often. But smaller quanta increase context switch overhead and cache churn. Larger quanta reduce overhead but worsen response time and can make RR behave like FCFS in the user’s experience.

### 3.5 Priority and Feedback: Priority Scheduling, MLQ, MLFQ, Aging

**Problem**

Systems want to differentiate classes of work (interactive vs batch, kernel vs user, real-time vs best-effort).
But priority systems can starve low-priority jobs forever.

**Mechanism**

`Priority scheduling`:
choose the runnable job with the highest priority.

To prevent starvation:

- `aging`: gradually increase the priority of waiting jobs

`Multilevel queue (MLQ)`:
multiple distinct queues (classes); each queue has its own policy; strict priority between queues.

`Multilevel feedback queue (MLFQ)`:
jobs move between queues based on observed behavior (useful heuristic for “interactive has short bursts”).

Typical MLFQ shape:

- high priority queues have short quantum (favor responsiveness)
- using a full quantum demotes you (assume CPU-bound)
- blocking early keeps you high (assume interactive / I/O-bound)
- periodic boosts prevent starvation

![Supplement: MLFQ is a queue structure plus movement rules (demotion/boost)](../chapter6_graphviz/fig_6_3_mlfq_overview.svg)

**Invariants**

- Without explicit anti-starvation, strict priority scheduling can starve indefinitely.
- Feedback rules must not be gameable by trivial behavior (e.g., yielding just before quantum ends).
- Priority changes must be consistent with the intended performance model.

**What Breaks If This Fails**

- Starvation: some job never runs.
- Priority inversion: a high-priority job waits on a lock held by a low-priority job (Chapter 5).
- Unstable behavior: small changes in load cause large latency changes.

**One Trace: MLFQ intuition**

This table is about inference from observed behavior.
Feedback schedulers treat “uses full quantum” as evidence of CPU-bound work and “blocks early” as evidence of interactive/I/O-bound work, then shape priorities accordingly to improve response without starving throughput.
When you cover it, connect each row to an explicit fear: responsiveness loss (interactive stuck behind batch), starvation (low queue never runs), and gaming (workloads that manipulate the heuristic).

| Job behavior | Scheduler inference | Result |
| --- | --- | --- |
| short bursts, blocks often | interactive / I/O-bound | stays high priority |
| long bursts, uses full quantum | CPU-bound | demoted to lower queues |
| waits too long in low queue | risk of starvation | boosted upward periodically |

Feedback schedulers are making a bet: “behavior predicts intent.”
This is why MLFQ needs anti-starvation boosts and why real systems worry about gaming; the mechanism is simple, but the workload can adapt to the policy.

**Code Bridge**

- Real schedulers often implement “feedback” indirectly (weights, vruntime, interactivity heuristics), not as textbook MLFQ, but the same idea appears.

**Drills (With Answers)**

1. **Q:** Why does strict priority scheduling starve without aging?
**A:** Because high-priority work can continuously preempt or outrank low-priority work. If there is always some runnable job at a higher priority, lower levels may never be selected, so their waiting time can become unbounded. Aging (or periodic boosts) is the mechanism that reintroduces bounded waiting by eventually increasing the priority of long-waiting jobs.

2. **Q:** How can a scheduler accidentally encourage bad behavior (gaming)?
**A:** If the heuristic is “blocking early means interactive,” then a CPU-bound job can yield or sleep briefly before its quantum expires to appear interactive and stay at high priority. This can harm fairness and throughput because the scheduler is optimizing the wrong proxy. Real schedulers must anticipate that workloads can adapt to the policy and therefore choose heuristics that are harder to exploit.

3. **Q:** What is one concrete mechanism to prevent starvation in feedback systems?
**A:** Periodic priority boosts: after a time interval, move all jobs (or long-waiting jobs) back to a higher-priority queue. Aging is a more continuous version: gradually increase priority the longer a job waits. Both enforce bounded waiting by preventing permanent exile to a low-priority queue.

### 3.6 Thread Scheduling: What Is the Scheduling Unit?

**Problem**

Chapter 4 introduced threads, but scheduling decisions must choose a concrete unit.
User-level threads and kernel threads behave differently under blocking and multicore.

**Mechanism**

Key distinctions:

- Kernel schedules `kernel-visible` entities (kernel threads / tasks).
- User-level threading libraries can multiplex user threads on top of a smaller kernel-visible set.

Consequences:

- If the kernel sees one runnable entity, one blocking syscall blocks the process.
- If the kernel schedules many threads, one thread can block while others run.

**Invariants**

- Scheduling fairness is defined over kernel-visible entities.
- User-level scheduling cannot make progress while the entire process is blocked in the kernel.

**What Breaks If This Fails**

- M:1-style behavior destroys parallelism and can destroy responsiveness under blocking I/O.

**Code Bridge**

- In POSIX/Linux-like systems, find how thread creation maps to kernel primitives (clone/fork variants).

**Drills (With Answers)**

1. **Q:** Why does “user threads are cheap” not guarantee good system behavior?
**A:** Because the kernel schedules only kernel-visible entities. If you multiplex many user threads onto one kernel thread, you can lose parallelism and you can inherit “one blocks, all block” behavior on blocking syscalls. Cheap creation is irrelevant if the runtime cannot run when blocked and cannot occupy multiple cores; the system-level behavior depends on the kernel-visible scheduling unit.

2. **Q:** How does thread scheduling change the meaning of “ready queue” from Chapter 3?
**A:** In a thread-scheduled system, “ready” is primarily about kernel threads/tasks, not about user-level threads. A user-level “runnable” thread is only truly runnable if the runtime has an available runnable kernel thread to execute it. This is why M:N designs need kernel/runtime coordination: there are effectively two levels of “ready.”

3. **Q:** What symptom would you see if a system is effectively M:1 under the hood?
**A:** Poor multicore scaling (one core busy while others are idle) and “one blocking call stalls the whole process.” You may also see latency spikes when any task performs blocking I/O, because the runtime loses its only kernel execution resource. These symptoms point to a mismatch between application concurrency and kernel schedulable entities.

### 3.7 Multiple-Processor Scheduling: Load Balancing vs Affinity

**Problem**

On multicore systems, the scheduler must decide both:

- which job runs next
- on which CPU it runs

Moving a job can reduce load imbalance, but it can harm cache locality and NUMA locality.

**Mechanism**

Common patterns:

- per-CPU run queues
- load balancing via migration:
  - `push`: overloaded CPU moves work away
  - `pull`: idle CPU steals work
- `processor affinity`: prefer keeping a job on the same CPU to reuse cache state
- NUMA-aware placement: prefer CPUs near the memory a job uses

![Supplement: multiprocessor scheduling trades load balance against affinity](../chapter6_graphviz/fig_6_4_multiprocessor_load_balancing.svg)

**Invariants**

- Balance improves throughput only if migration overhead does not dominate.
- Affinity improves performance only if it does not cause persistent imbalance.
- Migration must preserve correctness of runnable accounting and locking.

**What Breaks If This Fails**

- Excess migration: cache thrash, worse performance on more cores.
- Persistent imbalance: one CPU overloaded while others idle.
- NUMA blindness: remote memory access dominates.

**One Trace: balancing decision**

This trace is about a second scheduling dimension: *placement*.
Balancing improves throughput when it turns idle cores into useful work, but migration can destroy locality (cache warmth, NUMA proximity), so the “fix” can become worse than the imbalance.
When you cover it, say what data is lost on migration (cache state) and what is gained (parallel service capacity).

| Step | Observation | Action | Tradeoff |
| --- | --- | --- | --- |
| measure | CPU0 run queue long, CPU1 idle | migrate or steal work | better balance, worse locality |
| run | CPU1 executes migrated work | - | throughput up if locality cost small |
| stabilize | keep affinity if stable | reduce migrations | avoid thrash |

This table is the locality-versus-balance trade in miniature.
Migration turns idle capacity into service capacity, but it can also destroy cache warmth and NUMA locality; the “stabilize” step is the difference between balancing and thrashing.

**Code Bridge**

- Find: per-CPU run queues, migration paths, and the knobs that influence affinity (weights, pinning, NUMA policy).

**Drills (With Answers)**

1. **Q:** Why can “more cores” reduce performance if migration is excessive?
**A:** Because migration can turn computation into coherence and cache-miss overhead. Moving a thread loses cache warmth and can create extra contention on shared data structures; on NUMA it can also turn local memory access into remote access. With enough migration, the system spends more time moving and reloading state than executing, so adding cores increases overhead rather than throughput.

2. **Q:** Why is processor affinity a performance mechanism, not a correctness mechanism?
**A:** Correctness does not depend on which core executes the thread; the program should produce the same logical result regardless of placement. Affinity is about exploiting locality: keeping a thread near its cached data and near its NUMA memory to reduce misses and latency. It changes cost, not semantics.

3. **Q:** What is the scheduling symptom of a NUMA-unaware system under memory-heavy load?
**A:** High latency and low throughput despite available cores, often with frequent migrations and heavy remote memory access. Threads may bounce between CPUs far from their memory, causing long stalls that look like “CPUs are busy but not productive.” The system can appear imbalanced or unstable because placement decisions ignore memory locality as a first-class constraint.

### 3.8 Real-Time CPU Scheduling: Deadlines and Admission

**Problem**

Some work must complete by a deadline.
Average performance is not enough; worst-case behavior matters.

**Mechanism**

Real-time systems are often classified as:

- `hard real-time`: missing a deadline is unacceptable
- `soft real-time`: occasional misses degrade quality but are tolerable

Two classic policies:

- `rate-monotonic (RM)`: fixed priority based on period (shorter period => higher priority)
- `earliest deadline first (EDF)`: dynamic priority; earliest deadline runs first

Real-time scheduling often includes `admission control`:
do not accept new real-time work if it would make existing deadlines impossible.

**Invariants**

- Deadlines must be expressed in the scheduling model, not as an afterthought.
- Overload must be handled explicitly (admission control or graceful degradation).

**What Breaks If This Fails**

- The system behaves “fine on average” but misses critical deadlines.
- Overload leads to cascading misses (everything becomes late).

**One Trace: EDF intuition**

EDF is “priority equals urgency.”
The scheduler constantly re-evaluates which task has the closest deadline, so priority is not a static attribute; it is derived from time.
When you cover the table, emphasize that under overload no algorithm can meet all deadlines, which is why admission control is part of the real-time story.

| Step | Runnable tasks | Policy | Result |
| --- | --- | --- | --- |
| choose | tasks have deadlines | pick earliest deadline | minimizes imminent miss risk |
| run | execute until completion or preemption | deadline order changes as time passes | dynamic priorities |

EDF works by turning time into priority, which is why it must be reevaluated continuously.
Under overload, EDF cannot perform miracles; admission control is what keeps “deadline scheduling” inside the feasible region.

**Code Bridge**

- In real systems, “real-time” classes often coexist with best-effort classes. Look for how the kernel isolates those classes.

**Drills (With Answers)**

1. **Q:** Why does EDF require dynamic priorities?
**A:** Because “earliest deadline” changes as time passes and as tasks arrive/complete. A task that was not urgent can become the most urgent simply because its deadline is approaching. EDF therefore recomputes priority from deadlines continuously; static priorities cannot represent “urgency” correctly across time.

2. **Q:** Why is admission control a correctness mechanism in hard real-time?
**A:** Hard real-time correctness includes meeting deadlines, not merely producing correct outputs eventually. If the system accepts more real-time work than can be scheduled feasibly, deadlines become mathematically impossible to meet. Admission control prevents the system from entering an infeasible state so that the deadlines it does accept remain guaranteed.

3. **Q:** What failure mode appears if a real-time system is overloaded?
**A:** Cascading deadline misses: as tasks become late, urgency increases, preemptions rise, and the system can thrash trying to catch up, making even more tasks late. The system may still “run,” but it violates its correctness contract because outputs arrive after they are useful or safe.

### 3.9 Algorithm Evaluation: Knowing When a Policy Will Work

**Problem**

No scheduling algorithm is best for all workloads.
You need methods to evaluate and compare policies honestly.

**Mechanism**

Evaluation approaches:

- deterministic modeling (given workload, compute schedule and metrics)
- queueing models (stochastic workloads)
- simulation (trace-driven)
- implementation and measurement (most realistic, most expensive)

The key is to match your evaluation method to the question you are asking.

**Invariants**

- The model must match the workload features that matter (arrival patterns, burst distribution, I/O).
- The metric must match what you care about (response vs throughput vs deadlines).

**What Breaks If This Fails**

- You choose a policy based on a model that ignores the real bottleneck.
- You “optimize” a metric that users do not experience.

**Code Bridge**

- When reading scheduler papers or kernel docs, look for: the assumed workload model, the metrics, and the failure modes they admit.

**Drills (With Answers)**

1. **Q:** Why is simulation often more informative than deterministic examples?
**A:** Deterministic examples are great for understanding one mechanism, but they can hide distributional effects and rare pathologies. Simulation can model burst distributions, arrival patterns, and contention across many runs, revealing tail latency, starvation probability, and sensitivity to workload changes. Schedulers live in distributions; simulation is closer to that reality.

2. **Q:** Why can a benchmark mislead if it excludes I/O and blocking?
**A:** Because blocking is a major reason schedulers exist. A CPU-only benchmark can make a policy look great even if it performs terribly when threads sleep/wake frequently, when I/O completion reshapes the runnable set, or when locks create short bursts and long waits. Excluding I/O often removes the real sources of latency and queueing behavior that users experience.

3. **Q:** Which metric would you choose for: interactive shell, web server, batch compiler farm, hard real-time control loop?
**A:** Interactive shell: response time (and tail response). Web server: tail latency and throughput together (SLOs are tail-focused). Batch compiler farm: turnaround time and throughput. Hard real-time control loop: deadline miss rate (and worst-case lateness), with admission control as part of correctness.

## 4. Canonical Traces To Reproduce From Memory

Do not merely read these.
Cover the tables and reproduce the reasoning and sequence from memory.

### 4.1 Dispatch and Preemption Loop

This is the minimal “policy becomes execution” loop.
When you reproduce it, separate the forcing event (timer/interrupt) from the decision (choose) and from the mechanism (switch).

| Step | Trigger | Kernel action |
| --- | --- | --- |
| regain control | timer / interrupt | enter kernel |
| choose | runnable set examined | select next |
| switch | save/restore | dispatcher runs |
| run | return to user | chosen thread executes |

Practice naming which part is “policy” (choose) and which part is “mechanism” (switch).
Most scheduler debates are policy debates, but correctness failures often happen in the mechanism and bookkeeping that make the decision real.

### 4.2 Compute Waiting/Turnaround/Response from a Gantt Chart

These definitions are the vocabulary for arguing about schedules.
When you cover this table, you should be able to compute each quantity from an actual Gantt chart and then explain what it means operationally (interactive “feel” vs batch completion).

| Quantity | Definition |
| --- | --- |
| response | arrival -> first run |
| turnaround | arrival -> completion |
| waiting | turnaround - CPU burst (single-burst model) |

These are the translation layer between a picture (Gantt chart) and an argument (“this policy is better”).
If you can compute them quickly, you can evaluate schedules without hand-waving about “feels faster.”

### 4.3 RR Quantum Tradeoff

This is the one-line tradeoff that drives RR design.
Small `q` buys responsiveness by switching often, but it spends more time paying overhead; large `q` buys throughput by switching rarely, but it delays service and “feels” like FCFS.

| If q is… | Then response time… | And overhead… |
| --- | --- | --- |
| smaller | improves | worsens |
| larger | worsens | improves |

Say the tradeoff as a sentence: smaller `q` improves interactivity by reducing time-to-first-run and time-between-turns, but increases overhead and cache churn.
This is why RR without an explicit `q` is not a complete design.

### 4.4 Starvation and Aging (Priority Scheduling)

This is the minimal starvation fix.
Strict priority encodes a total order that can permanently exclude low priority work; aging turns waiting time into a priority boost so bounded waiting is restored.

| Step | Observation | Fix |
| --- | --- | --- |
| strict priority | low-priority waits forever | starvation |
| aging | waiting raises priority | bounded waiting restored |

Aging converts “time spent waiting” into a priority signal, turning an unbounded fairness failure into a bounded-waiting guarantee.
When you see starvation in practice, it is usually a missing or ineffective version of this exact mechanism.

### 4.5 MLFQ Movement Rules

These are the “shape the workload” rules.
Reproduce them and then explain the intent: punish CPU hogs (demote), reward interactive behavior (keep/promote), and prevent starvation (boost).

| Behavior | Queue movement |
| --- | --- |
| uses full quantum | demote |
| blocks early | keep (or promote) |
| waits too long | periodic boost |

These rules are the implementation of the “interactive vs batch” hypothesis.
If you remember only one thing: boosts exist because any heuristic that demotes can create starvation unless something lifts long-waiting jobs back up.

### 4.6 Multiprocessor Balancing

This is the minimal load-balance loop.
The key mastery check is to be able to explain when migration helps (idle core exists) and when it hurts (thrash and lost locality).

| Step | CPU0 | CPU1 |
| --- | --- | --- |
| imbalance | long run queue | idle |
| migration | push/pull work | receives work |
| stabilize | avoid thrash | preserve locality |

Reproduce this as a *control loop* with a stability problem.
Without a stabilizing rule, load balancing can oscillate and make performance worse on more cores due to migration and coherence overhead.

### 4.7 EDF Choice

EDF is the “compare deadlines, run earliest” loop.
When you reproduce it, emphasize that priorities are time-dependent and that under overload you need admission control to preserve correctness.

| Step | Tasks | Decision |
| --- | --- | --- |
| evaluate | compare deadlines | pick earliest |
| run | execute | adjust as deadlines approach |

This is the smallest dynamic-priority trace: the “earliest” task can change as time passes and as new tasks arrive.
To master it, always say what happens under overload: either admission control rejects work or deadlines become impossible and correctness is lost.

## 5. Key Questions (Answered)

1. **Q:** Why is preemption fundamentally a *control* mechanism, not only a fairness mechanism?
**A:** Because it guarantees the kernel regains authority. Fairness is a consequence, but the root purpose is control: without forced regain (timer), the OS cannot enforce scheduling policy, cannot ensure responsiveness, and cannot reliably maintain global invariants against runaway code. Preemption is the control loop that makes “the OS is in charge” true at runtime.

2. **Q:** Why do response time and throughput often conflict?
**A:** Improving response time typically requires frequent switching so new work gets CPU service quickly, but frequent switching increases overhead and reduces throughput. Optimizing throughput tends to favor longer runs and fewer preemptions, which delays first service and harms interactivity. The conflict is largely “overhead vs latency” under scarcity.

3. **Q:** Why does SJF minimize average waiting time only under strong assumptions?
**A:** Because it assumes you know (or can perfectly predict) future burst lengths and that the model ignores or simplifies overhead and blocking complexities. Real burst lengths are not known; predictions can be wrong; and preemption/context switching adds cost. The optimality result is a teaching theorem under an idealized workload model, not a universal guarantee.

4. **Q:** Why is “quantum selection” a core design decision in RR?
**A:** Because the quantum determines the scheduler’s character: small `q` gives interactive responsiveness but can burn CPU on overhead and cache churn; large `q` preserves throughput but delays service and behaves like FCFS. `q` ties policy directly to machine costs (context-switch time) and workload shape (typical burst length). Picking `q` is therefore not tuning; it is the definition of the trade.

5. **Q:** Why does strict priority scheduling need anti-starvation (aging/boost)?
**A:** Strict priority can create unbounded waiting: low-priority work may never run if higher-priority work remains runnable. Aging/boost mechanisms convert “waited long enough” into increased priority so that bounded waiting is restored. Without anti-starvation, strict priority is a fairness failure even if it is simple and predictable for the favored class.

6. **Q:** Why does multiprocessor scheduling add the locality-versus-balance tradeoff?
**A:** Because placement now matters. Balancing spreads work so all cores are used, but moving work destroys cache locality and can increase remote NUMA accesses. Keeping affinity preserves locality but can leave cores idle if load is uneven. The scheduler must trade “use all cores” against “keep data close,” and the best choice changes with workload and hardware.

7. **Q:** Why can adding cores reduce performance when migration and contention dominate?
**A:** More cores can mean more contention on shared locks/queues and more cache coherence traffic. If load balancing migrates aggressively, you can add migration overhead and lose locality faster than you gain service capacity. The machine gets “more parallel,” but the workload becomes “more coordinated,” and coordination can dominate.

8. **Q:** Why does real-time scheduling require admission control under overload?
**A:** Because hard real-time correctness includes meeting deadlines. Under overload, deadlines become infeasible no matter what scheduling policy you choose; the system must reject or degrade work to preserve guarantees for accepted tasks. Admission control keeps the system in a feasible region so deadlines remain a correctness property, not a hope.

9. **Q:** Why are averages often misleading for user-perceived performance?
**A:** Because users experience tail events: the slow request, the stutter, the missed deadline. Averages can improve while starvation probability or tail latency worsens. Scheduling decisions shape distributions; evaluating only mean values hides the failure modes that actually matter operationally.

10. **Q:** What mechanism prevents a blocked thread from being treated as runnable?
**A:** Kernel state and queue discipline: blocked threads are removed from the run queue and placed on an event/device/condition wait queue, and only a completion/wakeup path moves them back to runnable state. The scheduler’s runnable set is built from these structures. “Blocked” is enforced by not being eligible for dispatch, not by a convention.

11. **Q:** If a scheduler is “fair,” what does that mean precisely: CPU time, progress, or bounded waiting?
**A:** It depends on the definition. Fairness can mean equal CPU time, proportional share by weights, bounded waiting (no starvation), or fairness of *progress* (completions). Many schedulers provide proportional time fairness but not strict bounded waiting; others provide bounded waiting at the cost of throughput. “Fair” is a claim that must be tied to an invariant.

12. **Q:** Why is scheduler evaluation inseparable from a workload model?
**A:** Because scheduler behavior depends on burst distributions, arrival patterns, blocking behavior, and contention. An algorithm can look excellent on CPU-only workloads and terrible on I/O-bound interactive workloads, or vice versa. Without a workload model, “this scheduler is better” is an ungrounded statement.

## 6. Suggested Bridge Into Real Kernels

If you later study a teaching kernel or Linux-like codebase, a good Chapter 6 reading order is:

1. run queue structures and “runnable” classification
2. timer tick handler and reschedule trigger
3. core selection function (policy)
4. dispatcher/context-switch code (mechanism)
5. wakeup paths (I/O completion -> runnable)
6. multiprocessor balancing and affinity code

Conceptual anchors to look for:

- where timeslices are accounted and enforced
- where fairness is encoded (weights, vruntime, priorities)
- where migration happens and what prevents thrash
- where scheduler decisions are made relative to interrupts and locks

## 7. How To Use This File

If you are short on time:

- Read `## 2. Mental Models To Know Cold` once.
- Reproduce the traces in `## 4. Canonical Traces To Reproduce From Memory`.

If you want Chapter 6 to become reasoning skill:

- For each algorithm, write down the failure mode you fear most (starvation, overhead, convoy effect) before reading the explanation.
- Reproduce one schedule from memory and compute its metrics without looking.
- When you make a claim (“RR is fair”), force yourself to state the invariant that makes it true.
