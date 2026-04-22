# POSIX Shared Memory: API Shape, Object Model, and Correct Usage

POSIX shared memory is mislearned whenever it is introduced as six unrelated functions. The chapter should start with one object: a **named kernel memory object** that processes can open, size, map, unmap, close, and eventually unlink. Once that object is clear, the API becomes short and coherent.

The concept-level point is simple. Shared memory here does **not** mean “one process gives another process a pointer.” A pointer value is meaningful only inside one process’s own virtual address space — that is, the address world relative to that one process’s current mappings. POSIX shared memory works because multiple processes separately map the **same kernel object** into their own address spaces.

The canonical object has three views that must not be collapsed:

1. **The name**: how unrelated processes refer to the same shared-memory object.
2. **The descriptor**: one process’s open handle to that object after `shm_open`.
3. **The mapping**: the process-local virtual-memory region returned by `mmap`, through which actual loads and stores happen.

A reminder sentence is needed here. A **descriptor** is the per-process handle to an open kernel object. A **mapping** is the act and result of telling the kernel, “make this object accessible at some address range inside this process.” So the name is how the object is found, the descriptor is how the process holds it open, and the mapping is how the process actually accesses its bytes.

Those are related, but they are not the same thing. The name is not the descriptor. The descriptor is not the mapping. The mapping is not the object’s whole lifetime.

A second distinction belongs immediately beside the first: **creation, sizing, and mapping are different operations**. A process can create or open a shared-memory object and still have no usable shared bytes yet. If the object has size zero, there is nothing meaningful to map. If the object is mapped before its layout is initialized, the mapping exists but the protocol may still be invalid.

That last point deserves one review sentence. A valid mapping only means the bytes are reachable through memory access. It does **not** mean the bytes already contain meaningful shared data or that the two processes agree on how to interpret those bytes.

So the first retention rule for this chapter is:

- `shm_open` gives you a handle to the object,
- `ftruncate` gives the object a size,
- `mmap` gives this process a usable address range onto that object.

A boundary condition should be stated early. The POSIX shared-memory name is **pathname-like**, meaning it behaves like a systemwide name by which processes can refer to the same object, but the portable abstraction is not “ordinary persistent disk file.” On many systems the namespace is implemented through something like `/dev/shm`, but conceptually the object is a kernel-managed shared-memory object local to one kernel instance.

A compact mechanism trace makes the model exact. Process A calls `shm_open("/ringbuf", ...)`. At that moment A has a descriptor, not a pointer. If the object is new, it may still have size zero. A calls `ftruncate` to set the size. A then calls `mmap` with a shared mapping. Only now does A have a usable address range. Later Process B can `shm_open` the same name, obtain its own descriptor, and map the same object at a completely different virtual address. What is shared is the underlying object, not the numerical pointer values.

**Retain.** POSIX shared memory is a named kernel object that processes open and then map. Name, descriptor, and mapping are distinct layers of the same mechanism.

**Do Not Confuse.** Shared memory is not created by handing another process a pointer, and `shm_open` by itself does not return usable memory.

## The canonical API lifecycle

For exam purposes, the cleanest way to remember POSIX shared memory is as a lifecycle.

### Step 1: create or open with `shm_open`

`shm_open` either creates a new named object or opens an existing one. Those two states must be distinguished because only the creator should usually perform first-time initialization.

### Step 2: size the object with `ftruncate`

A new shared-memory object may exist with length zero. `ftruncate` sets its byte extent. This is object sizing, not mapping, not synchronization, and not logical initialization of fields.

### Step 3: attach with `mmap`

`mmap` creates this process’s virtual-memory view of the shared object. Until `mmap` succeeds, the process has no pointer through which it can actually access shared data.

### Step 4: initialize or validate the layout

If this process is the creator, it must initialize the agreed layout. If it is an opener, it must validate the layout before use. Shared memory shares bytes, not types or meaning.

### Step 5: use the mapping

After successful mapping and successful protocol-level setup, loads and stores through the mapped region access the shared underlying object.

### Step 6: detach locally with `munmap`

`munmap` removes this process’s mapping. It does not remove the object globally.

### Step 7: drop the descriptor with `close`

`close` releases this process’s descriptor. If a valid mapping already exists, that mapping can still remain usable afterward because the descriptor and the mapping are different resources.

### Step 8: remove the name with `shm_unlink`

`shm_unlink` removes the namespace entry. It stops future `shm_open` lookups by that name, but it does not instantly tear down existing mappings or existing open references.

That yields the canonical retention sentence:

**create/open -> size -> map -> initialize/validate -> use -> unmap -> close -> unlink when the name should disappear**

