# Sockets as Communication Endpoints: Structure, Semantics, and Use

## Why sockets belong here at all

This section exists because sockets are often taught too late and too narrowly. They are presented as “network programming tools,” as if they belonged mainly to application code that happens to talk across machines. That presentation misses the operating-systems object. A socket is not first of all a convenience library call. It is a kernel-managed communication endpoint, and that makes it part of IPC even when the communication never leaves the local machine.

The object is the socket itself. Formally, a **socket** is a kernel-managed endpoint through which a process can send or receive data according to some communication domain and transport semantics. The definition needs each part. It is **kernel-managed**, so the operating system allocates state, tracks buffers, enforces access rules, and mediates blocking and wakeup. It is an **endpoint**, so it names one side of a communication relation rather than the whole relation. It supports a chosen **domain** and **semantics**, so the same high-level object can represent local interprocess communication, network communication, reliable byte streams, or message-oriented datagrams.

The interpretation follows immediately. A socket is the operating system’s answer to a recurring problem: two execution contexts need a kernel-recognized place to exchange bytes under well-defined rules. Pipes solve one version of that problem. Named pipes solve another. Message queues solve another. Sockets solve the version in which the endpoint may need an address, may need to support local or remote communication, may need to represent a stream or datagrams, and may need to interact with routing, buffering, connection setup, or readiness notification. That is why sockets belong in IPC. They are not conceptually outside it. They are one of its most general endpoint abstractions.

The boundary condition that matters most is that a socket is not itself “the network.” A process does not talk directly to Ethernet, TCP, or another process’s address space. It talks to a socket object the kernel understands. The kernel then uses that object’s domain and type to decide how communication is performed. This is why the same broad socket abstraction can cover a Unix domain socket between two local processes and a TCP socket between hosts on different machines.

A hidden constraint also appears here. The kernel must preserve endpoint state even while the process is descheduled. If a socket were just a user-space data structure, the operating system could not reliably buffer incoming data, wake blocked readers, or complete a network handshake asynchronously. Kernel residency is what gives the endpoint durable communication semantics independent of the user process’s current execution slice.

A simple mechanism trace makes the point concrete. When a process creates a socket, the kernel allocates a socket object and associates it with that process through a file descriptor or equivalent handle. When data later arrives for that endpoint, it arrives to kernel-managed buffers associated with the socket, not directly into the process’s memory. Only when the process performs a receive operation does the kernel copy or map the buffered data into user space according to the API and transport rules. The communication object therefore exists as operating-system state first and application-visible interface second.

**Misconception block.** “Sockets are only for network programming.” No. That is scope confusion. Network sockets are one important family, but the kernel abstraction is an IPC endpoint. If two local processes talk through a loopback TCP socket or a Unix domain socket, the abstraction is still IPC. The transport path differs; the operating-systems object does not.

This section supports later material because many higher-level mechanisms—RPC frameworks, web servers, event loops, service meshes, and even some container runtime plumbing—rest on the fact that a socket is a kernel object with endpoint semantics rather than just a convenience function in a language runtime.

**Retain.** A socket is a kernel-managed communication endpoint. That is why it belongs in IPC.

**Do Not Confuse.** A socket is not the same thing as a network, a protocol stack, or a complete connection. It is the endpoint object through which those things are mediated.

## Address, port, endpoint identity, and connection: separating objects that get collapsed in casual speech

This section exists because socket discussions collapse several different objects into one vague phrase such as “the socket address” or “the connection.” That vagueness is survivable in toy examples and fatal in systems reasoning. A socket chapter is not complete until these objects are separated.

The first object is the **socket object**. Formally, this is the kernel-resident endpoint state owned or referenced by a process. It includes the communication domain, type, protocol metadata, buffering state, readiness state, and any associated local or peer addressing information the kernel has established. Interpretation: this is the thing the process actually holds through a descriptor.

The second object is the **IP address**. Formally, an IP address identifies a network interface location within an IP network. Interpretation: it identifies a host interface, not a particular application process. A machine may have several IP addresses, and many different processes may communicate through the same IP address.

The third object is the **port**. Formally, a port is a transport-layer demultiplexing identifier used by the operating system to decide which endpoint should receive incoming transport traffic at a host. Interpretation: ports exist because the machine needs a way to distinguish among multiple communication endpoints using the same IP address. Without ports, the kernel would know that data is for a host but not which application endpoint at that host should receive it.

