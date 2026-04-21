# Boot-Time Process Tree, PID 1, and the Creation of init

There is a moment in boot when the machine is already executing instructions but the ordinary user-space process tree does not yet exist. That is the object this chapter studies: the transition from “the kernel is bringing the machine up” to “there is now a first ordinary user-space process from which the familiar process tree can grow.” The formal statement comes second: in a Unix-like system, the first ordinary user-space process is conventionally assigned **PID 1**, and that process is traditionally called **init**. The interpretation matters immediately. PID 1 is not just “the first process that happens to run.” It is the process that stands at the boundary between bootstrapping and normal process creation.

This chapter belongs **after** the ordinary process lifecycle for a simple reason. Before learning boot-time creation, one must already know what a normal process is, how a process is ordinarily created, what parent-child relationships mean, how `fork`, `exec`, and `wait` fit together, and why zombies and orphans exist. Without that background, the specialness of boot-time creation cannot even be stated cleanly. Once the ordinary lifecycle is understood, the right question appears naturally: if processes normally come from earlier processes, then where did the first one come from?

The point of this lesson is not to reteach `fork`/`exec` from zero. It is to expose the **boundary case** that ordinary lifecycle explanations usually leave implicit. “All processes are created by other processes” is good enough inside an already-running system. It is not the whole story for system startup, and it is not the whole story for kernel-internal execution contexts either. Boot is where the approximation shows its seam.

**Retain.** Ordinary process lifecycle comes first because boot-time creation is understood as an exception, or more precisely as a bootstrap case, relative to ordinary parent-child process creation.

**Do Not Confuse.** This chapter is not about replacing the usual lifecycle model. It is about identifying the exact point where that model begins to apply.

## The entities at the boundary: firmware, bootloader, kernel early boot, kernel threads, first user-space process, init

At power-on, the machine does not begin by running a shell, a user program, or even an ordinary process in the operating-system sense. It begins by executing platform-defined startup code from a reset vector. On real machines, that earliest code belongs to firmware. Firmware is not “the operating system starting.” Firmware is platform control logic whose job is to perform enough machine initialization to locate something bootable and transfer control onward.

A **bootloader** is the next distinct object. Its formal role is to load an operating system kernel image, together with whatever auxiliary data the kernel needs at entry, into memory and jump to the kernel’s entry point. Interpretation: the bootloader prepares the kernel to begin; it is not itself the kernel, and it is not one of the ordinary user processes that later appear in the system’s process tree. Some systems blur firmware and bootloader responsibilities, and some boot paths use multiple stages, but the conceptual separation remains useful: something before the kernel arranges for the kernel to start.

**Kernel early boot** begins when control reaches kernel code. The formal object here is the kernel executing its own initialization path before ordinary user-space execution exists. Interpretation: at this stage, the machine is “running the OS” in the broad sense, but not yet running the normal user-space world. Core subsystems must come up first: memory management, interrupt handling, scheduling structures, device discovery, internal synchronization machinery, and enough filesystem or image support to locate the first user-space program.

**Kernel threads** belong to the kernel’s own execution domain. A kernel thread is schedulable work that runs in kernel mode and does not represent a normal user-space program image with a user virtual address space. Interpretation: a kernel thread may look process-like to the scheduler and may even have a PID-like identifier in some systems, but it is not the same kind of object as a user process launched from an executable file. This distinction matters because boot often creates kernel threads before the first user-space process exists.

The **first user-space process** is the first schedulable execution context that is backed by a user-mode program image and enters the ordinary user-space side of the system call boundary. In Unix-like systems, this process is conventionally **PID 1**. Interpretation: this is the first point at which “user-space process tree” stops being merely potential and becomes actual.

**init** is the traditional name for that first user-space process. The formal statement is slightly broader than the historical name: in Unix-like systems, the process occupying PID 1 is the system’s initial user-space process and carries special system responsibilities, whether the actual program binary is the classic `init`, `systemd`, `launchd`, `busybox init`, or another implementation. Interpretation: “init” names a role before it names a specific program.

Boundary conditions matter here. Firmware and bootloader are not normally nodes in the operating system’s process tree. Kernel early boot is operating-system execution, but not yet ordinary process-tree execution. Kernel threads may exist before user-space processes, but they are not the same as the first user-space process. PID 1 is not merely “whichever process got a small number first”; it is the designated root of ordinary user-space startup.

**Retain.** Firmware gets the machine to a bootable state. The bootloader gets the kernel into memory and transfers control. Kernel early boot establishes core OS machinery. Kernel threads are kernel-side schedulable entities. The first user-space process is PID 1, whose role is traditionally called init.

**Do Not Confuse.** Earlier in time does not mean “ancestor in the user-space process tree.” Firmware and bootloader happen earlier, but they are not the parent chain of your shell.

