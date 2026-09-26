import { Router, findModuleExport } from "@decky/ui";

import {
  gameChanged,
  getArtwork,
  reportParentalMinutes,
  reportRuntimeDiagnostic,
  setSteamActivity,
  submitArtwork,
  triggerEvent,
  updateControllers,
  resetControllers,
  reportControllerTelemetry,
} from "./api";
import { sampleArtwork } from "./artwork";
import { ControllerMonitor, isSteamInputService } from "./controller_monitor";
import { isSteamControllerStore } from "./controller_battery";
import type { SteamControllerStore } from "./controller_battery";
import { normalizeAppId } from "./steam_app_id";
import {
  classifySteamNotification,
  CommunityNotificationObserver,
  isSteamServerNotificationStore,
  screenshotWasCaptured,
} from "./steam_events";
import type { LightEvent, SteamServerNotificationStore } from "./steam_events";
import type { Status } from "./types";

declare const SteamClient: any;
declare const appStore: any;

type Registration = { unregister?: () => void } | undefined;

function runningApp() {
  try {
    const app: any = Router?.MainRunningApp;
    const appid = normalizeAppId(app?.appid ?? app?.appID ?? app?.unAppID ?? app?.app_id);
    const title = String(app?.display_name ?? app?.name ?? "");
    return { appid, title };
  } catch {
    return { appid: 0, title: "" };
  }
}

function titleFor(appid: number): string {
  try {
    return String(appStore?.GetAppOverviewByAppID?.(appid)?.display_name ?? "");
  } catch {
    return "";
  }
}

class SignalBarRuntime {
  private alive = false;
  private desired = { appid: 0, title: "", source: "startup" };
  private confirmedKey = "";
  private syncing = false;
  private artworkGeneration = 0;
  private reportedAppId = 0;
  private suppressedStaleAppId = 0;
  private parentalAppId = -1;
  private parentalWaitStartedAt = 0;
  private pollTimer: number | undefined;
  private retryTimer: number | undefined;
  private gameRegistration: Registration;
  private downloadRegistration: Registration;
  private resumeRegistration: Registration;
  private parentalRegistration: Registration;
  private notificationsRegistration: Registration;
  private screenshotRegistration: Registration;
  private communityNotificationsTimer: number | undefined;
  private communityNotificationStore: SteamServerNotificationStore | undefined;
  private communityNotificationObserver = new CommunityNotificationObserver();
  private lastNativeCommentAt = 0;
  private lastServerCommentAt = 0;
  private controllerMonitor: ControllerMonitor | undefined;

  start() {
    if (this.alive) return;
    this.alive = true;
    this.registerSteamEvents();
    this.observeRunningApp("startup");
    this.pollTimer = window.setInterval(() => this.observeRunningApp("poll fallback"), 2000);
    console.log("[SignalBar] background runtime started");
  }

  stop() {
    this.alive = false;
    if (this.pollTimer !== undefined) window.clearInterval(this.pollTimer);
    if (this.communityNotificationsTimer !== undefined) {
      window.clearInterval(this.communityNotificationsTimer);
      this.communityNotificationsTimer = undefined;
    }
    if (this.retryTimer !== undefined) window.clearTimeout(this.retryTimer);
    this.gameRegistration?.unregister?.();
    this.downloadRegistration?.unregister?.();
    this.resumeRegistration?.unregister?.();
    this.parentalRegistration?.unregister?.();
    this.notificationsRegistration?.unregister?.();
    this.screenshotRegistration?.unregister?.();
    this.communityNotificationStore = undefined;
    this.communityNotificationObserver.reset();
    this.lastNativeCommentAt = 0;
    this.lastServerCommentAt = 0;
    void this.controllerMonitor?.stop().then(() => resetControllers()).catch(console.warn);
    void setSteamActivity(false, "").catch(() => undefined);
    console.log("[SignalBar] background runtime stopped");
  }

  private observeRunningApp(source: string) {
    const app = runningApp();
    if (this.suppressedStaleAppId && app.appid === this.suppressedStaleAppId) {
      this.requestGame(0, "", `${source}, stale AppID suppressed`);
      return;
    }
    if (app.appid !== this.suppressedStaleAppId) this.suppressedStaleAppId = 0;
    this.requestGame(app.appid, app.title, source);
  }

