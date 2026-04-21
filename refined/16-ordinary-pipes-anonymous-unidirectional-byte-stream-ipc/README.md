# Ordinary Pipes: Anonymous Unidirectional Byte-Stream IPC

## Why this section exists

A pipe is one of the simplest interprocess communication objects in Unix-like systems, but it is also one of the most frequently misdescribed. Students often remember the surface pattern — one process writes, another process reads — and then quietly import properties the object does not have. They imagine a pipe as a sequence of messages, or as a channel that works because the processes are parent and child, or as a data path whose behavior is determined mainly by `fork()`. None of those is the canonical center of the mechanism.

The real object is smaller and stricter. An ordinary pipe is a kernel-managed byte stream with one read end and one write end, made accessible through file descriptors. The parent-child pattern is common only because `fork()` duplicates descriptor tables. The pipe itself is not a family relation. It is a kernel object whose endpoints become usable in whatever processes hold descriptors referring to those endpoints.

This section exists to replace the pattern-memory version of pipes with the actual object model. Once that model is clear, the standard parent-child examples, shell pipelines, redirection patterns, and later IPC mechanisms all become easier to reason about. Without that model, students can often write simple code that appears to work, but they misread EOF, mis-handle close discipline, and do not understand why blocked reads or broken pipes occur.

The later material this supports is substantial. Shell pipelines are built from the same object. Redirection is descriptor manipulation applied to related kernel objects. Producer-consumer reasoning becomes concrete once the byte-stream and blocking semantics are explicit. Named pipes and sockets are easier to place once ordinary anonymous pipes are understood as the simplest kernel stream IPC primitive.

**Retain / Do Not Confuse**

Retain: the point of this chapter is not “how to memorize `pipe` examples,” but “what kernel object an ordinary pipe actually is.”

Do not confuse: the common parent-child coding pattern with the defining semantics of the pipe itself.

## The object: one kernel byte stream exposed through two file descriptors

The reason to begin with the object is that nearly every important pipe property follows from it. An ordinary pipe is not two unrelated descriptors that somehow talk to each other. It is one kernel-managed communication object, and the two descriptors returned by `pipe()` are just process-level handles onto the two different access directions of that object.

Formally, an **ordinary pipe** (also called an **anonymous pipe**) is a kernel-managed, unidirectional, byte-stream IPC object created by `pipe()`, which returns two file descriptors: one descriptor naming the read end, and one descriptor naming the write end. The underlying kernel object contains a bounded buffer or stream state used to transfer bytes written at the write end to readers at the read end.

The interpretation should be immediate. When `pipe(fd)` succeeds, the kernel has created exactly one communication channel, not two. The process receives two descriptors because the object has two roles. One descriptor is valid for reading from the stream; the other is valid for writing into it. Those descriptors are entries in the process’s descriptor table referring to kernel-side open-file state associated with the pipe ends. The data itself is not stored “inside the descriptor.” The data path lives in the kernel object.

This matters because it clarifies what `pipe()` does and does not create. It creates no pathname in the filesystem namespace. It creates no application-level packet structure. It creates no bidirectional session. It creates no magical parent-child link. It creates a unidirectional byte stream with two endpoint descriptors.

The boundary conditions are important. Because the pipe is anonymous, it is normally useful only to processes that already possess, or inherit, the descriptors referring to it. Because it is unidirectional, the read descriptor is for receiving bytes and the write descriptor is for sending bytes; a second pipe is needed for symmetric request-response if both directions are required. Because it is a byte stream, the reader observes a sequence of bytes, not a sequence of preserved writes as application-level messages.

The main failure mode at the object-definition level is conceptual rather than syntactic: treating `pipe()` as if it creates a message queue, a socket pair, or a filesystem object. Once that confusion enters, later behavior such as short reads, coalesced writes, and EOF conditions becomes hard to reason about correctly.

A minimal mechanism trace at the object level is already revealing. Suppose a process calls `pipe(fd)`. The kernel allocates a new pipe object, initializes internal buffer state, creates the access structures for the read and write sides, and installs two descriptors in the caller’s descriptor table. If the call returns successfully, the caller now has two integer descriptor values. One identifies the read end of this new pipe in the caller’s table; the other identifies the write end of the same underlying pipe object. That is the entire initial state. No process has yet communicated. No child is required. No bytes have yet moved.

