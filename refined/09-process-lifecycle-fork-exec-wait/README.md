# Process Lifecycle Cluster in Operating Systems: Parent, Child, Process Creation, `fork`, `exec`, `exit`, `wait`, Zombie, Orphan

## Why this cluster exists

Operating systems are not only collections of files, memory, and devices. They are also systems for **managing ongoing activities**. A running program is not merely code stored on disk; it is an execution context with memory, processor state, open files, scheduling metadata, security identity, and a place in a larger tree of processes. The concepts in this cluster—**parent**, **child**, **process creation**, **`fork`**, **`exec`**, **`exit`**, **`wait`**, **zombie**, and **orphan**—belong together because they answer one continuous question:

**How does the operating system bring a new process into existence, let it run, let it change what program it is running, and then clean it up correctly when it finishes?**

This material must be introduced once you already know what a **process** is and how it differs from a mere program file. The earlier question that forces this topic to appear is simple: if processes are running entities, **where do they come from, how are they related, and what exactly happens when one ends?** You cannot reason well about shells, pipelines, daemons, background jobs, login sessions, servers, or process synchronization until this lifecycle is understood as one connected mechanism.

## Local Working Terms Used in This Chapter

Three terms need local working definitions here because they matter to the lifecycle logic itself.

**Copy-on-write** means the parent and child are allowed to behave *as if* they each received separate memory copies after `fork`, while the implementation may delay real copying until one of them writes to a shared page. The local conceptual point is logical separation of memory, not immediate physical duplication of every page.

**Inherited open-file state** means that after `fork`, the child receives file-descriptor entries that may refer to the same underlying open-file kernel object as the parent’s corresponding entries. The local conceptual point is that “descriptor copied” does not automatically mean “underlying file state unshared.”

To **reap** a child means to collect its recorded termination status with `wait`-style logic so the kernel can finally remove the child’s remaining zombie bookkeeping entry. The local conceptual point is that child death and final cleanup are related but distinct events.

The large-scale role of this topic inside operating systems is that it explains how the kernel maintains control over computation over time. The kernel is not just scheduling anonymous work; it is managing a structured population of processes with inheritance, identity, and cleanup obligations.

## The process as the central object

### Formal definition: process

A **process** is an executing instance of a program together with the operating-system-managed state required to run it.

### Interpretation

What this is really saying is that a process is not just “the program.” The program file on disk is passive. A process is active. It includes the currently loaded code, the current register state, a virtual address space, open file descriptors, environment variables, credentials, signal dispositions, accounting information, and a kernel data structure that lets the operating system track and schedule it.

The first thing to notice is that **many processes can come from the same program file**, and one process can even stop running one program and start running another without ceasing to be the same process in the kernel’s bookkeeping sense. That second fact is exactly why the distinction between `fork` and `exec` matters.

## Program versus process

A dangerous early confusion is to treat “program” and “process” as interchangeable. They are not. A **program** is typically a file containing machine instructions and related metadata stored on disk. A **process** is a live execution context. The program is what may be loaded. The process is what is loaded and running.

This distinction matters because when a process calls `exec`, the program it runs changes, but the process identity in the kernel does not vanish and get recreated from nothing. Conversely, when a process calls `fork`, a new process appears even though, at the moment of creation, both processes may be associated with the same program image.

So, in this cluster, what is fixed and what varies?

What is fixed across many of these steps is the kernel’s need to preserve a coherent record of each process: its identity, parentage, state transitions, and resource ownership. What varies is the process’s address space, the specific program image inside it, whether it is running or terminated, and whether its parent is still alive.

## Parent and child

### Formal definition: parent process

A **parent process** is a process that creates another process.

### Interpretation

This means that parenthood is not a moral or permanent status; it is created by a specific event of process creation. A process becomes a parent by causing the kernel to create a new process on its behalf.

### Formal definition: child process

A **child process** is a process created by another process.

### Interpretation

A child process begins life with a direct ancestral relation to the creator. The important thing to notice first is that the parent-child relation is a **kernel-recorded relationship**, not merely a similarity of code or purpose. A shell creates a child when it launches a command. A server may create children to handle requests. A test harness may create children to isolate failures.

Parent and child are often similar immediately after creation, but they are not the same process. They have different process identifiers, separate kernel records, and separate futures.

## Process creation as a kernel event

### Formal definition: process creation

**Process creation** is the operating system action by which a new process control structure and execution context are established, producing a distinct schedulable entity.

