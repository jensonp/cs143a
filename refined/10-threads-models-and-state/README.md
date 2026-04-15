# Thread Cluster: thread, thread-private state, shared process state, TCB, thread vs process, kernel threads, user threads

## Why This Topic Appears in Operating Systems

An operating system has to manage *computation in progress*. It is not enough to store programs on disk and load them into memory. The system must represent, at every instant, which computations exist, what resources they own, what they are currently doing, what can interrupt them, and how the processor can stop one computation and resume another without losing correctness. Early in an operating systems course, this need usually appears under the topic of the **process**: a running program has memory, open files, an execution state, and protection boundaries. But as soon as one process must do more than one thing at once, or must overlap waiting with useful work, the process abstraction is too coarse. That pressure forces the introduction of the **thread**.

A serious understanding starts from the question: *what exactly is it that the CPU is executing?* The CPU does not execute “an application” in the vague everyday sense. At any instant, the CPU executes one specific sequence of instructions with one specific program counter, one register state, and one stack. That execution stream is the right starting point for the notion of a thread.

The topic matters because threads sit exactly at the boundary between several central OS concerns: scheduling, concurrency, synchronization, blocking, context switching, memory sharing, protection, and performance. If you do not distinguish carefully between a process and a thread, later topics such as locks, races, deadlock, condition variables, thread libraries, and multicore scheduling become confused immediately.

Those later terms are being used here as **forward-reference labels**, not as fully developed mechanisms yet. At this stage, the only fact you need is simpler: once multiple threads share one process state, correctness will later require explicit coordination rules to prevent one thread’s actions from invalidating another’s assumptions.

## The Problem a Thread Solves

Suppose a server process handles network requests. While it waits for one client’s disk read to complete, it would like to make progress on a different client. Suppose a browser tab needs to render the interface while also performing network activity. Suppose a program wants one activity to compute while another waits for user input. In all of these cases, there is a single larger task or application, but within it there are multiple independent control flows.

One possible solution is to create multiple processes. That works, but it is heavy if those activities need to share the same address space, the same data structures, or the same file descriptors. Copying or communicating between processes can be expensive or awkward. Another solution is to keep one process but allow multiple execution streams inside it. That is what a thread gives you.

So the process solves one problem: *resource ownership and protection*. The thread solves another: *separate schedulable flows of control within that protected resource container*.

That distinction is the foundation for everything that follows.

## Multiprocessing, Multiprogramming, and Multithreading

### Why This Section Exists

Once processes and threads have both been introduced, students are immediately confronted with three similar-looking words:

- multiprocessing
- multiprogramming
- multithreading

These are easy to blur because all three involve “more than one thing happening.” But they answer three different questions:

- **How many CPUs or cores does the machine have available?**
- **How many processes or jobs is the operating system managing at once?**
- **How many execution streams exist inside one process?**

This section exists to force those questions apart. Without this distinction, later reasoning about scheduling, blocking, concurrency, and parallelism becomes vague.

### The Three Definitions

#### Multiprocessing

**Multiprocessing** means the system has multiple processors or CPU cores available for execution.

In plain technical English, multiprocessing is about the **hardware execution capacity** of the machine. It answers: how many hardware execution engines can run simultaneously?

#### Multiprogramming

**Multiprogramming** means the operating system keeps multiple jobs or processes in the system so the CPU can stay busy by switching among them when one cannot make progress.

In plain technical English, multiprogramming is about the **OS managing multiple active processes over time**, even on one CPU core.

#### Multithreading

**Multithreading** means one process contains multiple threads of execution.

In plain technical English, multithreading is about the **internal execution structure of one process**, not about the whole machine.

### Concurrency vs Parallelism

**Concurrency** means multiple activities are logically in progress, even if they are not all executing at the exact same instant.

**Parallelism** means multiple activities are physically executing at the same time on different processors or cores.

A single-core system can support concurrency without parallelism. Multiple cores allow parallelism. A multithreaded process may therefore be concurrent without automatically being parallel.

### One Important Constraint

Only **one thread can run on one CPU core at a time**. Threads may be interleaved on a single core, or run truly simultaneously on multiple cores if the hardware and scheduling model allow it.

