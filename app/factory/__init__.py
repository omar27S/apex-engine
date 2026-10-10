"""THE FACTORY — the maximum factory's levers (Phase 7e, R66-R75).

Every module here is PURE at import time (Scar #6): no services, no network, no
filesystem writes at import. Files are touched only inside explicit functions.
The factory is the scale layer over the sealed engine: it does not change the
Constitution, it only decides HOW MUCH gets evaluated, WHO breeds, and which
memory remembers.

The three machines (R66-R68):
* the HEART (CEO's Oracle ARM VM) — always-on queue, resident data;
* the TURBO (public apex-engine repo) — sliced parallel bursts;
* the VAULT (private apex repo) — certificates, reports, ledgers, migrations.

Nothing here runs a server, a scheduler, or a loop (Build Mode, Scar #7).
"""
