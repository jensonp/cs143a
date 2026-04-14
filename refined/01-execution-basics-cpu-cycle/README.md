# Execution Basics Cluster: CPU, Instruction, Program Counter, Fetch, Decode, Execute

## Why This Topic Has to Appear Early

Operating systems do not begin with processes, files, or virtual memory. They begin one layer lower, with a question so basic that it is easy to stop seeing it: what is the machine actually doing, moment by moment, when any program runs at all? If that question is not clear, then later operating-system ideas become verbal rather than structural. You can memorize that the kernel handles traps, that a context switch saves registers, or that an interrupt changes control flow, but you do not really understand any of those claims until you understand the normal control flow they interrupt.

This topic exists to establish that normal control flow. Homework 1 is assuming a machine that repeatedly does a simple but profound thing: it finds the next instruction, figures out what that instruction means, carries it out, and then repeats. That repeating pattern is the machine loop. The names usually attached to its major parts are **fetch**, **decode**, and **execute**. To understand that loop, you must first know what a **CPU** is, what an **instruction** is, what a **program** is in machine terms, and what the **program counter** is doing.

The central problem this topic solves is the problem of ordered action. A computer is not merely a collection of components that can perform operations. It must also have a disciplined way to determine **which operation happens now**, **where that operation is stored**, **how its meaning is recognized**, and **what state changes once it is performed**. The fetch-decode-execute cycle is the answer.

What is fixed in this topic is the abstract structure of execution: there is stored machine code, there is some register that identifies the next instruction to consider, and there is a repeated process by which the processor advances from one instruction to the next. What varies is the actual instruction-set architecture, the specific instruction format, the number and role of registers, the address size, whether instructions are fixed or variable length, and how much work the hardware performs in each cycle internally. The high-level control logic, however, remains the same.

This topic supports almost everything that follows in operating systems. Once you understand normal sequential execution, you can understand what it means to interrupt that execution, what it means for one process to resume where it left off, why saving the program counter matters, what a system call must preserve, why privilege transitions are meaningful, and why the kernel can be described as taking control of the machine.

### Dependency bridge: later control-flow terms

This chapter will occasionally name later operating-systems terms such as **interrupt**, **exception**, **fault**, **trap**, **handler**, and **vector entry**. In this chapter, treat those words only as **forward references** to ways in which normal sequential execution can later be redirected. You do **not** need their full formal meaning yet. The only fact needed here is simpler: ordinary execution follows the current program counter, while later mechanisms will sometimes replace the normal next-PC rule with a protected control transfer defined by the architecture and the operating system.

## The CPU

### Formal definition

A **central processing unit (CPU)** is the hardware component that interprets and carries out machine instructions by reading architectural state, transforming that state according to instruction semantics, and producing the next machine state.

### Interpretation

In plain technical English, the CPU is the part of the machine that actually *runs* instructions. Memory stores data and code, but memory by itself does nothing. The CPU is the active agent that repeatedly looks at the current machine state and changes it according to the next instruction. When you hear that a program is “executing,” what that really means is that the CPU is stepping through instructions and updating registers, memory, and control flow.

The phrase “architectural state” matters. It means the part of machine state that the instruction set defines as visible or meaningful at the programming level: registers, memory values, condition codes or flags, and the program counter. Many real CPUs contain a great deal of hidden internal machinery, but at this stage, the important idea is that execution can be understood as movement from one visible state to the next.

A common misconception is to think of the CPU as the whole computer. It is not. The CPU depends on memory to hold instructions and data, and on buses or interconnects to communicate with that memory. Another common misconception is to think that the CPU “knows the program” in some large, global sense. It usually does not. At any instant, what it fundamentally has is the current architectural state and access to memory. The sense of a long-running program emerges because the CPU follows control flow one instruction at a time.

## The Program

### Formal definition

