# Remote Procedure Call (RPC): Procedure-Call Illusion Built Over Message Passing

RPC should be introduced as a **layered contrast**, not as a slogan. The real question is: when one computation boundary is no longer local, how do we make request/reply communication usable without pretending that communication has vanished?

The canonical contrast is this:

- **Local procedure call**: control transfer within one tightly coupled execution environment.
- **Message passing**: explicit send/receive communication between parties.
- **Client/server request-reply**: messages organized as service request and response.
- **RPC**: request-reply communication presented in the interface form of a procedure call.

That is the concept-level introduction. RPC is not a separate physical mechanism. It is a disciplined presentation of communication in call form.

So the canonical statement of the chapter is:

**RPC is a call-shaped abstraction built over request/reply communication, which itself is built over message passing.**

That sentence matters because it prevents the main mistake. RPC is useful precisely because application programmers do not want to assemble raw messages by hand every time. But the abstraction is dangerous if the reader forgets that the middle of the apparent call is still communication: argument packaging, transport over some communication path, server-side execution, reply delivery, timeout, retry, and partial failure.

A clean formal definition follows naturally. A remote procedure call is an abstraction in which a caller invokes a procedure-like operation, the runtime marshals arguments, sends a request to a server, causes the corresponding server-side procedure to run, receives a reply, unmarshals the result, and presents the outcome back to the caller in procedure-call form.

The retention point should already be visible here: **RPC does not eliminate communication. It organizes communication behind a procedure-call interface.**

A short review sentence helps keep the mechanism grounded. **Marshalling** means packaging arguments into a transmissible representation. **Unmarshalling** means rebuilding usable argument values from that transmitted representation. **Binding** means deciding which remote service instance the request should be sent to. **Transport** means the underlying communication mechanism that actually carries the request and reply, such as a socket-based channel.

**Retain.** RPC is procedure-call-shaped request/reply communication layered over message passing.

**Do Not Confuse.** A clean call interface does not make remote invocation semantically equivalent to an ordinary local call.

## RPC has a runtime structure: client, server, stubs, marshalling, unmarshalling, and binding

### Why this section exists

Once RPC is understood as an abstraction, the next question is where the abstraction is physically maintained. The caller does not magically talk to the remote procedure. A concrete runtime structure must preserve the interface illusion while still doing the underlying work of packaging arguments, choosing a destination, sending a request, receiving a reply, and rebuilding the result. This section exists because RPC cannot be understood or debugged without understanding the components that maintain the illusion.

### The object being introduced

The object is the **RPC execution path** as a set of cooperating roles: the caller-side participant, the server-side participant, the generated or handwritten adaptation code on both ends, and the data-conversion and service-location machinery that make remote invocation possible.

### Formal definition

In a conventional RPC system:

The **client** is the process or component that invokes a remote operation.

The **server** is the process or component that exports and executes the operation.

A **client stub** or **proxy** is caller-side code that presents the remote operation as a local-looking procedure entry point, collects the arguments, marshals them into a transmissible form, initiates the request, waits for a reply, unmarshals the result, and returns it to the caller or raises an error.

A **server stub** is server-side adaptation code that receives the request message, unmarshals the transmitted arguments, invokes the actual server procedure using the local calling convention, captures the result or error, marshals it, and sends the reply.

**Marshalling** is the transformation of in-memory arguments or return values into a canonical serialized representation suitable for transmission.

**Unmarshalling** is the inverse transformation from serialized representation back into an in-memory representation usable by the receiver.

**Binding** is the process by which a client identifies, locates, and connects to the server or service instance that should handle the call.

### Interpretation

These components divide responsibility cleanly. The client should write code against an interface, not directly against socket reads and writes. The client stub holds the call illusion together on the caller side. The server should implement service logic, not packet parsing. The server stub holds the illusion together on the server side. Marshalling and unmarshalling are what make arguments cross a representation boundary. Binding is what makes a symbolic service reference become an actual communication target.

The stubs are especially important conceptually. They are not cosmetic helper code. They are the exact place where the abstraction changes level. Above the client stub, the program thinks in terms of operations and parameters. Below the client stub, the runtime thinks in terms of request messages, connection state, and reply matching. Above the server stub, the server procedure thinks it received ordinary local arguments. Below the server stub, the system is still doing message reception and decoding.

