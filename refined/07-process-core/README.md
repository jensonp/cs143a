# Process Core Cluster

## Introduction: Why the Process Must Be Introduced

Operating systems exist because a computer is not running just one activity at one time in the simple, direct way a beginner first imagines. Even on a machine with a single CPU core, many independent computations must appear to make progress: a shell waits for input, an editor responds to keystrokes, a compiler translates code, a web browser loads pages, and background services react to external events. The machine therefore needs a disciplined way to represent “an executing program together with everything the operating system must know in order to manage it.” That representation is the **process**.

This topic appears early because several later ideas depend on it. Scheduling needs a unit that can run, wait, and be resumed. Memory management needs a unit that owns an address space. Security and resource control need a unit to which permissions, files, and accounting can attach.

So this chapter answers one central question: if a program on disk is passive, what is the live operating-system object that is actually executing, owning resources, and moving through states like ready, running, waiting, and terminated? The answer is the **process**. The rest of the chapter develops that object through four dimensions: program versus process, process address space, process rights, and process state.

This chapter deliberately revisits **address space** and **rights** as properties of a process even if earlier clusters already introduced them separately. Read those sections here as **process-centered synthesis**, not as the first place those ideas ever appear.

---

## 1. Program vs Process

### Formal definition: Program

A **program** is a passive, persistent description of computation, usually stored in an executable file. It contains machine instructions and often includes static data, metadata, symbol information, and references needed for loading and execution.

### Interpretation

In plain technical English, a program is not “something currently doing work.” It is closer to a recipe than to cooking. It is an object on disk. It can be copied, moved, inspected, and launched. But by itself it is not consuming CPU time, it has no current value of the program counter, no call stack, no open files, and no current execution state.

The first thing to notice is the word **passive**. A program exists even when nobody is running it.

### Formal definition: Process

A **process** is an active execution context created from a program, together with the operating system state required to manage that execution. This state typically includes an address space, processor context, resource ownership information, security credentials, accounting data, and a current execution state.

### Interpretation

What this is really saying is that a process is not just code. It is code **plus a current run-time situation**. A process has a present moment. It has a “where am I in the instructions?” value. It has memory that belongs to this execution. It has rights and restrictions. It may have open files, pending signals, a parent process, and a place in the scheduler’s queues.

The first thing to notice is the word **active**. A process is the operating system’s unit of managed execution.

### Why the distinction matters

Students often casually say “the program is running,” and in everyday speech that is acceptable. But conceptually it hides a critical distinction.

The same program file can give rise to many different processes. If ten users launch the same text editor executable, there are ten processes, not one. The executable code may be identical, but each process has its own run-time state. Each one may have different command-line arguments, different current directories, different environment variables, different open files, different heap contents, different stack contents, and different security credentials.

The reverse distinction matters too: a process may change state dramatically while still being “the same process.” It can allocate more heap memory, open more files, block for input, receive a signal, or even replace the program it is executing with another one through an operation such as `exec`. The process identity is an operating-system-managed execution object. The program image it is currently running is only one part of that story.

### What is fixed and what varies

For a given executable file, some things are fixed at the program level: the instruction bytes on disk, the intended entry point, and the static layout the loader understands.

For a process created from that program, many things vary:

- the process identifier,
- the current instruction pointer,
- the register contents,
- the stack frames,
- the heap contents,
- the mapped libraries,
- the open files,
- the user and group identity,
- the scheduling state,
- and the events it is waiting for.

This fixed-versus-varying distinction is one of the cleanest ways to remember the difference. A program is the reusable template. A process is one live instance of execution.

### Common misconception: “A process is just a program in memory”

That is incomplete. A process does involve memory, but it is not reducible to memory alone. If you only remembered the bytes in RAM and forgot the CPU register state, process identifier, open file table, credentials, signal dispositions, scheduling state, and parent-child links, you would not have enough information to resume and manage the execution correctly. The process is an operating system object, not merely a region of memory.