A **program**, at the machine-execution level, is an organized sequence of machine instructions and associated data stored in memory, such that the CPU can interpret the instructions one by one and thereby produce the intended computation.

### Interpretation

A program is not primarily “source code” in this context. It is not C, Rust, or Python text. Those are human-oriented representations. For execution basics, a program is the machine-level object the CPU can actually consume. In the simplest model assumed in early operating systems work, that means a sequence of binary-encoded instructions placed in memory at some addresses, together with any data the instructions will read or modify.

The important thing to notice is that a program is passive until the CPU is pointed at it. The machine does not “run a program” by absorbing the whole program at once. Instead, the CPU uses an address—stored in the program counter—to locate one instruction, executes it, updates state, and then proceeds to the next relevant instruction. The idea of a program as a flowing activity comes from repeated instruction execution, not from the stored bytes alone.

Another misconception worth removing early is the idea that a program is necessarily executed in the exact linear order it is written in memory. That is only the default case when no control-flow instruction changes the next instruction address. Branches, jumps, calls, returns, exceptions, and interrupts all alter which instruction comes next. So the program is a stored instruction space, but the executed path through that space depends on control flow.

## The Instruction

### Formal definition

An **instruction** is a machine-level encoded command that specifies an operation for the CPU to perform, together with enough information to identify the operands involved and the destination or state changes required by that operation.

### Interpretation

An instruction is the smallest normal unit of programmed action the CPU is meant to interpret at this level. It is not just an operation name like “add.” It is a binary pattern whose bits are arranged according to the machine’s instruction set architecture. Some bits usually identify *which operation* this is, while other bits identify *which registers*, *which memory addresses*, *which immediate constants*, or *which control-flow target* are relevant.

What you should notice first is that the CPU does not see a sentence. It sees a pattern of bits. The meaning of that bit pattern is determined by the instruction set architecture. If the architecture says that a certain bit pattern means “add register 2 and register 3 and place the result in register 1,” then that is what decode will recover from the raw fetched bits.

A crucial distinction is the difference between an **instruction as stored** and an **instruction as understood**. While the instruction is sitting in memory, it is just bits at an address. During fetch, those bits are retrieved. During decode, the CPU interprets which fields in those bits represent the opcode, operands, and any immediate value. During execute, the effect described by the instruction is applied to machine state.

A common confusion is to identify an instruction with a single clock tick. That is not conceptually correct. Even on simple machines, an instruction is a semantic unit, not necessarily a one-cycle physical event. Some instructions take more time than others, and modern CPUs overlap many internal stages. For the machine loop taught in early OS courses, ignore those microarchitectural complications and focus on the logical order: fetch, decode, execute.

## The Program Counter

### Formal definition

The **program counter (PC)** is the architectural register whose value identifies the memory address of the instruction the CPU will fetch next under normal control flow.

### Interpretation

The program counter answers the question: “Where is the next instruction?” If the CPU had instructions in memory but no program counter, it would not know where to begin or how to continue. The PC is what turns stored code into a sequence of execution steps.

The first thing to notice is the word **next**. The PC usually does not describe the instruction currently being physically processed in every internal sense; rather, in the architectural model, it names the instruction whose address determines the next fetch. After an instruction is fetched and executed, the PC usually changes. If execution is sequential and instructions have fixed size, the PC may simply increase by that instruction size. If a branch, jump, call, return, trap, or interrupt changes control flow, the new PC value may be something entirely different.

This register is fundamental because it represents **control state**. Many machine components hold data values, but the PC determines where execution continues. That is why saving and restoring the PC is central to process switching, exception return, function calls, and debugging. If you lose the data in general-purpose registers, you may lose intermediate results. If you lose the PC, you lose the thread of control itself.

There are several subtle points students often miss.

First, the PC holds an address, not “the line number of the program.” Source lines are a higher-level fiction. The machine only knows addresses and encoded instructions.

