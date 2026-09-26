import test from "node:test";
import assert from "node:assert/strict";
import { buildSettingsSnapshot } from "../../src/settings_snapshot";
import type { Status } from "../../src/types";

const sampleStatus = {
    version: "0.5.0-beta.9",
    default_mode: "artwork", mode: "performance", display_override: "performance",
    game: { appid: 42, title: "Example Game" },
    artwork_default_source: "hero", artwork_default_mode: "auto", artwork_default_manual_y: .5,
    artwork_source: "header", artwork_mode: "manual", artwork_manual_y: .83, artwork_custom: true,
    performance_metric: "mixed", performance_smoothing: "balanced", performance_always: true,
    mixed_direction: "mirrored", temperature_palette: "custom",
    cool_temp_c: 45, hot_temp_c: 80,
    temperature_custom_cool: [12, 34, 56], temperature_custom_middle: [120, 130, 140], temperature_custom_hot: [255, 0, 9],
    parental_countdown_enabled: true, countdown_colour: "cyan", countdown_full_bar_minutes: 120, free_timer_minutes: 45,
    events_enabled: true, event_notifications_enabled: true, event_achievements_enabled: false,
    event_screenshots_enabled: true, event_recording_enabled: true, recording_marker_isolation: true,
    event_notification_variant: "notification-echo", event_achievement_variant: "achievement-confetti",
    event_screenshot_variant: "screenshot-bloom",
    controller_battery_display: "everywhere", controller_alerts_enabled: true, controller_alert_context: "both",
    controller_charging_mode: "continuous-home", controller_low_threshold: 20,
    controller_connect_enabled: true, controller_low_enabled: true,
    controller_connect_variant: "orbit", controller_persistent_variant: "tip",
    controller_low_variant: "drain", controller_charging_variant: "current", controller_duo_variant: "twin",
    controller_gauge_brightness: 65,
    controller_colour_normal: [0, 200, 25], controller_colour_medium: [240, 120, 0],
    controller_colour_low: [220, 12, 24], controller_colour_charging: [0, 80, 180],
    weather_display: "off", weather_location: null, weather_topbar_enabled: false,
    weather_brightness: 65, weather_shadow_cutoff: 25,
    weather_clear_day_variant: 0, weather_clear_night_variant: 0, weather_rain_variant: 0,
    weather_cloud_variant: 0, weather_breaks_variant: 0, weather_breaks_night_variant: 0, weather_snow_variant: 0, weather_storm_variant: 0,
    reverse_led_order: true, countdown_dark_edge_compensation: 2,
    debug: { led_path: "/private/device/path" },
} as unknown as Status;

test("debug snapshot includes every settings group and distinguishes defaults from the running game's choices", () => {
  const snapshot = buildSettingsSnapshot(sampleStatus);
  assert.deepEqual(snapshot.map((section) => section.title),
    ["Display", "Artwork", "Performance", "Playtime", "Light events", "Controllers", "Weather", "Advanced"]);
  const text = snapshot.flatMap((section) => section.lines).join("\n");
  for (const expected of ["Example Game", "Library Hero", "Library Header", "83%", "CPU + GPU",
    "Balanced", "Mirrored", "#0C2238", "2 h", "Centre echo", "Return + confetti",
    "Expanding echoes", "Continuous on Home", "Bright tip", "#00C819", "Weather LED brightness 65%", "Extra dark LEDs 2"]) {
    assert.ok(text.includes(expected), expected);
  }
  assert.ok(!text.includes("/private/device/path"));
  assert.ok(!text.includes("42"));
});

test("snapshot shows Home defaults without inventing a game-specific profile", () => {
  const status = { ...sampleStatus,
    game: { appid: 0, title: "" },
    default_mode: "artwork", mode: "artwork", display_override: "inherit",
    artwork_default_source: "hero", artwork_default_mode: "auto", artwork_default_manual_y: .5,
    artwork_source: "hero", artwork_mode: "auto", artwork_manual_y: .5, artwork_custom: false,
  } as Status;
  const snapshot = buildSettingsSnapshot(status);
  assert.match(snapshot[0].lines[1], /^Home/);
  assert.match(snapshot[1].lines[1], /^This game: none/);
});

test("snapshot names the Signals only display mode", () => {
  const status = { ...sampleStatus,
    game: { appid: 42, title: "StripMine" },
    default_mode: "events", mode: "events", display_override: "performance",
  } as Status;
  const snapshot = buildSettingsSnapshot(status);
  assert.ok(snapshot[0].lines[0].includes("Signals only"));
});

test("weather snapshot lists retained loops without removed temperature controls", () => {
  const snapshot = buildSettingsSnapshot({ ...sampleStatus, weather_rain_variant: 1 });
  const weather = snapshot.find((section) => section.title === "Weather");
  assert.ok(weather?.lines.some((line) => line.includes("rain: Pearl rain")));
  assert.ok(!weather?.lines.some((line) => /Temperature|halos/i.test(line)));
});