### Interpretation

This definition says that the operating system does not merely “start more instructions.” It creates a new managed object. The kernel allocates bookkeeping structures, assigns an identifier, records parentage, arranges memory mappings, establishes an initial execution state, and makes the new process eligible to run.

The thing to notice here is that process creation is not only about computation. It is about **administrative structure**: who owns the new process, what resources are inherited, what happens on termination, and how the parent can learn the child’s fate.

In Unix-like systems, the classic model separates two logically distinct needs:

First, create a new process.

Second, possibly replace the program image inside that process.

These are handled by `fork` and `exec` respectively.

## Why `fork` and `exec` are separate

At first glance, students often ask why there are two steps. Why not have one operation that directly says “run this new program”? The answer is conceptual and practical.

The parent often wants the child to inherit some things but not others. For example, the parent may want to redirect standard input or output, close some file descriptors, change process groups, alter the environment, or adjust privileges **in the child before the new program is loaded**. Separating creation from program replacement gives precise control over that intermediate state.

This separation also explains why shells work the way they do. The shell creates a child. In the child, it arranges redirection and pipeline endpoints. Then that child replaces its program image with the requested command. Without this staged model, command launching would be much less flexible.

## `fork`: creating a new process by duplicating the caller

### Formal definition: `fork`

`fork` is a system call by which a process requests that the kernel create a new process whose initial execution state is derived from the calling process.

### Interpretation

What this really says is that `fork` makes a **new process that begins as a near-copy of the old one**. It does **not** create a blank process from scratch in the ordinary Unix model. The child starts from the parent’s current state closely enough that, from the user-level program’s point of view, both continue from what appears to be the same point in execution.

The first thing to notice is that after `fork`, there are now **two independently schedulable processes**. They may run in either order. The operating system does not promise that the parent continues first or that the child continues first. That scheduling uncertainty is one of the first boundary conditions students must keep in mind.

### What is copied, what is shared, what is logically inherited

Immediately after `fork`, the child receives a new process identity but an initial state derived from the parent. Conceptually, the child gets:

- its own process identifier,
- a recorded parent identifier,
- a copy of the parent’s virtual address space, subject in real systems to implementation optimizations such as copy-on-write,
- copies of register state in the sense needed to resume execution,
- inherited open file descriptors that usually refer to the same underlying open-file objects in the kernel,
- inherited environment and many process attributes.

The important distinction is between **copying an entry in the process state** and **sharing the underlying kernel object**. For example, the child gets its own file-descriptor table entries, but those entries may point to the same underlying open-file description as the parent’s corresponding entries. That is why the file offset may be shared.

This is a common source of bugs and misconceptions. Students often say “the child gets copies of all open files,” but what usually matters semantically is subtler: the child gets inherited descriptors referring to the same open-file state. So one process advancing the file offset can affect what the other later reads or writes.

### The two return paths

The classical conceptual behavior of `fork` is that control continues in both parent and child, but each receives information allowing it to distinguish its role.

From the parent’s perspective, the return value identifies the child.

From the child’s perspective, the return value indicates that it is the newly created process rather than the creator.

This is not just an implementation quirk. It is the mechanism that allows one control path in the source program to split into two logical roles. The same point in the program text is now reached by two different processes with different identities.

### Failure mode of `fork`

`fork` can fail. The kernel may refuse process creation because of resource exhaustion or policy limits: too many processes, insufficient memory, or administrative limits on the user or system. In that case, no child is created, and the caller remains the only process continuing.

The conceptual lesson is that process creation is not guaranteed. The operating system mediates it under resource constraints.

## The state immediately after `fork`

Right after `fork`, parent and child are similar enough to be confusing. They have nearly identical memory contents, often the same code, the same stack contents, and inherited file descriptors. But they are already distinct in several crucial ways.

They have different process identifiers. They have separate address spaces logically, even if the kernel delays physical copying through copy-on-write. Either process may later modify its own memory, and those modifications are not conceptually changes to a single shared process. They have independent scheduling lives. One may exit while the other continues. One may call `exec`; the other may not.

The key insight is this: **`fork` duplicates the current computational situation into two processes that diverge from that moment onward**.

## `exec`: replacing the current program image

### Formal definition: `exec`

`exec` refers to a family of system calls by which a process requests that the kernel replace its current user-space program image with a new program loaded from an executable file.

### Interpretation