Second, the PC does not by itself guarantee that the next memory location really contains a valid instruction. It only provides the address to be fetched. If that address is invalid, inaccessible, or points to nonsensical bits, execution may fault or behave according to the architecture’s invalid-instruction rules.

Third, the PC is not the same thing as “the currently executing function.” A function is a higher-level program structure. The PC is a low-level address. Many adjacent PC values may belong to the same function, and control can jump among functions by simply changing the PC.

## State: What Execution Actually Changes

Before describing fetch, decode, and execute in order, it is necessary to be explicit about what execution acts on. Otherwise the machine loop sounds mystical.

At this level, the machine state usually includes at least the following:

The **memory**, which is an addressable collection of stored values. Some addresses contain instructions, some contain data, and some may contain both at different times depending on the model.

The **register file**, consisting of a finite set of small, fast storage locations inside the CPU. These may include general-purpose registers and special-purpose registers.

The **program counter**, which indicates the next instruction address.

Possibly **flags** or **condition codes**, which record facts such as whether a prior arithmetic result was zero, negative, or carried out of range.

Execution can be described as a repeated transition from one complete machine state to another. One instruction examines some part of the current state, then produces an updated state. This is the right conceptual model for operating systems, because later the OS will save a process’s relevant machine state and restore it later.

## Fetch

### Formal definition

The **fetch** stage is the part of the execution cycle in which the CPU uses the current program counter value to read the encoded instruction stored at the addressed memory location into a form available for interpretation.

### Interpretation

Fetch is the step where the machine asks: “What bits are at the instruction address named by the current PC?” The CPU consults memory using the PC as the address and retrieves the instruction bits located there.

There are several things being checked here, even in a simple model. The CPU has a current PC value. That value is treated as an address. The memory system is asked for the contents at that address, usually enough bytes to represent one instruction or the beginning of one instruction. If the address is valid and accessible, the encoded instruction is obtained. If the address is not valid or cannot be accessed, fetch may fail, producing an exception or fault instead of a normal instruction.

What conclusion does a successful fetch allow? It allows the machine to move from “I know where to look” to “I now have the raw instruction bits that were stored there.” Fetch does **not** yet tell us what the instruction means. It only retrieves the candidate instruction representation.

One dangerous confusion is to think fetch means “copy the whole program into the CPU.” It does not. In the simple execution model, the CPU fetches the next instruction as needed. Another confusion is to think fetch already implies sequentiality. Not exactly. Fetch uses the current PC. Sequentiality comes from how that PC was set previously and how it will be updated later.

Boundary conditions matter here. If the instruction set uses fixed-size instructions, then the number of bytes fetched may be known in advance. If the architecture uses variable-size instructions, the machine may need additional internal logic to determine instruction length. For the conceptual model used in early OS work, you usually treat fetch as “retrieve the instruction at PC,” without worrying yet about instruction-cache behavior or variable-length complexity.

## Decode

### Formal definition

The **decode** stage is the part of the execution cycle in which the CPU interprets the fetched instruction’s bit fields according to the instruction set architecture in order to determine the operation to perform, the operands involved, and any control information needed for execution.

### Interpretation

Decode answers the question: “What does this fetched bit pattern mean?” The CPU examines the fetched instruction and separates its relevant fields. One field may specify the opcode, which identifies the class of operation such as add, load, store, compare, or jump. Other fields may specify source registers, destination registers, immediate constants, addressing modes, or branch targets.

The order of reasoning in decode matters. First, the machine determines which part of the instruction is the opcode or operation-identifying field. Once that operation is known, the architecture tells the CPU how the rest of the bits should be interpreted. The same raw bit positions can mean different things for different instruction formats, so the operation class often determines the meaning of the remaining fields.

What conclusion does decode allow? It allows the machine to move from raw bits to a structured interpretation of the intended action. After decode, the CPU knows not merely the instruction bytes, but something like: “This is an add instruction; it will read registers R2 and R3 and write the result to R1,” or “This is a load instruction; it will compute an address from register R4 plus an offset and place the loaded value into R1.”

