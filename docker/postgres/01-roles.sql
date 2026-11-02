-- Docker runs this once on a new cluster. psql quotes values and identifiers;
-- passwords never become shell SQL or appear as command-line arguments.
\getenv database POSTGRES_DB
\getenv owner_user MIGRATION_DB_USER
\getenv owner_password MIGRATION_DB_PASSWORD
\getenv runtime_user RUNTIME_DB_USER
\getenv runtime_password RUNTIME_DB_PASSWORD
SELECT length(:'owner_password') > 0 AND length(:'runtime_password') > 0 AS passwords_present \gset
\if :passwords_present
CREATE ROLE :"owner_user" LOGIN PASSWORD :'owner_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
CREATE ROLE :"runtime_user" LOGIN PASSWORD :'runtime_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
ALTER DATABASE :"database" OWNER TO :"owner_user";
REVOKE ALL ON DATABASE :"database" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"database" TO :"runtime_user";
REVOKE ALL ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO :"owner_user";
GRANT USAGE ON SCHEMA public TO :"runtime_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner_user" IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO :"runtime_user";
\else
\echo 'Set nonempty migration and runtime passwords before initialising PostgreSQL.'
\quit 1
\endif
