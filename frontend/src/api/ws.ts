// Live-tick websocket client with auto-reconnect and per-token subscriptions.
import type { Tick } from "./types";

type TickHandler = (tick: Tick) => void;
type StateHandler = (state: { connected: boolean; marketStatus?: string }) => void;

export class LiveFeed {
  private ws: WebSocket | null = null;
  private url: string;
  private tickHandlers = new Set<TickHandler>();
  private stateHandlers = new Set<StateHandler>();
  private subscribed = new Map<string, { token: string; exch_seg: string }>();
  private reconnectDelay = 1000;
  private pingTimer?: number;
  private shouldRun = false;

  constructor() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    this.url = `${proto}://${location.host}/ws`;
  }

  connect() {
    this.shouldRun = true;
    this.open();
  }

  private open() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING))
      return;
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      this.reconnectDelay = 1000;
      this.emitState({ connected: true });
      // Re-apply all subscriptions on (re)connect.
      const all = Array.from(this.subscribed.values());
      if (all.length) this.send({ action: "subscribe", instruments: all });
      this.pingTimer = window.setInterval(() => this.send({ action: "ping" }), 20000);
    };

    this.ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "tick") this.tickHandlers.forEach((h) => h(msg));
      else if (msg.type === "market_state") this.emitState({ connected: true, marketStatus: msg.status });
    };

    this.ws.onclose = () => {
      this.emitState({ connected: false });
      window.clearInterval(this.pingTimer);
      if (this.shouldRun) {
        setTimeout(() => this.open(), this.reconnectDelay);
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, 15000);
      }
    };

    this.ws.onerror = () => this.ws?.close();
  }

  private send(obj: unknown) {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(obj));
  }

  subscribe(instruments: { token: string; exch_seg: string }[]) {
    const fresh = instruments.filter((i) => !this.subscribed.has(i.token));
    instruments.forEach((i) => this.subscribed.set(i.token, i));
    if (fresh.length) this.send({ action: "subscribe", instruments: fresh });
  }

  unsubscribe(tokens: string[]) {
    tokens.forEach((t) => this.subscribed.delete(t));
    this.send({ action: "unsubscribe", tokens });
  }

  onTick(h: TickHandler) {
    this.tickHandlers.add(h);
    return () => this.tickHandlers.delete(h);
  }

  onState(h: StateHandler) {
    this.stateHandlers.add(h);
    return () => this.stateHandlers.delete(h);
  }

  private emitState(s: { connected: boolean; marketStatus?: string }) {
    this.stateHandlers.forEach((h) => h(s));
  }

  close() {
    this.shouldRun = false;
    window.clearInterval(this.pingTimer);
    this.ws?.close();
  }
}

// App-wide singleton.
export const liveFeed = new LiveFeed();
