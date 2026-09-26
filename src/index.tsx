import {
  ButtonItem,
  ColorPickerModal,
  ConfirmModal,
  DropdownItem,
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
  importConfiguration,
  getArtwork,
  getStatus,
  previewCountdown,
  previewController,
  previewWeather,
  resetConfiguration,
  searchWeatherCities,
  setArtworkSetting,
  setMode,
  setGameDisplay,
  setSetting,
  startFreeTimer,
  stopFreeTimer,
  submitArtwork,
  triggerEvent,
} from "./api";
import { sampleArtwork } from "./artwork";
import { PalettePreview } from "./components/PalettePreview";
import { CONTROLLER_VARIANTS } from "./controller_variants";
import { EVENT_VARIANTS } from "./event_variants";
import { hslStringToRgb, performancePreview, rgbToHsl } from "./performance";
import { startSignalBarRuntime } from "./runtime";
import { buildSettingsSnapshot } from "./settings_snapshot";
import { WEATHER_CONDITIONS, WEATHER_VARIANTS } from "./weather_variants";
import { startWeatherTopBar } from "./weather_topbar";
import type { ArtworkPayload, ArtworkSource, CompanionPriority, Status, WeatherCondition, WeatherLocation } from "./types";

const MODE_OPTIONS = [
  { data: "artwork", label: "Artwork" },
  { data: "performance", label: "Performance" },
  { data: "events", label: "Signals only" },
  { data: "disabled", label: "Disabled" },
];

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

