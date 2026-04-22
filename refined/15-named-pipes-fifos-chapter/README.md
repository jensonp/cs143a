# Named Pipes (FIFOs): Filesystem-Named Pipe Endpoints for IPC

A named pipe should be introduced by stating exactly what naming changes and what naming does **not** change.

A FIFO is a **pipe-like kernel IPC object that is discoverable by pathname**. In plain operating-systems terms, that means the kernel maintains a communication object with pipe-style stream behavior, and processes can find that object by asking the operating system to resolve a filesystem path to it. That resolution step is what this chapter means by **namespace lookup**: the OS takes a pathname and tells the process which object that name refers to.

That is the structural gain over an ordinary anonymous pipe. An ordinary anonymous pipe is usually reached only through file descriptors that some process already holds. A FIFO is reached by name. So naming changes **how processes find the object**, not what kind of transport the object is.

The concept-level point should therefore be stated carefully:

**naming changes discovery and rendezvous; it does not upgrade the transport into a different data model.**

That sentence needs two reminder phrases.

Here, **discovery** means that unrelated processes can independently find the same kernel object by using the same pathname.  
Here, **rendezvous** means that they can meet at the same communication object without needing one process to pass the object handle directly to the other.

From that sentence, the core distinctions follow.

An **ordinary pipe** is unnamed and usually shared through inherited or explicitly passed **descriptors**. A descriptor is the small per-process handle — typically an integer in Unix/POSIX systems — that refers to an open kernel object such as a file, pipe, or socket.

A **FIFO** is still pipe-like, but processes can open it later by pathname rather than only by inheriting or receiving descriptors.

A **regular file** stores durable bytes with file-offset semantics. That needs to be unpacked. **Durable** here means the bytes remain as stored data after one writer finishes or exits. **File offset** means the kernel tracks a current read/write position inside the file, so later operations read or write at some position in persistent file contents. A FIFO does not behave that way. It is a live stream, not stored file contents.

A **socket** is a richer endpoint object with different connection and addressing semantics. That also needs to be unpacked. An **endpoint object** is a kernel communication object that one side of communication attaches to. **Addressing semantics** means the rules by which peers are identified and reached — for example, IP address plus port, or some local-socket naming scheme. A FIFO is not “a socket with a pathname.” It remains a narrower pipe-class object.

The portable model should now be stated clearly. A FIFO is best taught as a **stream-oriented, pipe-semantics object whose rendezvous is pathname-based**. It does not preserve application-level message boundaries. It does not become a regular file just because it appears in the filesystem namespace. And although some systems expose extensions that tempt looser language, the teaching model should remain the canonical one: a FIFO is still fundamentally a pipe-class object.

A worked structural contrast makes the point cleanly. If process P creates an ordinary pipe and then forks child C, the child can use the inherited descriptors. If process X starts now and process Y starts later with no shared setup process, an ordinary pipe gives them no shared object by itself. A FIFO does: both can open the same pathname and thereby attach to the same pipe-like kernel object.

That gain has a cost. Because naming broadens who can attach, stale paths, accidental attachment, and mismatched protocol assumptions become more likely. Naming solves discovery. It does not solve framing, peer validation, or application protocol design.

**Retain.** A FIFO is a pathname-discoverable pipe-like IPC object. Naming changes who can find the object, not what kind of transport it is.

**Do Not Confuse.** A FIFO is not a regular file, not a message queue, and not just a socket with a pathname.

## Canonical POSIX FIFO semantics

For exam purposes, the canonical semantics should be remembered in two phases: **open-time rendezvous** and **stream-time behavior**.

### Open-time rendezvous

A FIFO can be opened for reading or writing, but open behavior depends on whether a peer is present and whether nonblocking mode is used.

- In the ordinary blocking model, opening for reading waits until some writer opens the FIFO, and opening for writing waits until some reader opens the FIFO.
- In nonblocking mode, opening for reading can return immediately even without a writer, while opening for writing fails if no reader is present.

The exact platform details are less important than the conceptual rule: **pathname discovery does not remove peer-presence coordination.** It merely moves coordination to open time instead of descriptor-inheritance time.

That comparison needs one reminder sentence. In an ordinary anonymous pipe, one process typically creates the pipe first and then distributes the already-open ends by inheritance or explicit passing. In a FIFO, unrelated processes may each arrive later by pathname, so the coordination problem shifts to the act of opening the object.

Once opened, FIFO behavior is still pipe-class behavior. Reads on an empty FIFO block if a writer still exists. Reads return EOF only when the stream is empty and no writer remains. Writes fail with broken-pipe behavior if no reader remains. Short writes up to the platform’s atomicity bound may be protected from interleaving, but that does not create message semantics. Larger writes can interleave when multiple writers participate.

The portable teaching model should therefore be explicit: treat a FIFO as a **one-way byte stream** whose power lies in pathname-based rendezvous, not in richer transport semantics.

### Stream-time behavior

So the retention sentence is:

**A FIFO is a pathname-opened pipe: name-based rendezvous first, then ordinary stream semantics afterward.**

**Retain.** FIFO semantics are pipe semantics plus pathname-based discovery.

**Do Not Confuse.** Naming changes rendezvous, not EOF rules, blocking rules, or byte-stream semantics.

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