A common misunderstanding is to think decode is just naming the instruction. In fact, decode includes identifying all instruction fields relevant to later action. Another misunderstanding is to assume the operands are necessarily read during decode in a cleanly separated way on all machines. Architecturally, decode is the phase of understanding meaning; implementation details can overlap with operand access. For learning purposes, keep the conceptual separation: fetch gets bits, decode determines meaning, execute applies meaning.

Failure modes appear here too. If the fetched bit pattern does not correspond to any valid opcode or valid instruction form, the machine may raise an illegal-instruction exception. So successful fetch does not guarantee successful decode. Fetch can retrieve bits that exist at an address, but decode may discover that those bits do not represent a legal instruction under the architecture.

## Execute

### Formal definition

The **execute** stage is the part of the execution cycle in which the CPU carries out the operation determined during decode, using the specified operands, producing the required result, updating the relevant architectural state, and determining the correct next program counter value.

### Interpretation

Execute is where the instruction’s meaning becomes an actual state change. If the instruction is arithmetic, execute combines operand values and writes a result. If the instruction is a load, execute computes an effective address, reads memory, and writes the loaded value into a register. If it is a store, execute writes a register value into memory. If it is a branch, execute evaluates the branch condition and, depending on the result, either changes the PC to a target address or leaves control flow sequential.

It is important to be explicit about what is being checked here. The decoded instruction tells the machine which operation to perform and which operands matter. The CPU then obtains the operand values from the current state. If a memory access is required, it checks the relevant address path. If a condition is involved, it evaluates whether the condition is true or false. Based on those facts, it computes the result and writes back the new state.

The most important conclusion execute produces is the **next machine state**. That next state includes more than the obvious data result. It also includes the next PC value. Students often pay attention to arithmetic results and forget that every instruction, even a simple one, participates in control flow because execution must continue somewhere.

This is where normal sequential execution and altered control flow separate clearly. For a straight-line arithmetic instruction on a fixed-length instruction set, the next PC is usually the old PC plus the instruction length. For a taken branch or jump, the next PC becomes the branch target or jump target. For a not-taken conditional branch, the next PC becomes the sequential successor. For an exception, the normal next PC may be replaced by an architecture-defined control-transfer target chosen by the machine. Later chapters will make this more precise by introducing traps, interrupts, and vector-table-based handler selection.

A common misconception is to think execute is only about ALU work such as addition or subtraction. In fact, execute means “carry out the instruction semantics,” which includes memory access and control transfer. Another confusion is to think the PC update is a separate optional detail. It is not optional. Without determining the next PC, the machine cannot continue normal execution.

## The Machine Loop as a Whole

Now the pieces can be assembled.

The machine begins with some current machine state. In that state, the PC has a value, say `PC = A`, where `A` is some valid instruction address. During fetch, the CPU uses `A` to obtain the encoded instruction stored at address `A`. During decode, the CPU interprets the fetched bits and determines which operation they specify and which operands or targets are relevant. During execute, the CPU carries out that operation, changes registers and memory as required, and determines a new PC value, say `PC = B`. The machine then repeats the same overall process starting from the new state with PC equal to `B`.

This repeated cycle is what introductory operating systems material often assumes without re-deriving every time. It is the default behavior of the processor in the absence of interrupts, faults, or explicit control-transfer instructions that redirect execution in non-sequential ways.

A useful abstract statement is this: execution is repeated state transition driven by the instruction located at the current program counter. That sentence is compact, but it contains almost everything. “Repeated” captures the loop. “State transition” captures the fact that execution changes machine state. “Driven by the instruction located at the current program counter” captures control flow.

## Sequential Execution and Why It Is Only the Default

