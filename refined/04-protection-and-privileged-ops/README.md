# Protection Cluster: User Mode, Kernel Mode, Privileged Instruction, Trap, Timer Interrupt, CPU Protection, I/O Protection

## Why This Cluster Exists

An operating system is not just a collection of helpful routines. It is a system for **controlled sharing of a machine**. The machine has one processor, some memory, and devices that can change the outside world: disks can overwrite files, network cards can send packets, displays can show data, and timers can interrupt execution. If every program could execute any machine instruction at any time, then the first bug or malicious program could overwrite the disk, disable interrupts, hang the processor forever, or read and alter another program’s state. In that world, there is no real operating system, only competing pieces of code fighting over hardware.

So this topic appears because a basic question from earlier operating-systems study becomes unavoidable:

**How can many programs run on one machine without being allowed to seize total control of that machine?**

That question forces the need for a protection boundary. The boundary must separate ordinary program execution from system-control execution. It must let programs ask for services they are not allowed to perform directly. It must also let the operating system take control back even when a program does not voluntarily give it up.

This entire cluster of ideas answers that one question.

The key move is this: the processor supports at least two execution states, and hardware enforces different rules in those states. Once hardware enforces the boundary, the operating system can build everything else on top of it: process isolation, system calls, scheduling, device control, safe sharing of I/O, and recovery from faults.

This chapter is also the point where several earlier preview terms become first-class concepts rather than motivational placeholders. Earlier files may have mentioned interrupts, traps, or kernel handling in order to explain why execution structure matters, but this is the first file where the authority boundary itself is being taught as a mechanism. Read it that way: earlier references were previews; here the protection machinery becomes formally intelligible.

## The Core Problem: Unrestricted Execution Is Incompatible with Multi-Program Systems

Suppose a user program could do all of the following directly:

It could write to the disk controller’s command registers and tell the disk to overwrite block 0. It could disable interrupts so the processor never receives clock interrupts again. It could load an arbitrary value into the memory-management registers and map itself over kernel memory. It could jump into any address, including an address containing operating-system code that assumes trusted calling conditions. It could loop forever and keep the CPU permanently.

None of those are abstract dangers. They are exactly the kinds of machine actions that real processors expose in some form. The operating system therefore cannot protect the machine merely by asking programs to behave. It needs enforcement from below, at the hardware level.

That enforcement comes from three linked ideas:

1. **Modes**: the processor distinguishes ordinary execution from privileged execution.
2. **Privileged instructions**: some instructions are legal only in privileged execution.
3. **Forced control transfers**: the processor can transfer control to the kernel on an event such as a system call, fault, or timer expiration.

The rest of the cluster is best understood as a consequence of those three ideas.

### Local minimum definition of process for this chapter

This chapter uses the word **process** before the full process chapter appears. For the purposes of this chapter only, treat a process as **a running user-level computation together with the operating system record that identifies it as a separately managed execution**. Later chapters will expand that into address space, rights, process state, lifecycle, and resource ownership. Here the term is needed only so we can say clearly that hardware is protecting one user computation from taking control of the whole machine.

## User Mode and Kernel Mode

### Formal definition: processor mode

A **processor mode** is a hardware-defined execution state that determines which instructions may execute, which resources may be accessed directly, and how certain control transfers are handled.

### Interpretation

What this is really saying is that the CPU does not treat all running code as equally trusted. The current mode acts like a hardware-level answer to the question, “How much authority does the currently executing code have?” The first thing to notice is that this is not a software convention. It is built into the processor’s control logic.

Most introductory operating-systems discussions use two modes:

- **User mode**: restricted execution.
- **Kernel mode**: privileged execution.

Some processors have more than two rings or levels, but the conceptual structure in operating systems is still usually taught as a user/kernel split, because that is the essential distinction.

### Formal definition: user mode

**User mode** is the processor mode in which ordinary application code runs, with hardware-enforced restrictions that prevent direct execution of privileged operations and direct control of protected machine resources.