A common misconception appears here.

**Misconception block: “A pipe is basically two file descriptors talking to each other.”**

That wording obscures the actual structure. The descriptors do not directly contain each other’s data path. They are access handles to one kernel communication object. Thinking of “the pipe” as the kernel object, and the descriptors as references to its ends, makes later close and EOF behavior intelligible.

This object model connects directly to later material on descriptor passing, redirection, shell pipelines, and the comparison between ordinary pipes, FIFOs, and sockets. All of those topics rely on understanding the difference between a per-process descriptor table and the underlying kernel object being referenced.

**Retain / Do Not Confuse**

Retain: `pipe()` creates one kernel-managed byte stream and returns two descriptors, one for reading and one for writing.

Do not confuse: the process-local descriptors with the kernel object they reference.

## Why pipes are associated with parent-child communication

This section exists because the standard first example of a pipe is almost always a parent and child after `fork()`, and that repeated pattern can hide the real reason the example works. If that reason is not made explicit, students conclude that pipes are inherently for relatives. They are not.

The object being introduced here is **descriptor inheritance as the practical distribution mechanism for anonymous pipe endpoints**. The formal statement is simple: ordinary pipes are commonly used for parent-child communication because `fork()` duplicates the calling process’s descriptor table, causing both parent and child to hold descriptors referring to the same underlying pipe ends. Interpretation: the communication path survives across `fork()` because descriptor references are copied, not because the kernel recognizes familial relationships as IPC privileges.

That interpretation is the key. Parent and child are common pipe peers because a newly created child automatically receives the parent’s open descriptors unless close-on-exec or explicit closure changes that state. This makes anonymous pipes convenient: the endpoints do not need to be rediscovered by name or reopened through the filesystem. The descriptors already exist, and `fork()` propagates them. The inherited descriptors are enough to allow communication.

The hidden constraint is that an anonymous pipe has no public name. If two unrelated processes start independently and have no prearranged way to receive inherited descriptors, an ordinary anonymous pipe is not the right primitive for connecting them after the fact. The practical communication pattern therefore often looks parent-child, or at least ancestor-descendant through descriptor inheritance, because inheritance is how the endpoints spread.

But the parent-child relationship is not the principle. Descriptor possession is the principle. If a descriptor is inherited through several generations, duplicated with `dup`, or passed through another mechanism that preserves access to the underlying object, the process holding it can use the pipe end regardless of whether it is the original creator or direct child. The pipe does not inspect the family tree and decide whether bytes may flow.

A short mechanism trace makes this concrete. A parent creates a pipe. Before `fork()`, the parent holds both descriptors. After `fork()`, the child’s descriptor table contains entries referring to the same read and write ends. The kernel object has not been cloned into separate streams. Instead, two processes now possess references to the same pipe ends. That shared reference structure is why communication is possible.

The common failure mode here is to think that a pipe “works between parent and child because the child was born from the parent.” That language makes the mechanism sound biological instead of descriptor-based. The real dependency is much stricter: if the descriptors are not inherited, duplicated, or otherwise made available, the anonymous pipe endpoints are inaccessible.

**Misconception block: “Ordinary pipes require a parent-child relationship.”**

No. Ordinary anonymous pipes require that the communicating processes hold usable descriptors referring to the pipe ends. Parent-child relationships are merely the most common way that happens, because `fork()` copies descriptors. Kinship is therefore a frequent pattern, not the underlying rule.

This section connects directly to shell pipelines and redirection. The shell creates pipes in the parent shell process, forks children for the stages of the pipeline, and arranges which inherited descriptors survive in which child. The shell pipeline works because of descriptor inheritance and descriptor rearrangement, not because commands have any special relation to one another beyond the shell’s setup.

**Retain / Do Not Confuse**

Retain: ordinary anonymous pipes are commonly used between parent and child because `fork()` copies descriptor references.

Do not confuse: descriptor inheritance in practice with kinship in principle.

