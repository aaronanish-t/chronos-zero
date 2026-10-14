-- Durable audit server (volume-backed, normal fsync). Runs once when its volume is first created.
-- The kernel creates the append-only audit_chain table on first use.
CREATE ROLE chronos_kernel LOGIN PASSWORD 'chronos_kernel';

CREATE DATABASE chronos_audit OWNER chronos_kernel;
