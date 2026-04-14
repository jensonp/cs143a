# HW1 Concept Backbone: Q1, Q3, Q6, Q11, Q12, Q20, Q23, Q26, plus full reasoning for Q13 and Q14

This note is meant to **solidify the concepts** behind a small but foundational subset of HW1.  
The goal is not just to memorize answers, but to understand the machine model and OS control model that make the answers true.

---

## 1. Q1 — Interrupt handling and saving context

### Homework statement
**Q1.** During interrupt handling, the interrupt service routine does not save the context of the currently executing process before handling the interrupt.  
**Answer:** False.

### Core concept
An interrupt is a hardware event that causes the CPU to stop normal execution and transfer control to privileged interrupt-handling code.  
If the OS wants the interrupted computation to continue later, it must preserve enough machine state to resume it correctly.

### What “context” means here
The important context includes at least:
- the **program counter**: where execution should continue
- the **register values**: temporary values the program was using
- the **stack-related state**
- the **status/flags** needed for correct continuation

The exact set depends on architecture, but the principle is fixed:  
**before another execution context is allowed to overwrite the CPU state, the old state must be preserved somewhere durable.**

### Mechanical reasoning
The CPU has only one live register set per core at a time.  
If an interrupt arrives while process A is running, then the CPU is about to begin executing interrupt-handling code instead of A’s user instructions.

That creates a problem:
- the interrupt handler will use registers
- the kernel may decide to schedule another process
- the original register contents of A would be lost unless saved

So the sequence is conceptually:
1. interrupt arrives
2. control transfers into interrupt-handling path
3. current execution state is preserved
4. interrupt handler runs
5. later, the saved state can be restored and execution resumes

### Why the statement is false
The statement says the ISR **does not save context**.  
But if that were true, the interrupted process could not reliably continue, because its live CPU state would be overwritten.

So the correct answer is **False**.

### Backbone idea to retain
Interrupt handling is not just “jump to a handler.”  
It is “jump to a handler **while preserving resumability** of the interrupted computation.”

---

## 2. Q3 — Can syscall arguments be passed only through registers?

### Homework statement
**Q3.** Syscall arguments can be passed to the kernel via CPU registers only.  
**Answer:** False.

### Core concept
A system call is a controlled request from user mode into kernel mode.  
The kernel needs:
- the syscall number
- the arguments
- a safe way to interpret those arguments

### The real rule
Arguments may be passed:
- in **registers**
- in **memory**
- or in a **hybrid form** where some scalar arguments are in registers and a pointer refers to a structure or buffer in user memory

### Why registers are common
Registers are fast and convenient for a small number of arguments.  
They also let the kernel begin dispatch without immediately dereferencing user memory.

### Why registers are not the only method
Some syscalls need:
- many arguments
- large structures
- buffers
- strings
- arrays

Those cannot always fit naturally into a fixed set of argument registers.  
So the user program may pass a **pointer** in a register, and the actual data lives in memory.

Examples:
- `write(fd, buf, count)`  
  The file descriptor and count may fit cleanly in registers, but `buf` is a pointer to memory.
- `exec`-style calls often involve arrays of pointers and strings in memory.
- ioctl-style interfaces often pass pointers to structures in memory.

### Mechanical reasoning
The syscall path has two separate jobs:
1. get the arguments
2. validate them

If an argument is in a register, the kernel reads the register.  
If an argument is in memory, the kernel validates the pointer and then reads the data from user space.

### Why the statement is false
The statement says **registers only**.  
But real syscall interfaces use registers, memory, or both.

So the correct answer is **False**.

### Backbone idea to retain
The important distinction is not “registers versus memory” by itself.  
The important distinction is:
- **how arguments arrive**
- and **how the kernel safely validates them**

---

## 3. Q6 — Does DMA require CPU intervention for the data transfer?

### Homework statement
**Q6.** Direct Memory Access (DMA) requires CPU intervention for data transfer between the device and memory.  
**Answer:** False.

### Core concept
DMA exists to reduce the CPU’s burden during large I/O transfers.

Without DMA, the CPU may have to do the transfer loop itself:
- read from device/controller register
- write to memory
- repeat for many bytes or words

