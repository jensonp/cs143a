# Named Pipes (FIFOs): Filesystem-Named Pipe Endpoints for IPC

Named pipes matter because ordinary pipes solve only half of a coordination problem. An ordinary pipe gives two processes a kernel-managed byte stream, but it assumes the processes already share file descriptors, usually because one process created the pipe and then passed the descriptors across `fork` and `exec`. That is enough for shell pipelines and parent-child setups. It is not enough when the processes are unrelated, started separately, or intended to meet through a stable rendezvous point. The missing mechanism is not a different data model. It is a different discovery model. A named pipe is the same broad class of kernel byte-stream IPC object, but made discoverable through the filesystem namespace.

Formally, a **named pipe**, also called a **FIFO special file**, is a kernel-managed IPC object with pipe-like byte-stream semantics that is bound to a pathname in the filesystem namespace. Processes open that pathname and obtain file descriptors referring to the FIFO’s read or write end; the data itself flows through kernel-managed pipe buffers rather than being stored as ordinary file contents on disk. The name “FIFO” refers to first-in, first-out byte delivery in the pipe sense: bytes are read in the order they were written, subject to the ordinary pipe rules for multiple writers and the lack of message boundaries.

The interpretation must be immediate, because this is where students often drift into the wrong abstraction. A named pipe is not “a file that happens to behave like a queue.” The pathname is only the discovery handle. The object of interest is still a pipe-like kernel communication channel. Naming changes **who can find the object** and **how they synchronize on it**. Naming does **not** change the object into persistent file storage, and it does **not** upgrade a byte stream into a message transport.

The boundary conditions follow directly from that interpretation. Because the name lives in the filesystem namespace, unrelated processes can rendezvous on the same object without descriptor inheritance. Because the underlying semantics remain pipe semantics, FIFO I/O remains sequential, unseekable, and stream-oriented. Because there is a name, the path can remain after the communicating processes have exited, which creates a new class of coordination error: the path may still exist even when no peer is currently attached.

A first mechanism sketch clarifies the object. One process creates a FIFO at a pathname. That creation establishes a special filesystem entry of FIFO type, not a regular data file. Later, a reader opens the pathname for reading, a writer opens the same pathname for writing, and the kernel binds both opens to the FIFO communication object. Bytes written by the writer are buffered in the kernel and removed by the reader in stream order. If one side opens too early, the open may block or fail according to the access mode and blocking flags. If the path exists but no peer is present, the name is still valid even though communication is not yet live. The name therefore coordinates discovery, but peer presence still controls communication progress.

A common misconception appears right at the start.

**Misconception block: “named pipe” means “pipe semantics plus file persistence.”** The pathname persists as a namespace entry until removed, but the communicated bytes are not ordinary file contents stored for later rereading. A FIFO is not an append-only mailbox on disk. Once bytes are read from the FIFO, they are consumed as pipe data; later readers do not reopen the path and recover prior traffic the way they would read a regular file. The filesystem name persists; the byte stream does not.

Connection to later material is straightforward. Once named pipes are understood as **named rendezvous points for pipe semantics**, later topics such as shell plumbing, service coordination, local IPC protocols, and Unix-domain sockets become easier to compare structurally.

**Retain / Do Not Confuse**

Retain: a named pipe is a kernel-managed pipe-like byte stream made discoverable by pathname.

Do not confuse: the filesystem name is persistent namespace state; the data stream is transient kernel IPC state.

## Why naming changes the structure of IPC

This section exists because the central idea in named pipes is not the buffering rule but the change in how two processes find each other. If that structural change is not made explicit, FIFOs look like ordinary pipes with an unnecessary pathname attached. The pathname is not decorative. It changes the coordination model.

The object introduced here is **rendezvous by pathname**. Formally, naming allows an IPC object to be looked up in the filesystem namespace rather than handed from one process to another through already-open file descriptors. In an ordinary pipe, the creating process calls `pipe()`, obtains two descriptors, and then some inheritance or explicit descriptor passing path must exist if another process is to use them. In a named pipe, the system call that creates the FIFO—canonically `mkfifo()` or equivalent—creates a namespace entry. Later, any process with appropriate pathname access can open the FIFO by name.

The interpretation is that naming externalizes the point of contact. With an ordinary pipe, the communication object is private unless descriptors are inherited or passed. With a FIFO, the namespace itself becomes the meeting place. This has three direct structural consequences.

First, **discovery happens by pathname**. A process does not need an inherited descriptor; it needs the path and permission to open it. Second, **descriptor inheritance through `fork` is no longer necessary**. The reader and writer may have no common ancestor that participates in setup. Third, **unrelated processes can rendezvous on the same object**. The pipe is no longer confined to a family tree of process creation. The coordination relation is now “both know the path and access rights,” not “both descend from the process that created the descriptors.”