### Why This Belongs in the Thread Chapter

This taxonomy explains why one blocked thread may or may not stall the rest, why kernel visibility matters, and why “more threads” is not the same thing as “more cores.” The deeper thread model makes more sense once these terms are fixed.

### Retain / Do Not Confuse

Retain:
- multiprocessing = multiple CPUs/cores
- multiprogramming = multiple jobs/processes managed by the OS
- multithreading = multiple threads inside one process
- concurrency is not the same as parallelism

Do not confuse:
- hardware multiplicity with software multiplicity
- many threads with automatic simultaneous execution
- many processes with one multithreaded process

## First Definition: Process

**Definition.** A **process** is an executing program together with the resources and execution environment that the operating system associates with it, including its address space, protection domain, open resources, and bookkeeping information.

In plain technical English, this means a process is the operating system’s unit of *ownership and isolation*. It is the container that says: these virtual memory mappings belong together, these open files belong together, these credentials and permissions apply here, and this computation is protected from unrelated computations. The first thing to notice is that this definition is broader than “the thing currently running on the CPU.” A process includes resources that may exist even while none of its instructions are currently being executed.

This is why it is dangerous to think of a process only as “a running program.” A program on disk is passive. A process is the live OS-managed instance of execution plus its owned environment.

## Second Definition: Thread

**Definition.** A **thread** is a single sequential flow of execution within a process, characterized by its own program counter, register state, stack, and scheduling state.

In plain technical English, a thread is the specific “path of execution” that the CPU can follow. It is the part that can be paused, resumed, preempted, blocked, or run in parallel with another execution stream in the same process. The first thing to notice is that a thread is *not* an isolated resource container. It usually lives inside a process and uses the process’s resources.

The essential sentence to retain is this: **a process is a resource container; a thread is an execution stream.**

That is not merely a slogan. It tells you what is shared, what is private, and what the OS scheduler must track.

## Why the Process Is Not Enough

If a process had exactly one execution stream forever, then the process abstraction could double as the scheduling abstraction. Historically, many systems started close to that idea. But once you allow concurrency inside one application, you need to separate two roles that were previously bundled together.

One role is: who owns the memory, files, credentials, and protection domain? The other role is: what exact register set and stack should the CPU run next? These are not the same question. A single owner can contain many execution streams. That is why modern operating systems separate **process state** from **thread state**.

This is also why saying “the process is blocked” can be misleading unless you are careful. Sometimes an entire process is effectively unable to proceed because all of its threads are blocked. But the block usually applies to a particular thread, because blocking is about the inability of a specific execution stream to continue until some condition changes.

## Thread-Private State and Shared Process State

Once a process contains multiple threads, the immediate conceptual question is: what belongs to each thread individually, and what belongs to the process as a whole?

This is one of the most important distinctions in the chapter because many bugs arise from misunderstanding it.

### Thread-Private State

**Definition.** **Thread-private state** is the execution state that must be separate for each thread in order for each thread to make independent progress.

In plain technical English, this is the information that would be corrupted if two threads had to share it while executing different instruction streams. The first thing to notice is that this state is private not because of security, but because of correctness of independent execution.

The main components are the following.

A thread has its own **program counter**. This is the location of the next instruction to execute. If two threads shared one program counter, they would not be two threads at all; they would be a single execution stream.

A thread has its own **register set**. General-purpose registers, floating-point registers, vector registers, condition codes, and architecture-specific control registers may contain temporary values needed by the currently running code. Since these values differ between one execution stream and another, each thread needs its own saved register context.

A thread has its own **stack**. Function calls, return addresses, saved frame information, and ordinary automatic local variables live on the stack. This is a major source of confusion for students. If two threads call the same function, they do **not** normally share the same local variables declared in that function, because each thread executes the function with its own stack frames. The code is shared, but the stack instances are separate.

A thread has its own **scheduling state**. It may be running, runnable, blocked, suspended, terminated, or waiting on a synchronization object. These states are inherently attached to the schedulable execution stream, not to the process container.

A thread often has thread-specific metadata such as its identifier, priority, CPU affinity information, pending signal state depending on the operating system design, and pointers used by the runtime or scheduler.

