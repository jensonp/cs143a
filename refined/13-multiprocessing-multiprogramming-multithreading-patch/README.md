# Multiprocessing / Multiprogramming / Multithreading Taxonomy Patch

## Purpose

This patch exists because Lecture 2 explicitly introduces the vocabulary distinction among **multiprocessing**, **multiprogramming**, and **multithreading**, but the refined thread material is currently stronger on deep mechanism than on this central taxonomy. Students often hear these three words close together and incorrectly treat them as synonyms. They are not.

This patch should be inserted into the refined thread material as a compact but conceptually strong vocabulary bridge. It gives the short clean distinctions the lecture expects, while also connecting them to the deeper process/thread material already present elsewhere in the refined notes.

## Where to Insert

Insert this as a new section in the thread-focused material **after the early process-versus-thread distinction and before the kernel-thread vs user-thread discussion**.

A good heading is:

`## Multiprocessing, Multiprogramming, and Multithreading`

## Patch Content to Insert

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

This section exists to force those questions apart. Without this distinction, later reasoning about scheduling, blocking, concurrency, parallelism, and thread models becomes vague.

### The Three Definitions

#### Multiprocessing

**Multiprocessing** means the system has multiple processors or CPU cores available for execution.

In plain technical English, multiprocessing is about the **hardware execution capacity** of the machine. The first thing to notice is that this is a property of the machine configuration, not of one specific program. If a machine has multiple cores, more than one execution stream may truly run at the same time.

So multiprocessing answers the question: **how many hardware execution engines can run simultaneously?**

#### Multiprogramming

**Multiprogramming** means the operating system keeps multiple jobs or processes in the system so that the CPU can stay busy by switching among them when one cannot make progress.

In plain technical English, multiprogramming is about the **OS managing multiple processes at once**, even on a machine with only one CPU core. The first thing to notice is that multiprogramming does **not** require true simultaneous execution. On one core, the OS can still keep several processes alive and make them appear to progress by interleaving their execution over time.

So multiprogramming answers the question: **how does the OS keep multiple processes active and the CPU utilized?**

#### Multithreading

**Multithreading** means one process contains multiple threads of execution.

In plain technical English, multithreading is about the **internal execution structure of a single process**. The process remains one resource container and one protection domain, but there are multiple distinct control flows inside it, each with its own program counter, register state, and stack.

So multithreading answers the question: **how many independent execution streams exist inside one process?**

### The Clean Contrast

These three terms live at different levels:

- **multiprocessing** = hardware level  
- **multiprogramming** = operating-system workload-management level  
- **multithreading** = process-internal execution-structure level

That three-level separation is the simplest reliable memory aid.

### Concurrency vs Parallelism

This vocabulary becomes much clearer if you also separate **concurrency** from **parallelism**.

#### Concurrency

**Concurrency** means multiple activities are logically in progress, even if they are not all executing at the exact same instant.

A single-core multiprogrammed system is concurrent because several processes are active over time, even though only one process runs on the core at a given moment.

A single process with multiple threads on one core is also concurrent in structure, because the threads represent multiple execution streams that the OS can interleave over time.

#### Parallelism

**Parallelism** means multiple activities are physically executing at the same time on different processors or cores.

So concurrency is about **structure and interleaving possibility**, while parallelism is about **actual simultaneous hardware execution**.

A useful contrast:
- one core can support concurrency without parallelism
- multiple cores allow parallelism
- multithreading gives more execution streams, but true parallelism depends on multiprocessing or multiple kernel-visible runnable threads on multiple cores

### One Important Constraint: One Thread per Core at a Time

Even with many threads, only **one thread can run on a given CPU core at a time**.

This matters because students sometimes hear “multithreading” and imagine all threads inside the process are literally executing together automatically. That is false. They may be:
- interleaved on one core,
- or truly parallel on multiple cores,
depending on the hardware and threading model.

So the number of threads and the number of simultaneously executing threads are different quantities.

### Why Blocking Behavior Belongs Here

This taxonomy is not just vocabulary. It explains why blocking behavior differs across models.

If the kernel can see and schedule multiple kernel threads separately, then one thread blocking in a system call does not necessarily stop the others.

If many user threads are multiplexed onto one kernel-visible execution entity, then one blocking system call may stall the whole process from the kernel’s perspective.

That means the question “what blocks?” is inseparable from the question “which execution entities are visible to the kernel?” This is why the taxonomy belongs near the thread-model discussion.

### A Compact Worked Contrast

Consider one machine with one CPU core and two processes, A and B.

If the OS switches between A and B so that the CPU stays busy when one waits for I/O, that is **multiprogramming**.

Now suppose process A contains three threads. Then A is **multithreaded**, because one process contains multiple execution streams.

But since the machine has only one core, only one thread total can run on that core at a time. So the system may be highly concurrent, but not parallel.

Now move the same workload onto a machine with four cores. The machine is now **multiprocessing-capable**. If the kernel sees multiple runnable threads, different threads or processes may truly run in parallel on different cores.

This example teaches the general rule:

- multiprogramming explains why multiple processes can be alive and interleaved,
- multithreading explains why one process can contain multiple execution streams,
- multiprocessing explains why some of those execution streams may run simultaneously.

### Common Misconceptions

#### Misconception 1: Multiprogramming and multiprocessing mean the same thing

False. Multiprogramming is about managing multiple processes over time. Multiprocessing is about having multiple hardware execution engines.

#### Misconception 2: Multithreading means multiple programs

False. Multithreading means multiple threads **inside one process**.

#### Misconception 3: If a program is multithreaded, it is automatically parallel

False. On one core, threads may only be interleaved. True parallelism depends on hardware and kernel scheduling visibility.

#### Misconception 4: More threads means more cores

False. Threads are execution contexts. Cores are hardware execution resources.

### Retain / Do Not Confuse

#### Retain
- **multiprocessing** = multiple CPUs/cores  
- **multiprogramming** = multiple jobs/processes managed by the OS  
- **multithreading** = multiple threads inside one process  
- concurrency is not the same as parallelism  
- only one thread can run on one core at a time  

#### Do Not Confuse
- do not confuse hardware multiplicity with software multiplicity  
- do not confuse many threads with true simultaneous execution  
- do not confuse many processes with one multithreaded process  
- do not confuse concurrency structure with physical parallel execution