With DMA, the CPU sets up the transfer, but dedicated hardware performs the bulk data movement.

### What the CPU still does
The CPU is not totally absent. It still:
- sets up the DMA operation
- provides buffer address, size, and direction
- starts the transfer
- later handles completion or error, often via interrupt

### What DMA hardware does
The DMA engine or controller transfers blocks of data directly between:
- device/controller-side buffering
- and main memory

### Mechanical reasoning
So there are two very different meanings of “intervention”:

**CPU intervention for setup and completion:** yes  
**CPU intervention for every byte/word moved during the transfer:** no

The homework statement is about the actual data transfer between device and memory.  
DMA is specifically designed so the CPU does **not** have to manually move the data item by item.

### Why the statement is false
The statement says DMA **requires CPU intervention for the data transfer**.  
That is the opposite of what DMA is for.

So the correct answer is **False**.

### Backbone idea to retain
DMA does not remove OS control.  
It removes the need for the CPU to act as the bulk-copy worker during large transfers.

---

## 4. Q11 — What does the Interrupt Vector Table hold?

### Homework statement
**Q11.** The Interrupt Vector Table holds the start address of the interrupt handler for different types of interrupts.  
**Answer:** True.

### Core concept
When an interrupt happens, the CPU must know **where to transfer control**.  
It cannot just “go to interrupts in general.”  
Different interrupt sources need different handlers.

### What the vector table is
The Interrupt Vector Table is a mapping from:
- interrupt number / interrupt type / exception class

to:
- the address of the corresponding handler routine

### Mechanical reasoning
The conceptual sequence is:
1. an interrupt occurs
2. the CPU identifies the interrupt type
3. it uses that type to index or select the proper vector entry
4. that entry gives the handler start address
5. control transfers there

### Why this matters
Without such a structure, the CPU would not know which handler should run for:
- timer interrupt
- keyboard interrupt
- disk completion interrupt
- illegal instruction
- page fault
- and so on

### Why the statement is true
That is exactly what the interrupt vector table is for.

So the correct answer is **True**.

### Backbone idea to retain
An interrupt needs both:
- a reason/type
- and a place to go

The vector table is the mechanism that turns interrupt identity into handler destination.

---

## 5. Q12 — Are all I/O instructions privileged?

### Homework statement
**Q12.** All I/O instructions are privileged instructions.  
**Answer:** True.

### Core concept
I/O devices are globally important, shared, and dangerous to misuse.  
If arbitrary user programs could directly issue device-control instructions, they could:
- overwrite disk contents
- read protected data
- interfere with device state
- bypass OS permission checks
- corrupt other processes or the system itself

### Why privilege is necessary
The OS must remain the authority over device access.  
So direct I/O instructions are reserved for kernel mode.

User programs do not directly perform device control.  
Instead they request I/O through **system calls** such as:
- `read`
- `write`
- `open`
- `ioctl`
- socket-related calls

The kernel then validates the request and performs the privileged device interaction.

### Mechanical reasoning
The protection logic is:
1. device-control operations are dangerous
2. dangerous machine operations must be restricted
3. restricted machine operations are privileged
4. user code reaches them only indirectly through syscalls

### Why the statement is true
In the model used by Lecture 1 and HW1, direct I/O instructions are privileged.

So the correct answer is **True**.

### Backbone idea to retain
The OS does not protect devices by hoping user programs behave.  
It protects devices by making direct I/O control a privileged operation.

---

## 6. Q20 — Which mechanism reduces CPU load for I/O devices with lots of data?

### Homework statement
**Q20.** Which mechanism is typically used for I/O devices with a lot of data to transfer, to reduce load on the CPU?  
**Answer:** **c) Direct Memory Access (DMA)**

### Core concept
Large I/O transfers create a scaling problem.  
If the CPU had to move every byte itself, it would waste time on bulk transfer work rather than useful scheduling and computation.

### Why interrupts alone are not enough
Interrupts solve the **notification** problem:
- the device tells the CPU when something important happened

But interrupts do not automatically solve the **bulk data movement** problem.  
The CPU could still be stuck copying the data.