Some systems also provide **thread-local storage**. This is a mechanism that gives each thread its own instance of certain variables even though the source code refers to them by a common name. Conceptually, thread-local storage belongs with thread-private state because each thread sees a different instance.

### Shared Process State

**Definition.** **Shared process state** is the resource state owned collectively by the process and visible, by default, to all threads in that process.

In plain technical English, this is the common environment inside which all threads execute. The first thing to notice is that shared here means “shared among the threads of one process,” not “shared with the whole machine.” The OS still isolates one process’s state from another process’s state unless special sharing mechanisms are used.

The most important shared component is the **address space**. All ordinary heap objects, global variables, static variables, code segments, and mapped memory in the process’s virtual address space are, by default, accessible to all threads in that process. This is exactly why threads are powerful and exactly why they are dangerous: communication is easy, but accidental interference is easy too.

The process’s **open files and file descriptors** are usually shared. If one thread reads from a file descriptor and changes the file offset, another thread using the same descriptor may observe the changed offset. This is a classic example of shared process state having surprising consequences.

The process’s **credentials and protection domain** are shared. Threads in the same process normally execute with the same user identity, access rights, and address-space-level protection.

The process’s **signal dispositions**, current working directory, memory mappings, and many other OS-managed resources are typically process-level rather than thread-level, although exact details vary by system.

### A Clean Contrast

Here is the conceptual split in sentence form.

A thread needs its own control state because each thread is a separate computation in time. A process provides the shared environment because threads inside one process are intended to cooperate on one larger job.

Whenever you are unsure whether something should be thread-private or process-shared, ask this question: *if two execution streams in the same application do different work at the same time, would sharing this state make their control flows interfere incorrectly?* If yes, it must be private. If instead the state defines the common resources they are working with, it is probably process-shared.

## The Thread Control Block (TCB)

Once threads exist as OS-managed or runtime-managed entities, the system needs a data structure to represent them.

**Definition.** A **Thread Control Block (TCB)** is the operating system or runtime data structure that stores the bookkeeping information needed to manage a thread.

In plain technical English, the TCB is the record that says who this thread is, what state it is in, where its saved CPU context is, what stack belongs to it, and what the scheduler or runtime needs to know to stop and restart it correctly. The first thing to notice is that the TCB is not the thread itself in a metaphysical sense; it is the system’s representation of that thread.

Typical TCB contents include saved register state, the current state of the thread such as running or blocked, scheduling parameters such as priority, links for placing the thread in ready or wait queues, a pointer to the thread’s stack, an identifier, accounting information, and a reference to the process that owns the thread.

Different systems choose different names and layouts. Some texts use “TCB” generically; some kernels use names like `task_struct`, `kthread`, or similar structures. The exact structure is not the conceptual point. The conceptual point is that the system cannot manage a thread unless it has somewhere to store the thread’s machine state and scheduling metadata when that thread is not actively occupying the CPU.

### Why the TCB Must Exist

Suppose thread A is running. A timer interrupt occurs, or A blocks on I/O, or the scheduler decides another thread should run. The system must save enough state so that thread A can later resume as if it had never been interrupted except for the passage of time. That saved state cannot just float abstractly. It must be stored somewhere. That somewhere is the TCB together with associated saved stack memory.

So the TCB appears because context switching requires persistent, per-thread storage of execution state.

### TCB versus PCB

Students often meet the **Process Control Block (PCB)** near the same time.

**Definition.** A **Process Control Block (PCB)** is the OS data structure that stores process-level bookkeeping information.

In plain technical English, the PCB represents the process as the owner of resources and as a protection unit. The TCB represents one execution stream inside that process.

A process with one thread may conceptually have one PCB and one TCB. A process with many threads still has one process-level record for shared state but now has multiple thread-level records, one per thread. That is the clean structural picture.

Do not confuse the fact that some real kernels merge or intertwine these structures for efficiency with the conceptual distinction. The abstraction still matters even if the implementation stores the fields in closely related or partially unified structures.

## What the CPU Actually Switches Between

A thread becomes concrete when you study context switching.