### Interpretation

User mode means “you may compute, but you may not govern the machine.” A program in user mode can usually perform ordinary arithmetic, use registers, branch, call functions, and read or write memory that is mapped into its own address space. But it cannot directly reprogram the timer, alter the page tables arbitrarily, execute device-control instructions, disable interrupts, or halt the machine.

### Formal definition: kernel mode

**Kernel mode** is the processor mode in which the operating-system kernel executes, with permission to perform privileged operations needed to manage the processor, memory, interrupts, and I/O devices.

### Interpretation

Kernel mode means “this code is allowed to act on behalf of the whole system.” The important thing to notice is that kernel mode is not “faster user mode” or “a library mode.” It is a fundamentally different authority level. Code running there can perform actions whose effects reach outside the current process and alter global machine state.

## What Is Fixed and What Varies Here?

What is fixed is the hardware rule: the CPU is always in some current mode, and mode affects what operations are allowed. What varies is the currently running code and which mode it is in at a given instant. A user process may be executing in user mode, then enter the kernel through a system call trap, execute kernel code in kernel mode for a short time, and later return to user mode.

That means a process is not “a user-mode thing” at all times. More precisely, the **same process** may alternate between user-mode execution of its own code and kernel-mode execution of operating-system code on its behalf.

This distinction matters because students often confuse:

- **process** with **mode**,
- **program identity** with **current privilege**, and
- **kernel code** with **kernel process**.

The kernel is code. A process may momentarily execute kernel code during a system call or interrupt handling. That does not mean the process has become trusted application code inside the kernel. It means the processor has switched to a privileged control path managed by the operating system.

## Privileged Instructions

Mode differences would be useless if every instruction remained legal in every mode. So now we need the second object in the chain.

### Formal definition: privileged instruction

A **privileged instruction** is a machine instruction that the processor permits to execute only in a privileged mode such as kernel mode; if attempted in user mode, the processor raises an exception or trap to the operating system.

### Interpretation

This means the hardware marks certain actions as too dangerous to be executed by arbitrary programs. The rule is not “user programs should avoid these instructions.” The rule is “the CPU itself refuses them when the current mode is unprivileged.” That hardware refusal is what makes the protection boundary real.

### Why privileged instructions must exist

If all instructions were available in user mode, then mode bits would not prevent anything important. A user program could simply execute the same machine operations the kernel uses to manage the system. So privileged instructions are the teeth behind the mode distinction.

### Common categories of privileged instructions

The exact instruction set depends on the processor architecture, but the general categories are stable:

- instructions that change processor control state, such as interrupt enable or disable;
- instructions that load memory-management or page-table control registers;
- instructions that start or control I/O operations directly;
- instructions that halt or reset the machine;
- instructions that install trap handlers or manipulate protected status registers.

### Why these instructions are dangerous in user mode

Each privileged category protects a different part of the machine:

If a user program could disable interrupts, the scheduler might never regain control. If it could modify memory-management registers, it could map the kernel’s memory or another process’s memory. If it could command devices directly, it could read from or write to disks and network devices without permission checks. If it could install its own exception handlers at the hardware level, it could intercept control paths meant for the operating system.

So the operating system depends on the processor making these instructions impossible in user mode.

## From “Need Service” to “Enter the Kernel”: Trap

A protected system must not only **block** forbidden actions. It must also provide a legitimate way for user programs to request privileged services. A program needs to open files, allocate memory, create processes, send data to devices, and terminate. Since user mode cannot do those things directly, there must be a controlled doorway into kernel mode.

That doorway is the trap mechanism.

### Formal definition: trap

A **trap** is a synchronous transfer of control to a predefined kernel handler caused by the currently executing instruction or by a processor-detected condition arising from that instruction.

### Interpretation