## The canonical boot-time sequence: from power-on to the beginning of the ordinary process tree

When the machine powers on, the CPU begins execution from a hardware-defined reset location. At this point there is no user-space process tree, no shell, and no ordinary parent process from which anything could have been forked. The firmware performs minimal machine bring-up: enough processor, memory, and device initialization to locate a boot path. Depending on the platform, firmware may directly load a kernel, or it may load a bootloader that then loads the kernel.

Once the kernel image is loaded into memory and control is transferred to the kernel entry point, the system enters kernel early boot. This is the phase in which the kernel constructs the conditions that ordinary processes later depend on. The exact order varies by operating system, but the logical requirements are stable. The kernel must establish its own execution environment, discover or initialize memory-management structures, set up interrupt and exception handling, initialize scheduling machinery, bring up essential device support, and make available enough storage or image-loading support to obtain the first user-space program.

Only after these prerequisites are in place can the kernel create or launch the first user-space process. The key fact is that this transition is **kernel-mediated**, not the result of an earlier user process calling `fork`. The kernel either directly fabricates the first user-space execution context or creates an internal bootstrap task that then transitions into user space by executing the initial program image. Either way, the chain does not begin with an ordinary user-space parent. It begins because the kernel decides that the machine is ready to cross from internal bootstrapping into ordinary process execution.

From that moment onward, the process tree that students usually picture becomes real in the familiar sense. PID 1 begins running in user space. It starts system initialization work, launches service managers, daemons, consoles, login programs, or equivalent session-establishment machinery, and becomes the ancestral root of the ordinary user-space process hierarchy. Not every later process is a direct child of PID 1, but every long-lived ordinary user-space lineage traces back to the boot transition that established PID 1.

A deep mechanism trace makes the boundary precise. Before the first user-space process can run, the kernel must do more than “load a file.” It must establish a process descriptor or equivalent control structure, assign an identity, create or attach an address-space object appropriate for user mode, map the executable image and its supporting data, prepare an initial user stack, set the instruction pointer to the user program’s entry location, arrange the privilege-level transition so execution will resume in user mode rather than kernel mode, and mark the task runnable so the scheduler may dispatch it. Each of those checks has a meaning. If there is no scheduler state, there is nothing to dispatch. If there is no address space, the code has nowhere valid to execute in user mode. If the executable image cannot be found or mapped, there is no first program to become PID 1. If the privilege transition is not prepared, execution never leaves boot-time kernel control. The first user-space process exists only when all of these conditions have been made true.

The failure modes at this stage are correspondingly severe. Failure before the first user-space process means the system does not merely “fail to launch an application”; it fails to complete boot into ordinary operating-system operation. The screen may freeze at early boot messages, panic diagnostics may appear, or the machine may reboot or drop into a recovery shell if such a fallback exists. These are not ordinary process-launch failures because the ordinary process world has not yet been established.

**Retain.** The boot-time sequence is: power-on, firmware/bootloader, kernel early initialization, kernel-mediated creation or launch of the first user-space process, then PID 1 beginning the ordinary user-space process tree.

**Do Not Confuse.** “The kernel loads init” is not shorthand for an ordinary parent process calling `fork` and `exec`. It is shorthand for the bootstrap transition that makes ordinary process creation possible.

## Why “all processes are created by other processes” is only approximately true

Inside an already-running system, the statement feels exact because it tracks what ordinary observation sees. A shell forks a child. A daemon supervisor spawns workers. A service manager launches services. Parents produce children. Within that domain, the statement is practically right and pedagogically useful.

But its domain is limited. The statement silently assumes that the system is already past bootstrapping and already possesses at least one process from which the rest can descend. The first user-space process cannot be explained by an earlier ordinary user-space parent, because there is none. The system must therefore include a special-case creation path in which the kernel itself initiates the first ordinary process context.

This is not a contradiction of the lifecycle model; it is the base case that lets the lifecycle model start. In the same way that recursive reasoning needs a non-recursive base case, process-tree reasoning needs a boot-time base case. Once PID 1 exists, the familiar model applies robustly. Before PID 1 exists, the kernel is still constructing the world in which that model becomes meaningful.

A second approximation hides here too. Even after boot, kernel threads and certain kernel-internal execution contexts are not well described as ordinary user processes created by other user processes. The scheduler may manage them, and the system may assign visible identifiers to them, but they belong to a different side of the privilege boundary and serve different purposes.

The misconception to reject is the overly literal reading: “there must always be a parent process in the same sense, all the way back forever.” No. There is an ordinary rule for ordinary runtime, and there is a bootstrap boundary where the kernel establishes the first ordinary process. That is the point at which the infinite regress stops.

**Retain.** “All processes are created by other processes” is true enough for ordinary runtime reasoning but incomplete at boot. The first ordinary user-space process requires a kernel bootstrap path.