The fourth object is **endpoint identity**. For Internet sockets, endpoint identity is commonly the pairing of an address and a port together with a communication domain and transport protocol. Interpretation: “192.0.2.10:80 over TCP” identifies a transport endpoint more specifically than the IP address alone. In real kernel matching, the complete identity also depends on protocol family and sometimes interface and namespace context.

The fifth object is the **connection**. Formally, a connection is a communication relation between endpoints established under connection-oriented semantics, typically maintaining state that allows reliable ordered transfer, flow control, and teardown. Interpretation: a connection is not the endpoint itself. It is a stateful relationship between two endpoints.

This distinction matters immediately. A listening TCP server socket bound to a port is not yet a connection. It is a passive endpoint waiting for connection attempts. When a client connects, the operating system typically keeps the listening socket and creates or exposes a different connected socket representing the particular client-server relation. That is why a server can listen on one port and serve many simultaneous clients: one passive endpoint, many connection-specific connected endpoints.

Boundary conditions are important here. A UDP socket may be bound to an IP address and port and may communicate with many peers without ever creating connection state in the TCP sense. Calling such a socket “a connection” is already wrong. Even in TCP, casual speech such as “close the socket” may refer either to closing the endpoint descriptor or to tearing down a connection represented by that endpoint. The wording hides whether one means endpoint object lifetime or transport relationship lifetime.

A worked example clarifies why ports exist. Suppose one machine has IP address `203.0.113.8` and is simultaneously running a web server, an SSH server, and a DNS server. Incoming traffic to the same IP address must still be delivered to different application endpoints. The web server listens on TCP port 80 or 443, SSH on TCP port 22, DNS often on UDP and TCP port 53. The IP address gets the packet to the host. The port helps the kernel deliver it to the correct socket endpoint at that host.

Loopback belongs here as well. The special local address `127.0.0.1` in IPv4 and `::1` in IPv6 directs traffic back to the same machine through the host’s own protocol stack. The communication is local in physical reachability but still uses endpoint identities and ports because the kernel still needs transport-level demultiplexing. Loopback therefore shows that sockets are not “network only” in the everyday sense. The network stack can be used as a local IPC path, and the same endpoint rules still apply.

**Misconception block.** “Socket = connection.” No. A socket is an endpoint object. A TCP connection is a stateful relationship between endpoints. A listening socket is not a connection. A UDP socket may never participate in connection state at all.

This section connects forward to RPC and service design because every distributed interface eventually has to answer endpoint-identity questions: which host, which port, which protocol, which listening endpoint, and which per-client communication relation.

**Retain.** IP address identifies the host interface, port identifies the transport endpoint at that host, the socket is the kernel object, and a connection is a stateful relation between endpoints.

**Do Not Confuse.** Binding a socket to an address and port does not by itself create a connection.

## Stream sockets and datagram sockets: what semantic promise the endpoint is making

This section exists because “using sockets” does not yet say what kind of communication semantics the kernel will enforce. The same broad endpoint abstraction can offer radically different guarantees. Without this distinction, later failures—partial reads, message-boundary confusion, reordering assumptions, or mistaken retry logic—become inevitable.

The object here is the socket type. Formally, a socket type determines the communication semantics associated with an endpoint within a given domain and protocol family. Two canonical families matter first: **connection-oriented stream sockets** and **connectionless datagram sockets**.

A **stream socket** provides an ordered byte stream between connected endpoints, classically with TCP-style semantics. Formally, the abstraction presents data as a sequence of bytes with no inherent application-level message boundaries. Interpretation: if one side writes 10 bytes and then 20 bytes, the other side receives 30 bytes of ordered stream data, but the division into 10 and 20 is not preserved by the stream abstraction. Reliability, ordering, retransmission, and flow control are usually part of the contract in TCP-style streams.

A **datagram socket** provides message-oriented communication, classically with UDP-style semantics. Formally, each send operation creates a datagram unit whose boundaries are preserved as a message delivery unit, though not necessarily with reliability, ordering, or uniqueness guarantees. Interpretation: a datagram is closer to “one packet-sized message unit” than to “part of a continuous file-like byte stream.” The receiver gets discrete messages, not arbitrary slices of one infinite stream.

The boundary conditions must be stated exactly. Stream sockets do not preserve message boundaries. Datagram sockets do preserve send-unit boundaries, but they do not promise reliable delivery, in-order arrival, or automatic retransmission in the usual UDP case. TCP-style streams require connection setup before data transfer. UDP-style datagrams usually do not. A stream write may be split across multiple transmissions and read back in multiple chunks. A datagram larger than the receiver’s buffer may be truncated or rejected according to platform rules.

