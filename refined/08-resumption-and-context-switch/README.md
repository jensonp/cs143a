# Resumption Cluster: PCB, Saved Registers, Program Counter, Scheduler, Context Switch, Overhead

## Why These Ideas Belong Together

### Scope note for “execution context”

In the early single-threaded teaching model, you can read **execution context** as “the currently running process’s machine-level continuation state.” Later, when the thread chapter appears, this will be refined: the saved-and-restored machine state belongs most directly to a **thread**, while the broader resource container belongs to the **process**. This chapter is compatible with both views; it is introducing the resumption mechanism before the final process/thread split is fully sharpened.

Operating systems do not merely *run* programs. They repeatedly stop one computation, preserve enough of its state that it can be resumed later, choose some other computation to run, and then reconstruct the chosen computation’s state so that the CPU continues as if nothing had interrupted it. That entire story is the resumption problem.

The six ideas in this cluster are six parts of one mechanism.

A running computation has a current machine state. Some of that state lives in CPU registers. One register, the **program counter**, is especially important because it tells the CPU which instruction should execute next. If a computation is going to be paused and later resumed, that machine state must be stored somewhere durable; the operating system uses a **process control block** to hold this and related information. Since multiple computations compete for one or more CPUs, the operating system needs a policy and mechanism to decide which one runs next; that decision-maker is the **scheduler**. The act of stopping one execution context and starting another is the **context switch**. The time spent doing this administrative work does not directly advance the user’s computation; that cost is **overhead**.

These are not separate glossary terms. They answer one forced question after another.

A CPU can only execute one instruction stream per core at a time. If more than one process or thread exists, then some execution must be paused. But paused *how*? By saving machine state. Saved *where*? In an operating-system data structure. Resumed *when* and *which one first*? According to scheduling. Switched *by what mechanism*? By a context switch. At *what cost*? Overhead.

That dependency chain is why these ideas should be learned together.

## The Problem the Cluster Solves

Suppose a user runs a text editor, a compiler, a music player, and a web browser at the same time on a single CPU core. Physically, the core cannot execute four instruction streams simultaneously. Yet the system must preserve the illusion that each program continues to make progress.

To create that illusion, the operating system must do three things correctly.

First, it must preserve the state of a paused computation exactly enough that resuming it produces the same future behavior it would have had without interruption, except for the fact that time has passed. Second, it must choose which computation should run next according to some policy such as fairness, priority, responsiveness, or throughput. Third, it must perform this transfer often enough to satisfy system goals, but not so often that the switching work itself consumes too much CPU time.

The resumption cluster is the conceptual machinery behind those three requirements.

## What Is Fixed and What Varies

Several things are fixed by the machine and by the operating system design.

The CPU architecture fixes what counts as machine state at the register level: general-purpose registers, stack pointer, program counter, flags or status register, and possibly floating-point or vector registers. The kernel design fixes where process metadata is stored and how the switch path is implemented. The hardware interrupt model fixes some of the events that can force the kernel to run.

Several things vary from one moment to another.

The contents of registers vary as the program executes. The value of the program counter changes instruction by instruction. The set of runnable processes varies as programs block for I/O, wake up, terminate, or are created. The scheduler’s choice varies depending on the ready queue, priorities, time slice consumption, and policy. The overhead varies depending on the hardware, cache effects, amount of state that must be saved, and whether the switch crosses an address-space boundary.

Seeing the fixed-versus-variable distinction matters because students often confuse the *mechanism* with the *current data*. The PCB is a fixed kind of structure, but its fields change. The scheduler is a fixed mechanism or policy module, but its decisions depend on changing runtime facts. The context switch path is a fixed kernel routine, but the saved state is whatever the interrupted computation happened to have at that instant.

## Definition 1: Program Counter

**Definition.** The **program counter** (PC), also called the instruction pointer on some architectures, is the register whose value identifies the memory address of the next instruction to be fetched and executed for the current execution context.

