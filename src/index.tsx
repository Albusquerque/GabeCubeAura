import {
  ButtonItem,
  ConfirmModal,
  DropdownItem,
  Focusable,
  PanelSection,
  PanelSectionRow,
  Navigation,
  SidebarNavigation,
  SliderField,
  TextField,
  showModal,
  ToggleField,
  staticClasses,
} from "@decky/ui";
import { definePlugin, openFilePicker, routerHook } from "@decky/api";
import { useCallback, useEffect, useRef, useState } from "react";
import { TbCubeSpark } from "react-icons/tb";

import {
  exportConfiguration,
  exportUpdateTestReport,
  checkForUpdates,
  dismissUpdateError,
  importConfiguration,
  getArtwork,
  getStatus,
  getUpdateStatus,
  installPreparedUpdate,
  previewCountdown,
  previewCustomization,
  previewLaunchArtwork,
  previewScreenSync,
  previewController,
  previewWeather,
  prepareUpdate,
  resetConfiguration,
  runUpdateLabScenario,
  searchWeatherCities,
  setArtworkSetting,
  setLaunchArtworkSetting,
  setGameDisplay,
  setSetting,
  setUpdatePreferences,
  startFreeTimer,
  stopFreeTimer,
  submitArtwork,
  triggerEvent,
} from "./api";
import { sampleArtwork } from "./artwork";
import { PalettePreview } from "./components/PalettePreview";
import { CUSTOMIZATION_PATTERN_OPTIONS, LAUNCH_ARTWORK_PATTERN_OPTIONS, customizationPatternLabel } from "./customization_catalog";
import { CONTROLLER_VARIANTS } from "./controller_variants";
import { EVENT_VARIANTS } from "./event_variants";
import { hslStringToRgb, performancePreview, rgbToHsl } from "./performance";
import { startGabeCubeAuraRuntime } from "./runtime";
import { startUpdateNotifications } from "./update_notifications";
import { buildSettingsSnapshot } from "./settings_snapshot";
import { WEATHER_CONDITIONS, WEATHER_VARIANTS } from "./weather_variants";
import { startWeatherTopBar } from "./weather_topbar";
import type { ArtworkPayload, ArtworkSource, CompanionPriority, GameDisplay, HomeDisplay, RGB, Status, UpdateLabResult, UpdateStatus, WeatherCondition, WeatherLocation } from "./types";

const HOME_DISPLAY_OPTIONS: { data: HomeDisplay; label: string }[] = [
  { data: "steam", label: "GabeCubeAura Off" },
  { data: "customization", label: "Customization+" },
  { data: "performance", label: "Performance" },
  { data: "weather", label: "Weather" },
  { data: "controller", label: "Controller status" },
];

const GAME_DISPLAY_OPTIONS: { data: GameDisplay; label: string }[] = [
  { data: "steam", label: "GabeCubeAura Off" },
  { data: "customization", label: "Customization+" },
  { data: "artwork", label: "Artwork" },
  { data: "performance", label: "Performance" },
  { data: "screen_sync", label: "Screen Sync" },
  { data: "weather", label: "Weather" },
  { data: "controller", label: "Controller status" },
];

const UPDATE_INTERVAL_OPTIONS = [
  { data: 15, label: "15 minutes" },
  { data: 60, label: "1 hour" },
  { data: 180, label: "3 hours" },
  { data: 360, label: "6 hours" },
  { data: 720, label: "12 hours" },
  { data: 1440, label: "24 hours" },
];

const UPDATE_CHANNEL_OPTIONS = [
  { data: "stable", label: "Stable" },
  { data: "beta", label: "Beta" },
];

const displayLabel = (display: HomeDisplay | GameDisplay) => (
  [...HOME_DISPLAY_OPTIONS, ...GAME_DISPLAY_OPTIONS].find((item) => item.data === display)?.label ?? display
);

const ARTWORK_OPTIONS = [
  { data: "auto", label: "Auto (best row)" },
  { data: "center", label: "Centre" },
  { data: "lower", label: "Lower" },
  { data: "manual", label: "Manual" },
];

const ARTWORK_SOURCE_OPTIONS = [
  { data: "hero", label: "Library Hero (wide artwork)" },
  { data: "header", label: "Library Header" },
  { data: "capsule", label: "Library Capsule (vertical)" },
];

const LAUNCH_ARTWORK_COLOUR_OPTIONS = [
  { data: 2, label: "2 dominant colours" },
  { data: 3, label: "3 dominant colours" },
];

const LAUNCH_PALETTE_MODE_OPTIONS = [
  { data: "artwork", label: "From artwork" },
  { data: "custom", label: "Custom for this game" },
];

const CUSTOMIZATION_COLOUR_OPTIONS = [
  { data: 1, label: "1 colour" },
  { data: 2, label: "2 colours" },
  { data: 3, label: "3 colours" },
];

const CUSTOMIZATION_DIRECTION_OPTIONS = [
  { data: "forward", label: "Left to right" },
  { data: "reverse", label: "Right to left" },
];

const PERFORMANCE_OPTIONS = [
  { data: "gpu", label: "GPU" },
  { data: "cpu", label: "CPU" },
  { data: "mixed", label: "CPU + GPU" },
];
const SMOOTHING_OPTIONS = [
  { data: "responsive", label: "Responsive" },
  { data: "balanced", label: "Balanced" },
  { data: "smooth", label: "Smooth" },
];
const SCREEN_SYNC_STYLE_OPTIONS = [
  { data: "panorama", label: "Panorama (17 screen zones)" },
  { data: "ambient", label: "Ambient (one screen colour)" },
];
const SCREEN_SYNC_REACTIVITY_OPTIONS = [
  { data: "calm", label: "Calm" },
  { data: "balanced", label: "Balanced" },
  { data: "fast", label: "Fast" },
];
const SCREEN_SYNC_COLOUR_OPTIONS = [
  { data: "natural", label: "Natural" },
  { data: "vivid", label: "Vivid" },
];

const PALETTE_OPTIONS = [
  { data: "thermal", label: "Cyan → amber → red" },
  { data: "classic", label: "Green → yellow → red" },
  { data: "icefire", label: "Blue → violet → pink" },
  { data: "custom", label: "Custom colours" },
];

const DIRECTION_OPTIONS = [
  { data: "same", label: "Both left → right" },
  { data: "mirrored", label: "Mirrored toward centre" },
];

const COUNTDOWN_COLOUR_OPTIONS = [
  { data: "cyan", label: "Cyan" },
  { data: "green", label: "Green" },
  { data: "amber", label: "Amber" },
  { data: "violet", label: "Violet" },
  { data: "white", label: "White" },
];

const COUNTDOWN_SCALE_OPTIONS = [
  { data: 0, label: "Timer duration (starts full)" },
  { data: 60, label: "Full bar = 1 hour" },
  { data: 120, label: "Full bar = 2 hours" },
  { data: 180, label: "Full bar = 3 hours" },
  { data: 240, label: "Full bar = 4 hours" },
];

const WEATHER_TEMPERATURE_UNITS = [
  { data: "celsius", label: "Celsius (°C)" },
  { data: "fahrenheit", label: "Fahrenheit (°F)" },
];
const COMPANION_PRIORITY_OPTIONS = [
  { data: "stripmine", label: "StripMine while the game is active" },
  { data: "signalbar", label: "GabeCubeAura" },
];
const CONTROLLER_ALERT_OPTIONS = [
  { data: "off", label: "Off" },
  { data: "home", label: "On Home" },
  { data: "game", label: "In game" },
  { data: "both", label: "Home + in game" },
];
const CONTROLLER_CHARGING_OPTIONS = [
  { data: "off", label: "Off" },
  { data: "brief", label: "Brief, about 3 seconds" },
  { data: "continuous-home", label: "Continuous on Home" },
  { data: "continuous-everywhere", label: "Continuous everywhere" },
];
const CONTROLLER_COLOUR_MODE_OPTIONS = [
  { data: "battery", label: "Battery level" },
  { data: "players", label: "Player seats" },
];
const CONTROLLER_COLOUR_PRESET_OPTIONS = [
  { data: "automatic", label: "Automatic" },
  { data: "manual", label: "Manual" },
];
const CONTROLLER_PREVIEW_COUNT_OPTIONS = [1, 2, 3, 4].map((count) => ({
  data: count,
  label: `${count} controller${count === 1 ? "" : "s"}`,
}));
function formatRemaining(seconds: number): string {
  const safe = Math.max(0, Math.ceil(seconds));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const remainder = safe % 60;
  if (hours > 0) return `${hours}h ${String(minutes).padStart(2, "0")}m`;
  return `${minutes}:${String(remainder).padStart(2, "0")}`;
}

function formatAge(seconds: number | null): string {
  if (seconds == null) return "never";
  if (seconds < 1) return `${Math.round(seconds * 1000)} ms ago`;
  return `${seconds.toFixed(1)} s ago`;
}

function formatUpdateDate(timestamp: number): string {
  if (!timestamp) return "Never";
  try {
    return new Date(timestamp * 1000).toLocaleString();
  } catch {
    return "Unavailable";
  }
}

function updatePhaseLabel(update: UpdateStatus): string {
  switch (update.phase) {
    case "checking": return "Checking for updates...";
    case "up_to_date": return "GabeCubeAura is up to date.";
    case "available": return update.return_to_stable
      ? `Stable version ${update.available_version} is ready to download.`
      : `Version ${update.available_version} is available.`;
    case "downloading": return `Downloading ${update.available_version}...`;
    case "verifying": return "Checking the downloaded package...";
    case "ready": return `Ready to install ${update.available_version}.`;
    case "installing":
    case "restart_pending": return "Restarting Decky to finish the update...";
    case "updated": return `Updated successfully to ${update.installed_version}.`;
    case "rolled_back": return `The new version did not start correctly. GabeCubeAura restored ${update.rollback_version || update.installed_version}.`;
    case "error": return update.error || "Could not check for updates. Try again later.";
    case "managed_by_decky": return "Updates are managed by Decky.";
    default: return "Ready to check for updates.";
  }
}

function controllerChargeLabel(controller: Status["controllers"]["controllers"][number]): string {
  if (controller.percent != null) return `${controller.percent}%`;
  if (controller.level != null) return `${controller.level}/4 level`;
  return "battery unavailable";
}

function ArtworkImage({ artwork, title, compact = false, sampleLine }: {
  artwork: ArtworkPayload;
  title: string;
  compact?: boolean;
  sampleLine?: number;
}) {
  if (!artwork.data_uri) return null;
  return <div style={{ width: "100%", display: "flex", justifyContent: "center" }}>
    <div style={{ position: "relative", display: "inline-flex", maxWidth: "100%" }}>
      <img
        src={artwork.data_uri}
        alt={`Artwork for ${title}`}
        style={{ display: "block", width: "auto", height: "auto", maxWidth: "100%", maxHeight: compact ? 160 : 360, objectFit: "contain", borderRadius: 4 }}
      />
      {sampleLine == null ? null : <div
        aria-label={`Selected sample row at ${Math.round(sampleLine * 100)} percent`}
        style={{
          position: "absolute",
          top: `${Math.max(0, Math.min(1, sampleLine)) * 100}%`,
          left: 0,
          right: 0,
          height: 2,
          transform: "translateY(-1px)",
          background: "#ff3b45",
          boxShadow: "0 0 4px rgba(255, 40, 50, .95)",
          pointerEvents: "none",
        }}
      />}
    </div>
  </div>;
}

function PerformanceReadout({ status }: { status: Status }) {
  return <div style={{ width: "100%", fontSize: ".84em" }}>
    CPU {status.performance.cpu_load == null ? "Unavailable" : `${Math.round(status.performance.cpu_load)}%`}
    {" · "}{status.performance.cpu_temperature == null ? "Unavailable" : `${Math.round(status.performance.cpu_temperature)}°C`}
    <br />
    GPU {status.performance.gpu_load == null ? "Unavailable" : `${Math.round(status.performance.gpu_load)}%`}
    {" · "}{status.performance.gpu_temperature == null ? "Unavailable" : `${Math.round(status.performance.gpu_temperature)}°C`}
    <div style={{ opacity: .65, marginTop: 4 }}>
      {status.performance.error ? `Sensor read failed: ${status.performance.error}`
        : status.performance.sample_age_s == null ? "Waiting for a fresh sensor reading…"
        : `Live sensors · updated ${formatAge(status.performance.sample_age_s)}`}
    </div>
  </div>;
}