What this is really saying is that `exec` does **not** create a new process. It transforms an existing process so that it begins executing a different program. The first thing to notice is the word **replace**. The old code, old stack, old data image, and old user-space execution context are discarded and replaced by the new program image.

This is one of the most important distinctions in the entire cluster:

- `fork` creates a **new process**.
- `exec` does **not** create a new process; it changes what program an **existing process** runs.

Students constantly confuse these two because they are often used together. The shell typically uses both, so beginners compress them mentally into one event. They are not one event.

### What remains across `exec`, and what does not

Across `exec`, the process remains the same process in several kernel-level senses. It typically retains the same process identifier. It retains its place as the same child of its parent. It retains many kernel-managed attributes, though some are reset according to operating system rules.

What does not remain is the old user-space program image. The new executable becomes the process’s code and initial data state. The stack is rebuilt according to the executable and the provided argument and environment information.

So the stable idea across `exec` is **process identity**, while the changing idea is **program content**.

### Why `exec` usually follows `fork`

After a parent calls `fork`, the child often does some setup and then calls `exec` to become the desired new program. This pattern solves the general problem “launch a new program in a customized execution context.”

The order is conceptually important.

First, the parent creates the child with `fork`.

Second, the child adjusts inherited state if needed, such as redirections.

Third, the child calls `exec`.

Only then does the child become, for example, `ls`, `grep`, a compiler, a server worker, or some other target program.

### Boundary condition: `exec` only returns on failure

Conceptually, a successful `exec` does not “come back” to the old program because the old program image no longer exists. If control appears to return to the caller after an `exec` attempt, that signals failure to replace the program image.

This boundary condition is crucial. A student who thinks successful `exec` returns normally has not yet internalized what replacement means.

### Local bridge for the shell example

Three compact meanings are needed before the shell example.

A **shell** is a command interpreter that reads user commands and asks the operating system to create and manage processes on the user’s behalf.

**Redirection** means changing which open file descriptor a process uses for standard input, standard output, or standard error before the new program begins running.

An **inherited file descriptor** is a file descriptor in the child that refers to kernel-managed open-file state passed along from the parent during process creation.

With those meanings fixed, the shell example can be read as a precise lifecycle protocol rather than as a bag of Unix trivia.

## Worked example: how a shell runs a command

This example is worth studying because it teaches the general pattern used throughout Unix-like systems.

Suppose a shell is running, and the user enters a command that should launch another program. We want to understand what happens conceptually, step by step.

At the start, there is one process of interest: the shell. The shell already exists, has its own process identifier, open terminal file descriptors, environment, and control state.

The shell first decides it wants a new running activity without destroying itself. It cannot simply `exec` the command directly, because then the shell itself would be replaced and would no longer remain as the interactive command interpreter. So the shell must first create another process.

It therefore calls `fork`.

At that point, there are two processes. The parent is still the shell. The child is a new process whose initial state is derived from the shell.

Now execution splits conceptually into two branches.

In the parent branch, the shell records the child’s identity because it may need to wait for it, report its status, or manage it as a background or foreground job.

In the child branch, the process is still, at this instant, essentially another copy of the shell program image. But this child is not supposed to remain a shell copy. Its job is to become the requested command.

Before it becomes that command, it may need to change some inherited state. For example, if the user requested output redirection, the child adjusts its file descriptors so that standard output points to a file rather than the terminal. If the command is part of a pipeline, the child arranges its standard input or output to connect to a pipe endpoint.

Only after those changes does the child call `exec` with the target executable.

If `exec` succeeds, the child process is still the same process from the kernel’s perspective, but its user-space program image is now the requested command rather than the shell.

Meanwhile, the parent shell may call `wait` or a related mechanism if it is a foreground command. That causes the shell to block until the child changes state in the required way, usually termination.

If the command finishes, the child calls `exit` or otherwise terminates. The kernel records its termination status. The parent shell collects that status with `wait`. Only then is the child fully cleaned up.

This example teaches the general lesson:

**A parent often remains alive and supervising while a child is created, possibly transformed with `exec`, and then later reaped with `wait`.**

That pattern is far more general than shells.

## `exit`: process termination from the process’s side

### Formal definition: `exit`

`exit` is the action by which a process terminates and supplies a status value to the operating system for later collection by its parent.

### Interpretation

What this is really saying is that process termination is not merely “the instructions stop.” The process announces completion to the kernel. The kernel then performs controlled teardown: closing process-owned resources according to system rules, marking the process as terminated, recording status information, and notifying or making visible the state change to the parent.