The major misconception to cut off is the cleanup confusion. `munmap`, `close`, and `shm_unlink` operate on different things:

- `munmap` affects this process’s mapping,
- `close` affects this process’s descriptor,
- `shm_unlink` affects the name.

A compact trace makes the lifecycle precise. Process A creates `/queue`, sizes it, maps it, initializes the header, and publishes readiness through a separate synchronization rule. Process B later opens `/queue`, maps it, validates the header, and begins use. When B is done, it `munmap`s and `close`s. When the object should no longer be discoverable by name, one designated process calls `shm_unlink`. Existing mappings can still continue until their final references disappear.

**Retain.** `shm_open` creates or opens, `ftruncate` sizes, `mmap` attaches, `munmap` detaches locally, `close` drops a descriptor, and `shm_unlink` removes the name.

**Do Not Confuse.** Unmapping is not unlinking, closing is not unmapping, and opening an object is not the same as initializing it.

## 4. A full worked example: producer and consumer over one shared-memory object

This section exists because POSIX shared memory is only fully understood when its object lifecycle and correctness obligations are seen in a concrete exchange between unrelated processes. A producer/consumer example exposes all the important issues at once: creation, rendezvous by name, layout agreement, initialization order, data visibility, and teardown.

The object in this example is a single shared-memory object that contains a fixed header followed by a ring buffer of records. Formally, the object is one named POSIX shared-memory region whose first bytes hold metadata—magic number, format version, capacity, element size, write position, read position, and a readiness indicator—and whose remaining bytes hold the actual payload slots. The interpretation is that the shared-memory object is being used as a structured in-kernel-backed byte container. Both processes are reading and writing bytes in the same underlying object, but they can do so correctly only because they agree in advance on the exact layout.

Consider the lifecycle from the producer’s side first. The producer is responsible for creation and first-time initialization. It chooses a name such as `/metrics_channel` and calls `shm_open` in a way that lets it discover whether it created the object newly or merely opened an old leftover one. In the clean case, it is the creator. It then calls `ftruncate` to the exact total size required: header bytes plus ring-buffer storage. Next it calls `mmap` with shared writable access. At this point the producer still does not have a logically usable channel, because the bytes exist but the protocol state is not yet initialized. It writes the header fields, zeroes or otherwise initializes the ring slots as required by the protocol, and only then marks the channel ready under whatever synchronization rule the design uses.

Now consider the consumer. It knows the shared-memory name `/metrics_channel`. It calls `shm_open` without claiming creator status; it merely opens the existing object. It then maps the object with read-only or read-write permissions according to the protocol. The consumer does not assume that “successful `shm_open` means ready data.” Instead it verifies the header: the magic number must match, the version must be one it understands, the declared object size and element size must match its own compiled layout assumptions, and the readiness state must say initialization is complete. Only then does it begin reading records.

The exact lifecycle can be traced as a sequence of object states.

At time 1, no object named `/metrics_channel` exists.

At time 2, the producer creates the object with `shm_open`. The name now resolves, but the object may still have length zero and contain no valid channel layout.

At time 3, the producer sizes the object with `ftruncate`. Now the object has the right byte extent, but its protocol fields may still be uninitialized.

At time 4, the producer maps and initializes the region. The object now contains a valid header and empty ring buffer, but the consumer must not assume this until the producer has published readiness under the chosen synchronization discipline.

At time 5, the consumer opens and maps the object. It validates the header and begins reading according to the agreed protocol.

At time 6, the producer writes records by updating payload slots and advancing the write position. The consumer reads records by checking availability, consuming slots, and advancing the read position. The important guarantee is that both processes are seeing the same underlying object contents. The important non-guarantee is that the OS is not sequencing those updates into a producer/consumer protocol for them.

At time 7, when no future opener should discover the object by name, one designated process calls `shm_unlink`. New consumers can no longer open by that name. Existing producer and consumer mappings continue.

At time 8, each process eventually calls `munmap` and `close`. When the last live reference disappears, the kernel reclaims the object.

The main failure mode in this example is not “shared memory stopped being shared.” The main failure mode is protocol violation. If the consumer maps the object and reads header fields before the producer has finished initialization, it may see default zero values, stale leftover contents, or partially written metadata and misinterpret the entire region. Shared memory solves data placement; it does not solve readiness.

A misconception block belongs here. **Do not confuse visibility with coordination.** Once both processes map the object correctly, writes become visible through the shared region. That does not imply that the producer and consumer have a safe handoff protocol, a correct ready/not-ready state machine, or protection from races on indices.

This example connects immediately to semaphores, mutexes, condition variables in shared memory, and lock-free local IPC. The channel is fast because data copies are avoided, but safe use still depends on explicit synchronization and explicit layout contracts.

