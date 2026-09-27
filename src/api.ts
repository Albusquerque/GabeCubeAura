import { callable } from "@decky/api";
import type { ArtworkPayload, Status, WeatherLocation, WeatherCondition } from "./types";
import type { ControllerTelemetry } from "./controller_monitor";

export const getStatus = callable<[], Status>("get_status");
export const exportConfiguration = callable<[], ConfigurationExportResult>("export_configuration");
export const importConfiguration = callable<[path: string], Status>("import_configuration");
export const resetConfiguration = callable<[], Status>("reset_configuration");
export const setMode = callable<[mode: string], Status>("set_mode");
export const setGameDisplay = callable<[appid: number, mode: string], Status>("set_game_display");
export const setSetting = callable<[key: string, value: unknown], Status>("set_setting");
export const setArtworkSetting = callable<[appid: number, key: string, value: unknown], Status>("set_artwork_setting");
export const setLaunchArtworkSetting = callable<[appid: number, key: string, value: unknown], Status>("set_launch_artwork_setting");
export const gameChanged = callable<[appid: number, title: string, launch: boolean], Status>("game_changed");
export const getArtwork = callable<[appid: number, source: string, purpose: "artwork" | "launch"], ArtworkPayload>("get_artwork");
export const submitArtwork = callable<[
  appid: number,
  fingerprint: string,
  colors: number[][],
  sampleY: number,
  dominantPalettes: { "2": number[][]; "3": number[][] },
  filename: string,
  source: string,
  purpose: "artwork" | "launch",
], Status>("submit_artwork");
export const previewLaunchArtwork = callable<[], boolean>("preview_launch_artwork");
export const previewCustomization = callable<[], boolean>("preview_customization");
export const setSteamActivity = callable<[active: boolean, reason: string], boolean>("set_steam_activity");
export const reportRuntimeDiagnostic = callable<[
  event: string,
  appid: number,
  source: string,
  durationMs: number,
], boolean>("report_runtime_diagnostic");
export const reportParentalMinutes = callable<[minutes: number], Status>("report_parental_minutes");
export const startFreeTimer = callable<[minutes: number], Status>("start_free_timer");
export const stopFreeTimer = callable<[], Status>("stop_free_timer");
export const previewCountdown = callable<[], Status>("preview_countdown");
export const triggerEvent = callable<[kind: string, preview: boolean, variant: string], boolean>("trigger_event");
export const updateControllers = callable<[controllers: ControllerBatteryUpdate[], source: string], boolean>("update_controllers");
export const resetControllers = callable<[], boolean>("reset_controllers");
export const reportControllerTelemetry = callable<[state: ControllerTelemetry], boolean>("report_controller_telemetry");
export const previewController = callable<[kind: string, variant: string], boolean>("preview_controller");
export const searchWeatherCities = callable<[query: string], { results: WeatherLocation[]; error: string }>("search_weather_cities");
export const previewWeather = callable<[condition: WeatherCondition, variant: number], boolean>("preview_weather");
export const stopWeatherPreview = callable<[], boolean>("stop_weather_preview");

export interface ConfigurationExportResult {
  path: string;
  exported_at: string;
}

export interface ControllerBatteryUpdate {
  id: string;
  name: string;
  percent: number | null;
  level: number | null;
  charging: boolean | null;
}