  private requestGame(appid: number, title: string, source: string) {
    if (!this.alive) return;
    const normalized = normalizeAppId(appid);
    const next = {
      appid: normalized,
      title: normalized > 0 ? String(title || "") : "",
      source: String(source || "unknown"),
    };
    const changedApp = next.appid !== this.desired.appid;
    this.desired = next;
    this.reportedAppId = next.appid;
    if (changedApp) {
      this.artworkGeneration += 1;
    }
    void this.flushGameState();
  }

  private async flushGameState() {
    if (this.syncing || !this.alive) return;
    this.syncing = true;
    try {
      while (this.alive) {
        const current = { ...this.desired };
        const key = `${current.appid}:${current.title}`;
        if (key === this.confirmedKey) break;
        try {
          const syncStartedAt = Date.now();
          const status = await gameChanged(current.appid, current.title);
          const syncMs = Date.now() - syncStartedAt;
          this.confirmedKey = key;
          this.parentalWaitStartedAt = current.appid > 0 ? Date.now() : 0;
          void reportRuntimeDiagnostic(
            "game_synced", current.appid, current.source, syncMs,
          ).catch((error) => console.warn("[SignalBar] runtime diagnostic failed", error));
          // Register only after the backend has accepted the new AppID. Some
          // Steam builds invoke this callback immediately on registration.
          this.registerParentalSignal(current.appid);
          if (current.appid > 0) {
            const generation = this.artworkGeneration;
            void this.syncArtwork(current.appid, status, generation);
          }
        } catch (error) {
          console.warn("[SignalBar] background game sync failed; retrying", error);
          this.scheduleRetry();
          break;
        }
      }
    } finally {
      this.syncing = false;
    }
  }

  private scheduleRetry() {
    if (!this.alive || this.retryTimer !== undefined) return;
    this.retryTimer = window.setTimeout(() => {
      this.retryTimer = undefined;
      void this.flushGameState();
    }, 1000);
  }

  private async syncArtwork(appid: number, status: Status, generation: number) {
    try {
      const artwork = await getArtwork(appid, status.artwork_source);
      if (!this.alive || generation !== this.artworkGeneration || this.desired.appid !== appid) return;
      if (!artwork.found || !artwork.data_uri || !artwork.fingerprint || artwork.cached) return;
      const result = await sampleArtwork(artwork.data_uri, status.artwork_mode, status.artwork_manual_y);
      if (!this.alive || generation !== this.artworkGeneration || this.desired.appid !== appid) return;
      await submitArtwork(
        appid,
        artwork.fingerprint,
        result.colors,
        result.y,
        artwork.filename ?? "",
        artwork.source ?? status.artwork_source,
      );
    } catch (error) {
      console.warn("[SignalBar] background artwork sampling failed", error);
    }
  }

  private registerParentalSignal(appid: number) {
    if (appid === this.parentalAppId) return;
    this.parentalAppId = appid;
    this.parentalRegistration?.unregister?.();
    this.parentalRegistration = undefined;
    try {
      this.parentalRegistration = SteamClient?.Parental?.RegisterForParentalPlaytimeWarnings?.(
        (minutes: unknown) => {
          const value = Number(minutes);
          if (!Number.isFinite(value)) return;
          const callbackDelay = this.parentalWaitStartedAt
            ? Math.max(0, Date.now() - this.parentalWaitStartedAt)
            : 0;
          this.parentalWaitStartedAt = 0;
          void reportRuntimeDiagnostic(
            "parental_received", appid, "Steam callback", callbackDelay,
          ).catch((error) => console.warn("[SignalBar] runtime diagnostic failed", error));
          void reportParentalMinutes(value).catch((error) => {
            console.warn("[SignalBar] parental playtime signal failed", error);
          });
        },
      );
    } catch (error) {
      console.warn("[SignalBar] Steam Families playtime hook unavailable", error);
    }
  }

