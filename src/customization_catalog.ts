import { CONTROLLER_VARIANTS } from "./controller_variants";
import { EVENT_VARIANTS } from "./event_variants";
import type { CustomizationPattern, LaunchArtworkPattern } from "./types";
import { WEATHER_VARIANTS } from "./weather_variants";

export const LAUNCH_ARTWORK_PATTERN_OPTIONS: { data: LaunchArtworkPattern; label: string }[] = [
  { data: "arpege-crossed", label: "Crossed arpeggio" },
  { data: "two-hands", label: "Two hands" },
  { data: "legato", label: "Legato" },
  { data: "nocturne", label: "Nocturne" },
  { data: "crescendo", label: "Crescendo" },
  { data: "color-wipe", label: "Color wipe" },
  { data: "scanner", label: "Scanner" },
  { data: "theater-chase", label: "Theater chase" },
  { data: "twinkle", label: "Twinkle" },
  { data: "ripple", label: "Ripple" },
];

type PatternEntry = { data: CustomizationPattern; label: string };

export const CUSTOMIZATION_PATTERN_ENTRIES: PatternEntry[] = [
  { data: "steady", label: "Steady · precise static colour" },
  ...Object.entries(EVENT_VARIANTS).flatMap(([kind, variants]) => variants.map((variant) => ({
    data: `event:${variant.data}`,
    label: `Light Events / ${kind} · ${variant.label}`,
  }))),
  ...Object.entries(CONTROLLER_VARIANTS).flatMap(([kind, variants]) => variants.map((variant) => ({
    data: `controller:${kind}:${variant.data}`,
    label: `Controllers / ${kind} · ${variant.label}`,
  }))),
  ...Object.entries(WEATHER_VARIANTS).flatMap(([condition, variants]) => variants.map((variant, index) => ({
    data: `weather:${condition}:${index}`,
    label: `Weather / ${condition.split("_").join(" ")} · ${variant.label}`,
  }))),
  ...LAUNCH_ARTWORK_PATTERN_OPTIONS.map((pattern) => ({
    data: pattern.data,
    label: `Game Launches · ${pattern.label}`,
  })),
];

const INTENSE_PATTERNS = new Set<CustomizationPattern>([
  "event:notification-double",
  "event:achievement-confetti", "event:achievement-rebound", "event:achievement-supernova",
  "event:screenshot-double", "event:screenshot-ripple",
  "controller:low:beacon", "controller:low:drain", "controller:low:heartbeat",
  "controller:charging:spark",
  "weather:storm:0", "weather:storm:1",
  "scanner", "theater-chase", "twinkle",
]);

const FLOWING_PATTERNS = new Set<CustomizationPattern>([
  "event:notification-original", "event:notification-return", "event:notification-echo",
  "event:notification-ample", "event:notification-beacon",
  "event:achievement-original", "event:achievement-twoway",
  "event:screenshot-original", "event:screenshot-scan", "event:screenshot-bloom",
  "controller:connect:welcome", "controller:connect:orbit", "controller:connect:handshake",
  "controller:charging:current",
  "controller:duo:twin", "controller:duo:focus", "controller:duo:double-welcome",
  "weather:clear_day:0", "weather:rain:0", "weather:rain:1",
  "arpege-crossed", "two-hands", "crescendo", "color-wipe", "ripple",
]);

export const CUSTOMIZATION_PATTERN_OPTIONS = ([
  ["Calm & ambient", (pattern: CustomizationPattern) => !FLOWING_PATTERNS.has(pattern) && !INTENSE_PATTERNS.has(pattern)],
  ["Flowing", (pattern: CustomizationPattern) => FLOWING_PATTERNS.has(pattern)],
  ["Energetic", (pattern: CustomizationPattern) => INTENSE_PATTERNS.has(pattern)],
] as const).map(([label, matches]) => ({
  label,
  options: CUSTOMIZATION_PATTERN_ENTRIES.filter((entry) => matches(entry.data)),
}));

export function customizationPatternLabel(pattern: CustomizationPattern): string {
  return CUSTOMIZATION_PATTERN_ENTRIES.find((entry) => entry.data === pattern)?.label ?? pattern;
}
