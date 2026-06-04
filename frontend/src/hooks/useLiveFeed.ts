import { useEffect, useRef, useState } from "react";
import { liveFeed } from "../api/ws";
import type { Tick } from "../api/types";

// Connect once at app mount.
export function useFeedConnection() {
  const [connected, setConnected] = useState(false);
  const [marketStatus, setMarketStatus] = useState<string | undefined>();

  useEffect(() => {
    liveFeed.connect();
    const off = liveFeed.onState((s) => {
      setConnected(s.connected);
      if (s.marketStatus) setMarketStatus(s.marketStatus);
    });
    return () => {
      off();
    };
  }, []);

  return { connected, marketStatus };
}

// Subscribe to a set of tokens and expose the latest tick keyed by token.
export function useTicks(instruments: { token: string; exch_seg: string }[]) {
  const [ticks, setTicks] = useState<Record<string, Tick>>({});
  const tokensKey = instruments.map((i) => i.token).sort().join(",");
  const prevTokens = useRef<string[]>([]);

  useEffect(() => {
    if (!instruments.length) return;
    liveFeed.subscribe(instruments);
    prevTokens.current = instruments.map((i) => i.token);
    const off = liveFeed.onTick((t) => {
      setTicks((prev) => ({ ...prev, [t.token]: t }));
    });
    return () => {
      off();
      liveFeed.unsubscribe(prevTokens.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tokensKey]);

  return ticks;
}