**Do Not Confuse.** Approximate does not mean useless. The ordinary rule remains the correct mental model after the boot base case has been accounted for.

## Why PID 1 is special

The first special feature of PID 1 is structural. It stands at the root of ordinary user-space startup. That alone would make it conceptually important, but operating systems, especially Unix-like ones, assign it additional semantic obligations.

The second special feature is **orphan adoption**. When a process loses its parent because that parent exits before waiting or before the child itself exits, the child must still have somewhere to be reparented so that exit status can eventually be collected and process-accounting invariants can remain coherent. PID 1 fills that role. Formally: orphaned ordinary user-space processes are reparented to PID 1 or to a designated subreaper mechanism derived from the same idea. Interpretation: PID 1 is the fallback ancestor that prevents abandoned descendants from becoming ownerless fragments of execution.

The third special feature is **supervision**. In many systems, PID 1 does not merely exist as a passive ancestral root. It actively starts and monitors services, restarts failed daemons when policy says to do so, orders boot targets or runlevels, coordinates shutdown, and represents the stable control point for system-wide service lifetime. This makes PID 1 the bridge between raw process creation and administratively meaningful service management.

The fourth special feature is what happens when PID 1 fails. Ordinary process failure is local: a process crashes, its parent may observe the termination, and the rest of the system often continues. PID 1 failure is global because it removes the system’s root process manager and orphan reaper from ordinary user space. The precise system response depends on the operating system and policy, but the broad rule is severe: if PID 1 cannot continue, the machine cannot continue normal multi-process operation in the ordinary way. On Linux, termination of PID 1 is treated as catastrophic; the kernel typically panics because the system has lost the process responsible for fundamental userspace management.

Boundary conditions matter here too. PID 1 is special because of its role, not because the number 1 is metaphysically magical. Different systems can organize startup differently. Containers can also have their own PID namespaces, in which a process appears as PID 1 inside the namespace and inherits many of the same reaping and signal-handling responsibilities relative to that namespace. The conceptual rule remains: the root process of a process domain has obligations beyond those of an ordinary leaf command.

A common failure mode in understanding is to think orphan adoption means “every process eventually becomes a direct child of PID 1.” No. Most processes remain in their ordinary parent-child lineages. Reparenting occurs when a parent disappears while descendants remain alive. PID 1 is special because it is the fallback root when lineage continuity is broken.

**Retain.** PID 1 is special because it is the first ordinary user-space process, the fallback adopter of orphans, and typically the central supervisor of system services.

**Do Not Confuse.** PID 1 is not just “the first shell” and not just “a process with a small PID.” Its role persists throughout system lifetime.

## Do not confuse these three boundaries

**Kernel bootstrapping vs ordinary parent-child creation.** During boot, the kernel is establishing the conditions under which process creation can occur at all. Ordinary parent-child creation happens later, when an already-running process duplicates or spawns another according to the OS process API. The first user-space process belongs to the former category, not the latter.

**init vs shell.** A shell is an interactive command interpreter that usually appears much later, after session setup or login. Init is the system’s first user-space process and service root. Your shell may be a descendant of a login manager, a session leader, or a terminal emulator process; it is not the system’s primordial process.

**Kernel threads vs user processes.** Kernel threads run kernel work in kernel mode and do not represent ordinary executable images in user space. User processes run program images in user mode and cross into the kernel through system calls, traps, and interrupts. Both may be schedulable; that does not make them interchangeable.

**Retain.** The process tree a user inspects with ordinary tools is downstream of kernel bootstrapping, distinct from shell hierarchy, and distinct from kernel-thread organization.

**Do Not Confuse.** Similar scheduler visibility does not imply the same creation path, same privilege level, or same role.

## A worked example: boot to login to shell to one command

Consider a Unix-like machine that has just powered on. Firmware runs first and hands control to a bootloader. The bootloader loads the kernel and transfers control. The kernel initializes core subsystems and then launches the first user-space process. That process becomes PID 1 and runs the system’s init implementation.

PID 1 then starts the machinery needed for user interaction. On a text-console system, it may start a `getty`-like login program on a terminal line. On a graphical system, it may start a display manager or equivalent session service. Suppose we stay with the text-console picture because the lineage is easier to read. PID 1 starts a login path on a terminal. The login program authenticates a user and, upon successful login, starts the user’s shell as part of the new session.

Now the shell is running, but it is not a root process. It is several layers downstream. When the user types a command such as `grep pattern file.txt`, the shell creates a child process. That child may `exec` the `grep` program image. The resulting process tree is now easy to interpret because the boot base case has already been established.

A simplified tree shape looks like this:

```text
PID 1 init
└── login/session manager
    └── user shell
        └── grep pattern file.txt
```

