import { normalizeAppId } from "./steam_app_id";

export interface ObservedGame {
  appid: number;
  title: string;
}

export type GameSessionDecision =
  | { action: "none" }
  | { action: "retain"; appid: number; title: string; source: string }
  | { action: "update"; appid: number; title: string; source: string; launch: boolean };

/**
 * Keeps an authoritative Steam lifetime session across transient Router gaps.
 * Router polling may discover a game, but cannot end a confirmed lifetime
 * session on its own.
 */
export class GameSessionLatch {
  private current: ObservedGame = { appid: 0, title: "" };
  private lifetimeAvailable = false;
  private zeroPolls = 0;
  private ignoredAfterResume = 0;
  private ignoredPolls = 0;

  constructor(private readonly fallbackZeroPolls = 15) {}

  snapshot(): ObservedGame {
    return { ...this.current };
  }

  setLifetimeAvailable(available: boolean) {
    this.lifetimeAvailable = Boolean(available);
    if (this.lifetimeAvailable) this.zeroPolls = 0;
  }

  seed(game: ObservedGame): GameSessionDecision {
    const normalized = this.clean(game);
    this.current = normalized;
    this.zeroPolls = 0;
    return {
      action: "update",
      ...normalized,
      source: "startup",
      launch: false,
    };
  }

  observePoll(game: ObservedGame): GameSessionDecision {
    const observed = this.clean(game);
    if (this.ignoredAfterResume && observed.appid === this.ignoredAfterResume) {
      this.ignoredPolls += 1;
      if (this.ignoredPolls < Math.max(2, this.fallbackZeroPolls)) {
        return this.current.appid > 0
          ? { action: "retain", ...this.current, source: "resume stale AppID retained" }
          : { action: "none" };
      }
      this.ignoredAfterResume = 0;
      this.ignoredPolls = 0;
      this.current = observed;
      return {
        action: "update", ...observed, source: "resume poll confirmed", launch: false,
      };
    }
    if (observed.appid > 0) {
      this.ignoredAfterResume = 0;
      this.ignoredPolls = 0;
      this.zeroPolls = 0;
      if (observed.appid === this.current.appid) {
        if (observed.title && observed.title !== this.current.title) {
          this.current.title = observed.title;
          return {
            action: "update", ...this.current, source: "poll title refresh", launch: false,
          };
        }
        return { action: "none" };
      }
      this.current = observed;
      return {
        action: "update",
        ...observed,
        source: "poll fallback",
        launch: true,
      };
    }
    if (this.current.appid <= 0) return { action: "none" };
    if (this.lifetimeAvailable) {
      return { action: "retain", ...this.current, source: "poll zero retained" };
    }
    this.zeroPolls += 1;
    if (this.zeroPolls < Math.max(2, this.fallbackZeroPolls)) {
      return { action: "retain", ...this.current, source: "fallback zero grace" };
    }
    this.current = { appid: 0, title: "" };
    this.zeroPolls = 0;
    return {
      action: "update",
      ...this.current,
      source: "poll fallback confirmed stop",
      launch: false,
    };
  }

  observeLifetime(appid: unknown, running: boolean, title = ""): GameSessionDecision {
    this.lifetimeAvailable = true;
    const normalized = normalizeAppId(appid);
    if (running && normalized > 0) {
      this.ignoredAfterResume = 0;
      this.ignoredPolls = 0;
      this.zeroPolls = 0;
      const changed = normalized !== this.current.appid;
      this.current = { appid: normalized, title: String(title || this.current.title || "") };
      return changed
        ? { action: "update", ...this.current, source: "Steam lifetime start", launch: true }
        : { action: "none" };
    }
    if (!running && normalized > 0 && normalized === this.current.appid) {
      this.current = { appid: 0, title: "" };
      this.zeroPolls = 0;
      return {
        action: "update",
        ...this.current,
        source: "Steam lifetime stop",
        launch: false,
      };
    }
    return { action: "none" };
  }

  suspend(staleAppId: unknown): GameSessionDecision {
    this.ignoredAfterResume = normalizeAppId(staleAppId);
    this.ignoredPolls = 0;
    this.current = { appid: 0, title: "" };
    this.zeroPolls = 0;
    return {
      action: "update",
      ...this.current,
      source: "resume from suspend",
      launch: false,
    };
  }

  private clean(game: ObservedGame): ObservedGame {
    const appid = normalizeAppId(game?.appid);
    return { appid, title: appid > 0 ? String(game?.title || "") : "" };
  }
}