Marshalling is equally central. A local procedure can receive pointers, stack values, registers, or references to structures already present in the same address space. A remote procedure cannot receive a raw pointer into the client’s memory and interpret it as a valid local address. It needs a representation that survives transmission and can be reconstructed independently. Marshalling is therefore not optional glue. It is the mechanism that turns local in-memory state into communicable data.

Binding closes the loop operationally. An interface definition is useless unless the client can resolve “which server instance should handle this call?” Static binding hard-codes the location. Dynamic binding may consult a name service, service registry, endpoint mapper, directory, or load balancer. This matters because in distributed systems, operation identity and server location are not the same thing.

### Boundary conditions, assumptions, and failure modes

A stub can only marshal what the interface definition makes serializable. Data that depends on local process state, local file descriptors, raw memory addresses, thread identities, or language-specific object references may not cross the boundary meaningfully without explicit translation rules. If the interface allows types whose meaning is not portable, marshalling becomes ambiguous or impossible.

Version mismatch is another failure mode. If the client stub and server stub disagree about operation names, field layout, optional parameters, or error representation, unmarshalling may fail or, worse, succeed incorrectly. That kind of failure is especially dangerous because it can preserve the call illusion while breaking the meaning.

Binding also introduces hidden constraints. If service discovery is stale, the client may bind to the wrong instance or to a dead one. If a load balancer redirects requests across replicas, retries may land on different servers. If the call has non-idempotent behavior, such rebinding can change semantics.

### Worked example or mechanism trace

Consider `lookupUser(17)`. The client does not directly talk to a socket. It calls a client proxy method. The proxy converts the integer `17` into a transportable request structure such as `{service: UserDirectory, operation: lookupUser, request-id: 9021, args: {id: 17}}`. Binding logic determines that `UserDirectory` currently resolves to `10.0.0.24:8443`. The request is sent there. On the server side, the server stub parses the request, reconstructs the integer argument, and calls the real local server procedure that knows how to query the user directory database. The procedure returns a user record. The stub serializes that record and sends it back. The client proxy deserializes the record into the client program’s local representation and returns it as the result of `lookupUser(17)`.

### Misconception block

**Misconception: “Serialization is a small implementation detail.”**

Serialization is not a peripheral concern. It determines what data can cross the boundary, what language interoperability is possible, how versioning works, what backward compatibility means, how much latency the call incurs, and whether failures will be detectable or silent. A bad serialization design can make an RPC system slow, brittle, ambiguous, or impossible to evolve.

### Connection to later material

These components connect directly to sockets, middleware, interface-definition languages, API gateways, service discovery systems, and load balancing. They also prepare later distributed-systems topics such as schema evolution, compatibility guarantees, and end-to-end observability, because those topics all act on the same runtime path.

### Retain / Do Not Confuse

**Retain.** RPC works because stubs, marshalling, unmarshalling, and binding maintain the procedure-call abstraction over real communication.

**Do Not Confuse.** The server procedure is not itself receiving a local call from the client process. It is receiving a local call from the server stub after remote communication has already occurred.

## The mechanism trace of an RPC call: the illusion at the surface, the messages underneath

### Why this section exists

An abstraction is only fully understood when its step-by-step mechanism is visible. RPC is especially prone to vague explanations because the interface hides the communication path. This section exists to make the hidden path explicit. At each step, it distinguishes the programmer-visible illusion from the actual underlying mechanism.

### The object being introduced

The object is a **complete end-to-end RPC invocation path** from call site to result delivery.

### Formal definition

A single RPC invocation consists of a caller-side invocation event, caller-side argument marshalling, request transmission, server-side reception, server-side argument unmarshalling, local execution of the target procedure, result marshalling, reply transmission, caller-side reply reception, caller-side unmarshalling, and final return or exception delivery to the original caller.

### Interpretation

The sequence matters because every point in it is a distinct semantic boundary. Local call syntax appears at the beginning and end only. The middle is distributed communication. The call illusion therefore covers a much larger causal chain than a local call does.

### Boundary conditions, assumptions, and failure modes

For the trace below to complete successfully, the client must be bound to a reachable server, the message must be transmittable, both sides must agree on representation, the server must remain alive long enough to execute the procedure, the reply must be deliverable, and the client must still be waiting in a compatible state when the reply arrives. Break any of those assumptions and the invocation may time out, fail, or become ambiguous.

### Full mechanism trace

Use the operation `lookupUser(17)`.

**Step 1: caller invokes a local-looking function.**

The client program writes something like `u = lookupUser(17)` against an interface reference.

