export type SteamRegistration = { unregister?: () => void };

export type ParentalRegistrationSource = {
  owner: unknown;
  register: (callback: (minutes: unknown) => void) => SteamRegistration | undefined;
};

export type ParentalRegistrationState = "idle" | "waiting" | "registered";

const RETRY_DELAYS_MS = [1000, 2000, 4000, 8000, 15000] as const;

/**
 * Keeps the Steam Families callback attached to the current game.
 *
 * SteamClient services can appear after a Decky plugin has started. A missing
 * service or registration handle is therefore treated as temporary and retried
 * with a bounded delay. Only a real unregisterable handle counts as success.
 */
export class ParentalPlaytimeSubscription {
  private targetAppId = 0;
  private registeredAppId = 0;
  private registration: SteamRegistration | undefined;
  private retryIndex = 0;
  private retryAt = 0;
  private generation = 0;

  constructor(
    private readonly source: () => ParentalRegistrationSource | undefined,
    private readonly onMinutes: (appid: number, minutes: number) => void,
    private readonly now: () => number = Date.now,
  ) {}

  selectApp(appid: number): ParentalRegistrationState {
    const next = Number.isFinite(appid) && appid > 0 ? Math.trunc(appid) : 0;
    if (next !== this.targetAppId) {
      this.release();
      this.targetAppId = next;
      this.retryIndex = 0;
      this.retryAt = 0;
      this.generation += 1;
    }
    return this.ensure();
  }

  ensure(): ParentalRegistrationState {
    if (this.targetAppId <= 0) return "idle";
    if (this.registration && this.registeredAppId === this.targetAppId) return "registered";
    if (this.now() < this.retryAt) return "waiting";

    const appid = this.targetAppId;
    const generation = this.generation;
    try {
      const source = this.source();
      if (!source || typeof source.register !== "function") {
        this.defer();
        return "waiting";
      }
      const registration = source.register.call(source.owner, (minutes: unknown) => {
        if (generation !== this.generation || appid !== this.targetAppId) return;
        const value = Number(minutes);
        if (Number.isFinite(value)) this.onMinutes(appid, value);
      });
      if (!registration || typeof registration.unregister !== "function") {
        this.defer();
        return "waiting";
      }
      this.registration = registration;
      this.registeredAppId = appid;
      this.retryIndex = 0;
      this.retryAt = 0;
      return "registered";
    } catch {
      this.defer();
      return "waiting";
    }
  }

  reset(): ParentalRegistrationState {
    const appid = this.targetAppId;
    this.release();
    this.targetAppId = appid;
    this.retryIndex = 0;
    this.retryAt = 0;
    this.generation += 1;
    return this.ensure();
  }

  stop() {
    this.release();
    this.targetAppId = 0;
    this.retryIndex = 0;
    this.retryAt = 0;
    this.generation += 1;
  }

  private defer() {
    const index = Math.min(this.retryIndex, RETRY_DELAYS_MS.length - 1);
    this.retryAt = this.now() + RETRY_DELAYS_MS[index];
    this.retryIndex = Math.min(index + 1, RETRY_DELAYS_MS.length - 1);
  }

  private release() {
    try {
      this.registration?.unregister?.();
    } catch {
      // Steam may invalidate registrations while changing account or resuming.
    }
    this.registration = undefined;
    this.registeredAppId = 0;
  }
}
