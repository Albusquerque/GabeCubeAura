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
  setScreenSyncContext,
} from "./api";
import { sampleArtwork } from "./artwork";
import { ControllerMonitor, isSteamInputService } from "./controller_monitor";
import { isSteamControllerStore } from "./controller_battery";
import type { SteamControllerStore } from "./controller_battery";
import { normalizeAppId } from "./steam_app_id";
import { GameSessionLatch } from "./game_session";
import type { GameSessionDecision } from "./game_session";
import {
  isSteamScreensaverService,
  screensaverActiveFromResponse,
} from "./steam_screensaver";
import type { SteamScreensaverService } from "./steam_screensaver";
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

class GabeCubeAuraRuntime {
  private alive = false;
  private desired = { appid: 0, title: "", source: "startup", launchSequence: 0 };
  private session = new GameSessionLatch();
  private baselineEstablished = false;
  private confirmedKey = "";
  private syncing = false;
  private artworkGeneration = 0;
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
  private downloadActive = false;
  private screensaverService: SteamScreensaverService | undefined;
  private screensaverPolling = false;
  private screensaverFailures = 0;

  start() {
    if (this.alive) return;
    this.alive = true;
    this.applySessionDecision(this.session.seed(runningApp()));
    // Establish the observed AppID before lifetime notifications are attached.
    // Some Steam builds replay the currently running session immediately.
    this.baselineEstablished = true;
    this.registerSteamEvents();
    this.pollTimer = window.setInterval(() => {
      this.observeRunningApp();
      this.renewSteamActivity();
      void this.pollScreensaver();
    }, 2000);
    void setScreenSyncContext("steam-screensaver", false, "waiting", "").catch(() => undefined);
    void this.pollScreensaver();
    console.log("[GabeCubeAura] background runtime started");
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
    this.downloadActive = false;
    this.screensaverService = undefined;
    this.screensaverFailures = 0;
    void this.controllerMonitor?.stop().then(() => resetControllers()).catch(console.warn);
    void setSteamActivity(false, "").catch(() => undefined);
    void setScreenSyncContext("steam-screensaver", false, "waiting", "").catch(() => undefined);
    console.log("[GabeCubeAura] background runtime stopped");
  }

  private observeRunningApp() {
    this.applySessionDecision(this.session.observePoll(runningApp()));
    void reportRuntimeDiagnostic(
      "heartbeat", this.desired.appid, "background runtime", 0,
    ).catch(() => undefined);
  }

  private applySessionDecision(decision: GameSessionDecision) {
    if (decision.action === "retain") {
      void reportRuntimeDiagnostic(
        "game_retained", decision.appid, decision.source, 0,
      ).catch(() => undefined);
      return;
    }
    if (decision.action === "update") {
      this.requestGame(
        decision.appid, decision.title, decision.source, decision.launch,
      );
    }
  }