In plain technical English, the program counter answers the most immediate question in execution: *where does this computation continue?* If you know every register except the PC, you still do not know which instruction runs next. That is why the PC is not just another detail in saved state. It is the point of re-entry.

What the reader should notice first is that the PC is about *continuation*. It does not summarize the whole program. It identifies the exact next machine-level step.

The PC changes constantly during ordinary execution. After most instructions, it advances to the next sequential instruction. For a branch, jump, call, return, exception, or interrupt, it changes in a non-sequential way. When the operating system interrupts a running process, the CPU and kernel together must preserve enough information that the correct PC value is restored later.

This immediately yields an important boundary condition: resuming a process means resuming it at the correct next instruction, not merely somewhere in the same function or same source line. Operating systems work at machine-state granularity, not at the loose semantic granularity of “continue that program roughly where it was.”

A common misconception is to think that the PC somehow stores “the current line of code” in a source-language sense. It does not. It stores a machine instruction address, and the relationship between that address and a source line may be many-to-one, one-to-many, or obscured by optimization.

## Definition 2: Saved Registers

**Definition.** **Saved registers** are the register values of an execution context that have been copied out of the CPU into memory so that the context can later be restored and execution can continue correctly.

In plain technical English, this means the operating system takes the live working state currently inside the processor and writes it somewhere safe before letting some other context overwrite those same hardware registers.

The first thing to notice is that registers are a scarce hardware resource. On one CPU core, the hardware register file belongs only to the currently running context. If another process or thread is to run, those hardware registers cannot hold both states at once. Saving is therefore not optional; it is forced by physical reuse of the CPU.

What gets saved depends on architecture and switch type. At minimum, correct resumption requires the values whose future use affects execution: general-purpose registers, stack pointer, program counter, status flags, and often control registers associated with privilege or memory translation. Some architectures or kernels also save floating-point, SIMD, or other extended registers immediately or lazily.

Order matters conceptually. The kernel must capture the old context’s register state before restoring the new one, because once the new state is loaded into the hardware registers, the old values are gone from the CPU. The check is not a logical predicate like “if this is true,” but a preservation requirement: before reuse, copy out everything required for later correctness.

One subtle point is that not all process state lives in registers. Much of it is already in memory: code, global variables, heap, and the process stack. Registers are special because they are *in the CPU right now* and will be overwritten by the next running context. Students sometimes overstate the role of register saving by speaking as if the whole process is copied during every switch. That is false. Typically the address space remains in memory; the switch saves only the machine context plus kernel bookkeeping, though cache and translation effects can make the practical cost larger.

## Definition 3: Process Control Block

**Definition.** A **process control block** (PCB) is a kernel-resident data structure that stores the operating system’s record of a process, including enough execution state and management information for the kernel to track, schedule, suspend, and resume that process.

If you want the cleanest mental model, read the PCB here as “the kernel’s durable record of a resumable computation in the simplified process-first model.” Later chapters will separate process-level and thread-level records more carefully.

In plain technical English, the PCB is the operating system’s official file on a process. If the CPU forgets the process because it is no longer running, the kernel does not forget it, because the PCB preserves what the kernel needs to know.

What the reader should notice first is that the PCB is not just a box for saved registers. It is broader than that. It usually includes the process identifier, state such as running/ready/blocked, scheduling information such as priority or queue links, memory-management information, accounting data, open-file references, and pointers to resources owned by the process. Some systems separate per-process and per-thread structures, because multiple threads may share one address space while having distinct register sets.

This distinction matters. The register snapshot belongs more naturally to an *execution context* than to the abstract process as a whole. In a single-threaded model, that distinction is easy to ignore. In a multithreaded system, it becomes dangerous to ignore, because each thread needs its own PC, stack pointer, and register state even when threads share files and virtual memory.

The PCB solves a specific problem forced by multiprogramming: once a process is not currently on the CPU, there must still be a durable kernel object that remembers its status and how to bring it back.