### Common misconception: “Two processes running the same program are the same except for PID”

No. They may differ in nearly every run-time-relevant way. One may be blocked on keyboard input while another is computing. One may have administrator privileges while another does not. One may have already modified its heap or stack substantially. Shared code does not imply shared execution state.

---

## 2. From Program to Process

To understand the rest of the chapter, it helps to look at the creation path in conceptual order.

First, there is an executable program on disk. The operating system receives a request to run it. That request may come from a shell, a graphical launcher, a service manager, or another program.

Then the operating system creates a new process object. At this stage it allocates kernel-side bookkeeping structures: an identifier, scheduling metadata, a place to store processor context, and structures for credentials and resources.

Next, it creates or prepares the process address space. The code and data of the program are mapped into that address space. A stack is set up. The initial heap region is arranged. Shared libraries may be mapped. Arguments and environment strings are placed where the process can access them.

Then the operating system initializes the processor context for first execution. There must be an initial program counter value, meaning the address of the first instruction to execute, and an initial stack pointer value. General-purpose registers are initialized to whatever conventions the architecture and loader require.

Finally, the process is admitted to the scheduler, usually entering the **ready** state. It exists now as a live entity that may later be selected to run.

This creation story already hints at the three major dimensions of a process:

- memory structure,
- rights and ownership,
- dynamic execution state.

---

## 3. Process Address Space

### Why this subsection is shorter than the dedicated address-space chapter

A dedicated earlier chapter has already taught address spaces, virtual addresses, physical memory, translation, protection, and base/limit-style reasoning. This subsection should therefore not reteach all of that from scratch. Its job here is narrower: to explain what the address space contributes to the **process** as a live OS object.

### Formal definition

A **process address space** is the protected virtual memory world attached to one process, including the currently valid mappings, the access permissions on those mappings, and the interpretation of the process’s memory references relative to that mapping state.

### Interpretation

In plain technical English, this means the process does not just “have some memory.” It has a particular memory view that belongs to this execution instance. The same executable file can produce many processes, and each process can have a different address space state even when the code is initially similar. That difference may come from different heap growth, different mapped libraries, different file mappings, different stacks, different arguments, or later copy-on-write divergence after process creation.

The first thing to notice is that the address space is part of what makes a process a distinct managed execution object. A process is not just program text plus registers. It is also a specific protected memory world in which those registers and instructions are interpreted.

### What matters here from the earlier memory chapter

The earlier address-space chapter already established that:
- virtual addresses are process-relative,
- translation and protection are linked,
- and a process can behave as if it has a private orderly memory view even though physical memory is shared.

What this process chapter adds is the OS-level integration:

- the address space belongs to this process instance,
- it is part of what the kernel must preserve and manage over time,
- and it is one of the process-level objects that later operations such as `fork`, `exec`, context switching, and memory growth will affect.

### Typical regions, but now seen as process-owned state

The code region, static data, heap, stack, and mapped regions still matter, but here the teaching point is ownership and evolution rather than layout alone.

The heap matters because its contents depend on this process’s execution history.

The stack matters because it holds this process’s current call-state history.

Mapped regions matter because they help explain why one process can share code with another while still remaining a distinct process.

### Boundary condition worth retaining here

A process’s address space is not only a static diagram. It changes over time. Heap growth, new mappings, copy-on-write behavior, page faults, and protection changes all belong to the ongoing state of the process. That is one reason a process cannot be reduced to “a program in memory.”

### Common misconception

Do not confuse “process address space” with “all of physical RAM used by the program.” The address space is the process-owned virtual memory world. Physical storage is only the current lower-level realization of some of that world.

## Do Not Confuse: Process State, Process Rights, and Process Address Space

Process state answers what the process can do next relative to CPU service and waiting. Process rights answer what protected operations the OS will allow the process to perform. Process address space answers what memory world belongs to that process. These are different dimensions of one OS object, not three competing definitions of the same thing.