If the shell exits while `grep` is still running in some special case, the command process does not become ancestorless. It will be reparented according to the system’s orphan-handling rules, ultimately toward the process-domain root represented by PID 1 or a designated subreaper. That is where the special role of PID 1 re-enters an otherwise ordinary command-execution example.

What this worked example clarifies is the difference between **ancestry in the ordinary process tree** and **temporal precedence in boot**. Firmware happened before everything shown above, but firmware is not a parent node in this tree. The kernel ran before the shell existed, but the shell’s immediate parent is not “the kernel.” The tree begins in the ordinary sense once PID 1 exists.

**Retain.** The familiar shell-spawns-command picture sits on top of an earlier boot-created root: PID 1.

**Do Not Confuse.** “Earlier in boot” and “parent in the process tree” answer different questions.

## Linux-oriented trace: the canonical idea made concrete

Conceptually first: the operating system must reach a point where the kernel can transition from internal bootstrapping to the first user-space process. Linux follows that conceptual structure, but its concrete trace reveals useful details.

In Linux, early kernel execution begins in the architecture-specific entry path and proceeds into the main initialization path. A special task associated with the idle or swapper role exists from the beginning of scheduling setup; this is often discussed as PID 0, but it is not an ordinary user-space process and is not a normal parent in the everyday process-tree sense. During initialization, Linux creates crucial kernel-side tasks, including the kernel thread manager (`kthreadd`) and the bootstrap path that will become PID 1.

The important transition is this: Linux’s future PID 1 begins on the kernel side and then executes the initial userspace program image. Historically this might be `/sbin/init`; on modern distributions it is often `systemd`; with an initramfs, an early `/init` may run first and later hand off to the real root filesystem’s init. The central fact does not change. PID 1 is not born because an earlier user-space process called `fork`. It is established by the kernel’s own boot path and then turned into the first user-space process by executing the init program.

Once that exec into init succeeds, Linux has crossed the critical boot boundary. PID 1 now runs in user space. It mounts or finalizes userspace environment transitions, starts daemons and service units, spawns login mechanisms, and becomes the process-domain root for ordinary userspace. Later, when a user opens a terminal and starts `bash`, and `bash` starts `vim` or `ls`, those are ordinary descendants within a tree whose root has already been installed.

The Linux trace is especially useful because it exposes two common misconceptions. First, the presence of PID 0 or kernel threads does not mean user-space process ancestry begins there in the same way shell ancestry does. Second, saying “systemd is PID 1” is true only after the kernel has successfully performed the boot-to-userspace handoff. Before that, the system is still in kernel bootstrap territory.

A Linux-flavored simplified tree might therefore be read in two layers rather than one:

```text
Boot layer:
firmware -> bootloader -> Linux kernel early boot
                    -> kernel bootstrap task
                    -> exec of /init or /sbin/init

Ordinary user-space layer:
PID 1 systemd/init
├── service A
├── service B
└── getty/display manager
    └── login/session
        └── bash
            └── ls
```

The top layer is not an ordinary process tree. The bottom layer is. That distinction is the entire point.

**Retain.** Linux makes the general principle concrete: the kernel boot path establishes PID 1 and then hands ordinary userspace over to it.

**Do Not Confuse.** Linux-specific names such as `systemd`, `/sbin/init`, `/init`, `PID 0`, or `kthreadd` illustrate the mechanism; they do not replace the OS-canonical distinction between kernel bootstrap and ordinary userspace ancestry.

## What this supports later

This chapter is not an isolated curiosity. It supports later material in several directions.

First, it grounds **services and daemons**. Long-running background services do not merely “exist somewhere.” They are started under a service root, usually tied to PID 1, and their restart, shutdown, and dependency behavior makes sense only if the system-wide supervisor role is understood.

Second, it clarifies **orphan adoption**. The rule that abandoned children are adopted by a root process is no longer a strange exception once PID 1 is understood as the process-domain fallback ancestor.

Third, it supports **supervision** as a design concept. Modern systems care not only about creating processes but also about maintaining them, restarting them, ordering them, and collecting their failures. PID 1 is where process management becomes system management.

Fourth, it sharpens later reasoning about **job control and process trees**. Sessions, process groups, terminal control, and shell job management all sit downstream of the fact that the ordinary userspace tree has a boot-established root rather than an infinite regress of parents.

The larger lesson is methodological. Whenever an operating-systems rule sounds universal, ask for its base case, its privilege boundary, and its boot-time exception. Process creation is no exception: the ordinary rule is powerful, but it begins only after the kernel has created the conditions under which it can hold.

**Retain.** Understanding PID 1 turns later topics—daemons, orphan handling, supervision, sessions, and job control—into consequences of a single boot-established root.

**Do Not Confuse.** Later process-tree topics are not separate from boot. They are what ordinary process relationships look like after boot has successfully created their root.