A misconception worth killing early is that the PCB is somehow user-visible program data. It is not. It is a kernel data structure. User code does not directly manipulate it as an ordinary memory object.

## Definition 4: Scheduler

**Definition.** The **scheduler** is the operating-system component that chooses which ready execution context should run on a CPU next, according to a scheduling policy and current system state.

In plain technical English, the scheduler answers the question: *now that the CPU is available or must be reassigned, who gets it?*

The first thing to notice is the word **ready**. The scheduler does not choose among all existing processes indiscriminately. It chooses among contexts that are eligible to run. A blocked process waiting for disk input or a sleeping process waiting for a timer is not currently runnable and therefore should not be selected for immediate execution.

A second thing to notice is the difference between **policy** and **mechanism**. The scheduler’s mechanism is the code and data structures that pick a task from the ready set. The policy is the rule or objective being pursued: minimize average waiting time, maximize responsiveness, enforce priorities, guarantee fairness, and so on. Students often confuse these. “Round-robin” is a policy family. The ready queue and selection routine are mechanism.

The scheduler does not itself execute the user program directly. Its conclusion is a choice of next runnable context. That conclusion then feeds the context-switch mechanism.

The order of checks in scheduling reasoning typically looks like this. First, determine which contexts are in the ready state rather than blocked or terminated. Second, evaluate whatever attributes matter for the active policy: priority, virtual runtime, remaining quantum, deadline, affinity, and so on. Third, choose one context as the next to run on a given CPU. Fourth, if the chosen context is different from the current one, initiate a context switch. This ordering matters because policy is applied only to eligible candidates, and the switch is needed only if the winner is not already running.

## Definition 5: Context Switch

**Definition.** A **context switch** is the kernel-mediated transition in which the CPU stops executing one context, saves the state needed to resume it later, restores the state of another context, and transfers execution so the new context continues.

In plain technical English, a context switch is a handoff of the CPU’s identity. Before the switch, the hardware registers and program counter belong to one context. After the switch, they belong to another.

What the reader should notice first is that a context switch is a *mechanism of replacement*. It is not merely “the scheduler picking something.” The scheduler decides. The context switch performs.

A complete switch usually involves the following logical stages.

An event first causes entry into the kernel. The event might be a timer interrupt because the running process used up its time slice, a system call, an I/O trap, or a blocking condition such as waiting on a lock. Once in the kernel, the current context becomes known to the operating system. The kernel preserves the outgoing context’s live CPU state by saving registers, including the program counter and stack pointer, into kernel-managed memory associated with that context. The kernel updates that context’s state in its PCB or thread control block: perhaps from running to ready, or from running to blocked. The scheduler then examines runnable candidates and chooses a next context. The kernel restores the incoming context’s saved registers from its stored state. Finally, the kernel returns from trap or interrupt so the CPU resumes in the incoming context at its restored PC.

Each stage supports a specific conclusion. After saving registers, the old context is resumable. After updating process state, the kernel knows whether that context should remain eligible for later execution. After scheduling, the kernel knows which candidate should receive the CPU. After restoring registers, the CPU has become the new context at machine level. After returning to user mode or continuing kernel execution on behalf of the chosen context, real execution resumes.

A crucial distinction: not every transfer into the kernel is a context switch. A system call may enter the kernel and then return to the *same* process without switching to another. That is a mode switch or trap handling path, but not necessarily a context switch. Students blur these constantly. Kernel entry is common; context switching is specifically the replacement of one execution context by another.

## Definition 6: Overhead

**Definition.** **Overhead** is the portion of system work and elapsed time consumed by management activities required to support execution, rather than by the direct execution of the user-level computation being measured.

In plain technical English, overhead is the cost of making the system work as a system.

The first thing to notice is that overhead is not always “waste” in the sense of being optional. Much overhead is necessary. If you want fairness, protection, responsiveness, preemption, and virtual memory, you must pay certain administrative costs. The real question is whether the overhead is justified by the benefit and whether it is controlled.