## Unidirectionality and byte-stream semantics

This section exists because two separate misunderstandings often get bundled together. One is about direction: students assume a pipe is a general conversation channel. The other is about structure: students assume each `write()` produces a corresponding logical message on the reading side. Both are wrong in the ordinary pipe model.

The object being introduced is the pipe’s **unidirectional byte-stream semantics**. Formally, an ordinary pipe supports one direction of data transfer only: bytes written to the write end become available to reads on the read end. The data is delivered as a stream of bytes, not as a sequence of preserved application-level messages.

The interpretation follows immediately. If process A writes and process B reads, then the pipe behaves like a stream: the reader obtains whatever bytes are currently available, subject to normal read semantics and blocking rules. The reader is not told, at the kernel object level, “these 17 bytes were one message and the next 12 bytes were another.” The application may choose to impose a protocol — line-delimited records, length-prefixed units, fixed-size structures — but the pipe itself is not preserving those higher-level message boundaries for the application.

The unidirectionality means that a single ordinary pipe is not the right primitive for bidirectional request-response by itself. If parent and child must both send arbitrary data to each other, then one pipe is typically used for parent-to-child and another for child-to-parent, or a different IPC primitive is chosen.

The boundary conditions are worth stating explicitly. A `read()` may return fewer bytes than the reader conceptually “wanted,” even when more bytes will arrive later. A reader may consume bytes produced by several writes in one read call if they are contiguous in the stream. Conversely, a large logical application message may need multiple writes and multiple reads. The pipe only promises stream semantics. Application structure must be layered above it.

The primary failure mode here is protocol confusion. Programs that assume “one write equals one read equals one message” often appear to work in toy tests and then fail when scheduling changes, when data volume changes, or when multiple writers are involved. The bug is not that the kernel violated pipe semantics; it is that the program assumed stronger semantics than the object provides.

A short trace shows the issue. Suppose the writer performs `write(fd, "ABC", 3)` and then `write(fd, "DEF", 3)`. The reader might call `read(fd, buf, 6)` and receive `ABCDEF` in one read. Or it might call `read(fd, buf, 4)` and receive `ABCD`, then later receive `EF`. If the application wanted separate messages `ABC` and `DEF`, the application needed its own framing rule. The pipe never promised to preserve that distinction.

**Misconception block: “Pipe communication is message-based.”**

No. Ordinary anonymous pipes are byte streams. They move ordered bytes. They do not inherently transport discrete messages.

**Misconception block: “Ordinary pipes preserve application-level message boundaries.”**

No. The ordering of bytes matters; application message boundaries do not survive automatically. If the program requires boundaries, the program must encode them.

This section connects directly to producer-consumer reasoning, shell command composition, line-oriented filters, and the comparison with message-oriented IPC mechanisms. It also prepares the ground for understanding why sockets may look similar at one level but differ significantly depending on socket type and protocol.

**Retain / Do Not Confuse**

Retain: an ordinary pipe is unidirectional and byte-stream oriented.

Do not confuse: ordered byte delivery with preserved higher-level message structure.

## Full mechanism trace: `pipe()`, `fork()`, close discipline, transfer, EOF

This section exists because pipe behavior is easiest to misread at the lifecycle level. Students often know the API calls but not the logic that makes EOF, blocking, and deadlock behavior emerge. The mechanism trace is therefore the center of the chapter.

The object here is the **end-to-end lifetime of one ordinary pipe used between a writer and a reader after `fork()`**. Formally, the standard pattern is: create pipe, fork, close unused ends in each process, write from the designated writer, read from the designated reader, and observe EOF only after all write-end references are closed.

Interpretation: close discipline is not cleanup decoration. It is part of the communication protocol. The kernel decides whether the stream still has potential writers by tracking whether any descriptors referring to the write end remain open. If an unused write end stays open somewhere, the reader may block forever waiting for bytes or EOF because the kernel still sees a possible writer.

Now trace the full mechanism in order.

A parent process first calls `pipe()`. The kernel creates one pipe object and returns two descriptors in the parent: a read descriptor and a write descriptor.