**Retain.** In a real producer/consumer design, one process creates, sizes, and initializes the object; another opens and validates it; both then use an agreed layout over a shared mapping.

**Do Not Confuse.** Seeing the same bytes is not the same as having a correct producer/consumer protocol.

## 5. What POSIX shared memory guarantees, and what it very deliberately does not

This section exists because the mechanism is often oversold. Shared memory gives an extremely strong data-placement property and almost nothing beyond that automatically. Many incorrect designs come from importing guarantees that the API never offered.

The object to formalize here is the **contract** of POSIX shared memory. Formally, the mechanism guarantees that processes that have mapped the same shared-memory object with appropriate shared mappings can access the same underlying bytes through their own virtual address spaces. The interpretation is straightforward but limited: the same object contents are visible to all such mappings according to the platform’s memory and mapping semantics. This is the “yes” side of the contract.

Several equally important “no” statements must sit next to it.

First, shared memory does **not** guarantee synchronization. The OS does not, merely by virtue of the object being shared, serialize concurrent writers, establish happens-before relationships for your protocol, or wake a waiting consumer when a producer writes new data. Any ordering, exclusion, readiness signaling, or wait/notify behavior must come from additional mechanisms such as semaphores, mutexes, condition variables placed in shared memory with the right attributes, eventfd-like mechanisms where available, signals in specific designs, or carefully designed atomic protocols.

Second, shared memory does **not** guarantee agreement on layout. The kernel shares bytes, not types. If one process thinks the first eight bytes are a 64-bit sequence number and another thinks they are two 32-bit fields, both can access the same object perfectly and still communicate nonsense. Correctness therefore requires an explicit binary contract: field order, widths, alignment assumptions, padding rules, versioning, and if relevant, endianness and atomicity discipline.

Third, shared memory does **not** guarantee safe lifetime by itself. The kernel will manage raw object reclamation under the name/open/mapping rules, but it does not decide application-level ownership. Processes must agree on when initialization is complete, who is allowed to unlink, whether a leftover object from an earlier crashed run is acceptable or must be rejected, and what “shutdown” means for live mappings.

The boundary conditions become especially visible in failure cases. Suppose the reader opens the object after the creator has called `shm_open` and `ftruncate` but before the creator has written a valid header. From the API’s point of view everything may be working. The object exists. The reader can map it. The bytes are visible. Yet the reader’s interpretation is wrong because readiness was never synchronized. Or suppose two programs are built from different struct definitions after a protocol revision. Both map successfully. Both see the same bytes. The communication still fails because layout agreement is missing.

A full failure-mode trace makes this concrete. A creator decides the object should hold a 4096-byte header and buffer, creates it, sizes it, and begins initialization. Before it writes the magic number and version, a reader opens the object and maps 4096 bytes. The reader interprets the first word as a ready flag. Because the bytes happen still to be zero, the reader may spin forever, may assume an empty-but-valid channel, or may proceed into a path that was intended only after initialization. The shared memory has not malfunctioned. The program protocol has.

A second failure mode comes from mismatched layout assumptions. Version 1 of a program treats the header as `[magic, version, count, data...]`. Version 2 inserts a new field between version and count. An old reader and a new writer can map the same object and see each other’s writes, but the old reader now interprets the new field as `count`. Again, visibility succeeded; meaning failed.

A misconception block belongs here in explicit form. **Do not confuse “shared memory” with “the OS synchronizes for me.”** The operating system ensures that the mapping refers to a common underlying object. It does not invent a concurrency protocol for the bytes stored there.

This section connects directly to later material on locks, semaphores, atomics, and memory-order reasoning. Shared memory is where those synchronization topics stop being optional details and become part of the object’s meaning.

**Retain.** POSIX shared memory guarantees shared visibility of bytes through shared mappings. It does not guarantee synchronization, layout agreement, or application-level lifetime discipline.

**Do Not Confuse.** A correct mapping is not a correct protocol, and successful communication at the byte level is not successful agreement at the data-structure level.

## 6. Correct teardown: why `close`, `munmap`, and `shm_unlink` are different operations

This section exists because teardown is where programmers often discover too late that they never actually understood the object model. The three cleanup calls operate on different things, and using the wrong one for the intended effect either leaks resources or breaks future rendezvous.

The object here is the **teardown relationship** among open descriptor, process-local mapping, and namespace entry. Formally, `close` releases a file descriptor in one process, `munmap` removes an address-space mapping in one process, and `shm_unlink` removes the object’s name from the shared-memory namespace. Interpretation: cleanup is not one action but three, because there are three distinct resources in play.

