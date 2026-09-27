import type { ControllerBatteryUpdate } from "./api";
import { batteryPercent, controllerIndex, controllerItem, controllerRecord, messageBody, storeControllerItem } from "./controller_battery";

type Registration = { unregister: () => void };
type Handler = (message: unknown) => number;
export interface SteamInputService {
  GetControllerListHandler: { name: string };
  GetControllerList: (request: object) => Promise<{ BSuccess: () => boolean; Body: () => { toObject: () => unknown } }>;
  RegisterForNotifyControllerListChanged?: (handler: Handler) => Registration | null;
  RegisterForNotifyControllerBatteryState?: (handler: Handler) => Registration | null;
  RegisterForNotifyControllerDisconnected?: (handler: Handler) => Registration | null;
}

export function isSteamInputService(value: unknown): value is SteamInputService {
  const item = value as SteamInputService | null;
  return item?.GetControllerListHandler?.name === "SteamInputManager.GetControllerList#1"
    && typeof item.GetControllerList === "function";
}

export interface ControllerTelemetry {
  phase: "starting" | "ready" | "unavailable" | "error";
  hooks: number;
  queries: number;
  events: number;
  raw_count: number;
  query_ms: number | null;
  error: string;
  devices?: { index: number; name: string; list_percent: number | null; store_percent: number | null; event_percent: number | null;
    effective_percent: number | null; source: string; event_age_s: number | null }[];
}

interface Dependencies {
  discover: () => SteamInputService | undefined;
  readStore?: () => unknown;
  publish: (items: ControllerBatteryUpdate[], source: string) => Promise<unknown>;
  diagnose: (state: ControllerTelemetry) => Promise<unknown>;
  pollMs?: number;
  timeoutMs?: number;
}

/** Read-only SteamUI service consumer. No input feed, HID writes or pairing. */
export class ControllerMonitor {
  private alive = false;
  private service: SteamInputService | undefined;
  private timer: ReturnType<typeof setInterval> | undefined;
  private hooks = new Map<string, Registration>();
  private items = new Map<number, ControllerBatteryUpdate>();
  private battery = new Map<string, { at: number; body: Record<string, unknown> }>();
  private pendingBattery = new Map<number, { at: number; body: Record<string, unknown> }>();
  private listedPercent = new Map<number, number | null>();
  private storePercent = new Map<number, number | null>();
  private sources = new Map<number, string>();
  private rosterRevision = 0;
  private inFlight: Promise<void> | undefined;
  private again = false;
  private initialised = false;
  private delivery: Promise<void> = Promise.resolve();
  private state: ControllerTelemetry = { phase: "starting", hooks: 0, queries: 0, events: 0, raw_count: 0, query_ms: null, error: "" };

  constructor(private readonly deps: Dependencies) {}

  start() {
    if (this.alive) return;
    this.alive = true;
    void this.diagnose();
    void this.refresh();
    this.timer = setInterval(() => void this.refresh(), this.deps.pollMs ?? 2000);
  }

  async stop() {
    this.alive = false;
    clearInterval(this.timer);
    for (const hook of this.hooks.values()) {
      try { hook.unregister(); } catch { /* Steam may already be shutting down. */ }
    }
    this.hooks.clear();
    await this.delivery;
  }

  refresh(): Promise<void> {
    if (!this.alive) return Promise.resolve();
    if (this.inFlight) {
      this.again = true;
      return this.inFlight;
    }
    this.again = false;
    this.inFlight = Promise.resolve().then(() => this.query()).finally(() => {
      this.inFlight = undefined;
      if (this.again && this.alive) void this.refresh();
    });
    return this.inFlight;
  }

  private async diagnose() {
    if (!this.alive) return;
    this.state.devices = [...this.items].slice(0, 8).map(([index, item]) => {
      const event = this.battery.get(item.id);
      return { index, name: item.name, list_percent: this.listedPercent.get(index) ?? null,
        store_percent: this.storePercent.get(index) ?? null,
        event_percent: event ? batteryPercent(event.body.battery_level) : null,
        effective_percent: item.percent, source: this.sources.get(index) ?? "controller list",
        event_age_s: event ? Math.max(0, (Date.now() - event.at) / 1000) : null };
    });
    try { await this.deps.diagnose({ ...this.state }); } catch { /* Next poll retries backend startup. */ }
  }

  private deliver(source: string) {
    const snapshot = [...this.items.values()].slice(0, 8).map(item => ({ ...item }));
    const pending = this.delivery.then(async () => {
      if (this.alive) await this.deps.publish(snapshot, source);
    });
    this.delivery = pending.catch(async () => {
      this.state.phase = "error";
      this.state.error = "Controller data could not reach the GabeCubeAura backend; retrying";
      await this.diagnose();
    });
    return pending;
  }