---

## 4. Worked Example: Two Processes from One Program

Consider a program `editor` stored on disk. Two users launch it independently.

The program file is one object. There is one set of executable bytes on disk.

Now the operating system creates **Process A** and **Process B**.

Both processes may map the same underlying read-only code pages for efficiency. That means the instructions loaded from the executable can, in many systems, be shared physically while remaining logically part of each process’s address space.

But now observe what differs.

Process A has process identifier `PID_A`. Process B has process identifier `PID_B`.

Process A has its own stack. Its current function calls and local variables live there. Process B has a different stack with different function calls and different local values.

Process A’s heap contains a document buffer for `notes.txt`. Process B’s heap contains a different document buffer for `report.txt`.

Process A may have opened file descriptor entries pointing to the user’s home directory and `notes.txt`. Process B may have a different current working directory and different open files.

Process A might be running under one user identity and Process B under another. Therefore the rights checks for file access may differ even though the same executable program is being used.

Process A may currently be in the running state. Process B may be waiting for keyboard input.

This example teaches the general rule: **shared program image does not imply shared process state**. The process is the live, isolated, managed execution instance.

---

## 5. Process Rights

### Formal definition: Process rights

A process’s **rights** are the set of permissions, privileges, ownership credentials, and access capabilities that determine which operations the operating system will allow that process to perform on protected resources and system services.

### Interpretation

What this really means is that the operating system does not merely ask “what instruction is this process trying to execute?” It also asks “who is this process, under what authority is it acting, and is this operation permitted?”

The first thing to notice is that rights are about **allowed actions on protected objects**, not just about memory. A process may be denied access to files, devices, network actions, signals, or privileged system operations even while it continues to execute ordinary user-level instructions perfectly well.

### Why rights are attached to the process

The operating system must enforce protection boundaries between users, services, and applications. It therefore needs a unit to which authority can be attached. The process is a natural unit because it is the executing entity that actually requests services through system calls.

When a process asks to open a file, create a child, send a signal, map a device, or change its identity, the operating system checks the process’s credentials and associated permissions.

### Typical components of process rights

The exact model depends on the operating system, but conceptually a process often carries:

- a user identity,
- one or more group identities,
- privilege flags or capabilities,
- access control context,
- open-handle rights derived from previously authorized operations,
- and resource limits.

These should not be collapsed into one vague idea of “permissions.” They are related but not identical.

#### Identity

A process usually executes on behalf of some user or service account. This identity is used in many access checks.

The central observation is that rights are often not inherent in the program file itself. The same executable can run with different effective identities in different situations.

#### Privilege or capability

Some operations are restricted not merely by ownership but by special authority. Examples include loading kernel modules, binding certain ports, or changing system-wide settings.

This tells us that ordinary file read/write permission and elevated system privilege are different layers of control.

#### Inherited rights through open objects

If a process already has an open file descriptor or handle to some resource, that handle may embody a specific authorized access mode acquired earlier.

This distinction matters. Sometimes a process can use a resource not because it would pass a fresh global permission check right now, but because it already possesses a valid reference obtained legitimately earlier.

#### Resource limits

A process may be allowed in principle to allocate memory or create files, but only up to configured limits.

This is important because “permitted” is not the same as “unbounded.” Rights and quotas interact.

### How an access check is conceptually performed

Suppose a process requests a protected operation such as opening a file for writing. The operating system conceptually checks several questions.

First, what object is being requested? The exact file, device, socket, or kernel service must be identified.

Second, what operation is requested? Reading, writing, executing, deleting, signaling, mapping, and administrating are different actions and may have different rules.

Third, which process is making the request, and what credentials does it currently hold? The process’s effective identity, group set, capability set, and possibly security labels matter here.

Fourth, what protection rules apply to this object? That may involve file permissions, access control lists, capability checks, namespace rules, mandatory access control, or device-specific logic.