A mechanism trace shows why the difference exists. For a stream socket, the kernel tracks connection state, sequence ordering, send and receive buffers, acknowledgments, and flow-control windows. The receiver sees data as bytes accumulated in receive buffers and consumes however many bytes its read call requests or the kernel can provide. For a datagram socket, the kernel treats each outbound send as a separate datagram object for transport. The receive side dequeues one message unit at a time. The kernel therefore preserves datagram boundaries because the endpoint semantics require it, not because the application guessed correctly.

A local example helps. Suppose a log collector on one machine receives records over UDP. Each `sendto` from a producer corresponds to one log-record datagram. The collector’s `recvfrom` calls therefore return one record per receive if buffer sizes are adequate. By contrast, if the same producers send log records over TCP, the collector receives a byte stream. Two short records may arrive together in one read; one long record may require several reads. The application must delimit records explicitly.

**Misconception block.** “TCP preserves message boundaries.” No. TCP preserves byte order, not application message framing. If the sender performs three writes, the receiver may observe one read, two reads, or many reads covering those bytes in any grouping consistent with ordered-stream semantics.

This section connects to later material because the distinction between stream and datagram semantics controls everything above it: protocol framing, retry logic, timeout policy, RPC transport behavior, and event-driven read loops.

**Retain.** Stream sockets give ordered bytes, not messages. Datagram sockets give messages, not reliable ordered streams.

**Do Not Confuse.** Reliable delivery and message-boundary preservation are separate properties. TCP gives the first and not the second. UDP-style datagrams give the second and not the first.

## The full client/server trace: what the kernel changes at each step

This section exists because socket APIs are often memorized as a call sequence with no state model attached. That is not mastery. The real lesson is the kernel-state transition each call causes and the next operation it makes legal.

The object is the client/server endpoint lifecycle for a connection-oriented stream service. Formally, the server begins with a passive socket capable of accepting connection requests; the client begins with an unconnected active socket capable of initiating a connection. Interpretation: passive and active endpoints are different roles even when both are socket objects.

We trace a typical TCP-style interaction.

### Step 1: server socket creation

The server calls `socket(...)`. The kernel allocates a socket object with the requested domain and stream semantics and returns a descriptor referencing it. At this point the socket has type and protocol identity but no local endpoint identity yet unless defaults are later assigned. It is not listening and not connected.

What changes in kernel state: a new endpoint object exists, associated with the server process’s descriptor table. Buffers, protocol control structures, and internal state flags are initialized.

What this allows next: the server may configure the socket and, for a service endpoint, bind it to a local address and port.

### Step 2: server bind

The server calls `bind(...)`. The kernel associates the socket with a chosen local address and port, if allowed and available.

What changes in kernel state: the socket gains a local endpoint identity. The kernel reserves that transport-layer binding so incoming traffic for that address/port/protocol can be demultiplexed to this endpoint.

What this allows next: the socket can now become a known service endpoint. For a stream server, it may enter listening state.

Boundary condition: `bind` can fail if the port is already in use, access rules forbid the requested port, the address is invalid in the current namespace, or reuse policy is not satisfied.

### Step 3: server listen

The server calls `listen(...)`. The kernel marks the bound stream socket as a passive listening endpoint.

What changes in kernel state: the socket moves from merely bound to listening. The kernel allocates or activates data structures for pending connection requests and completed-but-not-yet-accepted connections, subject to backlog limits.

What this allows next: clients may attempt to connect, and the server may accept completed connection instances.

Important boundary condition: the listening socket itself remains a passive endpoint. It does not turn into a data-carrying per-client stream.

### Step 4: client socket creation

The client calls `socket(...)`. The kernel allocates an active endpoint object for the client process.

What changes in kernel state: a new client-side socket object exists, initially unconnected.

What this allows next: the client may initiate a connection using a remote endpoint identity.

### Step 5: client connect

The client calls `connect(server_addr, server_port)`. The kernel begins connection establishment toward the server’s listening endpoint.

What changes in kernel state: on the client side, the kernel records the intended peer endpoint and starts transport-level connection setup. On the server side, when the request arrives, the kernel associates it with the listening socket and places it into pending connection state. When the handshake completes, the server kernel has a connection instance ready to be accepted.

What this allows next: after successful completion, the client socket becomes a connected stream endpoint eligible for send and receive. The server may now obtain a per-connection socket through `accept`.