“Synchronous” is the key word here. A trap happens **because of the instruction stream the CPU is currently executing**. The processor does not just interrupt at an arbitrary later time. It reaches an instruction or condition that immediately requires the CPU to stop ordinary execution and jump to a handler chosen by the operating system or architecture.

The first thing to notice is that traps cover more than one situation. They include intentional entry into the kernel, such as a system call instruction, and unintentional exceptions, such as division by zero, invalid opcode, or page fault.

### Two major uses of traps

#### 1. System-call trap

A user program intentionally executes a special instruction whose meaning is roughly “request kernel service.” That instruction causes a trap into kernel mode. The operating system inspects which service was requested and performs the operation if allowed.

#### 2. Exception or fault trap

The currently executing instruction causes a condition the hardware cannot allow to continue normally: divide by zero, invalid memory reference, privileged instruction in user mode, or page not present. The processor traps into the kernel so the operating system can decide what to do.

### What the processor checks, in order, during a trap

The exact micro-steps vary by architecture, but conceptually the sequence is:

The processor identifies a trap condition. The condition may be an explicit trap instruction or an exception detected while decoding or executing an instruction. The processor then saves enough state to resume or diagnose the interrupted computation later. This typically includes at least the program counter and processor status, and often other machine state as defined by the architecture. The processor switches into kernel mode. It then loads the address of the appropriate trap handler from a protected table or vector. Control transfers to that kernel handler.

Each part matters. Saving state means the computation is not simply discarded. Switching mode means the handler can now execute privileged instructions. Using a protected handler address means a user program cannot redirect the trap to its own fake operating system.

### What conclusions a trap allows

A trap lets the system conclude one of several things:

- a valid system service was requested;
- the user program attempted an illegal action;
- a recoverable condition must be handled, such as a page fault;
- the process should be terminated because the fault is fatal.

So a trap is not “just an error.” It is the processor’s controlled handoff to the kernel whenever current execution requires privileged judgment.

## Trap Versus Procedure Call

This distinction is foundational.

A normal procedure call transfers control to another function **within the same privilege regime**. It is a programming-language or ordinary instruction-set control transfer. A trap transfers control across the protection boundary under hardware supervision.

In a procedure call, the target address is determined by the program’s instructions and allowed control-flow rules. In a trap, the target handler is chosen by protected machine state. In a procedure call, mode usually does not change. In a trap, mode commonly changes from user mode to kernel mode. In a procedure call, the callee cannot suddenly gain authority over hardware merely because it was called. In a trap, the handler executes with kernel authority precisely because hardware changed the mode.

Confusing system calls with ordinary function calls leads to weak understanding. A system call may be wrapped by a library function in source code, but the critical event is not the library call. The critical event is the trap into the kernel.

## Interrupts and Why the Timer Matters

A system with only traps would still be unsafe in one major way. A user program could simply never make a system call and never fault. It could loop forever in user mode, using the CPU indefinitely. If the operating system only regained control when the user program voluntarily entered the kernel, then scheduling would fail.

So the machine needs an **external** way to force control back to the operating system.

That is the role of interrupts.

### Formal definition: interrupt

An **interrupt** is an asynchronous transfer of control to a predefined handler caused by an external or independently progressing event, rather than by the semantic completion of the currently executing instruction.

### Interpretation

“Asynchronous” means the event is not tied to the meaning of the current instruction. The instruction stream did not ask for it. The event arrives from outside that stream: a device completion, a clock tick, or some other hardware signal. The processor notices the interrupt between instructions or at architecturally defined interruption points and transfers control to a handler.

### Formal definition: timer interrupt

A **timer interrupt** is a hardware interrupt generated by a timer device after a configured interval or at recurring intervals, causing the processor to transfer control to the operating system.

### Interpretation

This is the operating system’s alarm clock and leash on CPU ownership. The key thing to notice first is that the timer runs independently of user programs. A user program does not get to decide whether the timer fires. The kernel programs the timer, the timer counts, and when the interval expires the processor is interrupted.