When the system switches from one thread to another, the mechanism checks what execution state must be preserved for the current thread before it stops, and what execution state must be restored for the next thread before it starts. The essential saved items are the program counter, stack pointer, registers, and any other architecture-specific context necessary for correct restart. The scheduler also checks the state of candidate threads: which ones are runnable, which ones are blocked, what priorities apply, and what policy is being used.

The order of reasoning is as follows.

First, the system determines why the current thread is leaving the CPU. It may have used up its time slice, voluntarily yielded, blocked waiting for I/O or a lock, or been preempted by a higher-priority runnable thread.

Second, it determines what the current thread’s new state should be. If it blocked waiting for something, its state becomes blocked or waiting. If it merely lost the CPU but is still able to run, it becomes runnable. If it has finished execution, it becomes terminated.

Third, it saves the current thread’s machine context into that thread’s saved state area, usually associated with its TCB.

Fourth, it selects another runnable thread according to the scheduling policy.

Fifth, it restores that chosen thread’s saved machine context, updates hardware bookkeeping such as memory-management references if switching across processes, and resumes execution at the new thread’s saved program counter.

The key conceptual conclusion is that the scheduler fundamentally switches among **threads**, because threads are the independently schedulable execution entities. Process-level switching matters too when the next thread belongs to a different process, because then the address space and protection context also change. But the immediate object being run is still a thread.

## Thread versus Process: The Distinction That Must Stay Sharp

This section forces explicit separation between two ideas students constantly blur.

A **process** answers: who owns this memory and these resources, and what protection boundary contains them?

A **thread** answers: what particular sequence of instructions is currently making progress, and what private execution context does it need?

A process can exist even when none of its threads are running at this instant. A thread cannot meaningfully exist without some execution environment; in ordinary systems, that environment is a process.

Multiple processes imply separate address spaces unless explicit sharing is arranged. Multiple threads in one process usually imply one shared address space by default.

Communication between processes usually requires explicit interprocess communication mechanisms such as pipes, sockets, shared memory, or message passing. Communication between threads is often just ordinary memory access to shared variables, which is both efficient and dangerous.

Creating or switching processes often has more overhead than creating or switching threads because process changes may involve address-space changes, protection-domain bookkeeping, and resource duplication or reference changes. Thread operations can be lighter because the threads already share much of the process environment. “Can be lighter” is the right phrasing; actual cost depends on the system and the implementation.

Protection is process-oriented, not thread-oriented in the usual model. One thread cannot, by default, be prevented from accessing ordinary shared process memory that another thread can access. That is why a wild pointer in one thread can corrupt another thread’s data in the same process.

So threads improve concurrency and sharing, but they do not provide isolation from one another in the way separate processes do.

## Deep Trace: One Blocked Thread Under Different Threading Models

Suppose one process contains two logical threads, T1 and T2. T1 is computing. T2 issues a blocking I/O request. In a one-to-one kernel-thread model, the kernel sees T1 and T2 as separate schedulable execution entities. When T2 blocks, the kernel marks T2 blocked, saves its execution state, and can still schedule T1 because T1 remains runnable. The process as a whole stays alive and partially active. In a many-to-one pure user-thread model, the kernel may see only one kernel execution entity for the whole process. When T2 performs a blocking system call, the kernel blocks that one kernel-visible execution entity. At that point, even though the runtime conceptually still has T1 and T2 as separate user threads, the kernel cannot schedule T1 independently because it does not know T1 exists as a separate schedulable object. This trace teaches why “what blocks?” depends on the threading model and on which execution entities are visible to the kernel.

## Kernel Threads

The next major question is where the thread abstraction is implemented.

**Definition.** A **kernel thread** is a thread that the operating system kernel knows about directly and can schedule as an independent execution entity.

In plain technical English, the kernel maintains a thread record for it, can block and wake it, can preempt it, and can place it on CPU run queues. The first thing to notice is that “kernel thread” here means the scheduler can see the thread individually. It does not necessarily mean the thread runs kernel code all the time. User applications commonly use kernel-supported threads that spend most of their life executing user-mode code.

### Why Kernel Threads Matter