Fifth, do any boundary conditions or overrides apply? For example, is the file system mounted read-only? Has the process exceeded a quota? Is the requested operation blocked by a sandbox? Is the object locked or already in use in a conflicting way?

Only after all relevant checks pass does the operation proceed.

### Process rights vs memory protection

These are often confused.

Memory protection answers questions like: may this process read or write this virtual page in its own address space? Or may it access some mapped shared page?

Process rights in the broader operating system sense answer questions like: may this process open this file, send a signal to that process, create raw sockets, or issue this privileged system call?

So memory permissions are one component of the protection system, but they are not the whole rights model.

### Rights can change over time

A process’s rights are not always fixed forever from creation to termination.

The process may drop privileges intentionally. It may execute a new program image with changed effective credentials. It may inherit handles from a parent. It may gain access to a resource by opening it. It may lose opportunities because quotas are consumed.

So process rights are dynamic, though not arbitrarily so: they change according to controlled system rules.

### Failure modes and misconceptions

One common mistake is to think that if a user can run a program, then the process may do whatever the program’s code requests. No. The code can request; the operating system decides.

Another common mistake is to think rights belong purely to the executable file. In fact the running context matters deeply. The same program launched by different users may produce processes with different rights.

A third mistake is to treat all failures as “permission denied.” Some failures come from exhausted limits, missing object existence, incompatible sharing modes, or sandbox restrictions. Operational denial can arise for many reasons beyond a single permission bit.

---

## 6. Process State Model

The process state model answers a different question from the address-space and rights sections. Those sections describe what a process **has**. The state model describes what the process is **currently doing relative to execution and waiting**.

The user requested the classic five-state model:

- new,
- ready,
- running,
- waiting,
- terminated.

This is a simplified but foundational model. Real systems may include more detailed states, but this one captures the essential logic.

### Formal definition: Process state

A **process state** is an abstraction representing the current stage of a process in its lifetime with respect to creation, eligibility for CPU execution, actual CPU execution, waiting for an event, or completion.

### Interpretation

In plain technical English, the process state tells us where the process stands in the operating system’s control flow. Is it being created? Is it eligible to run but not currently selected? Is it on the CPU right now? Is it blocked because something external must happen first? Or is it finished and no longer a live execution?

The first thing to notice is that state is about **current execution status**, not about what program the process runs or what memory it owns.

---

## 7. The Five States in Order

## New

### Formal definition

A process is in the **new** state after it has been created conceptually but before it has been fully admitted to normal execution competition.

### Interpretation

This means the operating system is in the act of bringing the process into existence. Necessary structures are being initialized, resources are being allocated, credentials are being set, and the execution context is being prepared.

The key thing to notice is that a new process exists as an operating-system object, but it is not yet simply sitting in the ordinary pool of runnable work.

### What checks matter here

During this stage the system must ensure that creation is valid and possible.

It must check whether there are enough resources to create the process object and its initial memory structures.

It must determine the initial credentials and inheritance relationships.

It must set up the address space and initial execution context correctly.

If these preparations succeed, the process can move onward. If they fail, the process may never become runnable at all.

### Boundary conditions

Process creation can fail because the system has reached limits on process count, memory, kernel bookkeeping capacity, or policy constraints.

This is important: not every requested process reaches the ready state.

---

## Ready

### Formal definition

A process is in the **ready** state when it is fully prepared to execute and is eligible to use the CPU, but is not currently the process being executed on a CPU core.

### Interpretation

This means the process is not waiting for any external event. It has everything it needs except the CPU itself. The scheduler may choose it next, but it must compete with other ready processes.

The first thing to notice is the distinction between **able to run** and **actually running**. Ready means the first, not the second.

### What checks matter here

For a process to remain ready, it must have no unsatisfied blocking condition. It must not be waiting on I/O, a timer, a lock, or some other event. Its execution context is saved and available. It simply has not been granted CPU time at this instant.

### Common misconception