The first thing to notice is that termination is a **state transition** with aftereffects, not instantaneous disappearance.

### What `exit` causes the kernel to preserve

A terminated process cannot continue executing user instructions. Its ordinary resources are largely released. But the kernel typically retains a small amount of bookkeeping information long enough for the parent to learn what happened. This includes at least the process identity and termination status, and often accounting information needed by the waiting parent.

That preserved bookkeeping is the reason zombies exist.

### Exit status

The exit status is a compact report from child to parent. Conceptually, it answers questions such as: did the child finish normally, or was it terminated by a signal? If it finished normally, what small status code did it provide?

The operating system therefore treats termination as something the parent may need to observe, not just a local event inside the child.

## `wait`: termination observation from the parent’s side

### Formal definition: `wait`

`wait` refers to a family of system calls by which a parent process requests notification and status information about state changes in its child processes, commonly their termination.

### Interpretation

This means that `wait` is how the parent says to the kernel: “Tell me when one of my children has reached the relevant state, and give me the recorded information so cleanup can be completed.” The first thing to notice is that `wait` belongs to the **parent-side cleanup contract**.

A child can terminate with `exit`, but until the parent performs the corresponding observation-and-collection step, the kernel cannot necessarily discard all traces of that child. That is why `exit` and `wait` are conceptually paired.

### What `wait` checks, in what order, and what each possibility means

A serious student should understand the logic conceptually.

The parent requests information about child state changes. The kernel checks whether the calling process has children matching the request. If it has none, the request cannot succeed in the ordinary sense because there is no child from which to collect status.

If matching children exist, the kernel checks whether any have already changed into the state being awaited, usually a terminated-but-not-yet-collected state. If one does, the kernel can return immediately with that child’s identity and recorded status. That allows the parent to learn the result and allows the kernel to finish removing the child’s remaining bookkeeping entry.

If matching children exist but none has yet reached the awaited state, then what happens depends on the call mode. In the ordinary blocking case, the parent sleeps until an appropriate state change occurs. In nonblocking variants, the parent is told that no child is ready yet.

The important conceptual sequence is:

1. Determine whether relevant children exist.
2. Determine whether one already has a reportable state change.
3. If yes, deliver status and complete reaping.
4. If no, either block or return immediately depending on the waiting mode.

This is not programming detail for its own sake. It explains why `wait` is synchronization. It coordinates parent behavior with child lifecycle transitions.

## Zombie process

### Formal definition: zombie

A **zombie process** is a process that has terminated execution but still has an entry in the process table because its parent has not yet collected its termination status with `wait` or an equivalent mechanism.

### Interpretation

This is one of the most misunderstood definitions in operating systems. A zombie is **already dead** in the sense that it is no longer executing instructions. It does not consume CPU as a running process. Its memory and most ordinary resources have already been released. What remains is a minimal kernel record containing enough information for the parent to learn how the child ended.

The first thing to notice is that a zombie exists because the system has a responsibility to preserve termination information for the parent. The zombie is therefore not a “half-alive broken process.” It is a terminated process awaiting collection.

### Why zombies are necessary

Suppose the kernel deleted all trace of a child immediately when it terminated. Then the parent might never know whether the child succeeded, failed, crashed, or was even the same child it intended to track. The parent-child contract would be broken.

So the zombie state exists to bridge the gap between **child termination** and **parent acknowledgment**.

### Failure mode: zombie accumulation

If a parent creates many children and never waits for them, zombies accumulate. Each zombie occupies a slot in kernel bookkeeping. A few zombies are usually not catastrophic, but persistent failure to reap can exhaust process table resources over time.

The conceptual lesson is that cleanup in operating systems is often distributed across cooperating parties. The child exits. The parent must reap.

### Common misconception

A zombie is not the same as a stopped process, a sleeping process, or an orphan. A zombie is not “hung.” It is finished. The issue is not that it cannot die; it is that it **has died and not yet been reaped**.

## Orphan process

### Formal definition: orphan

An **orphan process** is a process whose parent has terminated while the process itself is still running or otherwise not yet terminated.

### Interpretation

This means the child is still alive, but the original parent is gone. The first thing to notice is the contrast with a zombie. In an orphan, the **child is alive** and the **parent is gone**. In a zombie, the **child is dead** and the **parent is alive enough not to have reaped it yet**.