If one kernel thread blocks in a system call, the kernel knows exactly which thread blocked. Other threads in the same process can still be scheduled if they are runnable. On a multicore machine, multiple kernel threads from the same process can run truly in parallel on different cores because the kernel scheduler sees them as separate runnable entities.

This gives kernel threads strong integration with blocking I/O, preemption, priorities, signals, timers, and multicore scheduling.

### What Is Fixed and What Varies

What is fixed is the kernel’s direct involvement in thread management. What varies is the specific implementation: the data structures, system calls, scheduling classes, and costs.

The kernel must store per-thread state somewhere, typically in or near a TCB-like structure. It must also maintain relations between a thread and its owning process. The scheduler checks run queues, priorities, affinity constraints, and wait conditions at the thread level.

### Costs and Tradeoffs

Kernel involvement adds flexibility and power, but it also adds overhead. Creating, destroying, blocking, or switching kernel threads usually requires kernel participation. That means mode switches, protected data-structure updates, and scheduler overhead. Whether this overhead is “large” depends on context, but conceptually it is greater than purely user-space bookkeeping.

## User Threads

**Definition.** A **user thread** is a thread managed primarily by a user-space runtime rather than directly by the kernel as an independently scheduled entity.

In plain technical English, the thread library inside the process keeps track of multiple execution streams and switches among them in user space. The kernel may see only one schedulable kernel entity for the whole process, or fewer kernel entities than there are user threads. The first thing to notice is that user threads are still real execution streams from the program’s point of view, but their management is not fully visible to the kernel.

### Why User Threads Exist

User-space management can make thread operations very fast. Creating a user thread, switching between user threads, or maintaining user-thread queues may require no kernel entry at all. That reduces overhead and allows custom scheduling policies tuned to the application.

This is attractive when the application frequently creates lightweight tasks or needs specialized scheduling behavior.

### The Core Limitation

The classical problem appears when the kernel does not know about each user thread separately.

Suppose a process has many user threads but only one kernel-schedulable entity. If one user thread performs a blocking system call and the kernel blocks that kernel entity, then from the kernel’s point of view the whole process is blocked. The other user threads cannot run, even if they are logically runnable, because the kernel does not see them as separate schedulable units.

Similarly, on a multicore machine, if the kernel sees only one schedulable entity, the user threads cannot achieve true parallel execution across multiple cores at the same time. They may be concurrent in the logical sense, but not parallel in the hardware sense.

This is the central conceptual weakness of pure user-level threading.

### User-Level Context Switching

When a user-thread runtime switches from one user thread to another, it performs a smaller-scale version of context switching. It checks which user threads are runnable, saves the current thread’s register and stack context into user-space bookkeeping, marks its state appropriately, restores the next thread’s context, and transfers control.

Because this occurs in user space, it can be very fast. But it only works while the runtime retains control. Once the kernel blocks the underlying execution entity, the runtime cannot schedule around that block unless the system provides special support such as nonblocking I/O or upcalls.

## Mapping Models: How User Threads and Kernel Threads Relate

To understand kernel versus user threads properly, it helps to separate the *programmer-visible thread abstraction* from the *kernel-visible schedulable abstraction*. Different systems map these layers differently.

### Many-to-One

Many user threads are mapped onto one kernel schedulable entity.

Interpretation: the thread library can manage many logical execution streams, but the kernel sees only one. User-thread operations are cheap, but one blocking call can stall all of them, and there is no true multicore parallelism.

### One-to-One

Each user-level thread corresponds to one kernel thread.

Interpretation: the programmer sees threads, and the kernel also sees each thread individually. Blocking one thread does not block all of them, and multicore parallelism is available. The cost is higher kernel involvement per thread.

Many modern general-purpose systems largely follow this model for ordinary application threads.

### Many-to-Many

Many user threads are multiplexed over some number of kernel threads.

Interpretation: the runtime keeps flexible user-level scheduling, but the kernel still exposes multiple schedulable entities, allowing better handling of blocking and multicore execution. This model is conceptually rich but more complex to implement correctly.

The value of these models is not mainly historical trivia. They teach you exactly where the scheduler’s visibility lies and therefore what kinds of blocking and parallelism are possible.