Failure mode: if no listening endpoint exists at the destination or the server actively rejects the attempt, `connect` fails with a refused-connection error. The kernel therefore never transitions the client socket into connected state.

### Step 6: server accept

The server calls `accept(...)`. The kernel removes one completed connection from the listening socket’s completed-connection queue and returns a **new** connected socket descriptor representing that client-server stream.

What changes in kernel state: the original listening socket remains listening. A second server-side socket object now exists, bound to the same local service endpoint but associated with a specific peer endpoint and a specific transport connection.

What this allows next: the new connected server socket can read and write stream data for that one client. The listening socket can continue accepting others.

This is the place where students finally see why “socket = connection” is wrong. One listening socket can produce many accepted connected sockets.

### Step 7: send/write

Either side calls `send` or `write` on its connected socket. The kernel copies some or all of the user buffer into the socket’s send buffer, subject to buffer capacity and blocking mode, and the transport layer transmits according to protocol rules.

What changes in kernel state: bytes enter kernel send buffers; sequence state, congestion state, and accounting metadata may advance. The peer is not guaranteed to have consumed the data yet merely because the local write returned.

What this allows next: the peer may later receive those bytes; the sender may write more, block, or get a partial write depending on mode and buffer availability.

Failure mode: a write may complete only partially. The application must track how many bytes the kernel accepted and retry for the remainder if protocol logic requires it.

### Step 8: recv/read

Either side calls `recv` or `read`. The kernel checks the socket’s receive buffer. If data is present, it returns some positive number of bytes up to the requested amount. If no data is present and the socket is blocking, the process sleeps until data, close, or error occurs.

What changes in kernel state: bytes are removed from the receive buffer and copied into user space; readiness state changes; blocked readers may wake.

What this allows next: the application can interpret the bytes it received, but only according to its own higher-level framing rules.

Failure modes: the call may block; it may return fewer bytes than requested; it may return zero to indicate peer close after buffered data is exhausted; it may return an error if the connection has failed.

### Step 9: close

A side calls `close`. The kernel decrements descriptor references to the socket. If this is the final reference, the kernel initiates transport shutdown according to protocol rules.

What changes in kernel state: local descriptor ownership ends; transport teardown begins or advances; peer-visible EOF may eventually be generated once all sent data and protocol teardown steps are handled.

What this allows next: the peer can observe closure through a zero-length read after remaining buffered data has been consumed.

A concise state picture helps:

```text
Server process: socket -> bind -> listen -> accept => connected socket for client A
                                         \-> accept => connected socket for client B

Client process: socket -> connect => connected socket to server
```

**Misconception block.** “The server reads and writes on the listening socket after `accept`.” No. The listening socket remains a passive queueing endpoint. Data transfer occurs on the newly accepted connected socket.

This full trace connects directly to event-driven I/O, concurrency control, and RPC servers. Readiness sets, edge-triggered notifications, thread-per-connection designs, and async runtimes all sit on top of these endpoint state transitions.

**Retain.** Each socket call matters because it changes kernel endpoint state and thereby changes what operations are legal next.

**Do Not Confuse.** Creating a socket is not binding it, binding is not listening, listening is not accepting, and accepting is not reading. Each step creates a different capability.

## Worked request/reply example: why bytes still need framing

This section exists because once stream sockets are understood as ordered byte streams, the next question becomes unavoidable: how does an application know where one request ends and the next begins? Without that answer, correct request/reply protocols cannot be built.

The object is an application-level request/reply exchange over a stream socket. Formally, the transport provides byte delivery; the application protocol must define message boundaries, parsing rules, and response correlation. Interpretation: the kernel moves bytes, not semantic units such as “request object,” “line,” or “JSON document,” unless the application protocol creates those units.

Consider a simple service: a client asks for the uppercase version of a word, and the server replies with the transformed word. Suppose the protocol says each message is encoded as a 4-byte length field followed by exactly that many payload bytes. The client sends the bytes for length `5` followed by `hello`. The server reads exactly 4 bytes to obtain the length, then keeps reading until it has accumulated exactly 5 payload bytes. It computes `HELLO`, then sends a reply using the same format: 4-byte length `5` followed by `HELLO`.

Why is this extra structure necessary? Because the stream abstraction does not preserve the sender’s write boundaries. The client might perform two writes—one for the length and one for the payload—or one combined write. The server may still receive those bytes in many possible chunks: 4 then 5, 2 then 2 then 5, 9 all at once, or another grouping consistent with ordered delivery. The server therefore cannot say “one read equals one request.” It must maintain protocol parsing state across reads.