  private installHooks(service: SteamInputService) {
    const callbacks: [keyof SteamInputService, Handler][] = [
      ["RegisterForNotifyControllerListChanged", () => {
        this.rosterRevision++;
        void this.refresh();
        return 1;
      }],
      ["RegisterForNotifyControllerDisconnected", message => {
        const index = controllerIndex(messageBody(message));
        if (index != null) {
          this.rosterRevision++;
          const item = this.items.get(index);
          if (item) this.battery.delete(item.id);
          this.pendingBattery.delete(index);
          this.listedPercent.delete(index);
          this.items.delete(index);
          if (this.initialised) void this.deliver("SteamInputManager disconnect").catch(() => undefined);
          void this.refresh();
        }
        return 1;
      }],
      ["RegisterForNotifyControllerBatteryState", message => {
        const body = messageBody(message);
        const index = controllerIndex(body);
        if (index != null) {
          const item = this.items.get(index);
          const reading = { at: Date.now(), body };
          if (item) {
            this.battery.set(item.id, reading);
            this.applyBattery(item, body);
            this.sources.set(index, "live battery event");
            void this.deliver("SteamInputManager battery").catch(() => undefined);
            void this.diagnose();
          } else {
            this.pendingBattery.set(index, reading);
            void this.refresh();
          }
        }
        return 1;
      }],
    ];
    for (const [key, callback] of callbacks) {
      if (this.hooks.has(key)) continue;
      const register = service[key];
      if (typeof register !== "function") continue;
      try {
        const hook = (register as (handler: Handler) => Registration | null).call(service, message => {
          if (!this.alive) return 1;
          this.state.events++;
          try { return callback(message); }
          catch { this.state.error = "Unreadable controller notification; polling is still active"; return 1; }
        });
        if (hook && typeof hook.unregister === "function") this.hooks.set(key, hook);
      } catch { /* Poll remains available; retry missing registrations next time. */ }
    }
    this.state.hooks = this.hooks.size;
  }

  private applyBattery(item: ControllerBatteryUpdate, body: Record<string, unknown>) {
    if ("battery_level" in body) item.percent = batteryPercent(body.battery_level);
    if (typeof body.charging === "boolean") item.charging = body.charging;
  }

  private async query() {
    if (!this.alive) return;
    let timeout: ReturnType<typeof setTimeout> | undefined;
    try {
      this.service ??= this.deps.discover();
      if (!this.service) {
        this.state.phase = "unavailable";
        this.state.error = "SteamInputManager is not loaded. Discovery retries every 2 seconds.";
        return;
      }
      this.installHooks(this.service);
      const roster = this.rosterRevision;
      const started = Date.now();
      this.state.queries++;
      const response = await Promise.race([
        this.service.GetControllerList({}),
        new Promise<never>((_, reject) => {
          timeout = setTimeout(() => reject(new Error("Controller list timed out")), this.deps.timeoutMs ?? 3500);
        }),
      ]);
      if (!this.alive) return;
      if (!response.BSuccess()) throw new Error("Steam refused the controller-list query");
      const body = messageBody(response);
      if (body.controllers != null && !Array.isArray(body.controllers)) throw new Error("Unexpected controller-list format");
      if (roster !== this.rosterRevision) { this.again = true; return; }
      const entries = (body.controllers ?? []) as unknown[];
      const fresh = new Map<number, ControllerBatteryUpdate>();
      const listed = new Map<number, number | null>();
      const storeItems = new Map<string, ControllerBatteryUpdate>();
      try {
        const snapshot = this.deps.readStore?.();
        if (Array.isArray(snapshot)) for (const raw of snapshot) {
          const match = storeControllerItem(raw);
          if (match) storeItems.set(match.item.id, match.item);
        }
      } catch { /* Steam store is optional: service + notifications still work. */ }
      this.storePercent.clear();
      this.sources.clear();
      for (const entry of entries) {
        const raw = controllerRecord(entry);
        if (!raw) continue;
        const item = controllerItem(raw);
        const index = controllerIndex(raw);
        if (!item || index == null) continue;
        listed.set(index, item.percent);
        const pending = this.pendingBattery.get(index);
        if (pending) this.battery.set(item.id, pending);
        const update = this.battery.get(item.id);
        // SteamUI patches its controller store with live battery notifications.
        // Repeated GetControllerList responses may still contain the initial
        // battery (e.g. 100). Never undo a live 41% reading on the next poll.
        // Keep it for this device connection, not for this reusable input slot.
        if (update) this.applyBattery(item, update.body);
        this.sources.set(index, update ? "live battery event" : "controller list");
        const ui = storeItems.get(item.id);
        this.storePercent.set(index, ui?.percent ?? null);
        // Read the same state Steam's header displays, including notifications
        // delivered before GabeCubeAura loaded. Never call its Init or mutate it.
        // Once our live subscription has a reading, neither startup snapshot
        // may overwrite it. Keep SteamUI as a seed, not a competing writer.
        if (ui?.percent != null && !update) {
          item.percent = ui.percent;
          item.charging = ui.charging ?? item.charging;
          this.sources.set(index, "SteamUI controller state");
        }
        fresh.set(index, item);
      }
      this.items = fresh;
      this.listedPercent = listed;
      this.pendingBattery.clear();
      const ids = new Set([...fresh.values()].map(item => item.id));
      for (const id of this.battery.keys()) if (!ids.has(id)) this.battery.delete(id);
      await this.deliver("SteamInputManager list");
      if (!this.alive) return;
      this.initialised = true;
      this.state.phase = "ready";
      this.state.error = "";
      this.state.raw_count = entries.length;
      this.state.query_ms = Date.now() - started;
    } catch (error) {
      this.state.phase = "error";
      this.state.error = error instanceof Error ? error.message.slice(0, 180) : "Steam controller query failed";
    } finally {
      clearTimeout(timeout);
      await this.diagnose();
    }
  }
}