Students often say a ready process is “idle.” That is misleading. It is not idle in the sense of being inactive by choice. It is prepared and eligible, but not selected. The bottleneck is CPU allocation.

---

## Running

### Formal definition

A process is in the **running** state when one of its threads of execution is currently executing instructions on a CPU core.

### Interpretation

This is the active, on-CPU state. The process is no longer merely eligible; it is currently being served by the processor.

The first thing to notice is that on a single-core system, only one process can be in this state at a time if we ignore kernel subtleties. On a multicore system, several processes may be running simultaneously on different cores.

### What changes while running

While running, the process may execute ordinary instructions, issue system calls, take traps or faults, allocate memory, manipulate files, or reach completion.

But it may also leave the running state for several different reasons:

- it may be preempted because its time slice ends,
- it may voluntarily block for I/O or some other event,
- it may terminate,
- or it may be interrupted and later resumed.

### Common misconception

Running does not mean “will continue until completion.” The operating system may take the CPU away long before the process’s logical job is finished.

---

## Waiting

### Formal definition

A process is in the **waiting** state when it cannot proceed until some external event or condition occurs.

### Interpretation

This means the process is blocked. Giving it the CPU right now would not help, because the next needed step depends on something not yet true. Perhaps the process requested keyboard input, disk I/O completion, network data arrival, timer expiration, child exit, or lock availability.

The first thing to notice is the difference between ready and waiting:

- a ready process could run immediately if chosen,
- a waiting process could not make useful forward progress even if chosen, because a required condition has not yet been satisfied.

### What is being checked

There is always some blocking condition behind the waiting state. Conceptually the operating system is tracking a predicate of the form: “Has the event this process is waiting for happened yet?”

As long as the answer is no, the process remains waiting.

When the answer becomes yes, the process can be transitioned back to ready.

This is one of the most important logical distinctions in the whole state model. A waiting process is not merely unlucky in scheduling; it is **not yet runnable**.

### Common misconception

Students often confuse waiting with ready because both states are off the CPU. But they differ for a deep reason: ready is blocked by scheduler choice, waiting is blocked by an unsatisfied event dependency.

---

## Terminated

### Formal definition

A process is in the **terminated** state after it has finished execution or has been forcibly ended, and is no longer a live executable entity.

### Interpretation

This means the process’s running life is over. It will not execute further instructions as a normal runnable process.

The first thing to notice is that some process-related information may still exist briefly after termination. The operating system may retain exit status and accounting information until the parent collects it or until cleanup completes.

So “terminated” does not always mean “all traces removed instantly.”

### Ways to reach termination

A process may terminate by normal completion, by calling an explicit exit operation, by receiving a fatal signal or exception, by violating a protection rule, or by being killed by another authorized entity.

### Boundary condition

In many systems there is an intermediate practical notion after death but before full cleanup, such as a zombie process in Unix-like systems. That detail is beyond the exact five-state model but is important not to lose conceptually. The simplified model compresses several cleanup subtleties into “terminated.”

---

## 8. State Transitions: What Causes Movement Between States

The state names are useful, but the real understanding comes from the transitions.

### New to Ready

This transition happens when creation and initialization succeed.

The operating system has finished enough setup that the process can now compete for CPU time. The address space exists in usable initial form. Initial context is prepared. Necessary bookkeeping is complete.

If setup fails, this transition never occurs.

### Ready to Running

This transition happens when the scheduler selects the process for execution on a CPU core.

Nothing about the process’s logical work has necessarily changed. What changed is the scheduler’s allocation decision.

### Running to Ready

This happens when the process is still able to continue but is taken off the CPU. In a preemptive system, this often occurs because the time slice ends or because a higher-priority process becomes eligible.

The critical insight is that the process did not become blocked. It remains runnable. It simply ceased to be the one currently running.

### Running to Waiting

This happens when the process reaches a point where progress depends on some event not yet completed. It may request input, wait for disk completion, sleep until a timer expires, or wait on synchronization.