This does not mean naming removes all coordination difficulty. It changes the location of the difficulty. Descriptor inheritance answers “how do both processes get handles to the same kernel object?” Naming answers that by pathname lookup. But a FIFO still requires compatible opening patterns, peer presence, and stream-level protocol agreement. The name solves discovery; it does not solve protocol design.

The hidden constraint is especially important: naming broadens who can attach, which means the chance of accidental attachment, stale-path reuse, or conflicting protocol assumptions increases. An ordinary pipe is usually private and short-lived. A FIFO can be reopened by entirely different processes at different times. That new power is exactly why coordination discipline becomes more important, not less.

A worked structural comparison makes the difference concrete. Suppose process P creates an ordinary pipe and then starts child C. C can use the inherited descriptor because the parent-child relation preserved handle reachability. Now suppose process X starts in the morning and process Y starts minutes later from a different login session with no common setup process. An ordinary pipe gives them no shared object unless some third mechanism passes descriptors. A FIFO does: X and Y both open `/tmp/metrics.fifo` and rendezvous there. The communication pattern is still pipe-like, but the discovery pattern has changed from inheritance to namespace lookup.

**Misconception block: naming changes the data model.** No. Naming changes who can locate the object and when they can attach. It does not change byte-stream semantics into message semantics, persistent semantics, or connection-oriented endpoint semantics.

Connection to later material is immediate. Shell pipelines lean on inheritance-based ordinary pipes. Local rendezvous patterns lean on name-based objects. Unix-domain sockets go one step further by combining naming with richer endpoint semantics.

**Retain / Do Not Confuse**

Retain: naming changes discovery and rendezvous. It lets unrelated processes meet on the same IPC object without inherited descriptors.

Do not confuse: naming solves handle discovery, not framing, authentication, ordering beyond stream order, or application protocol design.

## The formal object: FIFO semantics and what a FIFO is not

This section exists because “FIFO” is easy to say loosely and easy to map onto the wrong comparison class. The only way to use FIFOs correctly is to distinguish them sharply from three neighboring objects: ordinary pipes, regular files, and sockets.

The object introduced here is the FIFO special file as a member of the Unix/POSIX file-object universe. Formally, a FIFO is a special file type represented in the filesystem namespace but interpreted by the kernel as a pipe-like IPC endpoint set. It is opened with ordinary file-descriptor APIs, read and written with ordinary descriptor I/O calls, and subject to the semantics of pipes/FIFOs rather than the semantics of regular files.

The interpretation is easiest by contrast.

An **ordinary pipe** is an unnamed kernel byte stream created directly as a pair of descriptors. Its reachability is initially descriptor-based. A **named pipe** is still a pipe-like byte stream, but its reachability is pathname-based. Once opened, the read and write descriptors behave in the pipe/FIFO class, not in the regular-file class.

A **regular file** stores persistent data in the filesystem. It has contents with offsets, supports reopening later to reread prior bytes, and is governed by file-position semantics. A FIFO is different on every one of those dimensions. It is not seekable, does not offer durable stored contents, and does not mean “writer deposited bytes for later file retrieval.” The path names a communication endpoint, not stored content.

A **socket** is another IPC object class, but it is not equivalent to a FIFO. Sockets may be stream-oriented or message-oriented depending on type; they carry addressing or connection semantics not present in bare FIFO byte streams; Unix-domain sockets can support bidirectional communication, ancillary data such as file descriptor passing, and richer peer relations. A FIFO is far narrower: conceptually one byte stream with pipe semantics, typically used unidirectionally and without built-in message boundaries.

The boundary conditions matter because oversimplification creates real bugs. Canonical POSIX FIFO behavior includes blocking behavior on `open`, EOF behavior on `read`, failure or signal behavior on writing when no reader exists, and atomicity guarantees only up to `PIPE_BUF` bytes for writes. Beyond that bound, especially with multiple writers, interleaving may occur. Therefore “FIFO” should not be mentally expanded into “queue of complete application records.” It is a byte stream. Applications that need records must define framing explicitly.

A short semantic table is justified here because the distinctions are structural rather than stylistic:

| Object | Discovery / reachability | Data model | Persistence of bytes | Bidirectionality | Typical use |
|---|---|---|---|---|---|
| Ordinary pipe | inherited/passed descriptors | byte stream | no | portable model is one-way | parent-child plumbing |
| Named pipe (FIFO) | pathname open | byte stream | no | portable model is one-way | unrelated local-process rendezvous |
| Regular file | pathname open | file contents with offsets | yes | not IPC by itself | storage |
| Socket | pathname or network address depending on family | stream or messages depending on type | no | often bidirectional | richer IPC / networking |

