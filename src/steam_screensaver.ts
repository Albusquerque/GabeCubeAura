export interface SteamScreensaverService {
  GetActiveState(request: Record<string, never>): unknown;
  ForceScreensaver(request: unknown): unknown;
}

export function isSteamScreensaverService(value: unknown): value is SteamScreensaverService {
  const candidate = value as Partial<SteamScreensaverService> | null | undefined;
  return Boolean(
    candidate
    && typeof candidate.GetActiveState === "function"
    && typeof candidate.ForceScreensaver === "function"
  );
}

function bodyOf(response: any): any {
  try {
    if (typeof response?.Body === "function") return response.Body();
  } catch {
    return null;
  }
  return response?.body ?? response?.response ?? response;
}

export function screensaverActiveFromResponse(response: unknown): boolean | null {
  const body = bodyOf(response);
  for (const key of ["active", "bActive", "is_active", "isActive"]) {
    let value = body?.[key];
    try {
      if (typeof value === "function") value = value.call(body);
    } catch {
      return null;
    }
    if (typeof value === "boolean") return value;
    if (value === 0 || value === 1) return Boolean(value);
  }
  return null;
}