## A Fully Worked Example

Consider a web server process with one address space containing a request queue, a cache, configuration data, and several worker functions. The server has three threads inside one process.

Thread 1 waits for incoming network connections.

Thread 2 parses requests and checks the in-memory cache.

Thread 3 performs disk reads when a cache miss occurs.

Now ask, piece by piece, what state is shared and what state is private.

The process’s code segment is shared. All three threads execute instructions from the same loaded program image.

The request queue stored on the heap is shared. If Thread 1 enqueues a request, Thread 2 can dequeue it because both threads see the same heap object in the same process address space.

The cache stored in memory is shared for the same reason.

The current function call chain of Thread 2 is private to Thread 2. If Thread 2 is in `parse_headers` and Thread 3 is in `read_from_disk`, they do not overwrite each other’s local variables because each has a separate stack.

The current program counter of Thread 1 is private to Thread 1. It may be waiting inside a loop that accepts connections, while Thread 2 is executing parsing code and Thread 3 is inside an I/O completion path.

Suppose Thread 3 blocks on a disk read.

If these are kernel threads in a one-to-one system, the kernel marks Thread 3 blocked, saves its thread state, and can still run Threads 1 and 2. The server continues accepting and processing other requests.

If instead these are pure user threads mapped many-to-one onto a single kernel execution context, and Thread 3 performs a blocking system call that blocks that kernel entity, the entire process stops making progress from the kernel’s perspective. Threads 1 and 2 are logically ready, but they cannot run because the kernel does not schedule them separately.

This example teaches several general lessons.

First, sharing an address space makes cooperation cheap. The request queue and cache require no interprocess copying.

Second, independent stacks are what make independent control flow possible.

Third, the usefulness of threads depends heavily on where blocking occurs and whether the kernel can distinguish one thread from another.

Fourth, the same source-level idea of “three threads” can behave very differently depending on the threading model.

## Common Failure Modes and Misconceptions

A major misconception is: **threads are just smaller processes**. That is too vague and often wrong in the ways that matter. Threads are not miniature protection domains. They do not naturally isolate faults from one another. They are smaller only in the sense that they do not duplicate the full process resource container.

Another misconception is: **local variables are shared because the code is shared**. False. The code segment is shared, but local variables on the stack are per-thread because each thread has its own stack. A `static` local variable, however, behaves like shared process state because it lives in static storage, not on the stack. This is a favorite exam and debugging trap.

Another misconception is: **if threads share memory, they always see updates immediately and safely**. Sharing makes visibility possible, not correctness automatic. Later topics such as synchronization and memory consistency are required to make shared access well defined and race free.

Another misconception is: **blocking applies to the process as a whole**. In thread-based systems, blocking is often a thread property. One blocked thread does not necessarily imply a blocked process, unless all threads are blocked or the threading model hides the distinction from the kernel.

Another misconception is: **user threads are fake because the kernel does not know them**. They are not fake. They are genuine logical execution streams managed by a runtime. The important distinction is not real versus fake, but who schedules them and what consequences that has for blocking and parallelism.

Another misconception is: **kernel threads always mean the thread runs in kernel mode**. No. The phrase refers to who manages and schedules the thread, not to whether the thread is currently executing privileged code. An ordinary application thread can be kernel-scheduled while spending most of its time in user mode.

## Boundary Conditions and Edge Cases

A process with exactly one thread still has process state and thread state, even if introductory treatments temporarily blur them. The conceptual split still exists; it is just less visible because there is only one execution stream.

A multithreaded process may have threads in different states simultaneously: one running, one runnable, one blocked on I/O, one waiting for a lock. This is not an exception. It is the normal case that motivates threading.

A process can terminate while multiple threads exist. Then the operating system tears down the shared process resources, and all threads lose the environment they depended on. This reminds you again that the process is the container and the threads live inside it.

Some kernels blur the process-thread vocabulary internally. For example, the kernel may represent both with a generalized task abstraction. Do not let implementation naming erase the conceptual questions: what is private, what is shared, and what is the scheduler’s unit?