function OpaqueColorPickerModal({ title, color, closeModal, onConfirm }: {
  title: string;
  color: RGB;
  closeModal: () => void;
  onConfirm: (color: RGB) => void;
}) {
  const [initialHue, initialSaturation, initialLightness] = rgbToHsl(color);
  const [hue, setHue] = useState(initialHue);
  const [saturation, setSaturation] = useState(initialSaturation);
  const [lightness, setLightness] = useState(initialLightness);
  const selected = hslStringToRgb(`hsl(${hue}, ${saturation}%, ${lightness}%)`) ?? color;
  return <ConfirmModal strTitle={title} strOKButtonText="Use colour" strCancelButtonText="Cancel"
    onCancel={closeModal} onOK={() => { onConfirm(selected); closeModal(); }}>
    <div style={{ width: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
        <span style={{ width: 38, height: 38, borderRadius: 5,
          background: `rgb(${selected.join(", ")})`, boxShadow: "0 0 0 1px rgba(255,255,255,.45)" }} />
        <span style={{ opacity: .78, fontSize: ".8em" }}>Opaque RGB colour · no alpha channel on the LED hardware.</span>
      </div>
      <SliderField label="Hue" value={hue} min={0} max={360} step={1} showValue
        onChange={setHue} />
      <SliderField label="Saturation" value={saturation} min={0} max={100} step={1} showValue valueSuffix="%"
        onChange={setSaturation} />
      <SliderField label="Lightness" value={lightness} min={0} max={100} step={1} showValue valueSuffix="%"
        onChange={setLightness} />
    </div>
  </ConfirmModal>;
}

function chooseSettingColor(key: string, label: string, color: [number, number, number], setStatus: (value: Status) => void) {
  let modal: ReturnType<typeof showModal> | undefined;
  modal = showModal(<OpaqueColorPickerModal title={label} color={color}
    closeModal={() => modal?.Close()}
    onConfirm={(nextColor) => void setSetting(key, nextColor).then(setStatus).catch(console.warn)} />);
}

function ColorChoice({ label, color, onClick }: {
  label: string;
  color: [number, number, number];
  onClick: () => void;
}) {
  const cssColor = `rgb(${color.join(", ")})`;
  return <ButtonItem label={label} description={cssColor} onClick={onClick}>
    <span style={{
      display: "inline-block",
      width: 28,
      height: 28,
      borderRadius: 5,
      background: cssColor,
      boxShadow: "0 0 0 1px rgba(255,255,255,.45)",
    }} />
  </ButtonItem>;
}

function PreciseColorEditor({ label, color, onChange }: {
  label: string;
  color: RGB;
  onChange: (color: RGB) => void;
}) {
  const canonicalHex = `#${color.map((channel) => channel.toString(16).padStart(2, "0")).join("").toUpperCase()}`;
  const [hexText, setHexText] = useState(canonicalHex);
  useEffect(() => setHexText(canonicalHex), [canonicalHex]);
  const setChannel = (channel: number, value: number) => {
    const next = [...color] as RGB;
    next[channel] = Math.max(0, Math.min(255, Math.round(value)));
    onChange(next);
  };
  const choose = () => {
    let modal: ReturnType<typeof showModal> | undefined;
    modal = showModal(<OpaqueColorPickerModal title={label} color={color}
      closeModal={() => modal?.Close()} onConfirm={onChange} />);
  };
  return <div style={{ width: "100%" }}>
    <ColorChoice label={label} color={color} onClick={choose} />
    <TextField label="Hex" value={hexText} description="Exact #RRGGBB colour"
      onChange={(event) => {
        const next = event.currentTarget.value.toUpperCase();
        setHexText(next);
        const match = /^#?([0-9A-F]{6})$/.exec(next);
        if (match) onChange([
          parseInt(match[1].slice(0, 2), 16),
          parseInt(match[1].slice(2, 4), 16),
          parseInt(match[1].slice(4, 6), 16),
        ]);
      }} />
    <SliderField label="Red" value={color[0]} min={0} max={255} step={1} showValue
      onChange={(value) => setChannel(0, value)} />
    <SliderField label="Green" value={color[1]} min={0} max={255} step={1} showValue
      onChange={(value) => setChannel(1, value)} />
    <SliderField label="Blue" value={color[2]} min={0} max={255} step={1} showValue
      onChange={(value) => setChannel(2, value)} />
  </div>;
}

function addRecordingMarker(status: Status, colors: Status["events"]["colors"] | undefined) {
  if (!status.events.recording || !colors || colors.length !== 17) return colors ?? [];
  const marked = colors.map((color) => [...color] as [number, number, number]);
  if (status.recording_marker_isolation) {
    marked[7] = [0, 0, 0];
    marked[9] = [0, 0, 0];
  }
  marked[8] = [229, 54, 70];
  return marked;
}

function EventPreviewStrip({ status, kinds }: { status: Status; kinds: string[] }) {
  const visible = status.events.active && kinds.includes(status.events.kind);
  const recordingPreview = kinds.includes("record-start") && status.events.recording;
  const recordingFrame = addRecordingMarker(status, Array.from({ length: 17 }, () => [0, 0, 0]));
  return <div style={{ width: "100%", fontSize: ".78em", opacity: .84 }}>
    <div>{visible ? `Playing: ${status.events.variant}` : recordingPreview ? "Recording marker active" : "Preview appears here"}</div>
    <PalettePreview colors={visible ? status.events.colors : recordingPreview ? recordingFrame : []} />
  </div>;
}

function CountdownPanel({
  status,
  setStatus,
}: {
  status: Status;
  setStatus: (next: Status) => void;
}) {
  return (
    <>
      {status.countdown.active ? <PanelSection title="Active countdown">
        <PanelSectionRow>
          <div style={{ width: "100%", fontSize: ".84em" }}>
            <b>{status.countdown.label}</b>
            {" · "}{formatRemaining(status.countdown.remaining_seconds)} remaining
            {status.countdown.alerting ? " · triple white alert" : status.countdown_full_bar_minutes > 0
              ? ` · full bar = ${status.countdown_full_bar_minutes / 60}h`
              : " · starts full"}
            <PalettePreview colors={status.countdown.colors} />
            <div style={{ opacity: .7 }}>Live 17-LED countdown preview</div>
          </div>
        </PanelSectionRow>
      </PanelSection> : null}
      <PanelSection title="Playtime countdown">
      <PanelSectionRow>
        <ToggleField
          label="Steam Families limit"
          description="Always takes priority over Artwork, Performance and a personal timer while a game is running."
          checked={status.parental_countdown_enabled}
          onChange={async (value) => setStatus(await setSetting("parental_countdown_enabled", value))}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <DropdownItem
          label="Starting colour"
          rgOptions={COUNTDOWN_COLOUR_OPTIONS}
          selectedOption={status.countdown_colour}
          onChange={async (option) => setStatus(await setSetting("countdown_colour", String(option.data)))}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <DropdownItem
          label="Full bar scale"
          description="Timer duration starts at 17 LEDs. A fixed scale means 17 LEDs represent that much remaining time; longer limits stay full until they enter the selected window."
          rgOptions={COUNTDOWN_SCALE_OPTIONS}
          selectedOption={status.countdown_full_bar_minutes}
          onChange={async (option) => setStatus(await setSetting("countdown_full_bar_minutes", Number(option.data)))}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <SliderField
          label="Free timer"
          description="Duration used the next time you start the personal countdown."
          value={status.free_timer_minutes}
          min={5}
          max={240}
          step={5}
          showValue
          valueSuffix=" min"
          onChange={async (value) => setStatus(await setSetting("free_timer_minutes", value))}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem
          label="Personal limit"
          description="The timer keeps running when this Decky panel is closed."
          onClick={() => void startFreeTimer(status.free_timer_minutes).then(setStatus).catch(console.warn)}
        >
          Start / restart
        </ButtonItem>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem
          label="Stop personal limit"
          onClick={() => void stopFreeTimer().then(setStatus).catch(console.warn)}
        >
          Stop
        </ButtonItem>
      </PanelSectionRow>
      <PanelSectionRow>
        <div style={{ width: "100%", fontSize: ".8em", opacity: 0.86 }}>
          {status.countdown.active ? "The active timer and its live bar are shown at the top of this page." : "No countdown is active."}
          <div style={{ marginTop: 5, opacity: 0.75 }}>
            The bar empties from right to left. A configurable physical compensation counters diffuser bloom while this preview keeps the logical LED count. It turns amber below 15 minutes, then pure red below 5 minutes while the right-to-left circulation continues. During the final 8 seconds, three short white flashes repeat until zero.
          </div>
        </div>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem
          label="Test countdown and final alert"
          description="Runs a 15-second countdown whose final 8 seconds demonstrate the white alert without cancelling a real timer."
          onClick={() => void previewCountdown().then(setStatus).catch(console.warn)}
        >
          Preview
        </ButtonItem>
      </PanelSectionRow>
      </PanelSection>
    </>
  );
}

function EventsPanel({ status, setStatus }: { status: Status; setStatus: (next: Status) => void }) {
  const preview = async (kind: string, variant = "") => {
    await triggerEvent(kind, true, variant);
    setStatus(await getStatus());
  };
  const categories = ([
    ["notification", "Notifications", "event_notifications_enabled", "event_notification_variant"],
    ["achievement", "Achievements", "event_achievements_enabled", "event_achievement_variant"],
    ["screenshot", "Screenshots", "event_screenshots_enabled", "event_screenshot_variant"],
  ] as const);
  return (
    <>
      <PanelSection title="Light events">
        <PanelSectionRow>
          <ToggleField
            label="Steam event animations"
            description="Enabled by default. Short signals play even outside games, briefly replacing the current display. Previews work while off."
            checked={status.events_enabled}
            onChange={async (value) => setStatus(await setSetting("events_enabled", value))}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <div style={{ width: "100%", fontSize: ".8em", opacity: .82 }}>
            {status.events.active ? `Playing: ${status.events.variant}` : "No event animation active"}
            {status.events.recording ? " · recording marker on" : ""}
            <div style={{ marginTop: 5 }}>The final five minutes of a countdown are protected. New native LED writes interrupt animations.</div>
          </div>
        </PanelSectionRow>
      </PanelSection>
      {categories.map(([kind, label, enabledKey, variantKey]) => {
        const options = EVENT_VARIANTS[kind];
        const selected = status[variantKey];
        const detail = options.find((option) => option.data === selected)?.detail ?? "";
        return (
          <PanelSection key={kind} title={label}>
            <PanelSectionRow>
              <ToggleField label={`Show ${label.toLowerCase()}`} checked={status[enabledKey]}
                onChange={async (value) => setStatus(await setSetting(enabledKey, value))} />
            </PanelSectionRow>
            <PanelSectionRow>
              <DropdownItem label="Animation" rgOptions={[...options]} selectedOption={selected}
                onChange={async (option) => setStatus(await setSetting(variantKey, String(option.data)))} />
            </PanelSectionRow>
            <PanelSectionRow>
              <div style={{ fontSize: ".8em", opacity: .78 }}>{detail}</div>
            </PanelSectionRow>
            <PanelSectionRow>
              <EventPreviewStrip status={status} kinds={[kind]} />
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem label={`Preview ${label.toLowerCase()}`}
                description="Works with live events off, but not with Display disabled or in the final five countdown minutes."
                onClick={() => void preview(kind, selected).catch(console.warn)}>Play selected</ButtonItem>
            </PanelSectionRow>
          </PanelSection>
        );
      })}
      <PanelSection title="Recording">
        <PanelSectionRow>
          <ToggleField label="Recording · red start/stop" description="The centre LED stays red over Artwork or Performance while recording. Countdowns retain all 17 LEDs."
            checked={status.event_recording_enabled}
            onChange={async (value) => setStatus(await setSetting("event_recording_enabled", value))} />
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label="Isolate recording marker"
            description="Turns the LED immediately to each side of the red centre marker black, reducing colour bleed from Artwork or Performance."
            checked={status.recording_marker_isolation}
            disabled={!status.event_recording_enabled}
            onChange={async (value) => setStatus(await setSetting("recording_marker_isolation", value))}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <EventPreviewStrip status={status} kinds={["record-start", "record-stop"]} />
        </PanelSectionRow>
      {([
        ["record-start", "Recording starts"], ["record-stop", "Recording ends"],
      ] as const).map(([kind, label]) => (
        <PanelSectionRow key={kind}>
          <ButtonItem label={`Preview ${label}`} onClick={() => void preview(kind).catch(console.warn)}>Play</ButtonItem>
        </PanelSectionRow>
      ))}
      </PanelSection>
    </>
  );
}

function ControllersPanel({ status, setStatus }: { status: Status; setStatus: (next: Status) => void }) {
  const [previewMessage, setPreviewMessage] = useState("");
  const [previewCount, setPreviewCount] = useState(Math.max(1, Math.min(4, status.controllers.controllers.length || 2)));
  const [previewTarget, setPreviewTarget] = useState(0);
  const telemetry = status.debug.controller_telemetry;
  const stale = (status.debug.controller_last_update_age_s ?? 0) > 10;
  const automaticColours = status.controller_colour_preset === "automatic";
  const detectedControllerCount = status.controllers.controllers.length;
  const batteryColourChoices = [
    ["controller_colour_normal", `Healthy battery · above ${Math.max(35, status.controller_low_threshold + 5)}%`],
    ["controller_colour_medium", "Medium battery"],
    ["controller_colour_low", `Low battery · ${status.controller_low_threshold}% or less`],
  ] as const;
  const playerColourChoices = [
    ["controller_player_colour_1", "Player 1"],
    ["controller_player_colour_2", "Player 2"],
    ["controller_player_colour_3", "Player 3"],
    ["controller_player_colour_4", "Player 4"],
  ] as const;
  const preview = async (kind: keyof typeof CONTROLLER_VARIANTS, variant: string) => {
    try {
      const count = kind === "duo" ? Math.max(2, previewCount) : previewCount;
      const played = await previewController(kind, variant, count, Math.min(previewTarget, count - 1));
      setPreviewMessage(played ? "Preview requested. It does not test controller detection; LED output still follows GabeCubeAura priorities."
        : "Preview unavailable in Disabled mode or during the final five minutes of a countdown.");
      setStatus(await getStatus());
    } catch { setPreviewMessage("Preview could not reach GabeCubeAura. Check the Decky backend."); }
  };
  const groups = [
    ["connect", "Connection", "controller_connect_enabled", "controller_connect_variant"],
    ["persistent", "Permanent gauge", null, "controller_persistent_variant"],
    ["low", "Low battery", "controller_low_enabled", "controller_low_variant"],
    ["charging", "Charging style", null, "controller_charging_variant"],
    ["duo", "Multiple controllers", null, "controller_duo_variant"],
  ] as const;
  return <>
    <PanelSection title="Controller battery">
      <PanelSectionRow><div style={{ fontSize: ".8em", opacity: .8 }}>
        {status.controllers.controllers.length ? status.controllers.controllers.map((controller) =>
          `${controller.name}: ${controllerChargeLabel(controller)}${controller.charging ? " · charging" : ""}`).join(" · ")
          : telemetry?.phase === "ready" && !stale ? "Steam responded: no controllers connected."
          : telemetry?.phase === "starting" || !telemetry ? "Connecting to Steam controller service…"
          : "Controller detection unavailable. See the connection details below."}
        <div style={{ marginTop: 8 }}>
          Steam connection: {stale ? "stale (last reading over 10 seconds ago)" : telemetry?.phase ?? "starting"}
          {telemetry?.phase === "ready" ? ` · ${telemetry.hooks}/3 live hooks · checked every 2 s` : ""}
        </div>
        {telemetry?.error ? <div style={{ color: "#ffca86", marginTop: 6 }}>{telemetry.error}</div> : null}
        {previewMessage ? <div style={{ marginTop: 6 }}>{previewMessage}</div> : null}
      </div></PanelSectionRow>
      <PanelSectionRow><div style={{ fontSize: ".78em", opacity: .75 }}>
        Select <b>Controller status</b> for Home or In game on the Display routing page to use the permanent gauge. Brief alerts remain independent.
      </div></PanelSectionRow>
      <PanelSectionRow><ToggleField label="Brief controller alerts"
        description="Master switch for connection, low-battery and brief charging signals. It does not turn off the permanent gauge or continuous charging."
        checked={status.controller_alerts_enabled}
        onChange={async (value) => setStatus(await setSetting("controller_alerts_enabled", value))} /></PanelSectionRow>
      <PanelSectionRow><DropdownItem label="Where brief alerts play"
        description="Applies to connection, low-battery and brief charging signals, not continuous charging."
        rgOptions={CONTROLLER_ALERT_OPTIONS}
        selectedOption={status.controller_alert_context}
        onChange={async (option) => setStatus(await setSetting("controller_alert_context", String(option.data)))} /></PanelSectionRow>
      <PanelSectionRow><DropdownItem label="Charging behavior"
        description="Choose one: a brief signal when charging starts, or movement while Steam reports charging below 100%. Continuous charging is independent of Brief controller alerts."
        rgOptions={CONTROLLER_CHARGING_OPTIONS} selectedOption={status.controller_charging_mode}
        onChange={async (option) => setStatus(await setSetting("controller_charging_mode", String(option.data)))} /></PanelSectionRow>
      <PanelSectionRow><div style={{ fontSize: ".78em", opacity: .78 }}>
        {status.controller_charging_mode === "brief"
          ? "Brief charging needs Brief controller alerts enabled and a reported battery level. It follows Where brief alerts play and ends after about 3 seconds. A controller already charging at startup does not trigger it."
          : status.controller_charging_mode.startsWith("continuous")
            ? "Continuous charging needs a reported battery level. It ends if Steam stops reporting charging, or at 100% after a short completion cue. It can yield to higher-priority signals."
            : "No charging signal. Connection and low-battery alerts can still play if enabled."}
      </div></PanelSectionRow>
      <PanelSectionRow><SliderField label="Low battery warning" value={status.controller_low_threshold}
        min={5} max={30} step={5} showValue valueSuffix="%"
        onChange={async (value) => setStatus(await setSetting("controller_low_threshold", value))} /></PanelSectionRow>
      <PanelSectionRow><div style={{ width: "100%", fontSize: ".78em", opacity: .8 }}>
        {status.controllers.active ? `Playing: ${status.controllers.kind} · ${status.controllers.variant}`
          : status.controllers.charging_active ? "Charging animation active" : "No controller animation active"}
        <div>Battery and charging readings depend on what Steam exposes for this controller and connection. Unknown is not treated as empty. An already-connected controller does not replay the connection signal at startup. Disabled mode and Steam LED ownership can prevent output.</div>
      </div></PanelSectionRow>
      <PanelSectionRow><div style={{ fontSize: ".78em", opacity: .75 }}>
        Each detected controller keeps a fixed seat. Two and four controllers use mirrored seats. Three controllers use three left-to-right zones. Separators remain dark and fixed white endpoints appear after the introduction.
      </div></PanelSectionRow>
    </PanelSection>
    <PanelSection title="Controller colours">
      <PanelSectionRow><div style={{ fontSize: ".8em", opacity: .8 }}>
        Automatic uses battery status colours with one controller, then fixed P1 to P4 colours from two controllers. Battery level still controls the length of every gauge. Low-battery and charging signals keep their warning colours, and white highlights stay white.
      </div></PanelSectionRow>
      <PanelSectionRow><DropdownItem label="Colour preset"
        description="Automatic follows the connected controller count. Manual keeps one colour meaning at every count."
        rgOptions={CONTROLLER_COLOUR_PRESET_OPTIONS}
        selectedOption={status.controller_colour_preset}
        onChange={async (option) => setStatus(await setSetting("controller_colour_preset", String(option.data)))} /></PanelSectionRow>
      <PanelSectionRow><DropdownItem label="Colour meaning"
        description={automaticColours
          ? "Managed by Automatic: battery level for one controller, player seats for two to four controllers."
          : "Choose battery status colours or fixed player-seat colours for permanent gauges and multiplayer patterns."}
        rgOptions={CONTROLLER_COLOUR_MODE_OPTIONS}
        selectedOption={status.controller_colour_mode}
        disabled={automaticColours}
        onChange={async (option) => setStatus(await setSetting("controller_colour_mode", String(option.data)))} /></PanelSectionRow>
      {automaticColours ? <PanelSectionRow><div style={{ fontSize: ".78em", opacity: .78 }}>
        {detectedControllerCount === 1
          ? "Current rule: one detected controller, so the gauge uses battery colours."
          : detectedControllerCount >= 2
            ? `Current rule: ${detectedControllerCount} detected controllers, so the gauges use player colours.`
            : "Current rule: the next single controller will use battery colours. Two or more will use player colours."}
        <div>Previews apply the same rule to the selected preview count.</div>
      </div></PanelSectionRow> : null}
      <PanelSectionRow><SliderField label="Controller brightness" min={10} max={100} step={5}
        showValue valueSuffix="%" value={status.controller_gauge_brightness}
        onChange={async (value) => setStatus(await setSetting("controller_gauge_brightness", value))} /></PanelSectionRow>
      {automaticColours ? <PanelSectionRow><div style={{ fontSize: ".78em", opacity: .72 }}>One controller</div></PanelSectionRow> : null}
      {(automaticColours || status.controller_colour_mode === "battery" ? batteryColourChoices : []).map(([key, label]) => <PanelSectionRow key={key}>
        <ColorChoice label={label} color={status[key]}
          onClick={() => chooseSettingColor(key, label, status[key], setStatus)} />
      </PanelSectionRow>)}
      {automaticColours ? <PanelSectionRow><div style={{ fontSize: ".78em", opacity: .72 }}>Two to four controllers</div></PanelSectionRow> : null}
      {(automaticColours || status.controller_colour_mode === "players" ? playerColourChoices : []).map(([key, label]) => <PanelSectionRow key={key}>
        <ColorChoice label={label} color={status[key]}
          onClick={() => chooseSettingColor(key, label, status[key], setStatus)} />
      </PanelSectionRow>)}
      <PanelSectionRow>
        <ColorChoice label="Connection / charging colour" color={status.controller_colour_charging}
          onClick={() => chooseSettingColor("controller_colour_charging", "Connection / charging colour", status.controller_colour_charging, setStatus)} />
      </PanelSectionRow>
    </PanelSection>
    <PanelSection title="Preview setup">
      <PanelSectionRow><DropdownItem label="Controllers in preview"
        description="Uses sample levels only. It does not change the detected controller roster."
        rgOptions={CONTROLLER_PREVIEW_COUNT_OPTIONS} selectedOption={previewCount}
        onChange={(option) => {
          const count = Number(option.data);
          setPreviewCount(count);
          setPreviewTarget((target) => Math.min(target, count - 1));
        }} /></PanelSectionRow>
      <PanelSectionRow><DropdownItem label="Preview controller"
        description="Connection, low-battery and charging previews use this player seat."
        rgOptions={CONTROLLER_PREVIEW_COUNT_OPTIONS.slice(0, previewCount).map((_, index) => ({ data: index, label: `Controller ${index + 1}` }))}
        selectedOption={previewTarget}
        onChange={(option) => setPreviewTarget(Number(option.data))} /></PanelSectionRow>
    </PanelSection>
    {groups.map(([kind, title, enabledKey, variantKey]) => {
      const selected = status[variantKey];
      const options = CONTROLLER_VARIANTS[kind];
      const detail = options.find((item) => item.data === selected)?.detail ?? "";
      return <PanelSection key={kind} title={title}>
        {kind === "charging" ? <PanelSectionRow><div style={{ fontSize: ".78em", opacity: .78 }}>
          This style is used for the brief signal or the repeating animation, depending on Charging behavior. Preview shows one cycle only.
        </div></PanelSectionRow> : null}
        {enabledKey ? <PanelSectionRow><ToggleField label={`Show ${title.toLowerCase()}`}
          checked={status[enabledKey]}
          onChange={async (value) => setStatus(await setSetting(enabledKey, value))} /></PanelSectionRow> : null}
        <PanelSectionRow><DropdownItem label="Visual style" rgOptions={[...options]}
          selectedOption={selected}
          onChange={async (option) => setStatus(await setSetting(variantKey, String(option.data)))} /></PanelSectionRow>
        <PanelSectionRow><div style={{ fontSize: ".8em", opacity: .78 }}>{detail}</div></PanelSectionRow>
        <PanelSectionRow><div style={{ width: "100%", fontSize: ".78em", opacity: .8 }}>
          {status.controllers.active && status.controllers.kind === kind ? `Playing: ${status.controllers.variant}` : "No preview playing"}
          <PalettePreview colors={status.controllers.active && status.controllers.kind === kind ? status.controllers.colors : []} />
        </div></PanelSectionRow>
        <PanelSectionRow><ButtonItem label={`Preview ${title.toLowerCase()}`}
          description="Uses sample battery data; it does not verify Steam detection. Disabled mode, countdown priority and Steam ownership can prevent LED output."
          onClick={() => void preview(kind, selected).catch(console.warn)}>Play selected</ButtonItem></PanelSectionRow>
      </PanelSection>;
    })}
  </>;
}

function WeatherPanel({ status, setStatus }: { status: Status; setStatus: (next: Status) => void }) {
  const [cityQuery, setCityQuery] = useState("");
  const [countryQuery, setCountryQuery] = useState("");
  const [cityResults, setCityResults] = useState<WeatherLocation[]>([]);
  const [searching, setSearching] = useState(false);
  const [message, setMessage] = useState("");
  const [previewCondition, setPreviewCondition] = useState<WeatherCondition>("clear_day");
  const variantKey = `weather_${previewCondition}_variant` as keyof Status;
  const selectedVariant = Number(status[variantKey]);
  const currentLabel = WEATHER_CONDITIONS.find((item) => item.data === status.weather.condition)?.label ?? "Unknown";
  const findCity = async () => {
    setSearching(true);
    setMessage("");
    try {
      const city = cityQuery.trim();
      const country = countryQuery.trim();
      const response = await searchWeatherCities(country ? `${city}, ${country}` : city);
      setCityResults(response.results);
      if (response.error) setMessage(`City search failed: ${response.error}`);
      else if (!response.results.length) setMessage("No matching city. Enter the full country name, or try searching without it.");
    } catch (error) {
      setCityResults([]);
      setMessage(`City search failed: ${error instanceof Error ? error.message : String(error)}`);
    } finally { setSearching(false); }
  };
  const chooseCity = async (city: WeatherLocation) => {
    try {
      setStatus(await setSetting("weather_location", city));
      setCityResults([]);
      setCityQuery(city.name);
      setCountryQuery(city.country);
      setMessage("City saved. Select Weather on the Display routing page to show it on the LED bar.");
    } catch (error) { setMessage(`Could not save city: ${String(error)}`); }
  };
  const playPreview = async (condition: WeatherCondition = previewCondition) => {
    try {
      const variant = Number(status[`weather_${condition}_variant`]);
      const played = await previewWeather(condition, variant);
      setMessage(played ? "One cycle requested. Preview still follows countdown and Steam LED ownership."
        : "Preview unavailable in Disabled mode or during the final five minutes of a countdown.");
      setStatus(await getStatus());
    } catch (error) { setMessage(`Preview failed: ${String(error)}`); }
  };
  return <>
    <PanelSection title="Local weather">
      <PanelSectionRow><div style={{ fontSize: ".8em", opacity: .82 }}>
        {status.weather_location ? `${status.weather_location.name}, ${status.weather_location.country}` : "Choose a city to begin. Location is never detected automatically."}
        <div style={{ marginTop: 6 }}>
          {status.weather.phase === "ready"
            ? `${currentLabel} · updated ${formatAge(status.weather.age_s)}`
            : status.weather.phase === "loading" ? "Getting current weather…"
              : status.weather.phase === "error" ? `Weather unavailable: ${status.weather.error}`
                : status.weather.phase === "waiting" ? "Waiting for the first weather update…"
              : "Weather is off. The controller gauge is the fresh-install default."}
        </div>
        {message ? <div style={{ marginTop: 6 }}>{message}</div> : null}
      </div></PanelSectionRow>
      <PanelSectionRow><TextField label="City or postal code" value={cityQuery} onChange={(event) => setCityQuery(event.currentTarget.value)}
        description="Enter a city name or postal code." /></PanelSectionRow>
      <PanelSectionRow><TextField label="Country (full name, optional)" value={countryQuery} onChange={(event) => setCountryQuery(event.currentTarget.value)}
        description="Use the full country name, for example France. Two-letter codes do not work here." /></PanelSectionRow>
      <PanelSectionRow><ButtonItem label="Find city" disabled={searching || cityQuery.trim().length < 2}
        onClick={() => void findCity()}>{searching ? "Searching…" : "Search"}</ButtonItem></PanelSectionRow>
      {cityResults.map((city, index) => <PanelSectionRow key={`${city.latitude}:${city.longitude}:${index}`}>
        <ButtonItem label={`${city.name}, ${city.country}`} onClick={() => void chooseCity(city)}>Use this city</ButtonItem>
      </PanelSectionRow>)}
      {status.weather_location ? <PanelSectionRow><ButtonItem label="Remove city"
        description="Turns weather off and stops weather requests."
        onClick={() => void setSetting("weather_location", null).then((next) => { setStatus(next); setMessage("City removed."); }).catch((error) => setMessage(String(error)))}>Remove</ButtonItem></PanelSectionRow> : null}
      <PanelSectionRow><ToggleField label="SteamOS top-bar weather (experimental)"
        description="Show a weather icon and temperature beside the clock when Steam's top bar is available. Needs a chosen city. Independent of the LED display and controller gauge; hides if the top bar cannot be found."
        checked={status.weather_topbar_enabled}
        onChange={async (enabled) => {
          if (enabled && !status.weather_location) {
            setMessage("Choose a city before enabling top-bar weather.");
            return;
          }
          try {
            setStatus(await setSetting("weather_topbar_enabled", enabled));
            setMessage(enabled ? "Top-bar weather enabled. It may take a few seconds to appear." : "Top-bar weather disabled.");
          } catch (error) { setMessage(`Could not change top-bar weather: ${String(error)}`); }
        }} /></PanelSectionRow>
      <PanelSectionRow><DropdownItem label="Top-bar temperature unit"
        description="Applies to the number beside the SteamOS clock only, not the LED animations."
        rgOptions={WEATHER_TEMPERATURE_UNITS} selectedOption={status.weather_temperature_unit}
        onChange={async (option) => setStatus(await setSetting("weather_temperature_unit", String(option.data)))} /></PanelSectionRow>
      <PanelSectionRow><div style={{ fontSize: ".78em", opacity: .75 }}>
        Select <b>Weather</b> for Home, In game, or a game override on the Display routing page. Brief alerts and playtime warnings remain independent.
      </div></PanelSectionRow>
      <PanelSectionRow><div style={{ fontSize: ".76em", opacity: .72 }}>
        Current conditions refresh about every 15 minutes. The last reading can be reused for up to one hour; then weather yields the bar. No city, no network request. Data by <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a>.
      </div></PanelSectionRow>
    </PanelSection>
    <PanelSection title="Weather animations">
      <PanelSectionRow><DropdownItem label="Condition to configure" rgOptions={WEATHER_CONDITIONS}
        selectedOption={previewCondition} onChange={(option) => setPreviewCondition(option.data as WeatherCondition)} /></PanelSectionRow>
      <PanelSectionRow><DropdownItem label="Animation" rgOptions={WEATHER_VARIANTS[previewCondition].map((item, index) => ({ data: index, label: item.label }))}
        selectedOption={selectedVariant}
        onChange={async (option) => setStatus(await setSetting(variantKey, Number(option.data)))} /></PanelSectionRow>
      <PanelSectionRow><div style={{ fontSize: ".78em", opacity: .78 }}>
        {WEATHER_VARIANTS[previewCondition][selectedVariant]?.detail}
      </div></PanelSectionRow>
      <PanelSectionRow><ButtonItem label="Preview this animation"
        description="Plays one weather cycle with the selected condition, even before you choose a city. This does not test the weather connection."
        onClick={() => void playPreview()}>Play preview</ButtonItem></PanelSectionRow>
      <PanelSectionRow><div style={{ width: "100%", fontSize: ".78em", opacity: .8 }}>
        {status.weather.preview_active ? "Preview playing" : status.weather.active_here ? "Live weather signal available here" : "No weather signal playing here"}
        <PalettePreview colors={status.weather.colors} />
      </div></PanelSectionRow>
    </PanelSection>
    <PanelSection title="Weather brightness">
      <PanelSectionRow><div style={{ fontSize: ".78em", opacity: .78 }}>
        Brightness scales RGB linearly for all weather animations. Use 100% with cutoff 0 for the unprocessed animation. These controls affect Weather only, not Steam's master LED brightness or other GabeCubeAura modes.
      </div></PanelSectionRow>
      <PanelSectionRow><SliderField label="Weather LED brightness" min={10} max={100} step={5}
        showValue valueSuffix="%" value={status.weather_brightness}
        onChange={async (value) => setStatus(await setSetting("weather_brightness", value))} /></PanelSectionRow>
      <PanelSectionRow><SliderField label="Turn faint LEDs off" min={0} max={60} step={5}
        showValue value={status.weather_shadow_cutoff}
        onChange={async (value) => setStatus(await setSetting("weather_shadow_cutoff", value))} /></PanelSectionRow>
      <PanelSectionRow><div style={{ fontSize: ".76em", opacity: .72 }}>
        Cutoff turns a pixel fully off when its strongest RGB channel is at or below this value (scale from 0 to 255). It does not dim the remaining pixels further. A high cutoff can make transitions more abrupt. These are brightness controls, not measured hardware colour calibration.
      </div></PanelSectionRow>
      <PanelSectionRow><ButtonItem label="Preview night colours"
        description="Play the selected moon-and-stars loop to check the white glow on the physical bar."
        onClick={() => void playPreview("clear_night")}>Play night</ButtonItem></PanelSectionRow>
      <PanelSectionRow><ButtonItem label="Preview warm colours"
        description="Play the selected clear-day loop to check gold and pale sunlight."
        onClick={() => void playPreview("clear_day")}>Play daylight</ButtonItem></PanelSectionRow>
    </PanelSection>
  </>;
}

function CustomizationPanel({ status, setStatus }: { status: Status; setStatus: (next: Status) => void }) {
  const activeHome = status.home_display === "customization";
  const activeGame = status.game_display === "customization";
  const context = activeHome && activeGame ? "Everywhere" : activeHome ? "Home" : activeGame ? "In game" : "Not selected";
  const colourKeys = ["customization_colour_1", "customization_colour_2", "customization_colour_3"] as const;
  const preview = async () => {
    await previewCustomization();
    setStatus(await getStatus());
  };
  return <PanelSection title="Customization+">
    <PanelSectionRow><div style={{ fontSize: ".8em", opacity: .82 }}>
      Permanent display · <b>{context}</b>. Select Customization+ in Display routing for Home, in game, or both. Temporary layers still take priority.
    </div></PanelSectionRow>
    <PanelSectionRow><DropdownItem label="Pattern" rgOptions={CUSTOMIZATION_PATTERN_OPTIONS}
      selectedOption={status.customization_pattern}
      onChange={async (option) => setStatus(await setSetting("customization_pattern", String(option.data)))} /></PanelSectionRow>
    <>
      <PanelSectionRow><DropdownItem label="Palette" rgOptions={CUSTOMIZATION_COLOUR_OPTIONS}
        selectedOption={status.customization_colour_count}
        onChange={async (option) => setStatus(await setSetting("customization_colour_count", Number(option.data)))} /></PanelSectionRow>
      {colourKeys.slice(0, status.customization_colour_count).map((key, index) => <PanelSectionRow key={key}>
        <PreciseColorEditor label={`Colour ${index + 1}`} color={status[key]}
          onChange={(color) => void setSetting(key, color).then(setStatus).catch(console.warn)} />
      </PanelSectionRow>)}
    </>
    <PanelSectionRow><SliderField label="Brightness" description="Raw RGB ceiling: 34 is the minimum retained by GabeCubeAura because lower values switch the physical bar off; 255 is full output."
      value={status.customization_brightness} min={34} max={255} step={1} showValue valueSuffix=" / 255"
      onChange={async (value) => setStatus(await setSetting("customization_brightness", value))} /></PanelSectionRow>
    {status.customization_pattern !== "steady" ? <PanelSectionRow><SliderField label="Speed"
      value={status.customization_speed} min={1} max={100} step={1} showValue valueSuffix=" / 100"
      onChange={async (value) => setStatus(await setSetting("customization_speed", value))} /></PanelSectionRow> : null}
    {status.customization_pattern !== "steady" ? <PanelSectionRow>
      <DropdownItem label="Direction" rgOptions={CUSTOMIZATION_DIRECTION_OPTIONS}
        selectedOption={status.customization_direction}
        onChange={async (option) => setStatus(await setSetting("customization_direction", String(option.data)))} />
    </PanelSectionRow> : null}
    <PanelSectionRow><ButtonItem label="Preview Customization+" description="Plays for 8 seconds without changing Display routing."
      onClick={() => void preview().catch(console.warn)}>Preview</ButtonItem></PanelSectionRow>
    <PanelSectionRow><div style={{ width: "100%", fontSize: ".78em", opacity: .82 }}>
      {status.customization.preview_active ? "Preview playing" : "Live 17-LED preview"}
      <PalettePreview colors={status.customization.colors} />
    </div></PanelSectionRow>
  </PanelSection>;
}

function ScreenSyncPanel({ status, setStatus }: { status: Status; setStatus: (next: Status) => void }) {
  const activation = status.screen_sync.activation;
  const directGamescopeSelector = status.screen_sync.node_id === null
    && status.screen_sync.capture_selector.includes("Gamescope name");
  const activationLabel = activation.reason === "manual-preview"
    ? `Manual preview (${Math.ceil(activation.preview_remaining_s)} s remaining)`
    : activation.reason === "steam-screensaver"
      ? "Following Steam screensaver"
      : activation.reason === "game-route"
        ? "Following the current game"
        : activation.screensaver_detection === "unavailable"
          ? "Steam screensaver detection unavailable"
          : activation.screensaver_detection === "error"
            ? `Steam screensaver detection error: ${activation.screensaver_detail}`
            : "Waiting for an activation context";
  const phase = status.screen_sync.fallback_active
    ? `Using Customization+: ${status.screen_sync.fallback_reason}`
    : status.screen_sync.phase === "capturing"
    ? `Capturing ${status.screen_sync.frames_per_second.toFixed(1)} frames/s`
    : status.screen_sync.phase === "conflict"
      ? "Paused because another app is capturing Gamescope"
      : status.screen_sync.phase === "waiting"
        ? `Capture closed, waiting to rediscover Gamescope${status.screen_sync.error ? `: ${status.screen_sync.error}` : ""}`
      : status.screen_sync.phase === "error"
        ? `Unavailable: ${status.screen_sync.error}`
        : status.current_display === "screen_sync" && status.game.appid > 0
          ? "Waiting for safe LED ownership"
          : "Select Screen Sync as the in-game display or for the current game";
  return <>
    <PanelSection title="Screen Sync">
      <PanelSectionRow><div style={{ fontSize: ".8em", opacity: .82 }}>
        Matches the visible Gamescope picture to the 17-pixel light bar. Frames stay in memory and are never saved or sent over the network.
      </div></PanelSectionRow>
      <PanelSectionRow><div style={{ width: "100%", fontSize: ".78em", opacity: .78 }}>
        <div>Capture revision: {status.screen_sync.revision}</div>
        <div style={{ color: status.debug.engine_running ? "#93f7a7" : "#ff9a9a" }}>
          Runtime: {status.debug.engine_running
            ? `render loop live · decision ${formatAge(status.debug.decision_age_s)}`
            : `render loop stopped${status.error ? ` · ${status.error}` : ""}`}
        </div>
        {status.debug.last_runtime_error ? <div style={{ color: "#ff9a9a" }}>
          Last runtime fault ({formatAge(status.debug.last_runtime_error_age_s)}): {status.debug.last_runtime_error}
        </div> : null}
        <div>{phase}</div>
        {status.screen_sync.node_name ? <div>Source: {status.screen_sync.node_name}</div> : null}
        {status.screen_sync.runtime_dir ? <div>PipeWire session: {status.screen_sync.runtime_dir}</div> : null}
        {status.screen_sync.capture_identity ? <div>PipeWire identity: {status.screen_sync.capture_identity}</div> : null}
        {status.screen_sync.capture_selector ? <div>Selector: {status.screen_sync.capture_selector}</div> : null}
        {directGamescopeSelector
          ? <div style={{ color: status.screen_sync.phase === "capturing" ? "#93f7a7" : "#ffd37a" }}>
            {status.screen_sync.phase === "capturing"
              ? "Direct Gamescope source active. Numeric node enumeration is not required."
              : "Gamescope is not ready in this PipeWire session yet. Retrying automatically."}
          </div>
          : null}
        {status.screen_sync.orphan_processes_cleaned > 0
          ? <div>Recovered stale capture processes: {status.screen_sync.orphan_processes_cleaned}</div>
          : null}
        {status.screen_sync.capture_sessions_released > 0
          ? <div>Failed capture sessions released before retry: {status.screen_sync.capture_sessions_released}</div>
          : null}
        {status.screen_sync.last_release_error
          ? <div>Last released session: {status.screen_sync.last_release_error}</div>
          : null}
        {status.screen_sync.phase === "error" && status.screen_sync.discovery_detail
          ? <div>Discovery: {status.screen_sync.discovery_detail}</div>
          : null}
        {status.screen_sync.crop_top || status.screen_sync.crop_bottom
          ? <div>Ignored black bars: {status.screen_sync.crop_top} top, {status.screen_sync.crop_bottom} bottom</div>
          : null}
        <PalettePreview colors={status.screen_sync.colors} />
      </div></PanelSectionRow>
    </PanelSection>
    <PanelSection title="Activation">
      <PanelSectionRow><ToggleField
        label="Use during Steam screensaver"
        description="Temporarily follows the colours shown by Steam's screensaver. Your Home and in-game displays return when it closes."
        checked={status.screen_sync_screensaver_enabled}
        onChange={async (value) => setStatus(await setSetting("screen_sync_screensaver_enabled", value))} />
      </PanelSectionRow>
      <PanelSectionRow><div style={{ width: "100%", fontSize: ".78em", opacity: .78 }}>
        <div>{activationLabel}</div>
        <div>In-game default: {displayLabel(status.game_display)}</div>
        {status.display_override !== "inherit" && status.game.appid > 0
          ? <div>Current game override: {displayLabel(status.display_override)}</div>
          : null}
      </div></PanelSectionRow>
      <PanelSectionRow><ButtonItem
        label="Preview Screen Sync"
        description="Uses the real capture and rendering path for 15 seconds without changing Display routing."
        onClick={() => void previewScreenSync().then(setStatus).catch(console.warn)}>
        Preview for 15 seconds
      </ButtonItem></PanelSectionRow>
    </PanelSection>
    <PanelSection title="Screen mapping">
      <PanelSectionRow><DropdownItem label="Style" rgOptions={SCREEN_SYNC_STYLE_OPTIONS}
        selectedOption={status.screen_sync_style}
        onChange={async (option) => setStatus(await setSetting("screen_sync_style", String(option.data)))} /></PanelSectionRow>
      <PanelSectionRow><DropdownItem label="Reactivity" rgOptions={SCREEN_SYNC_REACTIVITY_OPTIONS}
        selectedOption={status.screen_sync_reactivity}
        onChange={async (option) => setStatus(await setSetting("screen_sync_reactivity", String(option.data)))} /></PanelSectionRow>
      <PanelSectionRow><DropdownItem label="Colour intensity" rgOptions={SCREEN_SYNC_COLOUR_OPTIONS}
        selectedOption={status.screen_sync_colour_intensity}
        onChange={async (option) => setStatus(await setSetting("screen_sync_colour_intensity", String(option.data)))} /></PanelSectionRow>
      <PanelSectionRow><SliderField label="Brightness"
        description="34 is the minimum retained because lower values switch the physical light bar off."
        value={status.screen_sync_brightness} min={34} max={255} step={1} showValue valueSuffix=" / 255"
        onChange={async (value) => setStatus(await setSetting("screen_sync_brightness", value))} /></PanelSectionRow>
      <PanelSectionRow><ToggleField label="Ignore cinematic black bars"
        description="Applies a crop only after the same top and bottom bars are detected in three consecutive frames."
        checked={status.screen_sync_ignore_black_bars}
        onChange={async (value) => setStatus(await setSetting("screen_sync_ignore_black_bars", value))} /></PanelSectionRow>
      <PanelSectionRow><SliderField label="Black threshold"
        description="Pixels at or below this brightness are treated as fully off."
        value={status.screen_sync_black_threshold} min={0} max={32} step={1} showValue
        onChange={async (value) => setStatus(await setSetting("screen_sync_black_threshold", value))} /></PanelSectionRow>
    </PanelSection>
    <PanelSection title="Capture fallback">
      <PanelSectionRow><div style={{ fontSize: ".76em", opacity: .76 }}>
        When Screen Sync pauses for Steam Game Recording or another capture consumer, Customization+ takes over automatically. The centre LED remains red while recording.
      </div></PanelSectionRow>
      {status.screen_sync.fallback_active ? <PanelSectionRow><div style={{ fontSize: ".78em" }}>
        Active: {status.screen_sync.fallback_reason}
      </div></PanelSectionRow> : null}
    </PanelSection>
    <PanelSection title="Capture safety">
      <PanelSectionRow>
        <div style={{ fontSize: ".76em", opacity: .74, paddingBottom: 8 }}>
          Screen Sync uses the local Gamescope PipeWire video source at 34 by 18 pixels and 10 frames per second. If Steam Game Recording, screen sharing, or another Gamescope capture consumer is active, capture stops and the fallback is used instead of competing for the stream.
        </div>
      </PanelSectionRow>
      <PanelSectionRow><ButtonItem
        label="Refresh capture status"
        description="Read the current Gamescope and PipeWire state and update the 17-colour preview."
        onClick={() => void getStatus().then(setStatus).catch(console.warn)}>
        Refresh
      </ButtonItem></PanelSectionRow>
    </PanelSection>
  </>;
}

function CompatibilityPanel({ status, setStatus }: { status: Status; setStatus: (next: Status) => void }) {
  const priorities = ([
    ["Artwork", "stripmine_priority_artwork", "The sampled game artwork display."],
    ["Performance", "stripmine_priority_performance", "CPU, GPU and mixed performance displays."],
    ["Weather", "stripmine_priority_weather", "Permanent and preview weather animations."],
    ["Controller displays", "stripmine_priority_controller", "Battery gauges, connection and charging displays."],
    ["Game launches", "stripmine_priority_game_launches", "Temporary animations using colours from the launched game's artwork."],
    ["Customization+", "stripmine_priority_customization", "The persistent user-authored display."],
    ["Screen Sync", "stripmine_priority_screen_sync", "Live colours captured from the running game."],
    ["Light Events", "stripmine_priority_light_events", "Notifications, achievements, screenshots and recording cues."],
  ] as const);
  return <>
    <PanelSection title="TW3-SteamRGB compatibility">
      <PanelSectionRow>
        <ToggleField
          label="Yield to TW3-SteamRGB HUD"
          description="While The Witcher 3 is running, pause GabeCubeAura permanent displays only when TW3-SteamRGB publishes a fresh ownership claim."
          checked={status.tw3_steamrgb_integration_enabled}
          onChange={async (value) => setStatus(await setSetting("tw3_steamrgb_integration_enabled", value))}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <div style={{ width: "100%", fontSize: ".82em", opacity: .86 }}>
          {status.tw3_steamrgb_detected
            ? status.tw3_steamrgb_active
              ? "A live TW3-SteamRGB claim is active. GabeCubeAura keeps temporary alerts available but yields its permanent display."
              : "A live TW3-SteamRGB claim was detected but is being ignored by this setting."
            : status.game.appid === 292030
              ? "The Witcher 3 is running, but no live TW3-SteamRGB claim is detected. GabeCubeAura keeps control."
              : "No live TW3-SteamRGB claim is detected."}
          <div style={{ marginTop: 6, opacity: .72 }}>
            Disable this only when TW3-SteamRGB is absent or for troubleshooting. If another plugin is physically writing to the bar, GabeCubeAura can still yield through its normal Valve and external-owner safety guard.
          </div>
        </div>
      </PanelSectionRow>
    </PanelSection>
    <PanelSection title="StripMine compatibility">
      <PanelSectionRow>
        <ToggleField
          label="Coordinate LED ownership"
          description="GabeCubeAura and StripMine exchange a short local lease before either writes. Unknown applications are still treated as conflicts."
          checked={status.stripmine_integration_enabled}
          onChange={async (value) => setStatus(await setSetting("stripmine_integration_enabled", value))}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <div style={{ width: "100%", fontSize: ".82em", opacity: .86 }}>
          {status.stripmine_detected
            ? "StripMine is active and the ownership link is live."
            : "StripMine is not currently claiming the light bar."}
          <div style={{ marginTop: 6, opacity: .72 }}>
            The selected owner keeps the bar until its output ends. Transfers wait for an acknowledgement, so intentional takeovers do not appear as external conflicts.
          </div>
        </div>
      </PanelSectionRow>
    </PanelSection>
    <PanelSection title="Priority while StripMine is active">
      {priorities.map(([label, key, description]) => <PanelSectionRow key={key}>
        <DropdownItem
          label={label}
          description={description}
          rgOptions={COMPANION_PRIORITY_OPTIONS}
          selectedOption={status[key]}
          onChange={async (option) => setStatus(await setSetting(key, option.data as CompanionPriority))}
        />
      </PanelSectionRow>)}
      <PanelSectionRow>
        <div style={{ width: "100%", fontSize: ".78em", opacity: .75 }}>
          Playtime countdowns and their critical alerts always remain GabeCubeAura priorities. If coordination is disabled, both plugins fall back to their independent ownership guards.
        </div>
      </PanelSectionRow>
    </PanelSection>
  </>;
}

type Page = "quick" | "routing" | "customization" | "artwork" | "performance" | "screen-sync" | "launches" | "countdown" | "events" | "controllers" | "weather" | "compatibility" | "updates" | "advanced";

const PAGE_END_LABELS: Record<Exclude<Page, "quick">, string> = {
  routing: "Display routing",
  customization: "Customization+",
  artwork: "Artwork",
  performance: "Performance",
  "screen-sync": "Screen Sync",
  launches: "Game launches",
  countdown: "Playtime",
  events: "Light events",
  controllers: "Controllers",
  weather: "Weather",
  compatibility: "Compatibility",
  updates: "Updates",
  advanced: "Advanced",
};

function SettingsPageEnd({ page, setStatus }: {
  page: Exclude<Page, "quick">;
  setStatus: (next: Status) => void;
}) {
  return <PanelSection>
    <PanelSectionRow><ButtonItem
      label={`End of ${PAGE_END_LABELS[page]} settings`}
      description="This final row keeps the complete page reachable with controller navigation."
      onClick={() => void getStatus().then(setStatus).catch(console.warn)}>
      Refresh status
    </ButtonItem></PanelSectionRow>
  </PanelSection>;
}

function Content({ page = "quick" }: { page?: Page }) {
  const [status, setStatusState] = useState<Status | null>(null);
  const [hero, setHero] = useState<ArtworkPayload | null>(null);
  const [heroRequestKey, setHeroRequestKey] = useState("");
  const [launchHero, setLaunchHero] = useState<ArtworkPayload | null>(null);
  const [launchHeroRequestKey, setLaunchHeroRequestKey] = useState("");
  const artworkRequests = useRef({ artwork: 0, launch: 0 });
  const [showDebug, setShowDebug] = useState(false);
  const [configurationExportPath, setConfigurationExportPath] = useState("");
  const [configurationExportError, setConfigurationExportError] = useState("");
  const [configurationActionMessage, setConfigurationActionMessage] = useState("");
  const [configurationBusy, setConfigurationBusy] = useState(false);
  const [launchPreviewError, setLaunchPreviewError] = useState("");
  const [update, setUpdate] = useState<UpdateStatus | null>(null);
  const [updateBusy, setUpdateBusy] = useState(false);
  const [updateLabResult, setUpdateLabResult] = useState<UpdateLabResult | null>(null);
  const [updateLabReportPath, setUpdateLabReportPath] = useState("");
  const manualTimer = useRef<number | null>(null);
  const setStatus = (next: Status) => {
    setStatusState(next);
  };

  useEffect(() => {
    let alive = true;
    void getStatus().then((next) => alive && setStatus(next)).catch(console.warn);
    const timer = window.setInterval(() => {
      void getStatus().then((next) => alive && setStatus(next)).catch(() => undefined);
    }, page === "events" || page === "controllers" || page === "weather"
      || page === "compatibility" || page === "launches" ? 100
      : page === "screen-sync" ? 250 : 1000);
    return () => {
      alive = false;
      window.clearInterval(timer);
      if (manualTimer.current != null) window.clearTimeout(manualTimer.current);
    };
  }, [page]);

  useEffect(() => {
    if (page !== "quick" && page !== "updates" && page !== "advanced") return;
    let alive = true;
    const refresh = () => void getUpdateStatus()
      .then((next) => alive && setUpdate(next))
      .catch((error) => console.warn("[GabeCubeAura] update status failed", error));
    refresh();
    const timer = window.setInterval(refresh, page === "updates" ? 1000 : 30_000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [page]);

  useEffect(() => {
    setLaunchPreviewError("");
  }, [status?.game.appid]);

  const loadAndSampleArtwork = useCallback(async (
    appid: number,
    source: ArtworkSource,
    purpose: "artwork" | "launch" = "artwork",
  ) => {
    const request = ++artworkRequests.current[purpose];
    const setArtwork = purpose === "launch" ? setLaunchHero : setHero;
    const setRequestKey = purpose === "launch" ? setLaunchHeroRequestKey : setHeroRequestKey;
    if (appid <= 0) {
      setArtwork(null);
      setRequestKey("");
      return;
    }
    const current = await getStatus();
    if (request !== artworkRequests.current[purpose]) return;
    const artwork = await getArtwork(appid, source, purpose);
    if (request !== artworkRequests.current[purpose]) return;
    setArtwork(artwork);
    setRequestKey(`${appid}:${source}`);
    if (!artwork.found || !artwork.data_uri || !artwork.fingerprint || artwork.cached) {
      const refreshed = await getStatus();
      if (request === artworkRequests.current[purpose]) setStatus(refreshed);
      return;
    }
    const mode = current.artwork_mode;
    const manualY = current.artwork_manual_y;
    const result = await sampleArtwork(artwork.data_uri, mode, manualY);
    if (request !== artworkRequests.current[purpose]) return;
    const next = await submitArtwork(
      appid,
      artwork.fingerprint,
      result.colors,
      result.y,
      result.dominantPalettes,
      artwork.filename ?? "",
      artwork.source ?? source,
      purpose,
    );
    if (request === artworkRequests.current[purpose]) setStatus(next);
  }, []);

  const refreshArtworkAfterConfiguration = (next: Status) => {
    setHeroRequestKey("");
    setLaunchHeroRequestKey("");
    if (next.game.appid > 0) {
      void Promise.all([
        loadAndSampleArtwork(next.game.appid, next.artwork_source, "artwork"),
        loadAndSampleArtwork(next.game.appid, next.launch_artwork_source, "launch"),
      ]).catch(console.warn);
    }
  };

  const importSelectedConfiguration = async (path: string) => {
    setConfigurationBusy(true);
    setConfigurationActionMessage("");
    try {
      const next = await importConfiguration(path);
      setStatus(next);
      refreshArtworkAfterConfiguration(next);
      setConfigurationActionMessage(`Imported ${path}. Saved settings and game profiles replaced.`);
    } catch (error) {
      setConfigurationActionMessage(`Import failed; saved settings were kept. ${String(error)}`);
    } finally {
      setConfigurationBusy(false);
    }
  };

  const chooseConfigurationFile = async () => {
    try {
      const selected = await openFilePicker(0, "/home/deck/Documents", true, false,
        undefined, ["json"]);
      const path = selected?.realpath || selected?.path;
      if (!path) return;
      let modal: ReturnType<typeof showModal> | undefined;
      modal = showModal(<ConfirmModal strTitle="Import GabeCubeAura configuration?"
        strDescription="This replaces every saved setting and per-game profile. The personal timer stops."
        strOKButtonText="Import" strCancelButtonText="Cancel"
        onCancel={() => modal?.Close()}
        onOK={() => { modal?.Close(); void importSelectedConfiguration(path); }} />);
    } catch (error) {
      if (!String(error).toLowerCase().includes("cancel")) {
        setConfigurationActionMessage(`Could not open configuration picker: ${String(error)}`);
      }
    }
  };

  const confirmConfigurationReset = () => {
    let modal: ReturnType<typeof showModal> | undefined;
    modal = showModal(<ConfirmModal strTitle="Reset GabeCubeAura settings?"
      strDescription="All saved settings and per-game profiles will return to the shipped defaults. The personal timer stops. Export a JSON backup first if you want to restore them later."
      strOKButtonText="Reset settings" strCancelButtonText="Cancel" bDestructiveWarning
      onCancel={() => modal?.Close()}
      onOK={() => {
        modal?.Close();
        setConfigurationBusy(true);
        setConfigurationActionMessage("");
        void resetConfiguration().then((next) => {
          setStatus(next);
          refreshArtworkAfterConfiguration(next);
          setConfigurationActionMessage("Settings and per-game profiles reset to GabeCubeAura defaults.");
        }).catch((error) => {
          setConfigurationActionMessage(`Reset failed: ${String(error)}`);
        }).finally(() => setConfigurationBusy(false));
      }} />);
  };

  useEffect(() => {
    if (!status) return;
    const needsArtwork = page === "artwork" || page === "launches"
      || (page === "quick" && status.current_display === "artwork");
    if (!needsArtwork) {
      setHero(null);
      setHeroRequestKey("");
      setLaunchHero(null);
      setLaunchHeroRequestKey("");
      return;
    }
    const purposes: ("artwork" | "launch")[] = [page === "launches" ? "launch" : "artwork"];
    for (const purpose of purposes) {
      const source = purpose === "launch" ? status.launch_artwork_source : status.artwork_source;
      void loadAndSampleArtwork(status.game.appid, source, purpose).catch((error) => {
        console.warn("[GabeCubeAura] artwork preview failed", error);
      });
    }
  }, [page, status?.game.appid, status?.current_display, status?.artwork_source,
    status?.launch_artwork_source, loadAndSampleArtwork]);

  if (!status) {
    return <PanelSection><PanelSectionRow>Loading GabeCubeAura…</PanelSectionRow></PanelSection>;
  }
  if (!status.available) {
    return (
      <PanelSection title="GabeCubeAura">
        <PanelSectionRow>
          <div style={{ fontSize: ".88em", opacity: 0.82 }}>
            No 17-pixel <code>valve-leds</code> light bar was found. GabeCubeAura is idle and has made no hardware changes.
            {status.error ? <div style={{ marginTop: 6 }}>{status.error}</div> : null}
          </div>
        </PanelSectionRow>
      </PanelSection>
    );
  }

  const changeArtworkSetting = async (key: string, value: unknown) => {
    const next = await setArtworkSetting(status.game.appid, key, value);
    setStatus(next);
    if (next.game.appid > 0) await loadAndSampleArtwork(next.game.appid, next.artwork_source, "artwork");
  };
  const changeManualPosition = (value: number) => {
    setStatus({ ...status, artwork_manual_y: value });
    if (manualTimer.current != null) window.clearTimeout(manualTimer.current);
    manualTimer.current = window.setTimeout(() => {
      manualTimer.current = null;
      void changeArtworkSetting("manual_y", value);
    }, 250);
  };
  const chooseTemperatureColor = (
    key: "temperature_custom_cool" | "temperature_custom_middle" | "temperature_custom_hot",
    label: string,
    color: [number, number, number],
  ) => {
    chooseSettingColor(key, label, color, setStatus);
  };
  const artColors = status.artwork.colors;
  const currentArtwork = status.game.appid > 0 && heroRequestKey === `${status.game.appid}:${status.artwork_source}`
    && hero?.appid === status.game.appid && hero.found && hero.data_uri ? hero : null;
  const currentLaunchArtwork = status.game.appid > 0 && launchHeroRequestKey === `${status.game.appid}:${status.launch_artwork_source}`
    && launchHero?.appid === status.game.appid && launchHero.found && launchHero.data_uri ? launchHero : null;
  const runLaunchPreview = async () => {
    setLaunchPreviewError("");
    try {
      const started = await previewLaunchArtwork();
      const next = await getStatus();
      setStatus(next);
      if (!started) {
        setLaunchPreviewError(!next.signalbar_enabled
          ? "Enable GabeCubeAura outputs before starting a preview."
          : "Preview could not start. Wait for the current game's artwork palette, then try again.");
      }
    } catch (error) {
      setLaunchPreviewError(`Preview failed: ${String(error)}`);
    }
  };
  const performanceColors = performancePreview(status);
  const baseShownColors = status.provider.startsWith("launch-artwork:") ? status.launch_artwork.colors
    : status.provider.startsWith("screen-sync") ? status.screen_sync.colors
    : status.provider.startsWith("customization:") ? status.customization.colors
    : status.provider.startsWith("event:") ? status.events.colors
    : status.provider.startsWith("controller:") || status.provider.startsWith("controller-") ? status.controllers.colors
    : status.provider === "countdown" ? status.countdown.colors
      : status.provider.startsWith("weather") ? status.weather.colors
      : status.provider.startsWith("artwork") ? artColors
        : status.provider.startsWith("performance") ? performanceColors : [];
  const shownColors = status.provider.endsWith("+recording")
    ? addRecordingMarker(status, baseShownColors) : baseShownColors;
  const shownLabel = status.provider.startsWith("launch-artwork:")
    ? `Game launch · ${LAUNCH_ARTWORK_PATTERN_OPTIONS.find((item) => item.data === status.launch_artwork_pattern)?.label ?? status.launch_artwork_pattern}`
    : status.provider.startsWith("screen-sync") ? "Screen Sync"
    : status.provider.startsWith("customization:") ? `Customization+ · ${customizationPatternLabel(status.customization_pattern)}`
    : status.provider.startsWith("event:") ? status.events.variant
    : status.provider.startsWith("controller:") ? `Controller · ${status.controllers.variant}`
      : status.provider === "controller-battery" ? "Controller battery"
      : status.provider === "controller-charging" ? "Controller charging"
      : status.provider === "controller-charge-complete" ? "Controller fully charged"
      : status.provider.startsWith("weather") ? `Weather · ${status.weather.location?.name ?? "preview"}`
    : status.provider === "countdown" ? status.countdown.label
      : status.provider === "valve" ? "Steam / another app"
        : status.provider === "none" ? "No GabeCubeAura output" : status.provider;
  const showPage = (target: Page) => page === target;

  const runUpdateAction = async (action: () => Promise<UpdateStatus>) => {
    setUpdateBusy(true);
    try {
      setUpdate(await action());
    } catch (error) {
      console.warn("[GabeCubeAura] update action failed", error);
      setUpdate(await getUpdateStatus());
    } finally {
      setUpdateBusy(false);
    }
  };

  const confirmUpdateInstall = () => {
    if (!update?.confirmation_token || !update.available_version) return;
    const token = update.confirmation_token;
    const target = update.available_version;
    let modal: ReturnType<typeof showModal> | undefined;
    modal = showModal(<ConfirmModal strTitle={update.return_to_stable ? "Return to stable GabeCubeAura?" : "Update GabeCubeAura?"}
      strDescription={update.return_to_stable
        ? `Return from ${update.installed_version} to stable ${target}? The downloaded package passed its checksum and package checks. Your settings and artwork cache will be kept. If the stable build does not start, GabeCubeAura restores the working beta. Decky will restart briefly.`
        : `Update from ${update.installed_version} to ${target}? The downloaded package passed its checksum and package checks. Your settings and artwork cache will be kept. Decky will restart briefly.`}
      strOKButtonText={update.return_to_stable ? "Install stable and restart" : "Update and restart Decky"} strCancelButtonText="Cancel"
      onCancel={() => modal?.Close()}
      onOK={() => {
        modal?.Close();
        setUpdateBusy(true);
        void installPreparedUpdate(token).catch((error) => {
          console.warn("[GabeCubeAura] update installation failed", error);
          setUpdateBusy(false);
          void getUpdateStatus().then(setUpdate).catch(console.warn);
        });
      }} />);
  };

  const runUpdateLab = async (scenario: UpdateLabResult["scenario"]) => {
    setUpdateBusy(true);
    setUpdateLabReportPath("");
    try {
      setUpdateLabResult(await runUpdateLabScenario(scenario));
    } catch (error) {
      setUpdateLabResult({
        scenario,
        passed: false,
        started_at: 0,
        finished_at: 0,
        details: String(error),
        report_available: false,
      });
    } finally {
      setUpdateBusy(false);
    }
  };

  return (
    <>
      {page === "quick" ? <PanelSection title="Status">
        <PanelSectionRow>
          <div style={{ width: "100%", fontSize: ".88em", lineHeight: 1.45 }}>
            <div><b>{status.active ? "Active" : "Suspended"}</b> · owner: {status.owner}</div>
            <div>Provider: {status.provider}</div>
            {status.game.appid > 0 || status.game.title ? (
              <div>{status.game.title || "Running game"} · AppID {status.game.appid || "unknown"}</div>
            ) : <div>No game running</div>}
            {status.suspension_reason ? <div style={{ opacity: 0.72 }}>{status.suspension_reason}</div> : null}
          </div>
        </PanelSectionRow>
      </PanelSection> : null}

      {page === "quick" && update?.phase === "available" ? <PanelSection title="Software update">
        <PanelSectionRow>
          <ButtonItem label={`Update available: ${update.available_version}`}
            description="Review the release notes and package checks before installing."
            onClick={() => { Navigation.CloseSideMenus(); Navigation.Navigate("/gabecubeaura/settings/updates"); }}>
            Review update
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection> : null}

      {page === "quick" ? <PanelSection title="Permanent displays">
        <PanelSectionRow><ToggleField label="Enable GabeCubeAura outputs"
          description="Turns off every GabeCubeAura light without deleting display routes, launch effects, or per-game choices."
          checked={status.signalbar_enabled}
          onChange={async (value) => setStatus(await setSetting("signalbar_enabled", value))} /></PanelSectionRow>
        <PanelSectionRow><div style={{ width: "100%", fontSize: ".82em" }}>
          <div>Home: <b>{displayLabel(status.home_display)}</b></div>
          <div>In game: <b>{displayLabel(status.game_display)}</b></div>
          <div>Current: <b>{displayLabel(status.current_display)}</b></div>
        </div></PanelSectionRow>
        {status.game.appid > 0 ? <>
          <PanelSectionRow><DropdownItem label="Display for this game"
            description={`Saved for ${status.game.title || `AppID ${status.game.appid}`}. Does not change other games.`}
            rgOptions={[{ data: "inherit", label: "Use in-game default" }, ...GAME_DISPLAY_OPTIONS]}
            selectedOption={status.display_override}
            onChange={async (option) => setStatus(await setGameDisplay(status.game.appid, String(option.data)))} /></PanelSectionRow>
          <PanelSectionRow><div style={{ fontSize: ".78em", opacity: .75 }}>
            {!status.signalbar_enabled ? "GabeCubeAura is disabled. The saved game choice will apply when re-enabled."
              : `Active display: ${displayLabel(status.current_display)}${status.display_override === "inherit" ? " (in-game default)" : " (game profile)"}. Temporary signals keep their own priority.`}
          </div></PanelSectionRow>
        </> : null}
      </PanelSection> : null}

      {page === "quick" ? <PanelSection title="Temporary layers">
        <PanelSectionRow><div style={{ width: "100%", fontSize: ".82em", lineHeight: 1.5 }}>
          <div>Game launches: <b>{status.launch_artwork_animation_enabled
            ? `On · ${LAUNCH_ARTWORK_PATTERN_OPTIONS.find((item) => item.data === status.launch_artwork_pattern)?.label} · ${status.launch_artwork_duration_seconds} s · ${status.launch_artwork_colour_count} colours`
            : "Off"}</b></div>
          <div>Light events: <b>{status.events_enabled ? "On" : "Off"}</b></div>
          <div>Playtime warnings: <b>{status.parental_countdown_enabled ? "On" : "Off"}</b></div>
          <div>Controller alerts: <b>{status.controller_alerts_enabled ? "On" : "Off"}</b></div>
        </div></PanelSectionRow>
      </PanelSection> : null}

      {page === "quick" ? <PanelSection title="Now showing">
        <PanelSectionRow>
          <div style={{ width: "100%", fontSize: ".84em" }}>
            <div><b>{shownLabel}</b></div>
            {status.game.title ? <div>{status.game.title}</div> : null}
            {status.provider.startsWith("controller") && status.controllers.controllers.length ? <div style={{ marginTop: 5 }}>
              {status.controllers.controllers.map((controller) =>
                `${controller.name} ${controllerChargeLabel(controller)}`).join(" · ")}
            </div> : null}
            {status.provider.startsWith("weather") ? <div style={{ marginTop: 5 }}>
              {WEATHER_CONDITIONS.find((item) => item.data === status.weather.condition)?.label ?? "Current weather"}
            </div> : null}
            {status.provider.startsWith("performance") ? <div style={{ marginTop: 7 }}>
              <div style={{ marginBottom: 4, fontSize: ".92em", opacity: .72 }}>Performance sensors</div>
              <PerformanceReadout status={status} />
            </div> : null}
            {status.provider.startsWith("artwork") && status.game.appid > 0 ? <div style={{ marginTop: 8 }}>
              <div style={{ marginBottom: 6, opacity: .76 }}>
                Game artwork{currentArtwork?.source_label ? ` · ${currentArtwork.source_label}` : ""}
              </div>
              {currentArtwork ? <ArtworkImage artwork={currentArtwork} title={status.game.title || "current game"} compact />
                : <div style={{ opacity: .65 }}>No game artwork available yet.</div>}
            </div> : null}
            <PalettePreview colors={shownColors} />
            <div style={{ opacity: .65 }}>17-LED logical preview</div>
            <div style={{ opacity: .72 }}>Family countdown takes priority. Short alerts temporarily replace the selected permanent display, then it returns.</div>
          </div>
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem label="Detailed settings" onClick={() => { Navigation.CloseSideMenus(); Navigation.Navigate("/gabecubeaura/settings"); }}>
            Open settings
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection> : null}

      {showPage("routing") ? <>
        <PanelSection title="Display routing">
          <PanelSectionRow><ToggleField label="Enable GabeCubeAura outputs"
            description="Turns off every GabeCubeAura light without deleting display routes, launch effects, or per-game choices."
            checked={status.signalbar_enabled}
            onChange={async (value) => setStatus(await setSetting("signalbar_enabled", value))} /></PanelSectionRow>
          <PanelSectionRow><DropdownItem label="Home display"
            description="The permanent display used when no game is running. Temporary alerts and previews may still replace it."
            rgOptions={HOME_DISPLAY_OPTIONS} selectedOption={status.home_display}
            onChange={async (option) => setStatus(await setSetting("home_display", String(option.data)))} /></PanelSectionRow>
          <PanelSectionRow><DropdownItem label="In-game display"
            description="The permanent display used by games without their own override."
            rgOptions={GAME_DISPLAY_OPTIONS} selectedOption={status.game_display}
            onChange={async (option) => setStatus(await setSetting("game_display", String(option.data)))} /></PanelSectionRow>
          <PanelSectionRow><div style={{ fontSize: ".78em", opacity: .75 }}>
            <b>GabeCubeAura Off</b> means no permanent GabeCubeAura display in that context; Steam keeps the bar between temporary layers. Game launches, alerts and playtime warnings remain available. The master switch above disables everything. Weather requires a city.
          </div></PanelSectionRow>
        </PanelSection>
        {status.game.appid > 0 ? <PanelSection title="Current game override">
          <PanelSectionRow><DropdownItem label={status.game.title || `AppID ${status.game.appid}`}
            description="Saved for this AppID only."
            rgOptions={[{ data: "inherit", label: "Use in-game default" }, ...GAME_DISPLAY_OPTIONS]}
            selectedOption={status.display_override}
            onChange={async (option) => setStatus(await setGameDisplay(status.game.appid, String(option.data)))} /></PanelSectionRow>
        </PanelSection> : null}
      </> : null}

      {showPage("customization") ? <CustomizationPanel status={status} setStatus={setStatus} /> : null}

      {showPage("screen-sync") ? <ScreenSyncPanel status={status} setStatus={setStatus} /> : null}

      {showPage("artwork") ? <PanelSection title="Artwork display">
        <PanelSectionRow>
          <DropdownItem
            label="Steam image"
            rgOptions={ARTWORK_SOURCE_OPTIONS}
            selectedOption={status.artwork_source}
            onChange={(option) => void changeArtworkSetting("source", String(option.data))}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <DropdownItem
            label="Sample row"
            rgOptions={ARTWORK_OPTIONS}
            selectedOption={status.artwork_mode}
            onChange={(option) => void changeArtworkSetting("mode", String(option.data))}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <div style={{ fontSize: ".78em", opacity: 0.72 }}>
            {status.game.appid > 0
              ? status.artwork_custom
                ? `Saved for ${status.game.title || `AppID ${status.game.appid}`}`
                : "Using the default; your first change will be saved for this game."
              : "No game running: changes update the default for new games."}
          </div>
        </PanelSectionRow>
        {status.artwork_mode === "manual" ? (
          <PanelSectionRow>
            <SliderField
              label="Vertical position"
              value={Math.round(status.artwork_manual_y * 100)}
              min={15}
              max={90}
              step={1}
              showValue
              valueSuffix="%"
              onChange={(value) => changeManualPosition(value / 100)}
            />
          </PanelSectionRow>
        ) : null}
        {currentArtwork ? (
          <PanelSectionRow>
            <ArtworkImage
              artwork={currentArtwork}
              title={status.game.title || "current game"}
              sampleLine={status.artwork_mode === "manual" ? status.artwork_manual_y : undefined}
            />
          </PanelSectionRow>
        ) : null}
        <PanelSectionRow>
          <div style={{ width: "100%", fontSize: ".8em", opacity: 0.86 }}>
            {status.game.title || (status.game.appid > 0 ? `AppID ${status.game.appid}` : "No game selected")}
            {currentArtwork?.source_label ? ` · ${currentArtwork.source_label}` : ""}
            {status.artwork.sample_y != null ? ` · row ${Math.round(status.artwork.sample_y * 100)}%` : ""}
            <PalettePreview colors={artColors} />
          </div>
        </PanelSectionRow>
      </PanelSection> : null}

      {showPage("launches") ? <PanelSection title="Game launch animation">
        <PanelSectionRow><ToggleField
          label="Animate from game artwork"
          description="Play one sequence when GabeCubeAura detects a newly running Steam AppID. This works with every Home and in-game display; starting GabeCubeAura while a game is already running does not replay it."
          checked={status.launch_artwork_animation_enabled}
          onChange={async (value) => setStatus(await setSetting("launch_artwork_animation_enabled", value))}
        /></PanelSectionRow>
        <PanelSectionRow><div style={{ fontSize: ".8em", opacity: .82 }}>
          {status.game.appid > 0
            ? `${status.game.title || "Running game"} · AppID ${status.game.appid} · ${status.launch_artwork_palette_mode === "custom" ? "custom palette saved" : "artwork palette"}`
            : "Start a game to detect its artwork or save a palette for its AppID."}
        </div></PanelSectionRow>
        <PanelSectionRow><DropdownItem
          label="Artwork image"
          description="Uses Steam's local artwork, including custom SteamGridDB images already installed in Steam. No image is uploaded."
          rgOptions={ARTWORK_SOURCE_OPTIONS}
          selectedOption={status.launch_artwork_source}
          onChange={async (option) => {
            const next = await setSetting("launch_artwork_source", String(option.data));
            setStatus(next);
            if (next.game.appid > 0) await loadAndSampleArtwork(
              next.game.appid, next.launch_artwork_source, "launch",
            );
          }}
        /></PanelSectionRow>
        <PanelSectionRow><DropdownItem
          label="Palette source"
          description="A custom palette is saved for this AppID and reused on future launches."
          rgOptions={LAUNCH_PALETTE_MODE_OPTIONS}
          selectedOption={status.launch_artwork_palette_mode}
          disabled={status.game.appid <= 0}
          onChange={async (option) => setStatus(await setLaunchArtworkSetting(
            status.game.appid, "palette_mode", String(option.data),
          ))}
        /></PanelSectionRow>
        <PanelSectionRow><DropdownItem
          label="Number of colours"
          rgOptions={LAUNCH_ARTWORK_COLOUR_OPTIONS}
          selectedOption={status.launch_artwork_colour_count}
          onChange={async (option) => setStatus(await setSetting("launch_artwork_colour_count", Number(option.data)))}
        /></PanelSectionRow>
        {status.launch_artwork_palette_mode === "custom" && status.game.appid > 0
          ? status.launch_artwork_custom_palettes[String(status.launch_artwork_colour_count) as "2" | "3"].map((color, index) =>
            <PanelSectionRow key={`launch-custom-${status.launch_artwork_colour_count}-${index}`}>
              <PreciseColorEditor label={`Launch colour ${index + 1}`} color={color}
                onChange={(nextColor) => {
                  const palettes = {
                    "2": status.launch_artwork_custom_palettes["2"].map((entry) => [...entry] as RGB) as [RGB, RGB],
                    "3": status.launch_artwork_custom_palettes["3"].map((entry) => [...entry] as RGB) as [RGB, RGB, RGB],
                  };
                  palettes[String(status.launch_artwork_colour_count) as "2" | "3"][index] = nextColor;
                  void setLaunchArtworkSetting(status.game.appid, "custom_palettes", palettes).then(setStatus).catch(console.warn);
                }} />
            </PanelSectionRow>) : null}
        <PanelSectionRow><DropdownItem
          label="Pattern"
          rgOptions={LAUNCH_ARTWORK_PATTERN_OPTIONS}
          selectedOption={status.launch_artwork_pattern}
          onChange={async (option) => setStatus(await setSetting("launch_artwork_pattern", String(option.data)))}
        /></PanelSectionRow>
        <PanelSectionRow><SliderField
          label="Animation duration"
          value={status.launch_artwork_duration_seconds}
          min={3}
          max={45}
          step={1}
          showValue
          valueSuffix=" s"
          onChange={async (value) => setStatus(await setSetting("launch_artwork_duration_seconds", value))}
        /></PanelSectionRow>
        <PanelSectionRow><div style={{ width: "100%", fontSize: ".8em", opacity: .86 }}>
          {status.launch_artwork_palette_mode === "custom" ? "Saved colours for this game." : "Detected colours from the complete image, independent of the permanent Artwork row."}
        </div></PanelSectionRow>
        <PanelSectionRow><ButtonItem
          label="Preview launch animation"
          description={!status.signalbar_enabled
            ? "Enable GabeCubeAura outputs first."
            : status.game.appid > 0 && (status.launch_artwork.dominant_colors?.length ?? 0) > 0
            ? "Play the selected pattern with the current game's active palette."
            : "Start a game and wait for its palette first."}
          disabled={!status.signalbar_enabled || status.game.appid <= 0 || (status.launch_artwork.dominant_colors?.length ?? 0) === 0}
          onClick={() => void runLaunchPreview()}
        >Preview</ButtonItem></PanelSectionRow>
        <PanelSectionRow><div style={{ width: "100%", fontSize: ".78em", opacity: .82 }}>
          Live 17-LED launch preview
          <PalettePreview colors={status.launch_artwork.colors ?? []} />
        </div></PanelSectionRow>
        <PanelSectionRow><div style={{ fontSize: ".76em", opacity: .72 }}>
          {status.launch_artwork.active
            ? `${status.launch_artwork.paused ? "Paused by a short alert" : "Playing"} · ${Math.ceil(status.launch_artwork.remaining_seconds)} s remaining`
            : status.launch_artwork.pending ? "Waiting for safe LED ownership and artwork colours…"
              : launchPreviewError || "Idle"}
        </div></PanelSectionRow>
        {currentLaunchArtwork ? <PanelSectionRow>
          <Focusable style={{ width: "100%", paddingBottom: 28, scrollMarginBottom: 24 }} aria-label="Launch artwork preview">
            <ArtworkImage artwork={currentLaunchArtwork} title={status.game.title || "current game"} />
          </Focusable>
        </PanelSectionRow> : null}
        <PanelSectionRow><ButtonItem
          label="Preview launch animation"
          description={!status.signalbar_enabled
            ? "Enable GabeCubeAura outputs first."
            : status.game.appid > 0 && (status.launch_artwork.dominant_colors?.length ?? 0) > 0
              ? "Play the selected pattern again after reviewing the artwork."
              : "Start a game and wait for its palette first."}
          disabled={!status.signalbar_enabled || status.game.appid <= 0 || (status.launch_artwork.dominant_colors?.length ?? 0) === 0}
          onClick={() => void runLaunchPreview()}
        >Preview</ButtonItem></PanelSectionRow>
      </PanelSection> : null}

      {showPage("performance") ? <PanelSection title="Performance">
        <PanelSectionRow><div style={{ fontSize: ".78em", opacity: .75 }}>
          Sensors update every 0.5 seconds in all display modes. These settings do not switch the active display.
        </div></PanelSectionRow>
        <PanelSectionRow>
          <DropdownItem
            label="Meter"
            rgOptions={PERFORMANCE_OPTIONS}
            selectedOption={status.performance_metric}
            onChange={async (option) => setStatus(await setSetting("performance_metric", String(option.data)))}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <DropdownItem
            label="Meter response"
            rgOptions={SMOOTHING_OPTIONS}
            selectedOption={status.performance_smoothing}
            onChange={async (option) => setStatus(await setSetting("performance_smoothing", String(option.data)))}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <div style={{ fontSize: ".78em", opacity: 0.72 }}>
            {status.performance_smoothing === "responsive"
              ? "Follows short CPU/GPU changes more closely."
              : status.performance_smoothing === "smooth"
                ? "Slow, steady movement with stronger filtering."
                : "Reduces sudden jumps while keeping sustained load changes visible."}
          </div>
        </PanelSectionRow>
        {status.performance_metric === "mixed" ? (
          <>
            <PanelSectionRow>
              <DropdownItem
                label="Fill direction"
                rgOptions={DIRECTION_OPTIONS}
                selectedOption={status.mixed_direction}
                onChange={async (option) => setStatus(await setSetting("mixed_direction", String(option.data)))}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <div style={{ fontSize: ".78em", opacity: 0.72 }}>
                CPU uses the left 8 LEDs, GPU the right 8, with the centre LED off. Choose two left-to-right meters or the mirrored layout that grows from both edges toward the centre.
              </div>
            </PanelSectionRow>
          </>
        ) : null}
        <PanelSectionRow>
          <div style={{ width: "100%" }}>
            <PerformanceReadout status={status} />
            <PalettePreview colors={performanceColors} />
          </div>
        </PanelSectionRow>
        <PanelSectionRow>
          <DropdownItem
            label="Temperature colours"
            rgOptions={PALETTE_OPTIONS}
            selectedOption={status.temperature_palette}
            onChange={async (option) => setStatus(await setSetting("temperature_palette", String(option.data)))}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <div style={{ fontSize: ".78em", opacity: 0.72 }}>
            Length shows load. Colour shows temperature: the palette starts at Cool temperature and reaches its final hot colour at Hot temperature, with a continuous blend between them.
          </div>
        </PanelSectionRow>
        {status.temperature_palette === "custom" ? <>
          <PanelSectionRow>
            <ColorChoice
              label="Cool colour"
              color={status.temperature_custom_cool}
              onClick={() => chooseTemperatureColor("temperature_custom_cool", "Cool colour", status.temperature_custom_cool)}
            />
          </PanelSectionRow>
          <PanelSectionRow>
            <ColorChoice
              label="Middle colour"
              color={status.temperature_custom_middle}
              onClick={() => chooseTemperatureColor("temperature_custom_middle", "Middle colour", status.temperature_custom_middle)}
            />
          </PanelSectionRow>
          <PanelSectionRow>
            <ColorChoice
              label="Hot colour"
              color={status.temperature_custom_hot}
              onClick={() => chooseTemperatureColor("temperature_custom_hot", "Hot colour", status.temperature_custom_hot)}
            />
          </PanelSectionRow>
        </> : null}
        <PanelSectionRow>
          <SliderField
            label="Cool temperature"
            value={status.cool_temp_c}
            min={30}
            max={80}
            step={1}
            showValue
            valueSuffix="°C"
            onChange={async (value) => setStatus(await setSetting("cool_temp_c", value))}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <SliderField
            label="Hot temperature"
            value={status.hot_temp_c}
            min={60}
            max={110}
            step={1}
            showValue
            valueSuffix="°C"
            onChange={async (value) => setStatus(await setSetting("hot_temp_c", value))}
          />
        </PanelSectionRow>
      </PanelSection> : null}

      {showPage("countdown") ? <CountdownPanel status={status} setStatus={setStatus} /> : null}

      {showPage("events") ? <EventsPanel status={status} setStatus={setStatus} /> : null}

      {showPage("controllers") ? <ControllersPanel status={status} setStatus={setStatus} /> : null}

      {showPage("weather") ? <WeatherPanel status={status} setStatus={setStatus} /> : null}

      {showPage("compatibility") ? <CompatibilityPanel status={status} setStatus={setStatus} /> : null}

      {showPage("updates") && update ? <>
        <PanelSection title="Software updates">
          <PanelSectionRow><div style={{ width: "100%", fontSize: ".82em", lineHeight: 1.45 }}>
            <div>Installed version: <b>{update.installed_version}</b></div>
            <div>{update.channel === "stable" ? "Latest stable version" : "Latest beta or stable version"}: <b>{update.available_version || update.installed_version}</b></div>
            <div>Current status: <b>{updatePhaseLabel(update)}</b></div>
            <div>Last checked: {formatUpdateDate(update.last_checked_at)}</div>
            {update.prepared_digest ? <div>Verified SHA256: <code>{update.prepared_digest.slice(0, 12)}...</code></div> : null}
            {update.test_build ? <div style={{ marginTop: 6, color: "#ffd166", fontWeight: 700 }}>TEST BUILD</div> : null}
          </div></PanelSectionRow>
          <PanelSectionRow><ButtonItem label="Check for updates"
            disabled={updateBusy || ["checking", "downloading", "verifying", "ready", "installing", "restart_pending"].includes(update.phase)}
            onClick={() => void runUpdateAction(checkForUpdates)}>Check now</ButtonItem></PanelSectionRow>
          {update.release_url ? <PanelSectionRow><ButtonItem label="View release notes"
            description="Opens the official Alyenax/GabeCubeAura release page."
            onClick={() => Navigation.NavigateToExternalWeb(update.release_url)}>Open GitHub</ButtonItem></PanelSectionRow> : null}
          {update.phase === "available" ? <PanelSectionRow><ButtonItem label={update.return_to_stable ? `Download stable ${update.available_version}` : "Download update"}
            description="Downloads and checks the archive. Nothing is installed yet."
            disabled={updateBusy} onClick={() => void runUpdateAction(prepareUpdate)}>Download and verify</ButtonItem></PanelSectionRow> : null}
          {update.phase === "ready" ? <PanelSectionRow><ButtonItem label={update.return_to_stable ? `Return to stable ${update.available_version}` : `Install ${update.available_version}`}
            description="Settings and artwork caches are kept. Decky restarts briefly."
            disabled={updateBusy} onClick={confirmUpdateInstall}>Update and restart Decky</ButtonItem></PanelSectionRow> : null}
          {update.release_notes ? <PanelSectionRow><div style={{ width: "100%", fontSize: ".76em", opacity: .8, whiteSpace: "pre-wrap", maxHeight: 180, overflow: "hidden" }}>
            {update.release_notes}
          </div></PanelSectionRow> : null}
          {update.phase === "error" ? <PanelSectionRow><ButtonItem label="Dismiss update error"
            onClick={() => void runUpdateAction(dismissUpdateError)}>Dismiss</ButtonItem></PanelSectionRow> : null}
        </PanelSection>
        <PanelSection title="Automatic checks">
          <PanelSectionRow><ToggleField label="Automatically check for updates"
            description="Checks once after GabeCubeAura starts, then at the selected interval. Nothing is installed without your confirmation."
            checked={update.auto_check} onChange={(value) => void runUpdateAction(() => setUpdatePreferences(value, update.notifications, update.check_interval_minutes, update.channel))} /></PanelSectionRow>
          <PanelSectionRow><DropdownItem label="Automatic check interval"
            description="Used after the automatic check that runs when Steam loads the plugin."
            disabled={!update.auto_check || updateBusy}
            rgOptions={UPDATE_INTERVAL_OPTIONS} selectedOption={update.check_interval_minutes}
            onChange={(option) => void runUpdateAction(() => setUpdatePreferences(update.auto_check, update.notifications, Number(option.data), update.channel))} /></PanelSectionRow>
          <PanelSectionRow><DropdownItem label="Update channel"
            description={update.channel === "stable"
              ? "Stable releases only."
              : "Published beta releases and later stable releases. Changing channel checks immediately."}
            disabled={updateBusy || ["downloading", "verifying", "ready", "installing", "restart_pending"].includes(update.phase)}
            rgOptions={UPDATE_CHANNEL_OPTIONS} selectedOption={update.channel}
            onChange={(option) => void runUpdateAction(() => setUpdatePreferences(update.auto_check, update.notifications, update.check_interval_minutes, String(option.data) as "stable" | "beta"))} /></PanelSectionRow>
          <PanelSectionRow><ToggleField label="Notify me when an update is available"
            description="Shows one Decky notification for each new version on the selected channel."
            checked={update.notifications} onChange={(value) => void runUpdateAction(() => setUpdatePreferences(update.auto_check, value, update.check_interval_minutes, update.channel))} /></PanelSectionRow>
        </PanelSection>
        <PanelSection title="Installation safety">
          <PanelSectionRow><div style={{ width: "100%", fontSize: ".78em", opacity: .82 }}>
            Updates are downloaded from the official GabeCubeAura repository and checked before installation. Settings and artwork caches are kept. Decky restarts briefly after an update.
            {update.last_result ? <div style={{ marginTop: 7 }}>Last result: {updatePhaseLabel(update)}</div> : null}
          </div></PanelSectionRow>
          <PanelSectionRow><ButtonItem label="Check again"
            description="Final focusable control for controller navigation."
            disabled={updateBusy || update.phase === "ready"} onClick={() => void runUpdateAction(checkForUpdates)}>Check for updates</ButtonItem></PanelSectionRow>
        </PanelSection>
      </> : null}

      {showPage("advanced") ? <PanelSection title="Advanced / debug">
        <PanelSectionRow>
          <ToggleField
            label="Show debug details"
            checked={showDebug}
            onChange={setShowDebug}
          />
        </PanelSectionRow>
        {showDebug ? (
          <>
            <PanelSectionRow>
              <div style={{ width: "100%", padding: "8px 10px", background: "rgba(0, 0, 0, .24)", borderRadius: 6, overflowWrap: "anywhere" }}>
                <div style={{ fontSize: ".88em", fontWeight: 700 }}>Saved configuration</div>
                <div style={{ fontSize: ".68em", opacity: .7, marginBottom: 6 }}>
                  GabeCubeAura {status.version} · saved choices, including inactive options · no device IDs
                </div>
                {buildSettingsSnapshot(status).map((section) => <div key={section.title} style={{ marginTop: 7 }}>
                  <div style={{ fontSize: ".77em", fontWeight: 700, color: "#9ee8f4" }}>{section.title}</div>
                  {section.lines.map((line, index) => <div key={index} style={{ fontSize: ".72em", lineHeight: 1.25 }}>{line}</div>)}
                </div>)}
              </div>
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem
                label="Export configuration JSON"
                description={configurationExportPath
                  ? `Saved to ${configurationExportPath}`
                  : "Write a readable copy to Documents when available; the exact path appears here."}
                onClick={() => void exportConfiguration()
                  .then((result) => {
                    setConfigurationExportPath(result.path);
                    setConfigurationExportError("");
                  })
                  .catch((error) => {
                    console.warn("[GabeCubeAura] configuration export failed", error);
                    setConfigurationExportError(error instanceof Error ? error.message : String(error));
                  })}
              >Export JSON</ButtonItem>
            </PanelSectionRow>
            {configurationExportError ? <PanelSectionRow>
              <div style={{ width: "100%", fontSize: ".76em", color: "#ff9e9e", overflowWrap: "anywhere" }}>
                Export failed: {configurationExportError}
              </div>
            </PanelSectionRow> : null}
            <PanelSectionRow><ButtonItem label="Import configuration JSON"
              description="Choose a GabeCubeAura export from Documents or another location. Replaces saved settings and per-game profiles."
              disabled={configurationBusy} onClick={() => void chooseConfigurationFile()}>Import JSON</ButtonItem></PanelSectionRow>
            <PanelSectionRow><ButtonItem label="Reset to defaults"
              description="Return to the shipped settings, clear per-game profiles and stop the personal timer. Confirmation required."
              disabled={configurationBusy} onClick={confirmConfigurationReset}>Reset</ButtonItem></PanelSectionRow>
            {configurationActionMessage ? <PanelSectionRow>
              <div style={{ width: "100%", fontSize: ".76em", overflowWrap: "anywhere" }}>
                {configurationActionMessage}
              </div>
            </PanelSectionRow> : null}
            <PanelSectionRow>
              <div style={{ width: "100%", fontSize: ".76em", opacity: 0.78, overflowWrap: "anywhere" }}>
                <div>LED path: {status.debug.led_path}</div>
                <div>Last LED write: {formatAge(status.debug.last_write_age_s)}</div>
                <div>Total LED writes: {status.debug.writes}</div>
                <div>
                  Render loop: {status.debug.engine_running ? "live" : "stopped"}
                  {` · decision ${formatAge(status.debug.decision_age_s)}`}
                  {status.error ? ` · ${status.error}` : ""}
                </div>
                {status.debug.last_runtime_error ? <div style={{ color: "#ff9a9a" }}>
                  Last runtime fault ({formatAge(status.debug.last_runtime_error_age_s)}): {status.debug.last_runtime_error}
                </div> : null}
                <div>
                  Ownership guard: {status.debug.guard_state === "blocked"
                    ? `blocked · ${status.debug.guard_reason}`
                    : "ready"}
                </div>
                <div>
                  Guard timers: cooldown {status.debug.cooldown_remaining.toFixed(1)} s
                  {" · "}stability {status.debug.stable_remaining.toFixed(1)} s
                </div>
                <div>Last external LED change: {formatAge(status.debug.last_external_age_s)}</div>
                <div>
                  Steam priority: {status.debug.steam_priority
                    ? status.debug.steam_priority_reason || "active"
                    : "inactive"}
                  {status.debug.steam_lease_remaining_s > 0
                    ? ` · lease ${status.debug.steam_lease_remaining_s.toFixed(1)} s`
                    : ""}
                </div>
                <div>
                  Ownership recovery: {status.debug.last_recovery_age_s == null
                    ? "none"
                    : `${status.debug.last_recovery_reason} · ${formatAge(status.debug.last_recovery_age_s)}`}
                </div>
                {status.debug.launch_handoff_remaining_s > 0 ? <div>
                  Waiting for Steam launch writes: {status.debug.launch_handoff_remaining_s.toFixed(1)} s
                </div> : null}
                <div>
                  Game detection: {status.debug.game_detection_source}
                  {status.debug.game_sync_ms == null ? "" : ` · backend ${Math.round(status.debug.game_sync_ms)} ms`}
                </div>
                <div>
                  Session continuity: {status.debug.game_session_state}
                  {` · retained ${status.debug.game_retained_count} time${status.debug.game_retained_count === 1 ? "" : "s"}`}
                  {status.debug.frontend_heartbeat_age_s == null
                    ? " · no frontend heartbeat"
                    : ` · heartbeat ${formatAge(status.debug.frontend_heartbeat_age_s)}`}
                </div>
                <div>
                  Steam Families callback: {status.debug.parental_callback_state === "waiting"
                    ? `waiting ${status.debug.parental_wait_s?.toFixed(1) ?? "0.0"} s`
                    : status.debug.parental_callback_state === "received"
                      ? `received after ${Math.round(status.debug.parental_callback_delay_ms ?? 0)} ms`
                      : status.debug.parental_callback_state}
                </div>
                <div>
                  Controller data: {status.debug.controller_callback_source}
                  {status.debug.controller_last_update_age_s == null
                    ? " · no reading yet"
                    : ` · ${formatAge(status.debug.controller_last_update_age_s)}`}
                </div>
                <div>Weather: {status.weather.phase} · {status.weather.location?.name ?? "no city"}
                  {status.weather.age_s == null ? "" : ` · updated ${formatAge(status.weather.age_s)}`}
                  {status.weather.error ? ` · ${status.weather.error}` : ""}
                </div>
                <div>
                  SteamInputManager: {status.debug.controller_telemetry?.phase ?? "starting"}
                  {` · hooks ${status.debug.controller_telemetry?.hooks ?? 0}/3 · queries ${status.debug.controller_telemetry?.queries ?? 0} · events ${status.debug.controller_telemetry?.events ?? 0}`}
                  {` · devices ${status.debug.controller_telemetry?.raw_count ?? 0} · query ${status.debug.controller_telemetry?.query_ms ?? "?"} ms`}
                </div>
                {status.debug.controller_telemetry?.devices?.map((device) => <div key={device.index}>
                  {device.name} · input {device.index}: list {device.list_percent ?? "?"}% / SteamUI {device.store_percent ?? "?"}% / event {device.event_percent ?? "?"}%
                  {` → ${device.effective_percent ?? "?"}% · ${device.source}`}
                  {device.event_age_s != null ? ` (${formatAge(device.event_age_s)})` : ""}
                </div>)}
              </div>
            </PanelSectionRow>
            <PanelSectionRow>
              <ToggleField
                label="Reverse physical LED order"
                description="Enabled for the official Steam Machine orientation. Previews stay left-to-right."
                checked={status.reverse_led_order}
                onChange={async (value) => setStatus(await setSetting("reverse_led_order", value))}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <SliderField
                label="Extra dark LEDs"
                description={status.countdown.active && !status.countdown.alerting
                  ? `Countdown · ${status.countdown.logical_lit} shown in preview → ${status.countdown.physical_lit} lit on hardware.`
                  : status.mode === "performance"
                    ? `Performance · ${status.performance.logical_lit} shown in preview → ${status.performance.physical_lit} lit on hardware.`
                    : "Countdown and Performance only. Artwork is unchanged. Previews keep the logical LED count."}
                value={status.countdown_dark_edge_compensation}
                min={0}
                max={6}
                step={1}
                showValue
                valueSuffix=""
                onChange={async (value) => setStatus(await setSetting("countdown_dark_edge_compensation", value))}
              />
            </PanelSectionRow>
          </>
        ) : null}
      </PanelSection> : null}

      {showPage("advanced") && update?.test_build ? <PanelSection title="Update lab · TEST BUILD">
        <PanelSectionRow><div style={{ width: "100%", fontSize: ".78em", opacity: .84 }}>
          These fixtures use isolated directories. They never replace the installed plugin or restart the real Decky service.
        </div></PanelSectionRow>
        <PanelSectionRow><ButtonItem label="Valid package"
          description="Build and validate a fixed local GabeCubeAura 1.1.0 fixture."
          disabled={updateBusy} onClick={() => void runUpdateLab("valid-package")}>Run validation only</ButtonItem></PanelSectionRow>
        <PanelSectionRow><ButtonItem label="Checksum mismatch"
          description="Confirm that a wrong SHA256 is rejected before staging."
          disabled={updateBusy} onClick={() => void runUpdateLab("checksum-mismatch")}>Run rejection test</ButtonItem></PanelSectionRow>
        <PanelSectionRow><ButtonItem label="Rollback rehearsal"
          description="Install a broken fixture in isolated directories and restore the previous fixture."
          disabled={updateBusy} onClick={() => void runUpdateLab("rollback")}>Rehearse rollback</ButtonItem></PanelSectionRow>
        {updateLabResult ? <PanelSectionRow><div style={{ width: "100%", fontSize: ".78em", color: updateLabResult.passed ? "#9ee8b0" : "#ff9e9e" }}>
          <b>{updateLabResult.passed ? "Passed" : "Failed"}: {updateLabResult.scenario}</b>
          <div style={{ marginTop: 4, opacity: .86 }}>{updateLabResult.details}</div>
        </div></PanelSectionRow> : null}
        <PanelSectionRow><ButtonItem label="Export test report"
          description={updateLabReportPath || "Writes the bounded fixture report to Documents."}
          disabled={updateBusy || !updateLabResult?.report_available}
          onClick={() => void exportUpdateTestReport().then((result) => setUpdateLabReportPath(result.path)).catch((error) => setUpdateLabReportPath(String(error)))}>
          Export JSON
        </ButtonItem></PanelSectionRow>
      </PanelSection> : null}

      {page !== "quick" ? <SettingsPageEnd page={page} setStatus={setStatus} /> : null}

    </>
  );
}

function GabeCubeAuraSettings() {
  return <SidebarNavigation title="GabeCubeAura settings" pages={[
    { title: "Display routing", route: "/gabecubeaura/settings/routing", content: <Content page="routing" /> },
    { title: "Customization+", route: "/gabecubeaura/settings/customization", content: <Content page="customization" /> },
    { title: "Artwork", route: "/gabecubeaura/settings/artwork", content: <Content page="artwork" /> },
    { title: "Performance", route: "/gabecubeaura/settings/performance", content: <Content page="performance" /> },
    { title: "Screen Sync", route: "/gabecubeaura/settings/screen-sync", content: <Content page="screen-sync" /> },
    { title: "Game launches", route: "/gabecubeaura/settings/launches", content: <Content page="launches" /> },
    { title: "Playtime", route: "/gabecubeaura/settings/countdown", content: <Content page="countdown" /> },
    { title: "Light events", route: "/gabecubeaura/settings/events", content: <Content page="events" /> },
    { title: "Controllers", route: "/gabecubeaura/settings/controllers", content: <Content page="controllers" /> },
    { title: "Weather", route: "/gabecubeaura/settings/weather", content: <Content page="weather" /> },
    { title: "Compatibility", route: "/gabecubeaura/settings/compatibility", content: <Content page="compatibility" /> },
    { title: "Updates", route: "/gabecubeaura/settings/updates", content: <Content page="updates" /> },
    "separator",
    { title: "Advanced / debug", route: "/gabecubeaura/settings/advanced", content: <Content page="advanced" /> },
  ]} />;
}

export default definePlugin(() => {
  // Decky invokes this initializer once when it loads the frontend bundle.
  // Runtime signals must start here, not when the user first opens the panel.
  const runtime = startGabeCubeAuraRuntime();
  const weatherTopBar = startWeatherTopBar();
  const updateNotifications = startUpdateNotifications();
  routerHook.addRoute("/gabecubeaura/settings", GabeCubeAuraSettings);
  return {
    name: "GabeCubeAura",
    titleView: <div className={staticClasses.Title}>GabeCubeAura</div>,
    content: <Content />,
    icon: <TbCubeSpark />,
    alwaysRender: true,
    onDismount() {
      runtime.stop();
      weatherTopBar.stop();
      updateNotifications.stop();
      routerHook.removeRoute("/gabecubeaura/settings");
    },
  };
});
