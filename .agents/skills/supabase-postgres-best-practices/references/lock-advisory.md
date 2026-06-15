---
title: Use Advisory Locks for Application-Level Locking
impact: MEDIUM
impactDescription: Efficient coordination without row-level lock overhead
tags: advisory-locks, coordination, application-locks
---

## Use Advisory Locks for Application-Level Locking

Advisory locks provide application-level coordination without requiring database rows to lock.

**Incorrect (creating rows just for locking):**

```sql
-- Creating dummy rows to lock on
create table resource_locks (
  resource_name text primary key
);

insert into resource_locks values ('report_generator');

-- Lock by selecting the row
select * from resource_locks where resource_name = 'report_generator' for update;
```

**Correct (advisory locks):**

```sql
-- Session-level advisory lock (released on disconnect or unlock)
select pg_advisory_lock(42, 1);  -- namespace 42, resource 1
-- ... do exclusive work ...
select pg_advisory_unlock(42, 1);

-- Transaction-level lock (released on commit/rollback)
begin;
select pg_advisory_xact_lock(42, 2);  -- namespace 42, resource 2
-- ... do work ...
commit;  -- Lock automatically released
```

Use deterministic integer namespaces and resource IDs instead of hashing lock names. Hash-based 32-bit keys can collide and make unrelated resources share a lock.

Try-lock for non-blocking operations:

```sql
-- Returns immediately with true/false instead of waiting
select pg_try_advisory_lock(42, 3);

-- Use in application
if (acquired) {
  -- Do work
  select pg_advisory_unlock(42, 3);
} else {
  -- Skip or retry later
}
```

Reference: [Advisory Locks](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS)