The **illusion** is that control is entering an ordinary local procedure.

The **actual mechanism** is that control enters the client stub or proxy, which is ordinary local code whose job is to begin a remote interaction.

**Step 2: client stub marshals arguments.**

The client stub inspects the arguments, packages the operation name or identifier, includes metadata such as request identifiers, authentication information, deadlines, or protocol version fields, and serializes the argument `17` into a portable representation.

The **illusion** is that the argument has simply been passed to a callee.

The **actual mechanism** is that the argument is being converted from local in-memory representation into a message payload suitable for transmission.

**Step 3: request message is sent.**

The stub hands the request to the transport/runtime layer. Bytes are placed on a connection or datagram path and routed toward the server.

The **illusion** is that the callee is now running.

The **actual mechanism** is only that a message has been emitted. The server may not yet have received it. No execution on the server is guaranteed at this point.

**Step 4: server stub receives and unmarshals.**

The server-side runtime accepts the request, identifies the target service and operation, validates framing and metadata, and converts the serialized argument back into the server’s local representation.

The **illusion** is that the remote procedure has received the original argument directly.

The **actual mechanism** is that a separate process has decoded a message and reconstructed a fresh local value corresponding to the transmitted data.

**Step 5: server procedure executes.**

The server stub invokes the actual local server procedure `lookupUser(17)` inside the server process. The procedure may read memory, consult a database, lock shared structures, or perform other local work.

The **illusion** is that the caller’s original call is now simply continuing remotely.

The **actual mechanism** is that a new local computation is running inside the server’s own failure domain, with its own scheduler, memory, and side effects.

**Step 6: result is marshalled.**

Suppose the server procedure returns a record such as `{id: 17, name: "Amina", tier: "admin"}`. The server stub serializes this record into the reply format.

The **illusion** is that the callee is preparing a normal return value.

The **actual mechanism** is that another message payload is being constructed, subject again to representation rules and protocol semantics.

**Step 7: reply is returned across the network.**

The reply is transmitted back to the client.

The **illusion** is that the return path of a normal call is in progress.

The **actual mechanism** is that a second communication event must succeed independently of the first. The request may have reached the server even if the reply does not reach the client.

**Step 8: caller receives result.**

The client-side runtime receives the reply, matches it against the outstanding request identifier, unmarshals the payload, and returns the reconstructed result to the client code.

The **illusion** is that the remote procedure has simply returned a value.

The **actual mechanism** is that the client proxy has interpreted a reply message and converted it into a local language-level result.

This trace exposes a critical truth: the only truly local steps are entering the client stub and leaving it with a result. Everything in the middle is distributed interaction.

### Misconception block

**Misconception: “If the call returns, the server definitely executed exactly once.”**

A returned result does not by itself prove exact-once execution semantics. The server might have executed once and replied once. It might have executed more than once under retry conditions but produced the same result. It might have executed once, but the reply observed by the client could be the result of duplicate requests filtered or coalesced by the runtime. Exact-once is not obtained merely from call syntax; it requires specific protocol guarantees and, in many real systems, remains only partially approximated.

### Connection to later material

This mechanism trace directly supports later study of RPC middleware, transport protocols, timeout handling, correlation identifiers, tracing systems, and distributed debugging. Once the path is visible, later machinery stops looking arbitrary.

### Retain / Do Not Confuse

**Retain.** An RPC call is a long causal chain hidden behind a short call expression.

**Do Not Confuse.** A server receiving a request is not the same event as the caller receiving a reply. Those events can be separated by delay, crash, or loss.

## RPC and local calls are fundamentally different because failure, time, and representation are different

### Why this section exists

The most damaging RPC mistakes happen when programmers carry local-call assumptions across a network boundary. This section exists to make the semantic break explicit. The abstraction is useful only if its limits are understood.

### The object being introduced

The object is the **semantic gap between local invocation and remote invocation**.

### Formal definition

A **local procedure call** is an invocation whose argument passing, execution, and return occur within one tightly coupled execution environment. An **RPC invocation** is an invocation-shaped interaction across separate processes or machines where communication latency, transmission failure, endpoint failure, retransmission policy, independent state changes, and representation conversion are part of the operation’s semantics.

### Interpretation

The surface syntax of the call may be similar, but the semantic contract is different in every place where distribution matters.

**Latency** is the first difference. A local call usually costs instruction execution, memory access, and perhaps a context switch. RPC may involve serialization cost, queueing, kernel crossing, network transmission, remote scheduling, storage access, and reply transmission. The timescale changes by orders of magnitude.

