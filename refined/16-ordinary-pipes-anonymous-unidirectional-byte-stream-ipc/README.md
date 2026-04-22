# Ordinary Pipes: Anonymous Unidirectional Byte-Stream IPC

An ordinary pipe should be introduced as a kernel object, not as a code pattern. The standard parent/child example is common, but it is not the conceptual center. The conceptual center is this: an ordinary pipe is **one kernel-managed byte stream** exposed through **two file descriptors**, one for reading and one for writing.

That immediately gives the canonical object model.

- The pipe itself is the kernel communication object.
- The two descriptors are process-level handles to its two ends.
- The stream is anonymous: there is no filesystem pathname by which unrelated processes can reopen it later.
- The stream is unidirectional: bytes move from write end to read end.
- The stream is byte-oriented: application-level message boundaries are not preserved automatically.

The term **descriptor** should be reactivated locally here. A descriptor is the small per-process handle — usually an integer in Unix/POSIX systems — that refers to an open kernel object. So when this chapter says that a process “has the read end,” it really means the process has a descriptor that refers to the read endpoint of the pipe object.

The parent-child association now becomes easy to explain correctly. Anonymous pipes are commonly used between parent and child because `fork()` duplicates the process’s descriptor table. That means the child receives descriptors referring to the same underlying pipe object that the parent already had. The pipe works because the descriptors were inherited, not because kinship is magical.

That distinction matters for exam reasoning. The real rule is **descriptor possession**, not family relation. Parent-child communication is simply the most common setup path because it is the easiest way to distribute the anonymous endpoints.

A short mechanism reminder fixes the picture. A process calls `pipe(fd)`. The kernel creates one pipe object and installs two descriptors in that process. Later, if the process calls `fork()`, both parent and child hold descriptors referring to the same read and write ends. Communication becomes possible because both now have handles to the same kernel object.

**Retain.** An ordinary pipe is one kernel-managed anonymous byte stream with one read end and one write end.

**Do Not Confuse.** Parent-child communication is the common distribution pattern for the endpoints, not the definition of the pipe.

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

**Retain / Do Not Confuse**

Retain: an ordinary pipe is unidirectional and byte-stream oriented.

Do not confuse: ordered byte delivery with preserved higher-level message structure.

## Full mechanism trace: `pipe()`, `fork()`, close discipline, transfer, EOF

This section exists because pipe behavior is easiest to misread at the lifecycle level. Students often know the API calls but not the logic that makes EOF, blocking, and deadlock behavior emerge. The mechanism trace is therefore the center of the chapter.

The object here is the **end-to-end lifetime of one ordinary pipe used between a writer and a reader after `fork()`**. Formally, the standard pattern is: create pipe, fork, close unused ends in each process, write from the designated writer, read from the designated reader, and observe EOF only after all write-end references are closed.

One quick reminder is needed before the close-discipline discussion: a descriptor counts as an open reference to an endpoint even if the process never actually reads or writes through it. That is why “forgetting to close an unused end” is not cosmetic. It changes the kernel’s view of whether readers or writers still exist.

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

## Ordinary pipes in the IPC landscape

Ordinary anonymous pipes are the right object when one process can create the stream and arrange endpoint inheritance or duplication during setup. That is why they fit shell pipelines so well: the shell creates the pipe, forks children, assigns the right ends, and closes the rest.

They are weaker when independent processes must rendezvous later by name, when bidirectional conversation is required, or when richer endpoint semantics are needed. That is where FIFOs, sockets, or other IPC objects become the better fit.

So the chapter’s final retention point should be short and exact: **ordinary pipes are the canonical local inherited byte-stream primitive.**

**Retain.** Use ordinary pipes when inherited descriptor setup is natural and one-way stream semantics are enough.

**Do Not Confuse.** Anonymous pipes are not the general solution to all IPC problems; they are the simplest stream primitive in the local descriptor-inheritance setting.