### Why DMA is the right mechanism
DMA offloads the block transfer itself.  
The CPU does setup and later handles completion, but does not manually copy every byte or word.

### Why the other answers are wrong
- **Interrupts**: good for notification, not the main bulk-transfer offload mechanism
- **Polling**: often wastes CPU time checking repeatedly
- **Memory-mapped I/O**: an access method, not the main answer to bulk-transfer CPU-load reduction here

### Backbone idea to retain
For large transfers, the central question is: **who moves the data?**  
DMA is the answer that reduces CPU load.

---

## 7. Q23 — Which task is NOT done via syscalls?

### Homework statement
**Q23.** Which of the following tasks in a process is NOT done via syscalls?  
a) Opening a file  
b) Allocating memory  
c) Adding two numbers  
d) Creating a network socket  
**Answer:** **c) Adding two numbers**

### Core concept
A syscall is needed when the process requests a service that requires kernel authority.

That includes actions like:
- opening a file
- creating a socket
- changing mappings
- interacting with devices
- creating processes
- requesting OS-managed resources

But ordinary arithmetic inside the process’s own execution does not need the kernel.

### Mechanical reasoning
Ask the key question:
**Does this action require protected OS authority, or can the CPU perform it directly within user mode?**

- **Opening a file** → needs kernel involvement, because files are OS-managed objects
- **Allocating memory** → in the OS course context, memory acquisition/growth of a process’s available memory involves kernel-mediated mechanisms at some point
- **Creating a network socket** → needs kernel involvement, because sockets are OS-managed communication objects
- **Adding two numbers** → simple user-mode computation; the CPU can do this directly

### Why the answer is c
Adding two numbers is ordinary arithmetic and does not inherently require crossing the user-kernel boundary.

So the correct answer is **c**.

### Backbone idea to retain
The syscall boundary is crossed for **authority transfer**, not for ordinary computation.  
The CPU can add numbers in user mode just fine.

---

## 8. Q26 — In base-and-bound translation, which register stores the size?

### Homework statement
**Q26.** In the base and bound method used for virtual address translation, the ________ stores the size of the virtual address space of a process.  
**Answer:** **bound register** (or **limit register**, depending on convention)

### Core concept
Base-and-bound is a simple memory protection and relocation scheme.

It uses:
- a **base register**
- a **bound / limit register**

### What each one means
- **Base register**: where the process’s region begins physically
- **Bound/limit register**: how large the legal process-relative address range is, or equivalently the maximum legal range depending on naming convention

### The important convention here
In your lecture and homework wording:
- **base register** = smallest legal physical address / start
- **bound register** = size of the legal range

So if the process generates virtual address `v`, the machine conceptually checks:
- is `0 <= v < bound` ?
- if yes, physical address = `base + v`
- if no, raise an exception

### Why size matters
The bound/limit register defines the legal extent of the process’s virtual address space in this simple model.

### Backbone idea to retain
Base shifts the address.  
Bound limits the address.

That is the cleanest memory aid:
- **base = start**
- **bound = size/range limit**

---

# Full reasoning for the image questions

---

## 9. Q13 — Printer interrupts for every printed character

### Problem
A laser printer produces up to **20 pages per minute**.  
Each page has **4000 characters**.  
The system uses interrupt-driven I/O.  
Each interrupt takes **50 microseconds** to process.  
An interrupt is raised for **every printed character**.  
How much CPU time is spent processing interrupts?

Choices:
- a) 3.33%
- b) 6.67%
- c) 9.67%
- d) 12.33%

### Step 1: Find how many characters are printed per minute
Pages per minute = 20  
Characters per page = 4000

So:

`20 * 4000 = 80,000 characters/minute`

If there is one interrupt per character, that means:

`80,000 interrupts/minute`

### Step 2: Compute total interrupt handling time per minute
Each interrupt takes:

`50 microseconds = 50 × 10^-6 seconds`

Total interrupt time per minute:

`80,000 * 50 microseconds = 4,000,000 microseconds`

Convert that:

`4,000,000 microseconds = 4 seconds`

So the CPU spends **4 seconds per minute** just handling interrupts.