Some systems support kernel threads that are not tied to a user process in the usual way, such as internal kernel worker threads. This does not invalidate the definitions above; it simply shows that “thread” as an execution stream also exists inside the kernel’s own environment.

## What This Topic Supports Later

This topic is not isolated vocabulary. It is the foundation for later operating-systems reasoning.

You need the thread/process distinction to understand **context switching**, because the saved and restored state is thread-private, while address-space changes are process-related.

You need it for **synchronization**, because locks and condition variables coordinate multiple threads sharing one process state.

You need it for **race conditions**, because races occur when multiple threads access shared process data without proper coordination.

You need it for **deadlock**, because threads block independently and may wait on resources held by one another.

You need it for **CPU scheduling**, because schedulers choose among runnable execution entities, which are generally threads.

You need it for **memory protection**, because threads inside one process share the same protection domain and therefore require software discipline rather than hardware-enforced isolation from one another.

You need it for **multicore parallelism**, because true simultaneous execution requires multiple kernel-visible schedulable entities.

Without a sharp grip on this chapter, those later topics become a pile of unrelated mechanisms instead of a coherent system.

## Conceptual Gaps and Dependencies

This topic assumes the reader already understands what a program is, what execution means, how a CPU follows a program counter through instructions, and what registers and the call stack are. It also assumes basic familiarity with virtual memory and the idea that a process has an address space distinct from another process’s address space.

For many students at this stage, the weakest prerequisites are usually the stack-frame model, the difference between code, heap, stack, globals, and static storage, and the meaning of a context switch at the machine-state level. If those ideas are fuzzy, the thread-private versus shared-state distinction will feel arbitrary when it is not.

This topic refers to nearby concepts that it does not fully teach. In particular, it touches but does not develop scheduling policy, blocking system calls, nonblocking I/O, interrupt handling, synchronization primitives, memory consistency, and interprocess communication. A student will hear these ideas invoked in lecture or homework shortly after learning threads, but they require separate treatment.

Homework-relevant or lecture-relevant facts that are not covered fully here include the exact API behavior of a particular threading library, the concrete system calls used to create threads on a given operating system, the detailed layout of a real kernel’s thread structures, and the low-level assembly steps of a specific architecture’s context switch routine. Those details matter for implementation courses or systems labs, but they are downstream from the conceptual model built here.

The concepts that should be studied immediately before this topic are: execution state, CPU registers, stacks and function calls, trap and interrupt basics, processes, virtual address spaces, and the purpose of protection boundaries. The concepts that should be studied immediately after this topic are: context switching, CPU scheduling, synchronization primitives such as mutexes and condition variables, races and critical sections, blocking versus nonblocking I/O, and deadlock.

## Do Not Confuse: Thread, Process, Core, and Parallelism

A thread is an execution context. A process is a resource container. A core is a hardware execution engine. Parallelism is actual simultaneous execution on multiple cores. One process may contain many threads, and a machine may have many cores, but the existence of many threads does not by itself imply parallel execution.

## Retain / Do Not Confuse

### Retain

- A process is the OS unit of resource ownership, protection, and shared execution environment.
- A thread is the OS or runtime unit of sequential execution and scheduling.
- Thread-private state includes the program counter, register context, stack, and scheduling state.
- Shared process state includes the address space, heap, globals, code, open files, and protection domain.
- The TCB is the bookkeeping structure that stores the state needed to manage and resume a thread.
- Kernel threads are individually visible to the kernel scheduler.
- User threads are primarily managed in user space, which can make them fast but can hide them from the kernel.
- Whether blocking one thread stalls others depends heavily on the threading model.

### Do Not Confuse

- Do not confuse **resource container** with **execution stream**.
- Do not confuse **shared code** with **shared local variables**; stacks are separate per thread.
- Do not confuse **shared memory** with **safe concurrent access**.
- Do not confuse **kernel-scheduled** with **always executing in kernel mode**.
- Do not confuse **logical concurrency** with **true multicore parallelism**.
- Do not confuse **one blocked thread** with **an entire process necessarily being blocked**.
- Do not confuse the **TCB** with the thread’s stack or with the process-level PCB; they are related but conceptually distinct.