### Why the timer interrupt is indispensable

The timer interrupt solves the problem of non-cooperative or buggy programs. Even if a process enters an infinite loop and never invokes the kernel voluntarily, the timer interrupt eventually fires. Control returns to the operating system, which can update accounting information, enforce time limits, and choose another process to run.

Without a timer interrupt, a multi-program operating system would have only cooperative scheduling or no safe preemption at all. The timer is therefore central to both scheduling and protection.

## Trap Versus Interrupt

These are often mixed up because both transfer control to the kernel. The distinction must be explicit.

A **trap** is synchronous with the currently executing instruction stream. It is caused by that stream: a system-call instruction, a divide-by-zero, a page fault, an illegal instruction, a privileged instruction attempted in user mode.

An **interrupt** is asynchronous relative to the current instruction stream. It is caused by an outside event: timer expiration, disk completion, network packet arrival.

Why does this distinction matter? Because it changes what the operating system can infer.

If a trap occurred, the kernel can conclude that something about the current instruction or its immediate effect required attention. If a timer interrupt occurred, the kernel can conclude only that time has passed or a hardware event has occurred; it does not mean the current instruction was wrong.

This difference also affects how return behavior is interpreted. A fault-like trap may require retrying the instruction, emulating it, delivering a signal, or killing the process. A timer interrupt typically returns to the interrupted computation unless the scheduler decides to context-switch to another process.

## CPU Protection

Now the cluster becomes more system-level. We have modes, privileged instructions, traps, and timer interrupts. What larger protection property do they jointly enforce for the processor itself?

### Formal definition: CPU protection

**CPU protection** is the set of hardware and operating-system mechanisms that ensure no user program can seize unrestricted control of the processor, execute privileged processor-management operations directly, or prevent the operating system from eventually regaining control of the CPU.

### Interpretation

CPU protection means the processor remains governable. It is not enough that a program cannot write the disk. The operating system must also ensure that the program cannot monopolize execution, disable control paths, or alter machine control state directly.

### Components of CPU protection

CPU protection depends on several earlier objects in the dependency chain.

First, user mode prevents direct execution of privileged processor-control instructions. Second, privileged instructions ensure that actions like disabling interrupts or loading control registers are reserved to the kernel. Third, traps ensure that if a user process tries to execute a privileged instruction, the processor does not perform it but instead transfers control to the kernel. Fourth, the timer interrupt ensures that the kernel regains control even if the user process never voluntarily enters the kernel.

The operating system usually loads a timer before scheduling a user process. The timer is a privileged resource, so only kernel code may configure it. When the timer expires, the hardware interrupts the CPU, which enters kernel mode and runs the timer interrupt handler. At that point the operating system can decide whether to resume the same process or switch to another one.

### What CPU protection is checking

Conceptually, CPU protection asks three recurring questions.

The first is: **Is the currently executing code allowed to perform this processor-control operation?** If no, the attempt traps.

The second is: **Can the current process continue to run indefinitely without the kernel regaining control?** The timer interrupt ensures the answer is no.

The third is: **When control returns to the kernel, can the kernel inspect and manage the interrupted process safely?** Saved processor state and protected trap/interrupt vectors ensure the answer is yes.

### Boundary conditions and failure modes in CPU protection

If the timer can be disabled by user code, CPU protection fails because preemption fails. If privileged instructions are mistakenly executable in user mode, CPU protection fails because user programs can take over machine control. If trap vectors can be modified by user code, CPU protection fails because entry into the kernel can be redirected. If return-from-trap instructions are not protected, user code may fabricate privileged returns.

Another subtle failure mode is assuming that user mode alone is enough. It is not. A user program that cannot execute privileged instructions may still loop forever. Without a timer interrupt, it can still monopolize the processor.

## I/O Protection

Processor protection is only part of the story. The machine also has devices that move data and affect the outside world. Protection must cover them too.

