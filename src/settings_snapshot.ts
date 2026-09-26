import { CONTROLLER_VARIANTS } from "./controller_variants";
import { EVENT_VARIANTS } from "./event_variants";
import { WEATHER_VARIANTS } from "./weather_variants";
import type { Status } from "./types";

export interface SettingsSnapshotSection {
  title: string;
  lines: string[];
}

const onOff = (value: boolean) => value ? "On" : "Off";
const percent = (value: number) => `${Math.round(value * 100)}%`;
const rgbHex = (value: [number, number, number]) =>
  `#${value.map((channel) => channel.toString(16).padStart(2, "0")).join("").toUpperCase()}`;
const selectedLabel = (options: readonly { data: string; label: string }[], value: string) =>
  options.find((option) => option.data === value)?.label ?? value;

const artworkSource = { hero: "Library Hero", header: "Library Header", capsule: "Library Capsule" };
const artworkRow = { auto: "Auto", center: "Centre", lower: "Lower", manual: "Manual" };
const displayMode = { artwork: "Artwork", performance: "Performance", events: "Signals only", disabled: "Disabled" };
const response = { responsive: "Responsive", balanced: "Balanced", smooth: "Smooth" };
const palette = {
  thermal: "Cyan → amber → red", classic: "Green → yellow → red",
  icefire: "Blue → violet → pink", custom: "Custom colours",
};
const alertContext = { off: "Off", home: "Home", game: "In game", both: "Home + in game" };
const chargingMode = {
  off: "Off", brief: "Brief (~3 s)",
  "continuous-home": "Continuous on Home", "continuous-everywhere": "Continuous everywhere",
};

/** One concise, read-only view of the settings exposed across the Decky tabs. */
export function buildSettingsSnapshot(status: Status): SettingsSnapshotSection[] {
  const gameRunning = status.game.appid > 0 || Boolean(status.game.title);
  const source = (value: Status["artwork_source"]) => artworkSource[value];
  const row = (value: Status["artwork_mode"]) => artworkRow[value];
  const controller = (kind: keyof typeof CONTROLLER_VARIANTS, value: string) =>
    selectedLabel(CONTROLLER_VARIANTS[kind], value);
  const event = (kind: keyof typeof EVENT_VARIANTS, value: string) =>
    selectedLabel(EVENT_VARIANTS[kind], value);
  return [
    {
      title: "Display",
      lines: [
        `Default ${displayMode[status.default_mode]} · Active ${displayMode[status.mode]}`,
        gameRunning
          ? `Game ${status.game.title || "Running game"} · Override ${status.display_override === "inherit" ? "Use default" : displayMode[status.display_override]}`
          : "Home · Game override applies when a game runs",
      ],
    },
    {
      title: "Artwork",
      lines: [
        `Default ${source(status.artwork_default_source)} · ${row(status.artwork_default_mode)} · saved manual ${percent(status.artwork_default_manual_y)}`,
        gameRunning
          ? `This game ${source(status.artwork_source)} · ${row(status.artwork_mode)} · manual ${percent(status.artwork_manual_y)} · profile ${status.artwork_custom ? "saved" : "default"}`
          : "This game: none; defaults shown above",
      ],
    },
    {
      title: "Performance",
      lines: [
        `Meter ${status.performance_metric === "mixed" ? "CPU + GPU" : status.performance_metric.toUpperCase()} · Response ${response[status.performance_smoothing]} · Home ${onOff(status.performance_always)}`,
        `Fill ${status.mixed_direction === "mirrored" ? "Mirrored" : "Both left to right"} (saved) · Palette ${palette[status.temperature_palette]}`,
        `Cool ${status.cool_temp_c}°C · Hot ${status.hot_temp_c}°C · saved custom ${rgbHex(status.temperature_custom_cool)} / ${rgbHex(status.temperature_custom_middle)} / ${rgbHex(status.temperature_custom_hot)}`,
      ],
    },
    {
      title: "Playtime",
      lines: [
        `Steam Families ${onOff(status.parental_countdown_enabled)} · Start ${status.countdown_colour} · Full bar ${status.countdown_full_bar_minutes === 0 ? "timer duration" : `${status.countdown_full_bar_minutes / 60} h`}`,
        `Personal timer preset ${status.free_timer_minutes} min`,
      ],
    },
    {
      title: "Light events",
      lines: [
        `Master ${onOff(status.events_enabled)} · Notifications ${onOff(status.event_notifications_enabled)}: ${event("notification", status.event_notification_variant)}`,
        `Achievements ${onOff(status.event_achievements_enabled)}: ${event("achievement", status.event_achievement_variant)}`,
        `Screenshots ${onOff(status.event_screenshots_enabled)}: ${event("screenshot", status.event_screenshot_variant)}`,
        `Recording ${onOff(status.event_recording_enabled)} · Red marker isolation ${onOff(status.recording_marker_isolation)}`,
      ],
    },
    {
      title: "Controllers",
      lines: [
        `Gauge ${status.controller_battery_display === "home" ? "On Home" : status.controller_battery_display === "game" ? "In game" : status.controller_battery_display === "everywhere" ? "Everywhere" : "Off"} · Brief alerts ${onOff(status.controller_alerts_enabled)} · Where ${alertContext[status.controller_alert_context]}`,
        `Charging ${chargingMode[status.controller_charging_mode]} · Low warning ≤${status.controller_low_threshold}%`,
        `Connect ${onOff(status.controller_connect_enabled)}: ${controller("connect", status.controller_connect_variant)} · Single ${controller("persistent", status.controller_persistent_variant)}`,
        `Low ${onOff(status.controller_low_enabled)}: ${controller("low", status.controller_low_variant)} · Charge style ${controller("charging", status.controller_charging_variant)}`,
        `Two controllers ${controller("duo", status.controller_duo_variant)} · Brightness ${status.controller_gauge_brightness}%`,
        `Colours healthy ${rgbHex(status.controller_colour_normal)} · medium ${rgbHex(status.controller_colour_medium)} · low ${rgbHex(status.controller_colour_low)} · charge ${rgbHex(status.controller_colour_charging)}`,
      ],
    },
    {
      title: "Weather",
      lines: [
        `City ${status.weather_location ? `${status.weather_location.name}, ${status.weather_location.country}` : "none"} · Display ${status.weather_display}`,
        `SteamOS top bar ${onOff(status.weather_topbar_enabled)} · ${status.weather_temperature_unit === "fahrenheit" ? "Fahrenheit" : "Celsius"} · experimental`,
        `Weather LED brightness ${status.weather_brightness}% · Faint LED cutoff ${status.weather_shadow_cutoff} (linear RGB)`,
        ...(["clear_day", "clear_night", "rain", "cloud", "breaks", "breaks_night", "snow", "storm"] as const).map((condition) =>
          `${condition.replace("_", " ")}: ${WEATHER_VARIANTS[condition][status[`weather_${condition}_variant`]]?.label ?? "unknown"}`),
      ],
    },
    {
      title: "Advanced",
      lines: [
        `Reverse physical LEDs ${onOff(status.reverse_led_order)} · Extra dark LEDs ${status.countdown_dark_edge_compensation} (Countdown + Performance)`,
      ],
    },
  ];
}
