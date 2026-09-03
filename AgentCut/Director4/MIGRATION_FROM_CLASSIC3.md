# Migrating from AgentCut Classic 3.x

Migration is non-destructive:

```bash
agentcut-director migrate-classic3 classic_project.json director_project.json
```

The source file is read but never overwritten. Director 4 records:

- source family and detected version/schema;
- SHA-256 of the canonical source document;
- migration timestamp;
- compatibility warnings;
- preserved legacy payloads when a field has no Director 4 equivalent.

After migration:

1. Run `agentcut-director validate director_project.json`.
2. Review warnings and source paths.
3. Export a Remotion bridge and run `remotion-verify`.
4. Render a proxy before treating the migration as accepted.

Classic 3 remains available under its original package and CLI names.
