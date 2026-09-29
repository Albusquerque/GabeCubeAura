import type { UpdateStatus } from "./types";

export function shouldNotifyUpdate(update: UpdateStatus, gameAppId: number): boolean {
  return update.phase === "available"
    && update.notifications
    && Boolean(update.available_version)
    && update.notified_version !== update.available_version
    && gameAppId <= 0;
}