Students often form the wrong mental model that the CPU always runs instructions from top to bottom in memory. The more accurate statement is narrower: **unless something changes control flow, the next instruction is the sequential successor of the current one**.

This distinction matters. Sequentiality is not a metaphysical law; it is a consequence of how the PC is updated for ordinary instructions. In a fixed-length instruction set where each instruction is 4 bytes, if the current PC is 100 and the current instruction does not redirect control, then the next PC may simply be 104. That looks like automatic linear execution, but really it is just repeated PC advancement by a fixed increment.

Once you see it this way, all control mechanisms become easier to understand. A branch is just an instruction whose execution sets the next PC differently. A call is just an instruction that both saves return information and sets the next PC to the callee’s address. A return restores the next PC from saved state. A later control-transfer event such as an interrupt or exception can redirect execution away from the ordinary sequential successor and toward an architecture-defined handler address. The full distinction among those events is introduced in later chapters. The conceptually central object is not “line order”; it is the rule that determines the next PC.

## A Fully Worked Example

Consider a simple toy machine with fixed-size instructions of 4 bytes each, three general-purpose registers `R1`, `R2`, and `R3`, memory addressed by byte number, and a program counter `PC`. Suppose the following instruction meanings exist:

`LOAD R1, [1000]` means read the value stored in memory at address 1000 and place it into `R1`.

`LOAD R2, [1004]` means read the value stored in memory at address 1004 and place it into `R2`.

`ADD R3, R1, R2` means compute `R1 + R2` and place the result into `R3`.

