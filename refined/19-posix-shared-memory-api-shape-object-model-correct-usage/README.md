# POSIX Shared Memory: API Shape, Object Model, and Correct Usage

## 1. Why POSIX shared memory must be learned as an object model, not as a function list

POSIX shared memory is easy to misuse when it is taught as six unrelated calls. The reason this section exists is that the mechanism is not “a process gets some shared bytes” in the abstract. The mechanism is a named kernel object that can be opened, sized, mapped into one or more virtual address spaces, and later detached and unnamed under rules that are close to file and `mmap` reasoning, but not identical to ordinary file use. If that object model is not fixed first, the API names are misleading: `shm_open` sounds like it returns memory, `close` sounds like it ends use, and `shm_unlink` sounds like it destroys the shared region immediately. None of those readings is correct.

The object to introduce first is the **POSIX shared-memory object** itself. Formally, it is a kernel-managed object in a shared-memory namespace, identified by a pathname-like name, opened through `shm_open`, given a byte length through `ftruncate`, and made accessible to a process only when that process maps it into its own virtual address space with `mmap`. The interpretation is immediate: the shared-memory object is not the same thing as the file descriptor returned by `shm_open`, and it is not the same thing as any one process’s pointer into the region after `mmap`. One kernel object can have many open descriptors over time and many simultaneous mappings in different processes.

This separation matters because the mechanism has three distinct views of “the same shared memory,” and each view obeys different lifetime rules. The **name** is how unrelated processes find the object. The **file descriptor** is one process’s open handle to that object. The **mapping** is a region in one process’s virtual address space whose pages refer to that object. If those are collapsed into one idea, cleanup and correctness both become confused.

Boundary conditions come early. The name is pathname-like, but in POSIX it is not intended to be treated as an ordinary hierarchical filesystem pathname; typically it begins with a slash and contains no further slashes. Many Unix-like systems implement the namespace using a tmpfs such as `/dev/shm`, which makes the object feel file-like in tooling, but the portable API abstraction is “named shared-memory object,” not “ordinary disk file.” The object is local to one kernel instance. It is not network shared memory, and it is not an IPC mechanism across machines.

A mechanism trace clarifies the distinction. Suppose Process A calls `shm_open` on `/ringbuf`. At that moment A does **not** yet have usable shared bytes. It has an open descriptor to a kernel object. If the object was newly created, its initial size is typically zero, so there may still be no meaningful region to map. Only after A sets the desired size with `ftruncate` and calls `mmap` with a shared mapping does A receive a usable address range. Later, Process B can independently call `shm_open` on the same name, obtain its own descriptor, and map the same object into a different virtual address range. The two pointers in A and B need not be numerically equal; what is shared is the underlying object, not the virtual addresses.

A common misconception appears here. **Do not confuse “shared memory” with “one process hands another process a pointer.”** A raw pointer value is meaningful only inside the virtual address space in which it was created. POSIX shared memory works because each process separately maps the same kernel object into its own address space. The relationship is object-based, not pointer-based.

This section connects directly to later material on `mmap`, page sharing, cache coherence visibility, and local IPC design. Once the object model is fixed, the API becomes a short sequence of operations on a stable abstraction rather than a memorized bag of calls.

**Retain.** POSIX shared memory is a named kernel object that processes open and then map. The name, descriptor, and mapping are related, but they are not the same thing.

**Do Not Confuse.** Shared memory is not created by giving another process a pointer value, and `shm_open` does not itself return a usable memory region.

## 2. The object itself: name, descriptor, size, and mapping

This section exists because most bugs in shared-memory code are really object-model bugs. The programmer thinks the name is the object, or the descriptor is the memory, or the mapping owns the object’s lifetime. The mechanism becomes simpler once those roles are separated exactly.

The object here is the four-layer relationship among **pathname-like name**, **open file descriptor**, **object size**, and **mapped virtual memory**. Formally, a POSIX shared-memory object has a namespace entry used for lookup, an open-description mechanism returned through `shm_open`, a current byte length just as a file-like object has a length, and zero or more process-local mappings created with `mmap`. The interpretation is that shared memory deliberately combines file-like and memory-like semantics. It is file-like when named, opened, permission-checked, and sized. It is memory-like only after mapping.

The name is how unrelated processes rendezvous. A writer can create an object under a chosen name such as `/telemetry`, and a reader that knows the same name can later open that object. The descriptor returned by `shm_open` is then the process’s handle for operations that act on the object through a file-descriptor interface: setting permissions indirectly via creation mode, checking errors, resizing with `ftruncate`, and supplying the descriptor to `mmap`. The descriptor is not the shared state itself. After `mmap`, the mapping is the process-local virtual-memory view through which loads and stores actually occur.

Sizing deserves special care. Creating the object and sizing the object are different operations. A newly created shared-memory object may exist with length zero. Formally, `ftruncate` sets the object’s length in bytes. Interpretation: `shm_open` answers “which object?” while `ftruncate` answers “how many bytes does that object currently contain?” If the size is wrong, the mapping and the data layout are wrong, even if the name and permissions are right.

The mapping step is where the OS turns an object into an address range. `mmap` with `MAP_SHARED` causes the process’s loads and stores through that region to refer to the shared object rather than to a private copy. Boundary conditions matter here. The mapping length is chosen by the caller, but meaningful access is only guaranteed within the current object size. The protection bits used in `mmap` must be compatible with how the descriptor was opened. A reader that opens read-only can map with read permissions; a writer that intends to modify must both open and map with write capability.