The critical insight is that CPU removal here is not merely scheduling competition. The process cannot proceed until the event occurs.

### Waiting to Ready

This happens when the awaited event occurs. Input arrives, I/O completes, the timer expires, the lock becomes available, or the child exits.

Notice the exact conclusion allowed by this transition: the process is not automatically running now. It has merely become eligible to run again.

### Running to Terminated

This occurs when execution ends, normally or abnormally.

### Possible simplified diagram in words

The lifetime flow is therefore:

A process begins in new. If initialization succeeds, it enters ready. From ready it may be scheduled into running. From running it may return to ready if preempted, move to waiting if blocked, or move to terminated if finished. From waiting it returns to ready when the needed event occurs. Eventually some running period leads to termination.

---

## 9. Fully Worked Example of the State Model

Consider a simple command-line program that reads a file, processes its contents, and prints a result.

At the start, the shell asks the operating system to create a new process for this program. During the **new** state, the operating system allocates the process structure, sets up the address space, loads the code, initializes the stack with arguments, assigns credentials, and prepares an initial CPU context.

Once that setup completes, the process enters **ready**. At this moment it has not executed any user instructions yet, but it could do so immediately if the scheduler chose it.

The scheduler then selects it, so it enters **running**. Now it begins executing startup code and eventually reaches the code that requests the input file to be opened and read.

Suppose the read request cannot complete instantly because the relevant disk data is not yet available in memory and an I/O operation must occur. The process issues the request and then enters **waiting**. Here the important point is that the process is off the CPU not because it lost a competition, but because it has no useful next instruction until the file data arrives.

Later the disk operation completes. The operating system marks the blocked condition satisfied, so the process moves from **waiting** to **ready**. Notice it does not jump directly to **running**. It must wait until the scheduler gives it CPU time again.

When chosen again, it returns to **running** and now processes the file contents in CPU-bound computation. Suppose its time slice expires before it finishes. Then it transitions from **running** to **ready**. This time the reason is not blocking but preemption. The process is still perfectly runnable.

Eventually it is scheduled again and continues in **running**. After printing the result, it calls exit and becomes **terminated**.

This example teaches several general lessons.

First, a process can leave running for qualitatively different reasons, and those reasons determine whether the next state is ready or waiting.

Second, waiting-to-ready means “the dependency cleared,” not “the process got the CPU.”

Third, ready-to-running is purely a scheduling decision, while running-to-waiting is usually driven by a program action plus an unavailable resource or event.

---

## 10. Relating the Four Core Ideas

Now we should connect program vs process, address space, rights, and state into one coherent picture.

A **program** is the passive executable template.

A **process** is the live execution instance created from that template.

The **process address space** is the protected virtual memory world in which that live instance executes. It contains code, data, heap, stack, and mappings, with permissions controlling the types of access allowed.

The **process rights** determine what system-level operations that live instance is allowed to request and perform beyond mere instruction execution inside its own address space.

The **process state** tells where that live instance stands over time in its execution lifecycle: being created, eligible to run, actually running, blocked waiting for an event, or finished.

These are not competing definitions of process. They are different aspects of the same operating-system object.

A process therefore answers four kinds of questions at once:

- What code is this execution associated with?
- What memory world does it currently have?
- What is it allowed to do?
- What is it doing right now relative to scheduling and waiting?

If one of these dimensions is missing, the concept is incomplete.

---

## 11. Important Distinctions That Students Commonly Confuse

### Program vs process

A program is passive and stored. A process is active and executing.

### Process vs processor state alone

Registers matter, but the process is more than registers. It also includes memory mappings, resources, credentials, and scheduler-visible state.

### Ready vs waiting

Both are off the CPU. But ready means “can run now if chosen,” while waiting means “cannot run usefully until some event occurs.”

### Memory permissions vs process rights

