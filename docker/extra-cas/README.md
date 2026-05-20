# Extra CA certificates

Drop additional trusted CA certificates here (one `.crt` per file, PEM format)
when building behind a TLS-inspecting corporate proxy. Each Dockerfile copies
the contents into its image's trust store before any network-dependent step,
then runs the distribution's `update-ca-certificates`. An empty directory is
a no-op.

Files in this directory are intentionally not committed (see `.gitignore`).
The directory itself is committed so the `COPY` in the Dockerfiles always
has something to copy.
