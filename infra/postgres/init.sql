-- Runs once when the (tmpfs-backed) data directory is first initialised.
-- Services connect as chronos_kernel: owner of the cartridge databases, not a superuser.
CREATE ROLE chronos_kernel LOGIN PASSWORD 'chronos_kernel';

CREATE DATABASE chronos_healthcare_fhir OWNER chronos_kernel;
CREATE DATABASE chronos_fintech_escrow OWNER chronos_kernel;
CREATE DATABASE chronos_cloud_devops OWNER chronos_kernel;
