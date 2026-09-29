import assert from "node:assert/strict";
import test from "node:test";

import {
  CUSTOMIZATION_PATTERN_ENTRIES,
  CUSTOMIZATION_PATTERN_OPTIONS,
  customizationPatternLabel,
} from "../../src/customization_catalog";

test("Customization+ groups all 65 unchanged names by dynamism", () => {
  assert.deepEqual(CUSTOMIZATION_PATTERN_OPTIONS.map((group) => group.label), [
    "Calm & ambient", "Flowing", "Energetic",
  ]);
  const grouped = CUSTOMIZATION_PATTERN_OPTIONS.flatMap((group) => group.options);
  assert.equal(grouped.length, 65);
  assert.equal(new Set(grouped.map((entry) => entry.data)).size, 65);
  assert.deepEqual(
    grouped.map((entry) => entry.data).sort(),
    CUSTOMIZATION_PATTERN_ENTRIES.map((entry) => entry.data).sort(),
  );
  assert.equal(customizationPatternLabel("nocturne"), "Game Launches · Nocturne");
  assert.equal(customizationPatternLabel("event:achievement-supernova"), "Light Events / achievement · Supernova");
});

test("representative effects move from calm through energetic without renaming", () => {
  const grouped = Object.fromEntries(CUSTOMIZATION_PATTERN_OPTIONS.map((group) => [
    group.label,
    new Map(group.options.map((entry) => [entry.data, entry.label])),
  ]));
  assert.equal(grouped["Calm & ambient"].get("steady"), "Steady · precise static colour");
  assert.equal(grouped.Flowing.get("color-wipe"), "Game Launches · Color wipe");
  assert.equal(grouped.Energetic.get("theater-chase"), "Game Launches · Theater chase");
});