**Timeout** follows from latency. A local call usually blocks until the callee returns or the process fails. RPC needs explicit waiting policy because the caller cannot distinguish “slow” from “dead” without a time budget. Timeouts are therefore part of interface meaning, not an optional convenience.

**Partial failure** is the decisive difference. In a local call, if the process dies, both caller and callee die together because they are inside one local execution environment. In RPC, the client may fail while the server survives, or the server may fail while the client continues, or the network path between them may fail while both endpoints remain alive. This creates states with no local-call analogue.

**Retries** appear because communication may fail transiently. If the caller times out, it may resend the request. But a retry is not semantically neutral. If the original request actually reached the server and the retry reaches it again, the operation may execute twice.

That creates **duplicate execution risk**. For idempotent operations such as pure lookup, executing twice may be harmless. For non-idempotent operations such as “charge credit card,” “increment balance,” or “append record,” duplicate execution can corrupt semantics unless the protocol includes deduplication tokens, operation IDs, transactional controls, or other safeguards.

**Data representation** is the last unavoidable difference. Local calls can pass data according to one process-local representation convention. RPC must encode data so that two independent contexts can interpret it consistently. Endianness, alignment, string encoding, schema evolution, nullable fields, unknown fields, and language interoperability all become semantic concerns.

### Boundary conditions, assumptions, and failure modes

A timeout does not mean the server did not execute. It means only that the client did not receive a satisfactory reply before the deadline. The request might still be in flight, already executing, already committed, or already finished with a lost reply.

A retry does not mean the original failed. It means only that the client has insufficient evidence of success. The original may have succeeded and the retry may now produce duplicate effects.

A successful return does not necessarily mean the call is safe to repeat. Safety under repetition depends on the operation’s semantics, not on the fact that the interface looks like a function.

Even “simple” values are not trivial. A timestamp, decimal, map, optional field, or floating-point number may have cross-language and cross-platform interpretation hazards. Representation is therefore a correctness issue.

### Worked example or mechanism trace

Take `withdraw(account=51, amount=10)`. The client sends the request. The server receives it, debits the account, and begins constructing the reply. Before the reply reaches the client, the network drops the response. The client times out. What is now true?

The client does not know whether the server executed. The server may have debited the account exactly once. If the client blindly retries, the server may debit the account a second time. The call syntax `withdraw(51, 10)` looks like an ordinary function call that either returned or did not. The actual distributed semantics are weaker: after timeout, the client is in an uncertain state about the operation outcome.

This example is why RPC design cares so much about idempotence, unique request IDs, deduplication windows, transactional messaging, and explicit status queries. Those mechanisms are not patches on top of RPC. They are what make RPC usable in the presence of uncertainty.

### Misconception block

**Misconception: “RPC failure is basically exception handling with a longer delay.”**

No. Exception handling inside a local process usually preserves a common view of execution state. RPC failure often destroys shared knowledge about what happened. After a timeout, the client and server may no longer agree about whether the operation ran, whether it completed, or whether its effects are visible. That epistemic gap is the defining difficulty of distributed invocation.

### Connection to later material

This section connects directly to distributed systems, fault tolerance, idempotence, consensus on operation outcome, service-level objectives, and API design under uncertainty. It also clarifies why transport choice, retry policy, and deadline propagation are architectural questions rather than tuning details.

### Retain / Do Not Confuse

**Retain.** RPC resembles a call at the interface but differs fundamentally from a local call because time, failure, retries, duplicates, and representation are part of the operation.

**Do Not Confuse.** Timeout is not proof of non-execution, and return is not proof of exact-once execution.

## Worked example: `lookupUser(id)` as a disciplined RPC operation

### Why this section exists

A worked example is necessary because RPC is easiest to misunderstand when described only abstractly. The example below shows how a clean remote lookup operation can be designed so that the abstraction is useful without denying the distributed reality underneath.

### The object being introduced

The object is a **read-oriented RPC service operation** with a request type, reply type, binding decision, and failure interpretation.

### Formal definition

Assume a service `UserDirectory` exporting operation `lookupUser(id) -> UserRecord | NotFound | ServiceError`. The client invokes the operation through a proxy. The request contains at least the service identity, operation identity, request ID, protocol version, and serialized argument `id`. The reply contains the request ID, status, and either a serialized `UserRecord` or an error description.