The parent then calls `fork()`. After `fork()`, both parent and child possess descriptor entries referring to the same underlying read and write ends. At this point, each process has both ends, even though that is usually not the final intended communication pattern.

Suppose the intended direction is parent writes to child. The parent should behave as the writer, so the parent closes its unused read end. The child should behave as the reader, so the child closes its unused write end. These closes matter immediately. They reduce the kernel’s reference counts and make the communication pattern truthful: one process now retains only the ability to write, and the other retains only the ability to read.

The parent writes bytes to the write end. The kernel appends those bytes into the pipe’s stream buffer, subject to capacity and blocking rules. The child reads bytes from the read end. The kernel removes delivered bytes from the pipe buffer and copies them into the child’s user buffer.

If the child attempts to read when the pipe buffer is empty but at least one write end still exists somewhere, the read blocks by default until data arrives or the situation changes. If instead the pipe buffer is empty and no write ends remain open anywhere, the read returns end-of-file: typically a return value of zero. That zero-length result is how the kernel signals “the stream has ended; no future writer remains.”

The subtle point is that EOF does not mean “the writer process is currently not writing.” It means “the stream is empty and all write-end references are gone.” Those are different conditions. A reader waiting for EOF can remain blocked indefinitely if some process accidentally keeps a write descriptor open, even if that process never intends to write.

The mirror failure exists on the writing side. If a process writes to the pipe when no read end remains open, the kernel cannot deliver the stream to any reader. In Unix-like systems, this triggers broken-pipe behavior: the write fails, commonly with `EPIPE`, and a `SIGPIPE` may be generated unless handled or ignored. This is the writer-side analogue of “no peer remains.”

A full worked mechanism trace with state is useful.

1. Parent calls `pipe()`: descriptors `p[0]` for read, `p[1]` for write. One kernel pipe object exists.
2. Parent calls `fork()`: both parent and child now have `p[0]` and `p[1]`, referring to the same pipe ends.
3. Parent closes `p[0]`: parent is not a reader.
4. Child closes `p[1]`: child is not a writer.
5. Parent writes bytes on `p[1]`: bytes enter the kernel pipe buffer.
6. Child reads from `p[0]`: bytes leave the pipe buffer and enter the child’s address space.
7. Parent finishes writing and closes `p[1]`.
8. Child continues reading until buffered bytes are exhausted.
9. Once the buffer becomes empty and no write-end references remain open anywhere, child’s next `read()` returns zero, indicating EOF.

The failure modes become visible from the trace. If the child forgets to close its inherited copy of `p[1]`, then even after the parent closes its own `p[1]`, the kernel still sees a write end open. The child may drain the available bytes and then block forever waiting, because EOF cannot be delivered while the child itself still holds an open writer reference. This is one of the classic pipe bugs.

**Misconception block: “Closing unused ends is just tidiness.”**

No. Closing unused ends is semantically necessary. It affects whether reads block, whether EOF can be observed, and whether the kernel correctly understands which directions are still live.

This mechanism trace connects directly to shell pipeline setup, `dup2`-based redirection, and deadlock analysis in multi-process stream topologies. The same principles reappear whenever multiple processes inherit descriptors to the same pipe ends.

**Retain / Do Not Confuse**

Retain: EOF on a pipe appears only when the stream is empty and all write ends are closed; close discipline is part of correctness.

Do not confuse: “no data available right now” with “the pipe has ended.”

## Worked example: parent sends data to child

This section exists because the mechanism trace shows the lifecycle abstractly, but a concrete communication pattern makes the consequences of correct and incorrect close discipline easier to see. The example is deliberately ordinary: a parent computes or obtains data, sends it to a child through a pipe, and the child consumes the stream until EOF.

The object being introduced is **one-way parent-to-child stream transfer using an ordinary anonymous pipe**. Formally, the parent creates a pipe before `fork()`, then after `fork()` the parent retains only the write end and the child retains only the read end. The parent writes the data and closes the write end when finished. The child reads until `read()` returns zero, indicating EOF.

Interpretation: the close at the end of writing is how the parent tells the child, at the kernel stream level, that the byte stream is complete. There is no separate end-of-message packet built into the pipe object. EOF is the completion signal for the stream as a whole.