### Formal definition: I/O protection

**I/O protection** is the set of hardware and operating-system mechanisms that prevent user programs from directly controlling input/output devices or device-control interfaces except through kernel-mediated operations that enforce correctness, isolation, and permissions.

### Interpretation

I/O protection means ordinary programs do not talk to devices as masters. They request I/O through the operating system. The kernel checks whether the operation is allowed, arranges it, and manages the device state. The first thing to notice is that device control is dangerous for the same reason processor control is dangerous: devices are shared, stateful, and globally consequential.

### Why direct device access is dangerous

If a user program could directly issue disk commands, it could read or overwrite any file-system block regardless of file permissions. If it could directly control the network device, it could forge traffic or bypass firewall and accounting logic. If it could reprogram the console or DMA engine, it could corrupt memory or snoop on data transfers.

So device access must be mediated.

### How I/O protection is usually enforced

The exact mechanism depends on architecture, but the conceptual pattern is stable.

Device-control instructions are privileged, or access to device-control registers is possible only from kernel mode, or memory regions used for memory-mapped I/O are mapped only into the kernel’s protected address space. Therefore, a user process cannot directly start device operations. Instead it traps into the kernel through a system call such as `read`, `write`, or `ioctl`. The kernel checks permissions, validates arguments, coordinates buffering and scheduling, and then uses its privileged access to command the device.

### What is fixed and what varies in I/O protection

What is fixed is that the kernel owns direct device control. What varies is which process requested I/O, what operation was requested, whether permissions allow it, and what device state currently exists.

This matters because the kernel is not merely relaying bytes. It is arbitrating among multiple requesters. Two user processes may both want disk access, but neither is allowed to manipulate the disk controller directly because the device state must remain coherent and policy-enforced.

### I/O completion and interrupts

I/O protection also links back to interrupts. After the kernel starts an I/O operation, the device typically works independently. When the operation completes or needs attention, the device raises an interrupt. The processor enters kernel mode and runs the device interrupt handler. The kernel then updates device state, wakes waiting processes, copies data if needed, and decides what should run next.

So a protected I/O path has both directions:

- **request path**: user code traps into the kernel to ask for I/O;
- **completion path**: device interrupts the kernel to report progress or completion.

## A Fully Worked Example: Reading a Byte from a File

A good worked example should reveal the whole mechanism, not just one definition. Consider a user program that wants to read one byte from an open file descriptor.

The source code may call a library function such as `read(fd, &x, 1)`. At the source level, that looks like an ordinary function call. But conceptually the important sequence starts when the library wrapper prepares the system-call number and arguments in architecturally defined locations such as registers or the stack, then executes the special system-call instruction.

At that moment the processor checks the instruction semantics. Because the instruction is defined as a trap-generating system-call instruction, the processor saves the current user-mode state, including at least the program counter needed to resume later. It switches the mode bit from user mode to kernel mode. It uses a protected trap-vector entry to jump to the system-call handler.

Now the kernel is executing in kernel mode. It examines the system-call number and sees that the request is a read operation. It then checks the arguments. Is the file descriptor valid for this process? Is it open for reading? Is the user buffer address a valid writable address in this process’s address space? These checks matter because the kernel must not trust user-provided values. A user could pass a bad descriptor or a pointer into unmapped or protected memory.

Suppose the descriptor refers to a disk file whose needed data is not yet in memory. The kernel then prepares a disk I/O request. Because disk-control interfaces are privileged, the user process could not have done this directly. The kernel programs the disk controller or queues the request through its driver. The requesting process may now block, because the data is not yet available.

At some later time, the disk device finishes the transfer and raises an interrupt. This interrupt is asynchronous relative to whatever instruction was running then. The processor saves the current state of that interrupted computation, switches to kernel mode if not already there, and jumps to the disk interrupt handler. The handler determines which operation completed, records the result, and wakes the process waiting for the data.