That distinction must be forced explicitly because students often blur them together simply because both involve abnormal-sounding family language.

### What the operating system does with orphans

Unix-like systems do not leave a living child without supervision forever. When a parent dies, orphaned children are typically reparented to a special long-lived process, historically `init` and in many systems a designated reaper process. That adopting process can later perform `wait` when the orphan eventually terminates.

This reparenting solves a structural problem: every process should continue to belong to a manageable hierarchy for cleanup and supervision purposes.

### Why orphan does not imply zombie

An orphan is not inherently a problem. Many background services intentionally become detached from their original parent. The critical fact is that orphanhood concerns **loss of parent while still alive**, not failure of termination cleanup.

The orphan may later terminate normally and be reaped by its new parent. So orphanhood is about **who the parent is**, while zombie state is about **whether the termination record has been collected**.

## Putting the lifecycle together as one chain

Now the entire cluster can be seen as one coherent sequence.

A process already exists. If it wants another concurrent activity, it requests process creation. In the classic Unix model, that is done with `fork`, producing parent and child. At the moment after `fork`, both are separate processes with closely related initial state.

The child may continue running the same program or may call `exec` to replace its program image with a new one. The parent and child then proceed independently, possibly synchronizing later.

When the child finishes, it terminates via `exit` or equivalent termination. The kernel releases most resources but preserves termination status in a zombie entry until the parent calls `wait`. When the parent waits and collects the status, the child is reaped and its remaining kernel record is removed.

If instead the parent dies first while the child still lives, the child becomes an orphan and is reparented so that eventual cleanup is still possible.

This chain explains not just one system call at a time, but the operating system’s deeper design goal: **processes must be created, transformed, terminated, and cleaned up without losing control of identity, status, or resources**.

## State distinctions that must not be blurred

The lifecycle cluster becomes much easier once a few distinctions are held firmly.

A **new child after `fork`** is alive and schedulable.

A process **after successful `exec`** is alive and schedulable but running a different program image than before.

A process **after `exit` but before `wait`** is a zombie: not alive as an executing process, but still present as a status record.

A process **whose parent has died while it remains alive** is an orphan.

A process **that is sleeping or blocked** is not necessarily any of the above special family states; it is simply alive but waiting for some event.

These are different axes. “Who is the parent?” and “is the process still executing?” are separate questions.

## Do Not Confuse: Zombie, Orphan, and Blocked Child

A zombie is already dead as an execution entity but still present as a termination record awaiting collection. An orphan is still alive, but its original parent is gone. A blocked child is still alive and simply waiting for some event. These states answer different questions: “is the child alive?”, “has the parent survived?”, and “can the child make progress right now?” Do not collapse them.

## Subtleties that matter for real understanding

### Copy-on-write and the meaning of “copy” after `fork`

Textbook language often says the child gets a copy of the parent’s address space. Conceptually this is right: parent and child should behave as though they each got their own copy. But modern systems often avoid immediately duplicating every memory page. Instead, both processes initially share physical pages marked so that a write triggers duplication. This is called copy-on-write.

The conceptual point is that implementation efficiency does not change the abstract semantics that parent and child are now logically separate processes with separable memory.

### Shared open-file state

The child inherits file descriptors, but the deeper kernel object those descriptors refer to may be shared. This is why redirections done in the child before `exec` are so powerful, and also why parent-child I/O interactions can surprise students.

The right question is not merely “does the child have the same descriptor number?” but “what underlying open-file state is shared?”

### Signals and abnormal termination

A child does not always terminate by a polite ordinary `exit`. It may be killed by a signal or stop because of tracing or job control. Parent waiting mechanisms therefore often report more than one kind of state change. Even if a course begins with ordinary normal termination, the broader concept is that the kernel records enough status for the parent to distinguish how the child changed state.

### Waiting for a specific child versus any child

In systems with many children, the parent may care which child changed state. That is why waiting interfaces often allow selection. Conceptually, this means the parent-child cleanup relationship is not just “some child ended,” but often “which child ended, under what condition, and what does that imply for the parent’s next action?”

## Common misconceptions, explicitly corrected

One common misconception is that `fork` runs a new program. It does not. It creates a new process initially derived from the current one.

Another is that `exec` creates a child. It does not. It replaces the current process’s program image.

Another is that a zombie is still executing. It is not. It has terminated.

Another is that orphan and zombie mean roughly the same thing. They do not. An orphan is alive without its original parent; a zombie is dead but not yet reaped.