For context switching, overhead includes the instructions required to enter the kernel, save state, update scheduler data structures, choose the next context, restore state, and return. It can also include indirect costs such as cache disruption, branch predictor disturbance, translation lookaside buffer effects, and lost locality. These indirect costs are often larger than the obvious save-and-restore instructions.

This is a major conceptual point: the direct switch path is not the whole cost. A switch can be “cheap” in instruction count and still expensive in performance because the incoming process may suffer cache misses and memory translation misses before it regains steady execution.

## How the Pieces Fit During Actual Resumption

The cleanest way to understand the cluster is to trace one forced suspension and later resumption.

Process A is currently running on a CPU core. At this instant, the hardware registers contain A’s live working state. The program counter contains the address of A’s next instruction. A timer interrupt arrives because the system uses preemptive scheduling and A’s quantum has expired.

The interrupt forces control into the kernel. This means the processor stops executing ordinary user instructions from A and begins executing privileged kernel code. At this moment, the operating system must preserve the fact that A was in the middle of a computation.

The kernel therefore saves A’s relevant register values into memory associated with A’s execution context. Among those saved values is A’s program counter. Without that saved PC, A could not later continue at the correct next instruction. The kernel also saves the stack pointer and status information, because continuing at the right instruction with the wrong stack or flags would still be incorrect.

The kernel then updates A’s bookkeeping in its PCB or thread control block. Since the interrupt was a time-slice expiration rather than a blocking event, A typically moves from the running state back to the ready state. That update matters because it tells the scheduler that A remains eligible to run again later.

Now the scheduler examines the ready set. Suppose process B has been waiting. According to the system’s policy, B is now selected. That choice is a scheduling decision, not yet a resumption.

The kernel now performs the incoming side of the context switch. It loads B’s saved register values from B’s stored context into the CPU registers. In particular, it restores B’s program counter and stack pointer. When the kernel returns from the interrupt path, the CPU does not go back to A. It resumes execution as B, at B’s restored PC, using B’s restored stack and other register contents.

Hours later in wall-clock time, but perhaps only milliseconds of CPU time later, the scheduler may select A again. At that point, the kernel restores A’s saved registers, including its program counter, and A continues as though it had simply been paused.

This description explains why the cluster should be understood as a chain.

The program counter identifies the continuation point. Saved registers preserve the machine context. The PCB provides the kernel’s durable record. The scheduler decides who runs. The context switch enacts that decision. The overhead is the cost of doing all of this often enough to share the CPU.

## Boundary Conditions and Edge Cases

The basic story becomes clearer when boundary conditions are made explicit.

One boundary condition is the difference between process switching and thread switching. If two threads belong to the same process, they typically share the same address space and many process resources, but they still require different register sets, stack pointers, and program counters. Switching between them still requires saving and restoring execution context, but some costs associated with changing address spaces may be smaller.

A second boundary condition is voluntary versus involuntary switching. A process may voluntarily yield because it blocks on I/O or waits for a mutex. In that case, the switch is prompted by the process’s inability or willingness to stop running. An involuntary switch occurs when the kernel preempts the process, often via a timer interrupt. In both cases, the mechanism of preserving and restoring context remains, but the state transitions differ. A blocking process usually moves from running to blocked, not to ready.

A third boundary condition is kernel-mode execution. If a process enters the kernel through a system call and the kernel completes the service quickly, the CPU may return to the same process with no context switch. Therefore “entered kernel” does not imply “switched process.”

A fourth boundary condition concerns what exactly is restored. The state required for correct resumption depends on architecture and kernel conventions. Some state may be eagerly saved on every switch; some may be deferred until first use. The general rule is simple: any state whose old value matters for future correct execution must either be preserved now or guaranteed recoverable later.

