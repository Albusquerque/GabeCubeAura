export type LightEvent = "notification" | "achievement" | "screenshot" | "record-start" | "record-stop";

const COMMUNITY_NOTIFICATION_TYPES = new Set([
  3, // ESteamNotificationType_Comment: reply in a subscribed discussion.
  27, // ESteamNotificationType_PartnerEvent: followed group/community post.
]);

export type SteamServerNotificationItem = {
  notification_id?: string | number;
  notification_type?: number;
  hidden?: boolean;
};

export type SteamServerNotificationRollup = {
  type?: number;
  item?: SteamServerNotificationItem;
};

export type SteamServerNotificationStore = {
  m_bLoaded?: boolean;
  m_rgNotificationRollups?: SteamServerNotificationRollup[];
  BHasNotificationsData?: () => boolean;
};

export type CommunityNotificationEvent = {
  id: string;
  type: number;
};

// SteamClient.Notifications EClientNotificationType values in @decky/ui.
// Only events with dedicated patterns are special; every other valid Steam
// notification, including Community comments and future types, gets a signal.

export function classifySteamNotification(type: number): LightEvent | null {
  if (!Number.isSafeInteger(type) || type <= 0) return null;
  if (type === 5) return "achievement";
  if (type === 14) return "screenshot";
  if (type === 55) return "record-start";
  if (type === 56) return "record-stop";
  return "notification";
}

export function isSteamServerNotificationStore(value: unknown): value is SteamServerNotificationStore {
  if (!value || typeof value !== "object") return false;
  const candidate = value as SteamServerNotificationStore;
  return Array.isArray(candidate.m_rgNotificationRollups)
    && typeof candidate.BHasNotificationsData === "function";
}

function serverStoreIsReady(store: SteamServerNotificationStore): boolean {
  if (store.m_bLoaded === true) return true;
  try {
    return store.BHasNotificationsData?.() === true;
  } catch {
    return false;
  }
}

function notificationIdentity(item: SteamServerNotificationItem | undefined): string {
  const id = item?.notification_id;
  if (typeof id !== "string" && typeof id !== "number") return "";
  return String(id).trim();
}

export class CommunityNotificationObserver {
  private initialized = false;
  private readonly seen = new Set<string>();
  private readonly seenOrder: string[] = [];

  constructor(private readonly maxSeen = 1024) {}

  reset() {
    this.initialized = false;
    this.seen.clear();
    this.seenOrder.length = 0;
  }

  scan(store: SteamServerNotificationStore | undefined): CommunityNotificationEvent[] {
    if (!store || !serverStoreIsReady(store)) return [];
    const current = (store.m_rgNotificationRollups ?? [])
      .map((rollup) => {
        const type = Number(rollup?.item?.notification_type ?? rollup?.type);
        return {
          id: notificationIdentity(rollup?.item),
          type,
          hidden: rollup?.item?.hidden === true,
        };
      })
      .filter((event) => event.id && Number.isSafeInteger(event.type) && COMMUNITY_NOTIFICATION_TYPES.has(event.type));

    if (!this.initialized) {
      current.forEach((event) => this.remember(event.id));
      this.initialized = true;
      return [];
    }

    const fresh: CommunityNotificationEvent[] = [];
    current.forEach((event) => {
      if (this.seen.has(event.id)) return;
      this.remember(event.id);
      if (!event.hidden) fresh.push({ id: event.id, type: event.type });
    });
    return fresh;
  }

  private remember(id: string) {
    if (this.seen.has(id)) return;
    this.seen.add(id);
    this.seenOrder.push(id);
    while (this.seenOrder.length > Math.max(1, this.maxSeen)) {
      const oldest = this.seenOrder.shift();
      if (oldest) this.seen.delete(oldest);
    }
  }
}

export function screenshotWasCaptured(notification: { strOperation?: string } | null | undefined): boolean {
  return notification?.strOperation === "written";
}