`STORE [1008], R3` means write the value in `R3` into memory at address 1008`.

Suppose these instructions are stored as follows:

- Address 200: `LOAD R1, [1000]`
- Address 204: `LOAD R2, [1004]`
- Address 208: `ADD R3, R1, R2`
- Address 212: `STORE [1008], R3`

Suppose the initial state is:

- `PC = 200`
- `memory[1000] = 7`
- `memory[1004] = 5`
- `memory[1008]` is unspecified initially
- `R1`, `R2`, and `R3` contain irrelevant old values

Now trace the machine loop carefully.

### First iteration

The current PC is 200. Fetch uses 200 as the address of the next instruction. The bits stored at address 200 are retrieved. Decode interprets those bits as the instruction `LOAD R1, [1000]`. Execute now carries out the semantics of that instruction. It checks the memory address named by the instruction, which is 1000. It reads the value at `memory[1000]`, which is 7. It writes 7 into `R1`. Because this instruction does not alter control flow, the next PC becomes the sequential successor. Since instructions are 4 bytes long, the next PC is `200 + 4 = 204`.

After the first iteration, the relevant state is:

- `R1 = 7`
- `PC = 204`
- other relevant values unchanged

### Second iteration

The current PC is now 204. Fetch retrieves the instruction bits stored at address 204. Decode identifies the instruction as `LOAD R2, [1004]`. Execute reads `memory[1004]`, which is 5, and writes that value into `R2`. Again, since this instruction does not redirect control, the next PC becomes 208.

After the second iteration, the relevant state is:

- `R1 = 7`
- `R2 = 5`
- `PC = 208`

### Third iteration

The current PC is 208. Fetch retrieves the bits at address 208. Decode interprets them as `ADD R3, R1, R2`. Execute reads the current values of `R1` and `R2`, which are 7 and 5. It computes `7 + 5 = 12`. It writes 12 into `R3`. Because this instruction is ordinary sequential arithmetic, the next PC becomes 212.

After the third iteration, the relevant state is:

- `R1 = 7`
- `R2 = 5`
- `R3 = 12`
- `PC = 212`

### Fourth iteration

The current PC is 212. Fetch retrieves the bits at address 212. Decode identifies the instruction as `STORE [1008], R3`. Execute reads the current value of `R3`, which is 12, and writes it into `memory[1008]`. Since no control redirection occurs, the next PC becomes 216.

After the fourth iteration, the relevant state is:

- `memory[1008] = 12`
- `PC = 216`

### What this example teaches generally

This example is not valuable because it is easy. It is valuable because it exposes the general structure of all instruction execution.

First, the CPU never executes the abstract program all at once. It always acts on the single instruction pointed to by the current PC.

Second, register and memory values observed by one instruction are whatever the previous instructions left behind. The machine state accumulates history.

Third, sequentiality is implemented by updating the PC to the next instruction address. The machine does not have a magical sense of “the next line”; it computes or adopts the next PC.

Fourth, the meaning of the program emerges from a chain of state changes. `ADD R3, R1, R2` only produces the intended result because the earlier load instructions established the right values in `R1` and `R2`.

## A Branching Example: Why the PC Is the Real Story

Now consider a toy conditional branch instruction `BEQ R1, R2, 300`, meaning: if `R1` equals `R2`, set the next PC to 300; otherwise continue sequentially.

Suppose the current state before execution is:

- `PC = 220`
- `R1 = 9`
- `R2 = 9`

Suppose the instruction at address 220 is `BEQ R1, R2, 300`.

Fetch retrieves the instruction at address 220. Decode identifies it as a conditional branch with source registers `R1` and `R2` and target address 300. Execute compares the current values of `R1` and `R2`. Because both are 9, the condition is true. Therefore the next PC becomes 300, not 224.

If instead `R1 = 9` and `R2 = 4`, then the branch condition would be false. In that case the instruction would not redirect control, and the next PC would become the sequential successor, 224.

This example teaches the most important lesson about control flow: the essence of branching is not “skipping lines.” It is selecting the next PC based on current machine state.

## Failure Modes and Boundary Conditions

Execution basics sound clean because the idealized machine loop is clean. But the idealized story sits on several assumptions. If you do not make them explicit, later OS concepts become confusing.

One assumption is that the PC refers to a valid executable address. If the PC points outside the program’s accessible memory, fetch may fault.

A second assumption is that the bytes at the fetched address encode a valid instruction. Memory can contain arbitrary data. Fetch may succeed and decode may still fail because the bit pattern is not a legal instruction.

A third assumption is that operand access is valid. An instruction may decode correctly but then attempt to read or write an invalid memory address during execution. In that case the fault occurs during operand access or execution, not necessarily during fetch.

A fourth assumption is that the machine model being used is architectural, not microarchitectural. Real processors pipeline, speculate, reorder, and cache aggressively. Those facts matter later, but the correctness-visible architectural story remains the fetch-decode-execute model.

A fifth boundary condition concerns instruction size. If instructions are variable length, the idea “next PC = old PC + fixed number” no longer universally holds. The sequential successor depends on instruction length. The conceptual rule is still the same: execute must determine the next PC either by default succession or by explicit redirection.

A sixth subtle point concerns self-modifying code or code generation. If memory contents can change, then the instruction fetched from a given address can differ over time. The machine loop still works, but the assumption that “address 200 always means the same instruction” no longer holds.

These failure modes are not side details. They are the bridge to operating systems. Many traps, faults, and protection mechanisms exist precisely because fetch, decode, or execute can fail or require intervention.

## Common Misconceptions to Eliminate Early

One common misconception is that the CPU reads source code. It does not. It executes machine instructions encoded in a representation defined by the instruction set architecture.

Another is that the program counter points to “the current line of code.” It points to an instruction address, not a source-level line number.

Another is that the next instruction is always the one physically after the current one in memory. That is only true when the instruction does not change control flow and no exception or interrupt intervenes.

Another is that fetch, decode, and execute are three separate boxes in time with no overlap in real hardware. Conceptually yes, physically not necessarily. The model is architectural and explanatory.

Another is that execute means only arithmetic. It really means applying instruction semantics, including memory operations and control transfers.

Another is that a program is “running” because it resides in memory. A program runs only when the CPU repeatedly fetches, decodes, and executes its instructions.

Finally, students often underweight the importance of the PC. In early OS work, the PC is one of the most important pieces of saved state because it determines where execution resumes.

## Why Operating Systems Care About This Cluster

Operating systems take control of a machine that is already executing according to the machine loop. The OS does not replace the basic mechanism; it relies on it and redirects it.

When a process runs, the CPU is repeatedly fetching, decoding, and executing that process’s instructions. When an interrupt arrives, the normal next-PC logic is altered so that control transfers to an interrupt handler. When a system call occurs, the program intentionally causes a controlled transfer into kernel code. When a context switch happens, the operating system saves the current architectural state, including the PC and registers, and restores another process’s state so that the machine loop continues as if that other process had always been the current one.

This is why HW1 can assume the machine loop without treating it as a minor implementation detail. It is the ground on which all later OS mechanisms stand. The kernel’s power comes from controlling *when* execution is redirected, *what state is saved*, *what state is restored*, and *which PC becomes current next*.

## Conceptual Gaps and Dependencies

This topic assumes several prerequisites, even if courses do not always name them explicitly. It assumes that you already understand the basic idea of digital state: that registers and memory hold values which persist until changed. It assumes some comfort with addressing, meaning the idea that memory locations are identified by numeric addresses. It assumes that a program can be represented as machine code rather than as source text. It also assumes that you can distinguish data from the mechanisms that operate on data.

The prerequisites most likely to be weak at this stage are usually three. First, many students do not yet firmly understand the difference between a source-language statement and a machine instruction. Second, many students use the term “memory” loosely and have not yet separated memory, registers, and control state into distinct roles. Third, many students treat the program counter as a vague execution marker rather than as the explicit address of the next instruction.

This topic refers to several nearby concepts without fully teaching them. It refers to the instruction set architecture, but does not teach the full design of any real ISA. It refers to registers and memory addressing, but does not fully teach addressing modes, stack discipline, or calling conventions. It refers to faults and illegal instructions, but does not yet teach exceptions, interrupts, or privilege levels. It also refers indirectly to sequential state transition systems, but does not formalize them beyond what is needed here.

For homework and lecture purposes, there are usually some facts not covered by this explanation alone. You may still need to know the exact register names or instruction syntax of the course’s toy machine or target architecture. You may need to know whether instructions are fixed width, how memory is laid out in the assignment model, and what assumptions the homework makes about valid addresses, alignment, or control transfer. If HW1 includes diagrams or asks for traces, you should verify the exact machine model the class is using.

The concepts that should be studied immediately before this topic are machine representation basics: bits and bytes, memory addresses, registers, and the idea that machine code is a binary encoding of operations. The concepts that should be studied immediately after this topic are control-flow instructions, function call and return, interrupts and exceptions, privilege mode, and process state. Those topics all depend directly on understanding that ordinary execution is a repeated fetch-decode-execute loop driven by the program counter.

## Retain / Do Not Confuse

Retain these ideas. The CPU is the active hardware that transforms machine state by carrying out instructions. A program is stored machine code plus associated data, not the source text you write. An instruction is an encoded machine command whose meaning is determined by the ISA. The program counter is the register that identifies the next instruction address. Fetch retrieves the instruction bits at the current PC. Decode determines what those bits mean. Execute applies that meaning to machine state and determines the next PC. Sequential execution is not magic; it is just the default rule for setting the next PC when no control transfer occurs.

Do not confuse source statements with machine instructions. Do not confuse the CPU with memory. Do not confuse the PC with a source-code line number. Do not confuse fetch with understanding, because fetch only retrieves bits. Do not confuse decode with execution, because decode identifies meaning but does not yet apply it. Do not confuse execute with arithmetic only, because execute includes memory actions and control transfer. Most importantly, do not confuse “the next instruction in the program text” with “the instruction whose address becomes the next PC.” In machine execution, the second idea is the real one.