Page access permissions are about what memory operations are legal in mapped memory. Process rights are broader and govern system-protected operations like file access and privileged services.

### Same program vs same execution

Multiple processes may run the same program while being different in identity, memory contents, open resources, state, and authority.

### Terminated vs fully erased

A process may be dead as an execution entity while some bookkeeping remains temporarily until the operating system or parent completes cleanup.

---

## 12. Why This Topic Matters for Later Operating Systems Material

This topic supports almost everything that follows in operating systems.

Scheduling assumes the ready/running/waiting distinctions and operates over processes or threads.

Context switching makes no sense until one understands that each process has saved execution context and an address space.

Virtual memory extends the address-space discussion into paging, replacement, protection, and sharing.

System calls and protection extend the rights discussion into kernel/user mode, access control, and privilege transitions.

Interprocess communication assumes that separate processes are isolated by default and must use controlled mechanisms to exchange information.

Process creation, exit, waiting, and parent-child structure all build directly on this foundation.

Threads later refine the picture by separating “unit of resource ownership” from “unit of CPU execution” more carefully, but that refinement is much easier once the basic process model is solid.

---

## Conceptual Gaps and Dependencies

This topic assumes several prerequisites.

It assumes you already understand, at least roughly, what a CPU executes: machine instructions, control flow, function calls, and the existence of registers such as the program counter and stack pointer. It assumes basic memory ideas such as variables occupying storage, the difference between code and data, and why function calls need stack-like behavior. It also assumes some notion that the operating system mediates access to hardware and protected resources.

For many students at this stage, the weakest prerequisite is usually **virtual memory intuition**. They may know that addresses exist but not yet grasp the difference between virtual addresses and physical memory. That weakness makes address-space explanations feel magical. Another common weak prerequisite is the distinction between a running computation and the executable file on disk; many students still use “program” and “process” interchangeably. A third weak area is permission structure: students may think permissions are just file bits and may not yet appreciate the broader idea of credentials, capabilities, and process-level authority.

This topic also refers to several nearby concepts without fully teaching them. It touches registers and context switching without fully explaining how a kernel saves and restores CPU state. It refers to the scheduler without teaching scheduling policies such as round robin, priority scheduling, fairness, or starvation. It mentions paging and memory mappings without teaching page tables, translation lookaside buffers, page faults in depth, or replacement policies. It refers to privileges and access control without fully developing user mode versus kernel mode, system call mechanics, or detailed security models.

Homework or lecture settings often require additional facts not covered here in full detail. For example, you may be asked to draw a process state transition diagram, distinguish CPU-bound from I/O-bound behavior, explain fork/exec/wait on Unix-like systems, name what is stored in a process control block, compare processes and threads, or explain how context-switch overhead arises. Those are natural extensions of this chapter, but they require details beyond the conceptual foundation presented here.

Immediately before this topic, a student should study machine execution basics: CPU, instructions, registers, memory hierarchy at a simple level, function calls and stack behavior, interrupts or traps at a rough conceptual level, and the basic purpose of the operating system as a resource manager and protection boundary.

Immediately after this topic, the best concepts to study are the process control block, context switching, CPU scheduling, threads, and virtual memory. Those topics build directly on what a process is, what state it can be in, and what memory and rights structure it carries.

## Retain / Do Not Confuse

Retain these ideas. A program is a passive executable description; a process is a live managed execution instance. A process includes more than code in memory: it includes address space, CPU context, resources, rights, and execution state. The address space is a protected virtual memory view, not simply raw physical RAM. Process rights govern what operations the operating system will permit. In the five-state model, ready means able to run but not currently running, while waiting means blocked on an event and not yet runnable.

Do not confuse these pairs. Do not confuse program with process. Do not confuse ready with waiting. Do not confuse memory-page permissions with general operating-system access rights. Do not confuse terminated with instantly erased. Do not confuse two processes running the same program with one shared execution. Those confusions cause a large fraction of early operating-systems mistakes.