### Step 3: Convert to percentage of one minute
One minute = 60 seconds

Fraction of time spent on interrupts:

`4 / 60 = 0.066666...`

As a percentage:

`0.066666... × 100 = 6.67%`

### Correct answer
**b) 6.67%**

### Mechanical backbone
This is a standard interrupt-overhead calculation:

1. compute **event rate**
2. multiply by **cost per event**
3. divide by total available time
4. convert to percent

Formula form:

`CPU fraction = (interrupts per second × interrupt time)`

or equivalently over one minute:

`CPU fraction = (interrupts per minute × interrupt time) / 60 seconds`

### Conceptual backbone
This question is teaching why interrupt frequency matters.

Interrupt-driven I/O is good because the CPU does not poll constantly.  
But if interrupts happen too often — here, **once per character** — the CPU spends a significant fraction of time doing handler overhead instead of useful work.

So the deeper point is not just arithmetic. It is:
- interrupts solve the notification problem
- but high interrupt frequency creates overhead
- coarse-grained transfer mechanisms are often better for efficiency

---

## 10. Q14 — Disk interrupts for every 512-byte sector

### Problem
A disk drive transfers data at **0.5 MB/s** and generates one interrupt for every **512-byte sector** transferred.  
Each interrupt takes **40 microseconds** to handle.  
What percentage of CPU time is spent handling interrupts?

Choices:
- a) 1.95%
- b) 3.90%
- c) 5.85%
- d) 7.80%

### Step 1: Express the data rate in bytes per second
Use the homework’s intended decimal-style interpretation:

`0.5 MB/s = 500,000 bytes/s`

### Step 2: Find interrupts per second
There is one interrupt per 512 bytes.

So:

`500,000 / 512 ≈ 976.5625 interrupts/s`

### Step 3: Compute CPU time spent per second on interrupt handling
Each interrupt costs:

`40 microseconds = 40 × 10^-6 seconds`

So total interrupt-handling time per second is:

`976.5625 × 40 × 10^-6`
`= 0.0390625 seconds`

That is about **0.03906 seconds per second**.

### Step 4: Convert to percent
`0.0390625 × 100 = 3.90625%`

Rounded:

**3.90%**

### Correct answer
**b) 3.90%**

### Mechanical backbone
Same exact pattern as Q13:

1. compute transfer events per second
2. multiply by handler cost
3. convert to fraction of a second
4. convert to percent

Formula form:

`interrupts/s = transfer rate / bytes per interrupt`
`CPU fraction = interrupts/s × interrupt handling time`

### Conceptual backbone
This problem reinforces the same general lesson as Q13, but in a storage context:

- higher transfer granularity matters
- one interrupt per small chunk increases overhead
- interrupt rate is determined by **transfer rate ÷ bytes per interrupt**
- the CPU cost depends on **how often** the handler runs, not just how fast the device is

It also connects naturally to why DMA and larger transfer units are so useful:
- fewer interrupts
- lower CPU overhead
- better scaling for high-throughput I/O

---

# Final compact retention summary

## Retain
- Interrupt handling must preserve enough state to resume the interrupted computation.
- Syscall arguments are not limited to registers; memory pointers and hybrid schemes are common.
- DMA reduces CPU burden by offloading bulk transfer between device and memory.
- The interrupt vector table maps interrupt type to handler start address.
- Direct I/O instructions are privileged because device control must remain under OS authority.
- DMA is the standard answer for large transfers when the goal is reducing CPU load.
- Syscalls are for requesting kernel-controlled services, not for ordinary arithmetic.
- In base-and-bound, **base = start**, **bound/limit = legal range size**.
- For interrupt-overhead problems:  
  **event rate × cost per event = total overhead rate**

## Do not confuse
- “CPU helps set up DMA” with “CPU performs the entire data transfer.”
- “trap/syscall boundary” with ordinary user-mode computation.
- “interrupts solve notification” with “interrupts solve bulk-copy cost.”
- “register passing is common” with “register passing is the only syscall argument method.”
- “base register” with “bound/limit register.”
- “registers only” with “registers are often used first.”