A mechanism reminder sharpens the formal point. If two writers each write short records to a FIFO, writes up to `PIPE_BUF` bytes are required by POSIX to be atomic with respect to interleaving; larger writes may be interleaved with other writers’ output. That single rule is enough to prove that FIFO semantics remain stream semantics, not message semantics. Atomic short writes prevent certain tearing effects, but they do not create an application-level message transport.

**Misconception block: “FIFO = socket with a pathname.”** A pathname alone does not make two IPC objects equivalent. Unix-domain sockets may share local-path naming, but they support different endpoint semantics, richer communication patterns, and different failure behavior. A FIFO is a named pipe, not a stripped-down socket.

Connection to later material is strong. The moment one understands why FIFOs are narrower than sockets, the motivation for Unix-domain sockets becomes obvious: they preserve local rendezvous by name while adding richer communication primitives.

**Retain / Do Not Confuse**

Retain: a FIFO is a special file type whose pathname names a pipe-like kernel IPC object.

Do not confuse: FIFO vs regular file is a storage-versus-stream distinction; FIFO vs socket is a pipe-semantics-versus-endpoint-semantics distinction.

## Canonical POSIX/Unix FIFO semantics

This section exists because FIFO errors almost always come from getting the exact blocking and peer-presence rules slightly wrong. The object here is not the pathname anymore but the behavior of `open`, `read`, `write`, and `close` once a FIFO is in play.

Formally, POSIX treats a FIFO as a special file that can be opened for reading or writing. When opening a FIFO, behavior depends on access mode and whether `O_NONBLOCK` is set. If `O_NONBLOCK` is clear, opening read-only blocks until some process opens the FIFO for writing, and opening write-only blocks until some process opens the FIFO for reading. If `O_NONBLOCK` is set, opening read-only returns immediately even if no writer is present, while opening write-only fails if no reader is currently open, conventionally with `ENXIO`. Once open, reads from an empty FIFO return end-of-file if no writer remains open; otherwise they block in blocking mode or fail with `EAGAIN` in nonblocking mode. Writes to a pipe or FIFO with no reader cause `EPIPE` and deliver `SIGPIPE`; writes of at most `PIPE_BUF` bytes are atomic relative to interleaving, while larger writes may be interleaved or partially transferred depending on blocking mode and available space.

The interpretation is that a FIFO has two distinct phases of coordination. The first is **rendezvous at open time**: are compatible readers and writers present yet? The second is **stream transfer after open**: are bytes available, is space available, and are peers still present? Students often collapse these into one idea called “the FIFO blocks.” That is too crude. Blocking can happen because the object has not yet been paired at open time, or because a reader or writer is waiting on stream state after both ends are already open.

The hidden assumptions should be made explicit.

The first assumption is unidirectional reasoning. Portable code should treat FIFOs as one-way byte streams, even though some systems have extension behavior that allows more exotic opens. Linux, for example, allows opening a FIFO read-write in ways POSIX leaves undefined, but that is not the portable semantic model to build teaching on.

The second assumption is peer-sensitive liveness. A path may exist while no useful communication relation exists. A writer may fail to open because no reader is present. A reader may open successfully in nonblocking mode and then observe immediate absence of data rather than a functioning stream. The namespace object alone does not guarantee a live peer.

The third assumption is protocol discipline under multiple participants. Multiple readers or multiple writers are permitted by the object model, but the semantics then belong to the shared byte stream, not to isolated per-peer channels. Reads drain shared data. Short writes may stay intact; larger writes may interleave. Therefore application-level record ownership is not guaranteed unless the protocol is designed carefully.

A full mechanism trace now makes the rules concrete.

A process first creates a FIFO at a pathname such as `/tmp/events.fifo`. At this point, the filesystem contains a FIFO special file entry. No bytes are “in the file,” and there may be no active kernel pipe instance yet. Now suppose process R opens the FIFO for reading in blocking mode. Because no writer is yet open, R blocks inside `open`. Later process W opens the same pathname for writing in blocking mode. W can now be paired with the waiting reader, so both opens complete. From this point onward, both processes hold descriptors referring to the FIFO stream. W writes bytes; the kernel places them in FIFO buffers. R reads bytes; those bytes are removed from the stream in order. If R reads faster than W writes and the buffer becomes empty while W is still open, R blocks in `read`. If W closes its descriptor and no other writer remains, then once buffered bytes are drained, a further `read` by R returns 0, signaling end-of-file. If instead R closes first and no reader remains, a subsequent write by W triggers `SIGPIPE` and fails with `EPIPE`. If either process had used `O_NONBLOCK`, some of these waits would turn into immediate return paths or errors rather than sleeps.