A full mechanism trace makes the hidden state explicit. The client writes 9 bytes total. The kernel may accept all 9 into the client send buffer. The network and peer kernel may deliver 3 bytes first. The server’s first read returns 3 bytes, which is not yet even the full header. The server buffers them in application memory and reads again. The next read returns 6 bytes. Now the application has 9 total, enough to parse the 4-byte header and the 5-byte payload. The request has become complete only because the application’s framing rule said how many bytes to wait for.

Failure modes are embedded in this example. A partial read means the application must continue accumulating. A partial write means the sender must continue sending until the full framed message has been handed to the kernel. Blocking means either side may sleep waiting for more buffer space or more incoming data. Peer close in the middle of a frame means the application has an incomplete message and must treat the protocol exchange as failed.

The same logic explains line-based protocols, delimiter-based protocols, and self-describing formats. A newline-delimited text protocol uses a delimiter as the frame boundary. HTTP historically uses a mixture of delimiters and length metadata depending on version and transfer mode. Binary protocols often use explicit length prefixes. The transport does not supply the boundary. The application must.

**Misconception block.** “If I send one request with one `write`, the peer will receive it with one `read`.” No. That assumption accidentally treats a stream like a message queue. Streams preserve byte order, not call boundaries.

This section connects directly to RPC systems and event-driven I/O. An RPC runtime is, among other things, a disciplined framing and serialization layer above sockets. An event loop must keep per-connection parse state precisely because request boundaries may span many readiness notifications.

**Retain.** On a stream socket, application messages exist only if the application defines framing.

**Do Not Confuse.** Transport reliability does not remove the need for application-level message boundaries.

## Failure modes and semantic edge cases: where socket reasoning usually breaks

This section exists because sockets are often learned from successful demonstrations. Real systems fail at the boundary conditions, and the relevant failures are semantic, not merely syntactic. A chapter that does not expose them leaves the reader with the wrong mental model.

The first object is **refused connection**. Formally, a connection attempt is refused when the destination host responds in a way indicating that no endpoint is accepting the requested connection at that endpoint identity, or policy forbids it. Interpretation: the network path may be perfectly fine; what failed is that no suitable passive endpoint completed the connection setup. This usually means no process is listening on that port, or the path actively rejected the attempt.

The second object is **partial write and partial read**. Formally, stream I/O operations may transfer fewer bytes than the caller requested without implying transport failure. Interpretation: a successful call returning fewer bytes than requested is still success. The application must track remaining bytes and continue until the logical protocol unit is complete.

The third object is **blocking behavior**. Formally, an operation blocks when the calling process cannot complete the requested action immediately and the kernel suspends the process pending a state change such as buffer availability, incoming data, connection completion, or peer closure. Interpretation: blocking is not an error. It is the operating system’s scheduling response to resource unavailability at the endpoint.

The fourth object is **peer close**. Formally, peer close means the remote endpoint has shut down its sending side or fully closed the connection, after which the local endpoint eventually observes end-of-stream semantics. Interpretation: a read returning zero on a stream socket means not “temporary absence of data” but “no more bytes will arrive from that peer on this stream,” assuming buffered data is already exhausted.

Boundary conditions matter sharply. A blocking `connect` may sleep until the handshake succeeds or fails; a nonblocking `connect` may return immediately with completion deferred. A `read` returning zero is different from a `read` that blocks and different from a `read` that returns an error. A short write does not mean the peer has seen any application-level message yet. A refused connection is different from a timeout, where no usable answer arrived in time.

A compact example shows how these cases combine. A client connects successfully, writes the first 12 bytes of a 40-byte framed request because the send buffer is tight, then blocks or returns short. The application must resume and send the remaining 28 bytes. Meanwhile, the server reads only 8 bytes, which is enough to know that the request header is incomplete. It keeps buffering. If the client crashes and closes before sending the rest, the server may later observe EOF while holding a partial frame. That is not a valid request. It is a protocol failure caused by peer close mid-message.

**Misconception block.** “A successful socket call moved the whole logical request.” No. Socket calls report endpoint-level transfer progress, not completion of your protocol’s semantic unit.

This section connects to event-driven I/O because readiness APIs are largely about managing these edge conditions without one blocked descriptor stalling the whole process. It also connects to RPC because reliable request semantics must be built above transport behavior, not assumed from it.