Another is that `wait` kills the child. It does not. The child is already terminated when ordinary waiting reaps a zombie. `wait` collects status and completes cleanup.

Another is that parent and child after `fork` share one memory space in the ordinary conceptual model. They do not, even though the implementation may optimize copying.

Another is that the parent always runs first after `fork`. There is no such guarantee. Scheduling order is not fixed.

## A second worked example: distinguishing zombie from orphan

This example is chosen because students reliably confuse these ideas.

Imagine process P creates process C.

### Case 1: child dies first, parent does not wait yet

P is alive. C terminates. The kernel releases C’s ordinary runtime resources but retains C’s termination record because P may still ask how C ended.

At this point, C is a zombie.

Why? Because the child is dead, and the parent is still around but has not yet collected the status.

If P now calls `wait`, the kernel checks that P has a child with an uncollected reportable state change, returns C’s status to P, and removes the remaining kernel record. C then ceases to exist even as a zombie.

### Case 2: parent dies first, child keeps running

P is alive. C is alive. P terminates before C.

At that moment, C becomes an orphan because its original parent no longer exists while C still does.

The operating system reparents C to a designated long-lived process. C may continue running normally. If C later terminates, its new parent can reap it.

Why is C not a zombie in this second case? Because C is still alive. Zombie status only applies after termination.

This example teaches the general diagnostic rule:

To classify the state, ask two questions in order.

First: **Is the child still executing, or has it terminated?**

Second: **Is the original parent still alive, and if not, who is now responsible for reaping?**

Those two checks separate the notions cleanly.

## The larger system role

This topic supports a great deal of later operating-systems material.

It underlies command interpreters and job control because shells depend on creating children, grouping them, tracking them, and reaping them.

It underlies server design because servers often create or manage worker processes.

It underlies synchronization because `wait` is a primitive form of coordination between related processes.

It underlies protection and resource management because inheritance across `fork` and replacement across `exec` affect descriptors, credentials, and execution environment.

It underlies reliability because failure to understand zombies, orphans, and termination status leads to resource leaks and supervisory mistakes.

Most importantly, it teaches that the operating system manages not just instantaneous execution, but **lifetimes**.

## Conceptual Gaps and Dependencies

This topic assumes prior understanding of the following prerequisites: the distinction between a program and a process; basic kernel versus user-space separation; process identifiers; the idea of a system call; the existence of an address space; the notion that files are accessed through file descriptors; and basic scheduling vocabulary such as running, blocked, and terminated.

The prerequisites most likely to be weak at this stage are the difference between a process and a program, the meaning of a virtual address space, and the distinction between a file descriptor and the underlying kernel open-file object. Weakness in any of those areas causes major confusion in `fork`/`exec` reasoning.

Nearby concepts referred to here without being fully taught include copy-on-write implementation details, signals, job control, process groups, sessions, pipes, terminal control, daemonization, credential changes across `exec`, and the exact status encoding returned by waiting interfaces.

Homework-relevant or lecture-relevant facts not covered fully by this explanation alone often include the exact return conventions of particular `fork` and `wait` variants, the detailed macros or bit-pattern interpretation for child status, special rules for signal disposition across `exec`, nonblocking wait variants, and course-specific examples involving pipes and redirection.

The best concepts to study immediately before this topic are: program versus process, kernel/user mode, system calls, address spaces, and file descriptors. The best concepts to study immediately after this topic are: pipes and redirection, process synchronization, signals, process scheduling states, job control, and daemon/service management.

## Retain / Do Not Confuse

### Retain

- A process is a live execution context, not just a program file.
- `fork` creates a new process.
- `exec` does not create a new process; it replaces the current process’s program image.
- `exit` terminates a process and leaves status for the parent.
- `wait` lets the parent collect that status and complete cleanup.
- A zombie is terminated but not yet reaped.
- An orphan is still alive after its parent has died.
- Parent and child after `fork` are separate processes with separate futures.

### Do Not Confuse

- Do not confuse **program** with **process**.
- Do not confuse **`fork`** with **`exec`**.
- Do not confuse **termination** with **reaping**.
- Do not confuse **zombie** with **orphan**.
- Do not confuse **inherited file descriptors** with **independent underlying file state**.
- Do not confuse **logical memory copying** after `fork` with literal immediate physical copying in implementation.
- Do not confuse **same point in code after `fork`** with **same process**.