const CONTROLLER_DISPLAY_OPTIONS = [
  { data: "off", label: "Off" },
  { data: "home", label: "On Home" },
  { data: "game", label: "In game" },
  { data: "everywhere", label: "Everywhere" },
];
const WEATHER_DISPLAY_OPTIONS = CONTROLLER_DISPLAY_OPTIONS;
const WEATHER_TEMPERATURE_UNITS = [
  { data: "celsius", label: "Celsius (°C)" },
  { data: "fahrenheit", label: "Fahrenheit (°F)" },
];
const COMPANION_PRIORITY_OPTIONS = [
  { data: "stripmine", label: "StripMine while the game is active" },
  { data: "signalbar", label: "SignalBar" },
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

function chooseSettingColor(key: string, label: string, color: [number, number, number], setStatus: (value: Status) => void) {
  const [hue, saturation, lightness] = rgbToHsl(color);
  let modal: ReturnType<typeof showModal> | undefined;
  modal = showModal(<ColorPickerModal title={label} defaultH={hue} defaultS={saturation}
    defaultL={lightness} defaultA={1} closeModal={() => modal?.Close()}
    onConfirm={(value) => {
      const nextColor = hslStringToRgb(value);
      if (nextColor) void setSetting(key, nextColor).then(setStatus).catch(console.warn);
    }} />);
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
  const telemetry = status.debug.controller_telemetry;
  const stale = (status.debug.controller_last_update_age_s ?? 0) > 10;
  const preview = async (kind: keyof typeof CONTROLLER_VARIANTS, variant: string) => {
    try {
      const played = await previewController(kind, variant);
      setPreviewMessage(played ? "Preview requested. It does not test controller detection; LED output still follows SignalBar priorities."
        : "Preview unavailable in Disabled mode or during the final five minutes of a countdown.");
      setStatus(await getStatus());
    } catch { setPreviewMessage("Preview could not reach SignalBar. Check the Decky backend."); }
  };
  const groups = [
    ["connect", "Connection", "controller_connect_enabled", "controller_connect_variant"],
    ["persistent", "Permanent gauge", null, "controller_persistent_variant"],
    ["low", "Low battery", "controller_low_enabled", "controller_low_variant"],
    ["charging", "Charging style", null, "controller_charging_variant"],
    ["duo", "Two controllers", null, "controller_duo_variant"],
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
      <PanelSectionRow><DropdownItem label="Permanent battery gauge"
        description="On Home by default. In game and Everywhere are also available. Turning this on switches the permanent weather display off. Countdowns and brief alerts take priority."
        rgOptions={CONTROLLER_DISPLAY_OPTIONS} selectedOption={status.controller_battery_display}
        onChange={async (option) => setStatus(await setSetting("controller_battery_display", String(option.data)))} /></PanelSectionRow>
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
        When two known battery levels are available, the gauges fill from opposite edges. The centre LED stays off; fixed white endpoints appear after the introduction.
      </div></PanelSectionRow>
    </PanelSection>
    <PanelSection title="Controller colours">
      <PanelSectionRow><div style={{ fontSize: ".8em", opacity: .8 }}>
        These colours tint controller gauges and signals, including previews. White highlights stay white.
        Other SignalBar modes are unchanged. Lower brightness may reduce pale glow on the diffuser.
      </div></PanelSectionRow>
      <PanelSectionRow><SliderField label="Controller brightness" min={10} max={100} step={5}
        showValue valueSuffix="%" value={status.controller_gauge_brightness}
        onChange={async (value) => setStatus(await setSetting("controller_gauge_brightness", value))} /></PanelSectionRow>
      {([
        ["controller_colour_normal", `Healthy battery · above ${Math.max(35, status.controller_low_threshold + 5)}%`],
        ["controller_colour_medium", "Medium battery"],
        ["controller_colour_low", `Low battery · ${status.controller_low_threshold}% or less`],
        ["controller_colour_charging", "Connection / charging colour"],
      ] as const).map(([key, label]) => <PanelSectionRow key={key}>
        <ColorChoice label={label} color={status[key]}
          onClick={() => chooseSettingColor(key, label, status[key], setStatus)} />
      </PanelSectionRow>)}
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
      setMessage("City saved. Choose where the weather should appear.");
    } catch (error) { setMessage(`Could not save city: ${String(error)}`); }
  };
  const setDisplay = async (display: string) => {
    if (display !== "off" && !status.weather_location) {
      setMessage("Choose a city first. No location is detected automatically.");
      return;
    }
    try {
      setStatus(await setSetting("weather_display", display));
      setMessage(display === "off" ? "Weather display off." : "Weather selected. The permanent controller gauge is now off.");
    } catch (error) { setMessage(`Could not change weather display: ${String(error)}`); }
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
      <PanelSectionRow><DropdownItem label="Permanent weather display"
        description="Off until you choose a city. On Home, In game or Everywhere replaces the permanent controller gauge; brief controller alerts and countdowns keep priority."
        rgOptions={WEATHER_DISPLAY_OPTIONS} selectedOption={status.weather_display}
        onChange={(option) => void setDisplay(String(option.data))} /></PanelSectionRow>
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
        Brightness scales RGB linearly for all weather animations. Use 100% with cutoff 0 for the unprocessed animation. These controls affect Weather only, not Steam's master LED brightness or other SignalBar modes.
      </div></PanelSectionRow>
      <PanelSectionRow><SliderField label="Weather LED brightness" min={10} max={100} step={5}
        showValue valueSuffix="%" value={status.weather_brightness}
        onChange={async (value) => setStatus(await setSetting("weather_brightness", value))} /></PanelSectionRow>
      <PanelSectionRow><SliderField label="Turn faint LEDs off" min={0} max={60} step={5}
        showValue value={status.weather_shadow_cutoff}
        onChange={async (value) => setStatus(await setSetting("weather_shadow_cutoff", value))} /></PanelSectionRow>
      <PanelSectionRow><div style={{ fontSize: ".76em", opacity: .72 }}>
        Cutoff turns a pixel fully off when its strongest RGB channel is at or below this value (0–255 scale). It does not dim the remaining pixels further. A high cutoff can make transitions more abrupt. These are brightness controls, not measured hardware colour calibration.
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

function CompatibilityPanel({ status, setStatus }: { status: Status; setStatus: (next: Status) => void }) {
  const priorities = ([
    ["Artwork", "stripmine_priority_artwork", "The sampled game artwork display."],
    ["Performance", "stripmine_priority_performance", "CPU, GPU and mixed performance displays."],
    ["Weather", "stripmine_priority_weather", "Permanent and preview weather animations."],
    ["Controller displays", "stripmine_priority_controller", "Battery gauges, connection and charging displays."],
    ["Light Events", "stripmine_priority_light_events", "Notifications, achievements, screenshots and recording cues."],
  ] as const);
  return <>
    <PanelSection title="StripMine compatibility">
      <PanelSectionRow>
        <ToggleField
          label="Coordinate LED ownership"
          description="SignalBar and StripMine exchange a short local lease before either writes. Unknown applications are still treated as conflicts."
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
          Playtime countdowns and their critical alerts always remain SignalBar priorities. If coordination is disabled, both plugins fall back to their independent ownership guards.
        </div>
      </PanelSectionRow>
    </PanelSection>
  </>;
}

type Page = "quick" | "artwork" | "performance" | "countdown" | "events" | "controllers" | "weather" | "compatibility" | "advanced";

function Content({ page = "quick" }: { page?: Page }) {
  const [status, setStatusState] = useState<Status | null>(null);
  const [hero, setHero] = useState<ArtworkPayload | null>(null);
  const [heroRequestKey, setHeroRequestKey] = useState("");
  const artworkRequest = useRef(0);
  const [showDebug, setShowDebug] = useState(false);
  const [configurationExportPath, setConfigurationExportPath] = useState("");
  const [configurationExportError, setConfigurationExportError] = useState("");
  const [configurationActionMessage, setConfigurationActionMessage] = useState("");
  const [configurationBusy, setConfigurationBusy] = useState(false);
  const manualTimer = useRef<number | null>(null);
  const setStatus = (next: Status) => {
    setStatusState(next);
  };

  useEffect(() => {
    let alive = true;
    void getStatus().then((next) => alive && setStatus(next)).catch(console.warn);
    const timer = window.setInterval(() => {
      void getStatus().then((next) => alive && setStatus(next)).catch(() => undefined);
    }, page === "events" || page === "controllers" || page === "weather" || page === "compatibility" ? 180 : 1000);
    return () => {
      alive = false;
      window.clearInterval(timer);
      if (manualTimer.current != null) window.clearTimeout(manualTimer.current);
    };
  }, [page]);

  const loadAndSampleArtwork = useCallback(async (appid: number, source: ArtworkSource) => {
    const request = ++artworkRequest.current;
    if (appid <= 0) {
      setHero(null);
      setHeroRequestKey("");
      return;
    }
    const current = await getStatus();
    if (request !== artworkRequest.current) return;
    const artwork = await getArtwork(appid, source);
    if (request !== artworkRequest.current) return;
    setHero(artwork);
    setHeroRequestKey(`${appid}:${source}`);
    if (!artwork.found || !artwork.data_uri || !artwork.fingerprint || artwork.cached) {
      const refreshed = await getStatus();
      if (request === artworkRequest.current) setStatus(refreshed);
      return;
    }
    const mode = current.artwork_mode;
    const manualY = current.artwork_manual_y;
    const result = await sampleArtwork(artwork.data_uri, mode, manualY);
    if (request !== artworkRequest.current) return;
    const next = await submitArtwork(
      appid,
      artwork.fingerprint,
      result.colors,
      result.y,
      artwork.filename ?? "",
      artwork.source ?? source,
    );
    if (request === artworkRequest.current) setStatus(next);
  }, []);

  const refreshArtworkAfterConfiguration = (next: Status) => {
    setHeroRequestKey("");
    if (next.game.appid > 0) {
      void loadAndSampleArtwork(next.game.appid, next.artwork_source).catch(console.warn);
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
      modal = showModal(<ConfirmModal strTitle="Import SignalBar configuration?"
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
    modal = showModal(<ConfirmModal strTitle="Reset SignalBar settings?"
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
          setConfigurationActionMessage("Settings and per-game profiles reset to SignalBar defaults.");
        }).catch((error) => {
          setConfigurationActionMessage(`Reset failed: ${String(error)}`);
        }).finally(() => setConfigurationBusy(false));
      }} />);
  };

  useEffect(() => {
    if (!status) return;
    const needsArtwork = page === "artwork" || (page === "quick" && status.mode === "artwork");
    if (!needsArtwork) {
      setHero(null);
      setHeroRequestKey("");
      return;
    }
    void loadAndSampleArtwork(status.game.appid, status.artwork_source).catch((error) => {
      console.warn("[SignalBar] artwork preview failed", error);
    });
  }, [page, status?.game.appid, status?.mode, status?.artwork_source, loadAndSampleArtwork]);

  if (!status) {
    return <PanelSection><PanelSectionRow>Loading SignalBar…</PanelSectionRow></PanelSection>;
  }
  if (!status.available) {
    return (
      <PanelSection title="SignalBar">
        <PanelSectionRow>
          <div style={{ fontSize: ".88em", opacity: 0.82 }}>
            No 17-pixel <code>valve-leds</code> light bar was found. SignalBar is idle and has made no hardware changes.
            {status.error ? <div style={{ marginTop: 6 }}>{status.error}</div> : null}
          </div>
        </PanelSectionRow>
      </PanelSection>
    );
  }

  const changeArtworkSetting = async (key: string, value: unknown) => {
    const next = await setArtworkSetting(status.game.appid, key, value);
    setStatus(next);
    if (next.game.appid > 0) await loadAndSampleArtwork(next.game.appid, next.artwork_source);
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
  const performanceColors = performancePreview(status);
  const baseShownColors = status.provider.startsWith("event:") ? status.events.colors
    : status.provider.startsWith("controller:") || status.provider.startsWith("controller-") ? status.controllers.colors
    : status.provider === "countdown" ? status.countdown.colors
      : status.provider.startsWith("weather") ? status.weather.colors
      : status.provider.startsWith("artwork") ? artColors
        : status.provider.startsWith("performance") ? performanceColors : [];
  const shownColors = status.provider.endsWith("+recording")
    ? addRecordingMarker(status, baseShownColors) : baseShownColors;
  const shownLabel = status.provider.startsWith("event:") ? status.events.variant
    : status.provider.startsWith("controller:") ? `Controller · ${status.controllers.variant}`
      : status.provider === "controller-battery" ? "Controller battery"
      : status.provider === "controller-charging" ? "Controller charging"
      : status.provider === "controller-charge-complete" ? "Controller fully charged"
      : status.provider.startsWith("weather") ? `Weather · ${status.weather.location?.name ?? "preview"}`
    : status.provider === "countdown" ? status.countdown.label
      : status.provider === "valve" ? "Steam / another app"
        : status.provider === "none" ? "No SignalBar output" : status.provider;

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

      {page === "quick" ? <PanelSection title="Mode">
        <PanelSectionRow>
          <DropdownItem
            label="Default display"
            description="Used on Home and by games without an override. Signals only removes Artwork, Performance and Weather while keeping Light Events, countdowns, controller alerts and enabled battery or charging status alive. Disabled turns off every SignalBar light."
            rgOptions={MODE_OPTIONS}
            selectedOption={status.default_mode}
            onChange={async (option) => setStatus(await setMode(String(option.data)))}
          />
        </PanelSectionRow>
        {status.game.appid > 0 ? <>
          <PanelSectionRow><DropdownItem label="Display for this game"
            description={`Saved for ${status.game.title || `AppID ${status.game.appid}`}. Does not change other games.`}
            rgOptions={[{ data: "inherit", label: "Use default" }, { data: "artwork", label: "Artwork" }, { data: "performance", label: "Performance" }]}
            selectedOption={status.display_override}
            onChange={async (option) => setStatus(await setGameDisplay(status.game.appid, String(option.data)))} /></PanelSectionRow>
          <PanelSectionRow><div style={{ fontSize: ".78em", opacity: .75 }}>
            {status.default_mode === "disabled" ? "SignalBar is disabled. The saved game choice will apply when re-enabled."
              : status.default_mode === "events" ? "Signals only is global: saved game displays remain dormant while Light Events, countdowns and enabled controller signals can still use the bar."
              : `Active display: ${status.mode === "performance" ? "Performance" : "Artwork"}${status.display_override === "inherit" ? " (default)" : " (game profile)"}. Countdowns and short alerts keep their usual priority.`}
          </div></PanelSectionRow>
        </> : <PanelSectionRow><div style={{ fontSize: ".78em", opacity: .75 }}>Launch a game to save its own Artwork or Performance choice.</div></PanelSectionRow>}
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
          <ButtonItem label="Detailed settings" onClick={() => { Navigation.CloseSideMenus(); Navigation.Navigate("/signalbar/settings"); }}>
            Open settings
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection> : null}

      {page === "artwork" ? <PanelSection title="Artwork">
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

      {page === "performance" ? <PanelSection title="Performance">
        <PanelSectionRow><div style={{ fontSize: ".78em", opacity: .75 }}>
          Sensors update every 0.5 seconds in all display modes. These settings do not switch the active display.
        </div></PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label="Always show Performance"
            description="When Default display is Performance, also show it on Home. A game's Artwork override still wins in that game. Steam's active LED animations retain priority."
            checked={status.performance_always}
            onChange={async (value) => setStatus(await setSetting("performance_always", value))}
          />
        </PanelSectionRow>
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

      {page === "countdown" ? <CountdownPanel status={status} setStatus={setStatus} /> : null}

      {page === "events" ? <EventsPanel status={status} setStatus={setStatus} /> : null}

      {page === "controllers" ? <ControllersPanel status={status} setStatus={setStatus} /> : null}

      {page === "weather" ? <WeatherPanel status={status} setStatus={setStatus} /> : null}

      {page === "compatibility" ? <CompatibilityPanel status={status} setStatus={setStatus} /> : null}

      {page === "advanced" ? <PanelSection title="Advanced / debug">
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
                  SignalBar {status.version} · saved choices, including inactive options · no device IDs
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
                    console.warn("[SignalBar] configuration export failed", error);
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
              description="Choose a SignalBar export from Documents or another location. Replaces saved settings and per-game profiles."
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
                  Game detection: {status.debug.game_detection_source}
                  {status.debug.game_sync_ms == null ? "" : ` · backend ${Math.round(status.debug.game_sync_ms)} ms`}
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

    </>
  );
}

function SignalBarSettings() {
  return <SidebarNavigation title="SignalBar settings" pages={[
    { title: "Artwork", route: "/signalbar/settings/artwork", content: <Content page="artwork" /> },
    { title: "Performance", route: "/signalbar/settings/performance", content: <Content page="performance" /> },
    { title: "Playtime", route: "/signalbar/settings/countdown", content: <Content page="countdown" /> },
    { title: "Light events", route: "/signalbar/settings/events", content: <Content page="events" /> },
    { title: "Controllers", route: "/signalbar/settings/controllers", content: <Content page="controllers" /> },
    { title: "Weather", route: "/signalbar/settings/weather", content: <Content page="weather" /> },
    { title: "Compatibility", route: "/signalbar/settings/compatibility", content: <Content page="compatibility" /> },
    "separator",
    { title: "Advanced / debug", route: "/signalbar/settings/advanced", content: <Content page="advanced" /> },
  ]} />;
}

export default definePlugin(() => {
  // Decky invokes this initializer once when it loads the frontend bundle.
  // Runtime signals must start here, not when the user first opens the panel.
  const runtime = startSignalBarRuntime();
  const weatherTopBar = startWeatherTopBar();
  routerHook.addRoute("/signalbar/settings", SignalBarSettings);
  return {
    name: "SignalBar",
    titleView: <div className={staticClasses.Title}>SignalBar</div>,
    content: <Content />,
    icon: <TbCubeSpark />,
    alwaysRender: true,
    onDismount() {
      runtime.stop();
      weatherTopBar.stop();
      routerHook.removeRoute("/signalbar/settings");
    },
  };
});