That trace reveals the main failure modes naturally. The call that blocks may be `open`, not only `read`. The object can be reachable by name while not yet ready for communication. End-of-file on a FIFO means “no writers remain,” not “the path disappeared.” And successful open does not imply application-level message framing or peer identity.

**Misconception block: naming creates message boundaries.** No. FIFO writes are still writes into a byte stream. POSIX atomicity up to `PIPE_BUF` protects short writes from interleaving with other writers, but the reader still sees a stream of bytes. If the application wants records, it must encode record lengths, delimiters, or fixed-size frames itself.

Connection to later material is direct. These exact semantics explain why shell plumbing works smoothly for simple one-writer/one-reader pipelines, why local rendezvous by path is useful, and why more demanding local IPC often moves to Unix-domain sockets.

**Retain / Do Not Confuse**

Retain: FIFO behavior has an open-time rendezvous phase and a stream-transfer phase; both can block, and both depend on peer presence.

Do not confuse: path existence is not peer existence, and atomic short writes are not message semantics.

## Worked example: two unrelated processes meeting by pathname

This section exists because the central practical use of FIFOs is not parent-child plumbing but unrelated-process rendezvous. The example must therefore involve processes that do not share descriptors through `fork`.

The object introduced here is a local coordination pattern: one process advertises a FIFO pathname as an intake channel, and another independently started process uses that pathname to attach. Formally, the processes are unrelated in the process-tree sense but related through shared namespace knowledge.

Consider a monitoring setup on a single machine. Process A is a long-running log collector launched by a service manager in the morning. Process B is a diagnostics utility started later by an administrator from a shell. They are unrelated in the ordinary sense: B is not a child of A, and A did not create descriptors for B. Process A expects diagnostic records on `/run/diag-feed`. Earlier, some setup step created a FIFO at that path with appropriate permissions.

At time `t0`, A opens `/run/diag-feed` for reading. If A uses blocking open and no writer exists yet, A sleeps in `open`. At time `t1`, the administrator starts B, and B opens `/run/diag-feed` for writing. That writer open completes because a reader is waiting, and the waiting reader open also completes. Now B writes a record such as a timestamped status line. The bytes travel through kernel pipe buffering, not into a regular file on `/run`. A reads the bytes and parses them according to the application protocol—say, newline-delimited records. When B exits and closes its descriptor, A eventually sees end-of-file once all buffered bytes are consumed, unless another writer has opened the FIFO in the meantime.

Several details in this example matter. First, A and B coordinate solely by pathname. Second, the protocol is not provided by the FIFO itself. If two administrators run B simultaneously, their writes may remain intact only up to `PIPE_BUF`; larger writes may interleave. Third, if A assumes “one writer at a time” but the environment violates that assumption, the bug is in the application protocol design, not in the kernel’s FIFO implementation. Fourth, if the path `/run/diag-feed` remains after A is gone, a later B may successfully reach the namespace object yet fail to make progress because no reader is attached.

The misconception to reject here is subtle: because the pathname looks file-like, it is tempting to think process B is “dropping records into a file that A later reads.” That is the wrong operational model. A and B are attached to a live kernel stream. If A is absent, the behavior is governed by FIFO open semantics, not by persistent storage semantics.

Connection to later material is immediate. This is exactly the coordination pattern used when local processes must discover each other by conventional pathnames without a common ancestor process doing descriptor setup.

**Retain / Do Not Confuse**

Retain: unrelated processes can use a FIFO because the namespace provides the meeting point that ordinary pipes lack.

Do not confuse: the pathname enables rendezvous, but correctness still depends on peer timing and protocol discipline.

## Failure modes, stale paths, and why multiple participants are dangerous

This section exists because FIFOs are often taught as simpler than sockets, and that is true only if the communication pattern is simple. The object here is the family of coordination failures that naming introduces or exposes.

The first failure mode is **blocking on open**. A reader opening blocking read-only waits for some writer to appear; a writer opening blocking write-only waits for some reader to appear. That is not an implementation accident. It is part of the rendezvous semantics. If the application assumes `open` is cheap and immediate the way a regular-file `open` often is, it will deadlock or appear to hang.

The second failure mode is **absent peer confusion**. In nonblocking mode, read-only open can succeed even with no writer, and write-only open can fail immediately because no reader exists. Later, a reader on an empty FIFO must distinguish between “temporarily no data while a writer still exists” and “EOF because no writers remain.” Those states matter operationally because one calls for waiting and the other calls for teardown or reconnection logic.