  private registerSteamEvents() {
    this.registerParentalSignal(0);
    this.registerLightEvents();
    this.registerControllerSignals();
    try {
      this.gameRegistration = SteamClient?.GameSessions?.RegisterForAppLifetimeNotifications?.((event: any) => {
        const appid = normalizeAppId(event?.unAppID);
        if (event?.bRunning && appid > 0) {
          this.suppressedStaleAppId = 0;
          this.requestGame(appid, titleFor(appid) || runningApp().title, "Steam lifetime event");
        } else if (appid > 0 && (appid === this.reportedAppId || appid === this.suppressedStaleAppId)) {
          this.suppressedStaleAppId = appid;
          this.requestGame(0, "", "Steam lifetime event");
        }
      });
    } catch (error) {
      console.warn("[SignalBar] Steam game hook unavailable", error);
    }
    try {
      this.resumeRegistration = SteamClient?.System?.RegisterForOnResumeFromSuspend?.(() => {
        void this.controllerMonitor?.refresh();
        const stale = runningApp();
        if (stale.appid > 0) this.suppressedStaleAppId = stale.appid;
        this.requestGame(0, "", "resume from suspend");
      });
    } catch (error) {
      console.warn("[SignalBar] Steam resume hook unavailable", error);
    }
    try {
      this.downloadRegistration = SteamClient?.Downloads?.RegisterForDownloadOverview?.((overview: any) => {
        const active = overview?.update_state && overview.update_state !== "None";
        void setSteamActivity(Boolean(active), active ? "Steam download activity" : "").catch(console.warn);
      });
    } catch (error) {
      console.warn("[SignalBar] Steam download hook unavailable", error);
    }
  }

  private emitLightEvent(kind: LightEvent) {
    if (!this.alive) return;
    void triggerEvent(kind, false, "").catch((error) => {
      console.warn(`[SignalBar] ${kind} event was not delivered`, error);
    });
  }

  private registerLightEvents() {
    try {
      this.screenshotRegistration = SteamClient?.GameSessions?.RegisterForScreenshotNotification?.((notice: any) => {
        if (screenshotWasCaptured(notice)) this.emitLightEvent("screenshot");
      });
    } catch (error) {
      console.warn("[SignalBar] screenshot hook unavailable", error);
    }
    try {
      // The callback's index identifies a notification-list position, not a
      // durable event ID. Caching it could suppress later, unrelated notices.
      this.notificationsRegistration = SteamClient?.Notifications?.RegisterForNotifications?.(
        (_index: number, type: number) => {
          if (!this.alive) return;
          const numericType = Number(type);
          const kind = classifySteamNotification(numericType);
          if (!kind) return;
          if (numericType === 27) {
            const now = Date.now();
            const duplicatesServerEvent = now - this.lastServerCommentAt < 2500;
            this.lastNativeCommentAt = now;
            if (duplicatesServerEvent) return;
          }
          this.emitLightEvent(kind);
        },
      );
    } catch (error) {
      console.warn("[SignalBar] Steam notification hook unavailable", error);
    }
    this.communityNotificationObserver.reset();
    this.lastNativeCommentAt = 0;
    this.lastServerCommentAt = 0;
    this.scanCommunityNotifications();
    this.communityNotificationsTimer = window.setInterval(
      () => this.scanCommunityNotifications(),
      1000,
    );
  }

  private scanCommunityNotifications() {
    if (!this.alive) return;
    try {
      if (!this.communityNotificationStore) {
        this.communityNotificationStore = findModuleExport(isSteamServerNotificationStore);
        if (this.communityNotificationStore) {
          console.log("[SignalBar] Steam Community notification centre connected");
        }
      }
      const events = this.communityNotificationObserver.scan(this.communityNotificationStore);
      events.forEach((event) => {
        if (event.type === 3) {
          const now = Date.now();
          const duplicatesNativeEvent = now - this.lastNativeCommentAt < 2500;
          this.lastServerCommentAt = now;
          if (duplicatesNativeEvent) return;
        }
        this.emitLightEvent("notification");
      });
    } catch (error) {
      console.warn("[SignalBar] Steam Community notification hook unavailable", error);
    }
  }

  private registerControllerSignals() {
    let controllerStore: SteamControllerStore | undefined;
    this.controllerMonitor = new ControllerMonitor({
      discover: () => findModuleExport(isSteamInputService),
      readStore: () => {
        controllerStore ??= findModuleExport(isSteamControllerStore);
        return controllerStore?.GetControllers();
      },
      publish: updateControllers,
      diagnose: reportControllerTelemetry,
    });
    this.controllerMonitor.start();
  }
}

export function startSignalBarRuntime() {
  const runtime = new SignalBarRuntime();
  runtime.start();
  return runtime;
}