A fifth boundary condition is multiprocessor scheduling. On multiple cores, several contexts can run at once, one per core. The resumption problem still exists independently per core, and the scheduler may also care about processor affinity, load balancing, and migration costs. The cluster remains valid, but there are more CPUs and more queues.

## A Fully Worked Example

Consider a single-core system using round-robin scheduling with a time quantum of 4 milliseconds. Two CPU-bound processes, A and B, are ready. Assume that the direct cost of one context switch is 0.2 milliseconds, and ignore I/O for the moment.

At time 0, process A begins running. Its registers are live in the CPU. Its program counter points to the next instruction in A. B is ready but not running.

At time 4 milliseconds, A’s quantum expires. A timer interrupt transfers control to the kernel. The kernel saves A’s live registers, including its PC, into A’s stored context. Because A is still runnable and not blocked, the kernel marks A ready. The scheduler sees that B has been waiting and selects B. The kernel restores B’s saved registers, including B’s PC, and returns from the interrupt path into B. The switch itself consumed 0.2 milliseconds, so B effectively starts receiving CPU service at time 4.2 milliseconds.

B now runs until its own quantum expires at time 8.2 milliseconds. The same sequence occurs in reverse. The kernel saves B’s context, marks B ready, selects A, restores A’s registers, and resumes A at exactly the PC where A had previously been interrupted. That second switch consumes another 0.2 milliseconds, so A resumes at time 8.4 milliseconds.

What should you conclude from this example?

First, neither A nor B restarts from the beginning after being preempted. Each continues from its saved program counter. That is the entire meaning of correct resumption.

Second, the PCB or related thread structure must hold enough information that each process can survive periods off the CPU without losing identity or execution progress.

Third, the scheduler’s policy here is simple fairness by rotation. The scheduler is not preserving execution state; it is deciding turn-taking.

Fourth, the context-switch cost is real. In each 4.0 milliseconds of nominal quantum, the system also pays 0.2 milliseconds to change ownership of the CPU. If a switch occurs after every quantum, the direct overhead fraction is approximately

\[
\frac{0.2}{4.0 + 0.2} \approx 4.76\%.
\]

If the quantum were reduced to 1 millisecond with the same switch cost, the direct overhead fraction would become

\[
\frac{0.2}{1.0 + 0.2} \approx 16.67\%.
\]

This teaches a general lesson, not just an arithmetic exercise. Smaller quanta improve responsiveness because no process waits as long for its next turn, but they increase switching overhead. Larger quanta reduce overhead but make the system feel less responsive and can hurt interactive workloads. Scheduling policy is therefore constrained by mechanism cost.

That tradeoff is one of the deep reasons operating systems cannot treat switching as free.

## What Is Actually Being Saved, and Why It Is Enough

A student often asks: if a process has megabytes or gigabytes of memory, how can the OS save it during a context switch? The answer is that the process memory is generally *not* copied on each switch. Most of the process state already persists in RAM. The issue is not persistence of memory; the issue is preservation of the CPU’s transient live state.

The registers matter because they hold values that may not yet have been written back to memory and because the program counter and stack pointer determine exactly how to continue execution. User memory remains in the process’s address space. When the process runs again, it sees that same memory image, subject of course to changes it or others made meanwhile.

This distinction helps separate context switching from swapping. Context switching changes which context owns the CPU. Swapping, in classic terminology, moves memory images between RAM and secondary storage. They are different mechanisms solving different scarcity problems.

## Common Misconceptions That Cause Trouble Later

One common mistake is to think the PCB *is* the process. The process is an executing program together with its resources and state. The PCB is the kernel’s structured record about it.

Another common mistake is to think the scheduler and context switch are the same thing. They are not. The scheduler decides *who*. The context switch performs the handoff.

A third mistake is to think any kernel entry is a context switch. A process can make a system call, spend time in kernel mode, and return to itself. No other context need run.