Imagine the parent wants to send the text `alpha\nbeta\n` to the child. The parent creates the pipe and forks. In the child, the inherited write end is closed immediately. In the parent, the inherited read end is closed immediately. The parent then writes the bytes of the text to the write end. The child performs reads and receives the bytes in stream order. It may receive the full string in one read or in several smaller reads; both are valid because the pipe is a stream. When the parent has sent all intended bytes, it closes the write end. The child continues reading until the buffer empties. Then the next `read()` returns zero, and the child knows the stream has ended.

Now consider the same example with one mistake: the child forgets to close its inherited write end. The parent still writes the data and closes its own write descriptor. The child reads `alpha\nbeta\n` successfully. But after draining those bytes, the child does not receive EOF, because one write descriptor still exists — the child’s own inherited copy. The child blocks in another read, waiting for bytes that it will never write and nobody else will write. From the kernel’s perspective, the stream might still receive future data because a writer reference remains open. That is why the close matters.

The boundary conditions in this example deserve precision. If the parent writes more data than fits in the current pipe buffer and the child is not reading, the parent may block on write. If the child begins reading before any data has been written and at least one writer remains open, the child may block on read. If the child exits early and closes the read end while the parent is still writing, the parent’s next write can fail with broken-pipe behavior. None of these outcomes is exceptional relative to the object model; each follows directly from bounded-buffer stream semantics and endpoint reference tracking.

**Misconception block: “If the parent wrote the whole string in one `write()`, the child will read it in one piece.”**

Not necessarily. The child sees a stream. Scheduling, buffer sizes, and read request sizes determine how bytes are returned. The application must not infer message boundaries from write calls.

This worked example connects immediately to shell command setup, where a shell commonly uses one child as producer and another as consumer, and to producer-consumer designs more generally, where close discipline and stream termination are part of the protocol.

**Retain / Do Not Confuse**

Retain: in one-way parent-to-child communication, the parent signals completion by closing the write end; the child reads until EOF.

Do not confuse: successful transfer of current bytes with termination of the stream.

## Blocking behavior, deadlock, and broken pipes

This section exists because most real pipe bugs are not syntax errors but liveness errors. The code compiles, the descriptors look plausible, and then the processes stop making progress. That happens when the programmer treats the pipe as an informal convenience rather than as a bounded stream object with precise endpoint-liveness rules.

The object being introduced is the set of **failure modes induced by ordinary pipe semantics**. Formally, the important cases are: blocking reads when no data is available but at least one writer remains open; blocking writes when the pipe buffer is full and at least one reader remains; deadlock caused by incorrect close discipline or circular waiting; and broken-pipe behavior when a writer attempts to write and no reader remains.

Interpretation: these failures are not arbitrary. They are exactly what the kernel should do if the pipe is being used as a bounded, synchronous-enough stream object with tracked endpoint existence.

Begin with blocking reads. If a reader calls `read()` on an empty pipe while some write end is still open somewhere, the kernel cannot return EOF because more data could still arrive. The default behavior is therefore to block the reader until bytes arrive or until all write ends close. The hidden constraint is existential, not behavioral: the kernel cares that a writer reference exists, not that the corresponding process sincerely intends to write.

Now blocking writes. Pipe buffers are finite. If the writer produces data faster than readers consume it, the buffer eventually fills. At that point, a further `write()` may block until space becomes available. The pipe is therefore not just a logical connection; it is also a bounded-flow-control object. Producer-consumer reasoning is not optional here.

Deadlock emerges when processes depend on stream progress that cannot occur because of descriptor state or waiting structure. The classic close-discipline deadlock occurs when a reader waits for EOF but some process accidentally keeps a write end open forever. Another deadlock form appears in two-way protocols built incorrectly from pipes, where each side waits to read before writing while both buffers and control paths are arranged so that neither side advances. The kernel is not “hung” in a mystical sense. The program has created a wait structure with no enabling event.

Broken-pipe behavior is the writer-side terminal failure. If a process writes to a pipe whose read end is no longer open in any process, the kernel cannot deliver the bytes. The write therefore fails rather than silently accumulating unreachable data. In Unix-like systems this usually means `SIGPIPE` and/or an `EPIPE` error. The signal is not a nuisance add-on; it is the kernel’s way of saying that the consumer side of the stream no longer exists.