**Retain.** Refusal, partial transfer, blocking, and peer close are normal endpoint behaviors the application must handle explicitly.

**Do Not Confuse.** Temporary inability to progress is not the same as error, and transport completion is not the same as application-level message completion.

## Local sockets, loopback, and the place of sockets among IPC mechanisms

This section exists because the topic is easy to misfile. Once sockets are associated with IP addresses and ports, it becomes tempting to think that local communication through sockets is somehow outside IPC proper and belongs to a separate “networking” category. That is the wrong conceptual map.

The object is the place of sockets within the larger IPC family. Formally, sockets are one endpoint abstraction among several IPC mechanisms, distinguished by their support for addressing, transport semantics, local or remote reachability, and kernel-mediated buffering and readiness behavior. Interpretation: they overlap with pipes and named pipes in purpose but differ in generality and addressing model.

Loopback shows one form of locality. A loopback socket uses the network stack but routes traffic back into the same host. The communication is local in physical scope, but it still uses host/port endpoint identity, transport semantics, and network-stack buffering. Unix domain sockets show another form of locality: they are sockets in a local communication domain that usually use filesystem pathnames or abstract names instead of IP addresses and ports. Both are IPC. The difference is not whether they are IPC, but which communication domain and endpoint naming scheme they use.

Comparing with pipes clarifies the design space. A pipe is typically created as a related pair of endpoints with a fixed unidirectional byte-stream relation and no global address. A named pipe adds a name in the filesystem namespace but still remains more specialized than sockets. A socket is more general: it can be bound, connected, listened on, used locally or remotely depending on domain, and integrated with richer endpoint identity and multiplexing rules.

A boundary condition is worth stating precisely. Not every IPC problem should use sockets. Pipes are often simpler for parent-child byte streams. Shared memory is more efficient for high-volume local data exchange when synchronization is handled separately. Message queues may better preserve message units. Sockets become attractive when endpoint naming, client/server structure, transport choice, locality flexibility, or event-loop integration matter.

**Misconception block.** “Local sockets are conceptually outside IPC.” No. They are IPC exactly because they mediate communication between processes through kernel-managed endpoints. The fact that the communication may stay on one machine does not make it something other than IPC.

This section connects directly to later material on pipes, named pipes, and event-driven I/O because those topics are easiest to compare once sockets are seen as one member of a family of kernel communication endpoints.

**Retain.** Sockets are IPC mechanisms whether used locally or remotely. Loopback and Unix domain sockets are still IPC.

**Do Not Confuse.** “Uses the network stack” and “is inter-machine” are different claims. Loopback satisfies the first and not necessarily the second.

## How this chapter supports later systems material

This closing section exists because sockets are rarely the final abstraction a systems programmer works with. They are the endpoint substrate on which richer systems are built.

The object is the set of later mechanisms that inherit socket semantics. Formally, higher-level communication systems such as RPC frameworks, application protocols, readiness multiplexers, and service supervisors build on top of endpoint objects whose blocking, buffering, framing, and failure semantics come from the socket layer. Interpretation: when a higher-level system misbehaves, the explanation often lies in socket semantics that were forgotten rather than in the high-level API itself.

RPC depends on sockets because a remote procedure call is, beneath its serialization and interface machinery, a disciplined request/reply exchange over communication endpoints. Pipes and named pipes remain the right comparison points because they solve narrower IPC problems with different naming and connectivity assumptions. Event-driven I/O matters because once many sockets exist at once, a process cannot block blindly on each one in sequence; it needs kernel support for readiness notification and structured state machines for partial progress.

A final mechanism trace ties the lesson together. A production RPC server typically opens a listening socket, accepts many connected sockets, marks them nonblocking, places them under an event loop, incrementally parses framed requests from each stream, dispatches handlers, queues partial writes of responses, observes EOF when clients close, and releases endpoint state when teardown completes. Every stage in that trace rests directly on this chapter’s distinctions: socket object versus connection, stream versus message semantics, endpoint identity versus peer relation, and protocol framing above raw bytes.

The hidden constraint is now visible. High-level communication abstractions do not erase endpoint semantics; they organize them. Mastery therefore means being able to reason downward from RPC, HTTP, or an async runtime to the kernel-managed endpoint state those systems ultimately rely on.

**Retain.** Sockets are the general IPC endpoint abstraction that underlies much of modern local and distributed systems work.

**Do Not Confuse.** Higher-level communication frameworks simplify socket use, but they do not change the underlying endpoint semantics on which correctness depends.