A fourth mistake is to think the program counter alone is enough for resumption. It is essential but insufficient. Continuing at the right instruction with the wrong general registers, wrong stack pointer, or wrong flags can corrupt execution.

A fifth mistake is to think overhead is only the few instructions that save and restore registers. The lost cache locality after a switch is often a major part of the real performance penalty.

A sixth mistake is to imagine that processes are the only schedulable objects. Many modern systems schedule threads, not whole processes, though textbook introductions often start with processes because the conceptual story is simpler.

## Why This Topic Must Appear Early in Operating Systems

This topic belongs early because many later operating-system ideas quietly rely on it.

You cannot understand preemption without knowing how a computation is stopped and resumed. You cannot understand threads without understanding that each thread needs its own saved register set and program counter. You cannot understand synchronization performance without understanding that blocking and waking induce scheduler activity and possibly context switches. You cannot understand CPU scheduling policies in a serious way unless you also understand the mechanism cost they incur. You cannot understand interrupts, traps, or kernel entry paths without seeing how they interact with preserving execution state.

In other words, the resumption cluster is a bridge topic. It connects machine-level execution state to operating-system policy.

## Conceptual Gaps and Dependencies

This topic assumes that the student already knows what a CPU register is, what memory addresses are, how ordinary sequential instruction execution works, what privilege separation between user mode and kernel mode means at a basic level, and why a single CPU core cannot literally execute multiple instruction streams at once. It also assumes some familiarity with interrupts and with the idea that a process has code, data, and a stack.

For many students at this stage, the weakest prerequisite is the difference between architectural state and memory state. Students often vaguely know that registers exist, but they do not yet feel why registers are the fragile part that must be saved during switching. Another weak prerequisite is the distinction between process and thread. If that distinction is not firm, the role of the PCB versus per-thread saved context becomes blurred.

Nearby concepts referred to here but not fully taught include the interrupt/trap mechanism, system-call entry and return, user mode versus kernel mode transitions, ready and blocked queue implementations, address-space switching, TLB behavior, cache locality, and the details of specific scheduling algorithms such as shortest-job-first, priority scheduling, multilevel feedback queues, and completely fair scheduling.

Homework-relevant and lecture-relevant facts that are not covered by this explanation alone include the exact fields of a PCB in a particular operating system, architecture-specific calling and trap conventions, the difference between dispatcher and scheduler in some textbook vocabularies, the distinction between process context switch and thread context switch in a given kernel, and the quantitative analysis of waiting time, turnaround time, and response time under specific scheduling policies.

Immediately before this topic, a student should study machine execution state, registers, stack behavior, interrupts, traps, and the basic definition of process versus thread. Immediately after this topic, the best next concepts are CPU scheduling policies, thread models, synchronization with blocking and wakeup, and the performance consequences of locality and multiprocessor load balancing.

## Retain / Do Not Confuse

### Retain

- The program counter is the exact continuation point: it tells the CPU which instruction executes next.
- Saved registers are necessary because the hardware registers can belong to only one running context per core at a time.
- The PCB is the kernel’s durable record of a process; it stores management information and links to resumable execution state.
- The scheduler chooses the next runnable context according to policy.
- The context switch is the mechanism that saves one context and restores another.
- Overhead is the cost of this management work, including indirect costs such as lost cache locality.
- Correct resumption requires more than saving the PC alone; the relevant machine state must be restored consistently.

### Do Not Confuse

- Do not confuse a **scheduler decision** with a **context switch**. One chooses; the other performs.
- Do not confuse **kernel entry** with **context switching**. A system call can enter and exit the kernel without switching to another process.
- Do not confuse a **process** with its **PCB**. The PCB describes and tracks the process; it is not the process itself.
- Do not confuse **context switching** with **swapping**. One changes CPU ownership; the other moves memory images between storage levels.
- Do not confuse the **program counter** with a source-code line number.
- Do not confuse **direct switch instructions** with the full performance cost; caches and translation state matter too.