`close` matters only to the descriptor. After a successful `mmap`, a process may close the descriptor and continue using the mapping, because the mapping already holds the needed reference to the underlying object. This is a common and correct pattern. It is also a strong diagnostic clue: if the mapping survives `close`, then the descriptor was never the memory itself.

`munmap` matters only to that process’s address space. After `munmap`, that process must stop dereferencing addresses in the former region. Other processes may still have perfectly valid mappings to the same object. The shared-memory object may continue to exist, and its name may continue to resolve, depending on whether descriptors or namespace entries remain.

`shm_unlink` matters to the name. Once it succeeds, future attempts to rendezvous by that name should fail because the namespace entry is gone. Existing descriptors and mappings, however, may continue to keep the object alive until the last reference disappears. This is analogous to unlinking a regular file while processes still have it open: the directory entry is gone, but the object is not reclaimed until no live references remain.

That last point creates both a useful pattern and a common trap. The useful pattern is early unlink after successful setup, when the design wants the object shared only among already participating processes and does not want later accidental openers. The trap is to assume that early unlink means current users lose access immediately. They do not. Access continues through existing mappings and descriptors.

A mechanism trace makes teardown exact. Process A creates and maps `/sessionbuf`. Process B opens and maps it. A then calls `shm_unlink` because no additional process should join. At this moment, a third process C cannot `shm_open` the name successfully. But A and B still read and write through their mappings. Later B calls `munmap` and exits. A still uses the object. Only when A too unmaps or otherwise releases the final live reference does the kernel reclaim the underlying object.

A misconception block belongs here explicitly. **Do not confuse `shm_unlink` with immediate destruction of all mappings.** Unlink removes discoverability by name. Reclamation waits for the last live reference to disappear.

This section connects to later resource-management design, especially crash resilience and cleanup discipline. High-performance IPC mechanisms become reliable only when ownership of unlinking and detachment is made explicit.

**Retain.** `close` drops a descriptor, `munmap` drops one process’s mapping, and `shm_unlink` drops the namespace name. They operate on different layers of the mechanism.

**Do Not Confuse.** Removing the name does not retroactively tear mappings out of other processes, and closing a descriptor does not by itself end mapped access.

## 7. Why this mechanism matters later: semaphores, `mmap`, and high-throughput local IPC

This section exists because POSIX shared memory is not an isolated API chapter. It is the place where several operating-systems ideas become one mechanism: namespace lookup, kernel objects, virtual-memory mapping, and user-managed synchronization.

The object here is POSIX shared memory as a **foundation mechanism**. Formally, it is a local interprocess communication substrate that trades simplicity of lifetime and protocol for very low-copy data exchange between processes on the same machine. The interpretation is that shared memory is often the right answer when the bottleneck is moving large or frequent data through kernel-mediated byte streams, but it is only the right answer when the program is willing to own layout and synchronization discipline.

The connection to **semaphores and locks** is immediate. Shared memory provides common bytes; semaphores, mutexes, condition variables, or atomic state machines provide safe access rules over those bytes. Without the synchronization layer, shared memory alone is an incomplete IPC design except in narrow single-writer or write-once/read-many cases that have been reasoned through very carefully.

The connection to **`mmap` reasoning** is structural. The same virtual-memory ideas that apply to file-backed mappings apply here: an object exists independently of any one process’s mapping; mappings are per-process virtual regions; protection and sharing flags matter; and lifetime depends on references, not just names. POSIX shared memory is therefore best understood as a specific use of mapping, not as a separate magical memory feature.

The connection to **high-throughput local IPC** is practical. Pipes and sockets give stronger message-transport structure and easier blocking semantics, but they often involve extra copying and kernel mediation per transfer. Shared memory can remove much of that overhead by letting processes operate on the same underlying data buffer directly. The price is that application protocols must now solve initialization order, readiness, versioning, synchronization, and teardown discipline.

A final misconception block is worth making explicit. **Do not confuse “faster IPC” with “simpler IPC.”** POSIX shared memory often improves throughput and lowers copy costs, but it raises the burden of protocol design. It is powerful precisely because the OS does less policy on your behalf.

This chapter therefore supports later chapters on process-shared synchronization primitives, memory-mapped I/O reasoning, lock-free data structures in a single machine, and the design tradeoff between convenience and control in IPC mechanisms.

**Retain.** POSIX shared memory is a kernel object mapped into multiple processes, ideal for local high-throughput IPC when paired with explicit synchronization and a stable binary layout.

**Do Not Confuse.** It is not a complete IPC protocol by itself, and it is not conceptually separate from `mmap`; it is one important application of `mmap`-style object mapping.