A mechanism trace clarifies the deadlock case caused by bad close discipline. Parent creates a pipe and forks child. Parent intends to write and child intends to read. Parent closes its read end, but child forgets to close its inherited write end. Parent writes all data and closes its own write end. Child reads all available bytes and then calls `read()` again expecting EOF. The pipe is now empty, but a write descriptor still exists in the child. The kernel therefore blocks the read instead of returning zero. The child waits forever on a stream it itself is keeping alive.

Boundary conditions matter here. Nonblocking I/O or readiness multiplexing can alter the immediate behavior seen by the program, but they do not change the underlying meaning of the pipe state. The chapter’s center is the ordinary blocking model because it exposes the canonical semantics most directly.

**Misconception block: “If a pipe read blocks, the writer must be slow.”**

Not necessarily. A read can block because the stream is currently empty while some write end remains open. That open write end may belong to a process that will never write another byte. Descriptor liveness, not programmer intention, determines the kernel’s choice.

This section connects directly to shell pipeline bugs, daemon supervision patterns involving inherited descriptors, producer-consumer backpressure, and the move to other IPC objects such as sockets when richer bidirectional or multiplexed behavior is required.

**Retain / Do Not Confuse**

Retain: blocking, deadlock, and broken-pipe behavior follow directly from bounded byte-stream semantics and endpoint reference tracking.

Do not confuse: the existence of an open end with active useful work by the process holding it.

## Ordinary pipes in the larger IPC landscape

This section exists to place the mechanism where it belongs in the IPC design space. Once the pipe has been defined accurately, its later uses stop looking like separate tricks and start looking like reuses of one clean primitive.

The object being introduced is the ordinary pipe as a **kernel stream IPC building block** that sits between descriptor-level process management and richer communication abstractions. Formally, an anonymous pipe is a kernel-managed, unidirectional byte stream accessible through inherited or otherwise preserved descriptors, typically used for local IPC among related processes or processes that receive the descriptors through setup.

Interpretation: this is why shell pipelines are so natural. The shell creates one pipe per adjacent pipeline stage, forks the command processes, duplicates the appropriate inherited ends onto standard input or standard output, closes the unused descriptors, and lets each command see only the stream end it needs. Redirection is the same descriptor discipline applied to files or pipe ends instead of terminals. Producer-consumer patterns map cleanly because a pipe provides exactly what that pattern asks for: ordered stream delivery plus bounded buffering and blocking semantics. Named pipes extend the concept by adding a filesystem-visible rendezvous point. Sockets generalize the communication model further, especially when bidirectionality, remote communication, or more elaborate endpoint semantics are needed.

The boundary condition to keep in view is scope. Ordinary anonymous pipes are strongest when one process can create the communication object and arrange endpoint inheritance or duplication at process creation time. When independent processes must rendezvous later by name, anonymous pipes are the wrong fit; named pipes or sockets become the natural next objects.

A final mechanism trace through a shell pipeline shows the continuity. For `cmd1 | cmd2`, the shell creates a pipe, forks a child for `cmd1`, duplicates the write end onto standard output in that child, closes unused ends, forks a child for `cmd2`, duplicates the read end onto standard input in that child, closes unused ends, and then closes its own copies. What remains visible to the commands is just standard I/O. Underneath, the shell has built exactly the same ordinary pipe mechanism developed in this chapter.

**Misconception block: “Shell pipelines are a separate feature from ordinary pipes.”**

No. Shell pipelines are a high-level arrangement of ordinary pipes plus descriptor duplication and closure.

This section connects directly to command interpreters, I/O redirection, named FIFOs, stream sockets, and later discussions of how operating systems unify diverse I/O objects behind descriptor-based APIs.

**Retain / Do Not Confuse**

Retain: ordinary pipes are the canonical local unidirectional byte-stream IPC primitive underlying shell pipelines and many producer-consumer patterns.

Do not confuse: the high-level syntax of shell pipelines with the low-level kernel object that makes them work.

