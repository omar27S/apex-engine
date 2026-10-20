"""THE MARKET -- the packages that SEE the market.

``app.market`` is the perception layer's fast half: the sockets and streams
that watch the market at the speed it actually moves. The FALCON remains the
slow, wide eye (REST, macro, sentiment, five-minute cadence); the HYPERFEED is
the fast, narrow eye (WebSocket, top-of-book and trades, millisecond cadence).

Honesty is binding here exactly as it is everywhere in APEX: a venue that
cannot be reached says so by name; a symbol with no measured tick is never
invented; the motion is judged on the remembered span, never on the sensor's
sampling cadence (the wound the falcon's D4 surgery already numbered).
"""