  private requestGame(appid: number, title: string, source: string, launch = false) {
    if (!this.alive) return;
    const normalized = normalizeAppId(appid);
    const previousAppId = this.desired.appid;
    const changedApp = normalized !== previousAppId;
    const isLaunch = normalized > 0 && changedApp && this.baselineEstablished && Boolean(launch);
    const next = {
      appid: normalized,
      title: normalized > 0 ? String(title || "") : "",
      source: String(source || "unknown"),
      launchSequence: this.desired.launchSequence + (isLaunch ? 1 : 0),
    };
    this.desired = next;
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
        const key = `${current.appid}:${current.title}:${current.launchSequence}`;
        if (key === this.confirmedKey) break;
        try {
          const syncStartedAt = Date.now();
          const launch = current.launchSequence !== this.desired.launchSequence
            ? false : current.launchSequence > 0 && current.appid > 0;
          const status = await gameChanged(current.appid, current.title, launch);
          const syncMs = Date.now() - syncStartedAt;
          this.confirmedKey = key;
          this.baselineEstablished = true;
          this.parentalWaitStartedAt = current.appid > 0 ? Date.now() : 0;
          void reportRuntimeDiagnostic(
            "game_synced", current.appid, current.source, syncMs,
          ).catch((error) => console.warn("[GabeCubeAura] runtime diagnostic failed", error));
          // Register only after the backend has accepted the new AppID. Some
          // Steam builds invoke this callback immediately on registration.
          this.registerParentalSignal(current.appid);
          if (current.appid > 0) {
            const generation = this.artworkGeneration;
            void this.syncArtwork(current.appid, status, generation);
          }
        } catch (error) {
          console.warn("[GabeCubeAura] background game sync failed; retrying", error);
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
    await Promise.all([
      this.syncArtworkPurpose(appid, status, generation, status.artwork_source, "artwork"),
      this.syncArtworkPurpose(appid, status, generation, status.launch_artwork_source, "launch"),
    ]);
  }

  private async syncArtworkPurpose(
    appid: number,
    status: Status,
    generation: number,
    source: Status["artwork_source"],
    purpose: "artwork" | "launch",
  ) {
    try {
      const artwork = await getArtwork(appid, source, purpose);
      if (!this.alive || generation !== this.artworkGeneration || this.desired.appid !== appid) return;
      if (!artwork.found || !artwork.data_uri || !artwork.fingerprint || artwork.cached) return;
      const result = await sampleArtwork(artwork.data_uri, status.artwork_mode, status.artwork_manual_y);
      if (!this.alive || generation !== this.artworkGeneration || this.desired.appid !== appid) return;
      await submitArtwork(
        appid,
        artwork.fingerprint,
        result.colors,
        result.y,
        result.dominantPalettes,
        artwork.filename ?? "",
        artwork.source ?? source,
        purpose,
      );
    } catch (error) {
      console.warn(`[GabeCubeAura] background ${purpose} artwork sampling failed`, error);
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
          ).catch((error) => console.warn("[GabeCubeAura] runtime diagnostic failed", error));
          void reportParentalMinutes(value).catch((error) => {
            console.warn("[GabeCubeAura] parental playtime signal failed", error);
          });
        },
      );
    } catch (error) {
      console.warn("[GabeCubeAura] Steam Families playtime hook unavailable", error);
    }
  }

  private registerSteamEvents() {
    this.registerParentalSignal(0);
    this.registerLightEvents();
    this.registerControllerSignals();
    try {
      const registerLifetime = SteamClient?.GameSessions?.RegisterForAppLifetimeNotifications;
      if (typeof registerLifetime === "function") {
        this.session.setLifetimeAvailable(true);
        this.gameRegistration = registerLifetime.call(SteamClient.GameSessions, (event: any) => {
          const appid = normalizeAppId(event?.unAppID);
          this.applySessionDecision(this.session.observeLifetime(
            appid,
            Boolean(event?.bRunning),
            titleFor(appid) || runningApp().title,
          ));
        });
      }
    } catch (error) {
      this.session.setLifetimeAvailable(false);
      console.warn("[GabeCubeAura] Steam game hook unavailable", error);
    }
    try {
      this.resumeRegistration = SteamClient?.System?.RegisterForOnResumeFromSuspend?.(() => {
        void this.controllerMonitor?.refresh();
        const stale = runningApp();
        this.applySessionDecision(this.session.suspend(stale.appid));
      });
    } catch (error) {
      console.warn("[GabeCubeAura] Steam resume hook unavailable", error);
    }
    try {
      this.downloadRegistration = SteamClient?.Downloads?.RegisterForDownloadOverview?.((overview: any) => {
        const active = overview?.update_state && overview.update_state !== "None";
        this.downloadActive = Boolean(active);
        this.renewSteamActivity();
      });
    } catch (error) {
      console.warn("[GabeCubeAura] Steam download hook unavailable", error);
    }
  }

  private renewSteamActivity() {
    void setSteamActivity(
      this.downloadActive,
      this.downloadActive ? "Steam download activity" : "",
    ).catch(console.warn);
  }

  private async pollScreensaver() {
    if (!this.alive || this.screensaverPolling) return;
    this.screensaverPolling = true;
    try {
      this.screensaverService ??= findModuleExport(isSteamScreensaverService);
      if (!this.screensaverService) {
        await setScreenSyncContext(
          "steam-screensaver", false, "unavailable", "Steam screensaver service was not found",
        );
        return;
      }
      const response = await Promise.race([
        Promise.resolve(this.screensaverService.GetActiveState({})),
        new Promise<never>((_resolve, reject) => window.setTimeout(
          () => reject(new Error("Steam screensaver state timed out")),
          1200,
        )),
      ]);
      const active = screensaverActiveFromResponse(response);
      if (active === null) throw new Error("Steam screensaver state was not recognised");
      this.screensaverFailures = 0;
      await setScreenSyncContext("steam-screensaver", active, "available", "");
    } catch (error) {
      this.screensaverFailures += 1;
      if (this.screensaverFailures >= 2) this.screensaverService = undefined;
      await setScreenSyncContext(
        "steam-screensaver",
        false,
        "error",
        String(error instanceof Error ? error.message : error).slice(0, 180),
      ).catch(() => undefined);
    } finally {
      this.screensaverPolling = false;
    }
  }

  private emitLightEvent(kind: LightEvent) {
    if (!this.alive) return;
    void triggerEvent(kind, false, "").catch((error) => {
      console.warn(`[GabeCubeAura] ${kind} event was not delivered`, error);
    });
  }

  private registerLightEvents() {
    try {
      this.screenshotRegistration = SteamClient?.GameSessions?.RegisterForScreenshotNotification?.((notice: any) => {
        if (screenshotWasCaptured(notice)) this.emitLightEvent("screenshot");
      });
    } catch (error) {
      console.warn("[GabeCubeAura] screenshot hook unavailable", error);
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
      console.warn("[GabeCubeAura] Steam notification hook unavailable", error);
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
          console.log("[GabeCubeAura] Steam Community notification centre connected");
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
      console.warn("[GabeCubeAura] Steam Community notification hook unavailable", error);
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

export function startGabeCubeAuraRuntime() {
  const runtime = new GabeCubeAuraRuntime();
  runtime.start();
  return runtime;
}