A short mechanism trace makes the layers concrete. A process creates `/telemetry` with `shm_open`. The returned descriptor is valid, but the object length is zero. The process then calls `ftruncate` to make it, say, 4096 bytes. Now the kernel object has a defined size, but there is still no process pointer. The process then calls `mmap`; only now does it obtain a virtual address. At this point, the descriptor could even be closed, and the mapping can remain valid. That fact shows that the descriptor is not the mapping. The mapping continues because the process’s address-space entry still refers to the kernel object.

A misconception block is necessary here. **Do not confuse the shared-memory name with a persistent file pathname.** On many systems the name is backed by something visible under `/dev/shm`, and operationally that is useful. But the portable POSIX abstraction is a name in the shared-memory namespace. Correct reasoning should not depend on ordinary directory traversal semantics, hard links, or disk-file persistence assumptions.

This section connects forward to `mmap` reasoning in general. The same discipline that distinguishes a file descriptor from a mapping in file-backed mappings applies here too, but the IPC setting makes lifetime and layout discipline much more visible.

**Retain.** The name identifies the object, the descriptor is an open handle, `ftruncate` sets the object size, and `mmap` creates the process-local address range used for actual access.

**Do Not Confuse.** Creating an object is not mapping it; sizing an object is not initializing its contents; closing a descriptor is not the same as removing a mapping.

## 3. The API shape as a lifecycle: creation, opening, sizing, mapping, detaching, and unlinking

This section exists because POSIX shared memory has a very particular lifecycle, and correctness depends on doing the operations in the right conceptual order. The calls make sense once they are read as transitions in the state of the object and of each process’s relationship to it.

The object being introduced here is the **lifecycle of access** to a shared-memory object. Formally, the lifecycle is: create or open a named object with `shm_open`; if newly created, set its length with `ftruncate`; map it with `mmap`; use the mapped region; later remove the process-local mapping with `munmap`; drop the descriptor with `close`; and remove the namespace entry with `shm_unlink` when the name should no longer resolve to the object. The interpretation is that some steps affect the kernel object globally and some affect only one process’s local handle or mapping.

`shm_open` has two roles, and they must be separated. It can **create** a new object if called with creation flags and the name does not already exist. It can also **open** an existing object if the name already resolves to one. Those are different states of the world. Correct programs often distinguish them because only the creator should perform first-time initialization, establish the layout version, and choose the size. Using creation flags such as `O_CREAT` and, when exclusivity matters, `O_EXCL`, is how one process detects whether it is the initializer or merely an opener.

`ftruncate` has exactly one role here: it sets the length of the shared object. It is not mapping, not initialization of logical fields, and not synchronization. If the writer expects a header plus payload totaling 64 KiB, then `ftruncate` must set the object to at least that size before any process relies on that layout. If the object is resized later, every process must reason carefully about whether its existing mapping length, data structure assumptions, and access pattern still match the object.

`mmap` has the role of attaching the object to a process’s virtual address space. Until this call succeeds, the process has no pointer through which it can read or write shared data. The crucial flag is that the mapping must be shared rather than private. The mapping length should match the amount of data the process intends to access and must be consistent with the sized object.

`munmap` removes **this process’s mapping**. It does not remove the shared-memory object from the kernel, and it does not affect other processes’ mappings except indirectly through later lifetime rules. `close` removes **this process’s file descriptor**. If the process already has a valid mapping, that mapping can remain usable after `close`, because the descriptor and the mapping are different resources. `shm_unlink` removes **the name** from the namespace. It prevents future `shm_open` calls on that name from finding the object, but it does not instantly invalidate existing mappings or descriptors. The object is actually reclaimed only when no mappings and no relevant open references remain.

The hidden constraint is that lifecycle discipline is part of correctness. Someone must own creation, someone must own initialization, someone must decide who unlinks, and everyone must agree when it is safe to detach. Without this protocol, the API can be used in a race-prone but syntactically correct way.

A full mechanism trace makes the lifecycle precise. Process A calls `shm_open` with creation and exclusivity intent on `/queue`. Because the name did not exist, A is now the creator. A calls `ftruncate` to set the object size to the exact bytes needed for the agreed header and buffer. A then `mmap`s the object with a shared writable mapping and initializes the header fields: magic number, version, capacity, write index, read index, and ready flag. Only after logical initialization is complete should A publish “ready” through a synchronization mechanism. Later, Process B calls `shm_open` on `/queue`, obtains its own descriptor, and `mmap`s the same object. B reads the header, verifies the magic number and version, and begins use. When B is done, it calls `munmap` to remove its mapping and `close` to drop its descriptor. When the system no longer wants the object discoverable by name, one designated process calls `shm_unlink`. Existing users continue until they unmap and close; new openers can no longer find the object by name.

A misconception must be cut off explicitly. **Do not confuse `shm_unlink` with “destroy the shared memory now.”** `shm_unlink` removes the name, not necessarily the live object. Existing mappings are not torn out from underneath running processes simply because the name was removed.

This lifecycle view connects directly to later work on robust resource ownership and crash cleanup. Shared memory is fast, but the speed benefit is bought with stronger responsibility for protocol discipline.

**Retain.** `shm_open` creates or opens, `ftruncate` sizes, `mmap` attaches, `munmap` detaches a mapping, `close` drops a descriptor, and `shm_unlink` removes the name.

**Do Not Confuse.** Unmapping is not unlinking, closing is not unmapping, and opening an existing object is not performing first-time initialization.

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