The third failure mode is **stale path confusion**. Because the path persists independently of any current communication session, users often conflate “the path exists” with “the service is running.” A FIFO pathname can remain in the filesystem long after the intended reader or writer has disappeared. Processes then successfully resolve the name but still fail to rendezvous or progress. Naming therefore improves discoverability while also making stale coordination artifacts possible.

The fourth failure mode is **protocol ambiguity under multiple readers or writers**. A FIFO does not assign messages to participants. Readers compete to drain the shared byte stream. Writers contribute to the same stream, with only bounded atomicity guarantees for short writes. If several producers write newline-delimited records smaller than `PIPE_BUF`, each individual record may remain intact, but no fairness or per-producer isolation follows from that. If records exceed the atomicity bound, interleaving becomes possible. Therefore “many processes share one FIFO” is not wrong, but it demands a protocol whose assumptions explicitly fit stream semantics.

A short mechanism trace illustrates the stale-path bug. Suppose a service once listened on `/tmp/control.fifo` and then crashed without removing the pathname. Hours later, an operator starts a client that opens the FIFO for writing. In blocking mode, the client may hang waiting for a reader that no longer exists. In nonblocking mode, the writer open may fail immediately because no reader is present. The path looked valid, but the communication relation was dead. That is the precise sense in which naming changes coordination: it gives a stable rendezvous point, but stability of the name is not stability of the peer.

Three misconception blocks belong together here.

**Misconception block: “named pipe = ordinary file on disk.”** False. The pathname lives in the filesystem namespace, but the FIFO’s communicated bytes are not durable file contents with offsets and rereads.

**Misconception block: “named pipe = socket.”** False. Both may be named locally, but sockets have richer endpoint semantics. A FIFO remains a pipe-like byte stream with narrower coordination capabilities.

**Misconception block: “naming upgrades stream semantics into message semantics.”** False. Naming changes discovery. It does not create packets, records, or sender identity.

Connection to later material follows from the failures themselves. Once applications need robust peer identity, bidirectional conversation, connection state, or message framing that should be preserved by the transport, Unix-domain sockets become the natural next step.

**Retain / Do Not Confuse**

Retain: the major FIFO risks are open-time blocking, absent-peer confusion, stale-path mistakes, and protocol ambiguity with multiple participants.

Do not confuse: the simplicity of the API surface does not imply simplicity of coordination when more than one reader or writer is involved.

## Why FIFOs still matter

This section exists because named pipes can look like an awkward midpoint between ordinary pipes and sockets unless their niche is stated clearly. The object here is their design role in the IPC landscape.

Formally, a FIFO occupies the point in the design space where a program wants **local**, **filesystem-named**, **kernel-managed**, **stream-oriented** IPC without requiring descriptor inheritance and without needing the richer semantics of sockets. The interpretation is practical: a FIFO is the tool for “we need one machine-local rendezvous path and pipe semantics are enough.”

That role connects directly to **shell plumbing**. Ordinary shell pipelines rely on anonymous pipes created by the shell and inherited by children. A FIFO extends the same broad stream model beyond one process family and one launch moment. It also supports **local rendezvous patterns** in which a service and later-started clients agree on a path. And it clarifies the transition to **sockets and Unix-domain sockets**: the moment the application needs bidirectional channels, more explicit connection semantics, peer credentials, descriptor passing, or safer multi-client structure, the FIFO’s limitations become design signals rather than surprises.

The hidden lesson is that naming changes coordination more than it changes transport. A pathname is a social fact inside the OS namespace: multiple programs can independently discover it, permissions can control access to it, and its persistence can outlive any one communication session. That is why naming matters. It is not because the bytes behave differently. It is because the existence of a shared name changes which processes can find each other at all.

A final worked comparison makes the lesson compact. If a shell starts `producer | consumer`, an ordinary pipe is the natural object because the shell already controls both descriptor sets. If a long-running collector and an independently started maintenance tool must exchange a local byte stream through a conventional path, a FIFO is natural. If two peers need full-duplex conversation, per-connection isolation, or richer endpoint semantics, a Unix-domain socket is usually the right answer. The transport chosen should match the coordination problem, not just the presence of a pathname.

**Retain / Do Not Confuse**

Retain: FIFOs are useful exactly when naming-by-path solves the coordination problem and pipe semantics are still sufficient.

Do not confuse: choose a FIFO because name-based local rendezvous is the right structure, not because it looks like an easy substitute for either files or sockets.