Eventually the scheduler chooses that process again. The kernel resumes the read system call, copies the requested byte into the user buffer after validating that the destination is allowed, sets the return value to indicate success, restores the saved user-mode state, and executes a protected return-from-trap instruction.

The processor then switches back to user mode and resumes the user program at the instruction after the system-call trap.

This example teaches several general truths.

First, user code does not directly perform privileged work; it requests it. Second, the same logical operation may involve both a **trap** into the kernel and a later **interrupt** from a device. Third, protection is not only about forbidding dangerous instructions. It is also about validating user-supplied arguments and preserving controlled ownership of shared hardware.

## Attempted Violation Example: User Program Tries to Disable Interrupts

Now consider a different example because it highlights CPU protection sharply.

Suppose a user program executes an instruction that, on this architecture, disables interrupts. The program may be malicious and trying to prevent preemption, or it may simply be buggy and executing random bits.

The processor decodes the instruction and checks the current mode. The mode is user mode. The instruction is marked privileged. Therefore the processor does **not** perform the interrupt-disable operation. Instead it raises a trap or exception for privileged-instruction violation. As part of trap handling, the processor saves the current execution state, switches to kernel mode, and transfers control to the kernel’s exception handler.

The kernel now concludes that the process attempted an illegal privileged operation. Depending on policy and architecture, the kernel may terminate the process, send it a signal, log the event, or in some specialized environment emulate the instruction. In a standard protected operating system, termination is the common outcome.

The important lesson is that the machine state that mattered most — interrupt enable state — was never changed. The forbidden effect did not happen. That is the essence of hardware-enforced protection.

## CPU Protection and I/O Protection Are Related but Not Identical

Students often remember these as one vague idea: “the OS protects stuff.” That is not enough.

CPU protection is about who governs processor execution and control state. It focuses on privilege level, preemption, interrupt control, and the guarantee that the OS regains control.

I/O protection is about who governs devices and device interfaces. It focuses on preventing direct device manipulation and requiring kernel mediation for operations that read from or write to the outside world or to shared device state.

They are related because both rely on user/kernel mode and privileged operations. But they protect different classes of resources and different failure modes.

A system could have decent I/O protection but poor CPU protection if user code can disable interrupts or monopolize the processor. A system could have decent CPU protection but poor I/O protection if user code can still access device registers directly. A correct operating system needs both.

## Hidden Assumptions in This Topic

Several assumptions are often left implicit, but understanding them makes the topic much clearer.

One hidden assumption is that the trap and interrupt handler addresses are themselves protected. If user code could rewrite the vector table, then traps and interrupts would enter attacker-controlled code.

Another hidden assumption is that returning from kernel mode to user mode is itself controlled by privileged instructions. Otherwise a user program might fabricate a return sequence that re-enters user execution with privileged status still set.

A third hidden assumption is that memory protection exists alongside CPU and I/O protection. If user processes could write kernel memory directly, they could simply patch the kernel or the trap table. So in real systems, mode protection and memory protection are tightly coupled.

A fourth hidden assumption is that devices capable of DMA are also constrained. Otherwise a device could write into arbitrary memory and bypass CPU-mode checks. This is why advanced systems also need mechanisms such as IOMMUs. That detail is usually taught later, but it is good to know that I/O protection has a deeper hardware layer in modern machines.

## Common Misconceptions

One misconception is that user mode means a program cannot do anything dangerous. That is false. A user program can still consume CPU time, allocate memory within limits, crash itself, generate enormous legal I/O requests, or exploit kernel bugs. User mode restricts direct privileged control; it does not make programs harmless.

Another misconception is that kernel mode means all kernel actions are automatically safe. Also false. Kernel code has great power, which means kernel bugs are especially dangerous. Protection mechanisms prevent user code from directly performing privileged actions, but they do not prevent faulty kernel logic from making bad decisions.

A third misconception is that a trap is just another word for interrupt. They are related but distinct. The source and meaning of the event differ, and the operating system interprets them differently.