### Interpretation

This is a good first RPC example because the operation is logically simple, has one explicit argument, and is naturally read-mostly. That lets the example focus on communication structure rather than business complexity. It also shows a useful design principle: lookup operations are often safer under retry than state-changing updates because they are closer to idempotent reads.

Suppose the client writes:

```text
user = directory.lookupUser(17)
```

At the interface boundary, this is intentionally call-shaped. Underneath, the client proxy constructs a request such as:

```text
{
  service: "UserDirectory",
  operation: "lookupUser",
  request_id: 9021,
  version: 3,
  args: { id: 17 }
}
```

Binding resolves `UserDirectory` through a registry or configured endpoint to a concrete server instance. The request is transmitted. The server stub decodes it and invokes the local server procedure. Suppose the database returns the row for user 17. The server stub builds a reply such as:

```text
{
  request_id: 9021,
  status: "ok",
  result: { id: 17, name: "Amina", tier: "admin" }
}
```

The client proxy verifies that the reply matches request 9021, unmarshals the result, and returns a local `UserRecord` object to the caller.

Notice what made this example disciplined rather than magical. The operation has explicit schema, explicit status encoding, explicit correlation identity, and an interface chosen with retry and representation in mind.

### Boundary conditions, assumptions, and failure modes

If the server cannot be located, the operation fails before any remote execution begins. If the request times out, the client knows only that no acceptable reply arrived in time. If the server replies with `NotFound`, that is a valid application-level outcome, not a transport failure. If the client and server disagree on schema version, the record may fail to decode. If the service is replicated and the client retries, different replicas may answer, so the API contract must define whether slight staleness is permitted.

Even for a lookup, semantics require care. If user records contain optional or newly added fields, the serialization format must define how unknown fields are handled. If access control is enforced remotely, the client cannot infer that “same input implies same output” independent of caller identity or time.

### Worked example or mechanism trace

A complete run looks like this.

The client program asks for user 17. The proxy serializes the request and sends it. The request reaches the server. The server stub reconstructs `id = 17` and invokes the local lookup procedure. The procedure queries storage and obtains the record. The stub serializes the record and returns it. The client proxy reconstructs a local record object and gives it to the program.

Now consider the same example under timeout. The client sends the request, the server executes successfully, but the reply is delayed beyond the client deadline. The client reports timeout. If the client retries, the second request may also succeed. Because this is a lookup, duplicate execution is ordinarily harmless. The API has therefore been chosen in a way that is naturally robust under retry, which is exactly the kind of design RPC encourages when used well.

### Misconception block

**Misconception: “A clean API shape means the distributed part has been solved.”**

A clean procedure signature is only the visible top layer. Correctness still depends on service discovery, serialization compatibility, deadline handling, retry rules, authentication, and server-side execution semantics. Good RPC design makes these issues manageable; it does not erase them.

### Connection to later material

This example connects immediately to sockets because the request and reply must eventually be transported somehow. It connects to service boundaries because the operation exposes a service contract instead of raw transport details. It connects to distributed systems because timeout and retry semantics are already present even in simple lookups. It connects to API design because operation granularity, idempotence, status encoding, and schema evolution all appear in miniature here.

### Retain / Do Not Confuse

**Retain.** A well-designed RPC operation exposes a clean call interface while explicitly accounting for schema, correlation, location, timeout, and error semantics.

**Do Not Confuse.** Simplicity of signature does not imply simplicity of execution path.

## Why RPC belongs in this sequence

RPC belongs here because it is the disciplined answer to a systems question that appears after sockets: once computation is separated across processes or machines, how do we expose communication as an interface that programmers can use without writing raw transport logic every time?

From below, RPC depends on endpoints and transports such as sockets. From above, RPC supports service boundaries and API contracts. It therefore sits between raw communication mechanisms and higher-level distributed service structure.

That placement explains both its power and its danger. It is powerful because it lets programmers think in terms of operations instead of packet handling. It is dangerous because the call-shaped interface can tempt them to forget the semantic realities underneath: latency, timeout, partial failure, retries, duplicates, and representation boundaries.

So the correct closing retention point is simple: **RPC is not “networking hidden away.” It is communication disciplined into a procedure-call interface, with all distributed failure semantics still in force.**

**Retain.** RPC is a middle layer between raw endpoint communication and service-oriented program structure.

**Do Not Confuse.** The abstraction improves usability; it does not erase distributed uncertainty.