A fourth misconception is that the operating system regains control only when a process makes a system call. False. The timer interrupt exists precisely so the OS does not depend on user cooperation.

A fifth misconception is that system calls are ordinary function calls into the kernel. At the source level they may be wrapped by functions, but the actual crossing of the protection boundary occurs through a hardware trap mechanism.

## How This Topic Supports Later Material

This cluster supports nearly every major later topic in operating systems.

It supports **system calls**, because a system call is a controlled trap into the kernel.

It supports **process scheduling**, because timer interrupts let the operating system preempt user processes.

It supports **memory protection and virtual memory**, because privileged control of memory-management hardware is necessary to isolate address spaces.

It supports **device drivers and file systems**, because I/O protection requires kernel-mediated device access and interrupt-driven completion handling.

It supports **security**, because privilege separation is the hardware basis for enforcing trust boundaries.

It supports **exception handling**, because many faults are delivered through the same trap machinery.

Without this protection cluster, all of those later topics become either impossible or merely advisory rather than enforced.

## Conceptual Gaps and Dependencies

This topic assumes several prerequisite concepts. It assumes a basic model of the CPU as a fetch-decode-execute machine with registers, a program counter, and instructions. It assumes the reader knows what an operating system is trying to manage: processes, memory, and devices. It also assumes some comfort with the difference between hardware and software responsibilities.

For many students at this stage, the weakest prerequisite is often the distinction between **architecture-level events** and **source-code-level constructs**. Students may know what a function call looks like in C, but not what the processor actually does on a trap or interrupt. Another weak prerequisite is often the notion of a device controller and how software issues commands to hardware rather than “talking to the disk” abstractly.

This topic refers to nearby ideas without fully teaching them. It refers to memory protection, page faults, kernel stacks, interrupt vector tables, device controllers, DMA, and context switching, but it does not fully develop them here. It also touches scheduler decisions without teaching scheduling policies.

There are homework-relevant and lecture-relevant facts that are not covered by explanation alone. A course may require architecture-specific details such as the exact status register bits saved on a trap, the distinction among trap, fault, and abort in a particular ISA, the exact return instruction used to leave kernel mode, or the exact privilege rings and page-protection bits on x86, ARM, or RISC-V. Those details depend on the course and architecture and must be learned separately.

Immediately before this topic, the most useful concepts to study are: what a process is, what the CPU and device hardware model looks like, what an instruction set is, and what it means for multiple programs to share one machine. Immediately after this topic, the most natural concepts to study are: system calls, context switching, scheduling and preemption, memory protection and address spaces, and interrupt-driven I/O.

## Retain / Do Not Confuse

### Retain

- User mode and kernel mode are hardware-enforced execution states with different authority.
- Privileged instructions are the concrete mechanism that makes the mode distinction matter.
- A trap is a synchronous entry into the kernel caused by the current instruction stream or its immediate effects.
- A timer interrupt is an asynchronous hardware event that lets the OS regain control of the CPU.
- CPU protection means user code cannot take over processor control or avoid eventual kernel preemption.
- I/O protection means user code cannot directly command devices; device access is mediated by the kernel.
- A single user request such as `read` can involve both a trap into the kernel and a later interrupt from a device.

### Do Not Confuse

- Do not confuse a **process** with a **mode**. A process can execute user code in user mode and later kernel code during a system call.
- Do not confuse a **trap** with an **interrupt**. Trap: synchronous with current instruction stream. Interrupt: asynchronous external event.
- Do not confuse a **system call wrapper function** with the actual **protection-boundary crossing**. The crossing occurs at the trap instruction.
- Do not confuse **CPU protection** with **I/O protection**. They rely on related mechanisms but protect different resources and failure modes.
- Do not confuse **being in user mode** with **being harmless**. User programs can still misbehave; they are simply prevented from directly performing privileged machine operations.
