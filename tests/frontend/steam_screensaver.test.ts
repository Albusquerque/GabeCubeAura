import assert from "node:assert/strict";
import test from "node:test";

import {
  isSteamScreensaverService,
  screensaverActiveFromResponse,
} from "../../src/steam_screensaver";

test("screensaver service discovery requires both private capabilities", () => {
  assert.equal(isSteamScreensaverService({ GetActiveState() {}, ForceScreensaver() {} }), true);
  assert.equal(isSteamScreensaverService({ GetActiveState() {} }), false);
  assert.equal(isSteamScreensaverService(null), false);
});

test("screensaver active state unwraps current Steam response shapes", () => {
  assert.equal(screensaverActiveFromResponse({ Body: () => ({ active: true }) }), true);
  assert.equal(screensaverActiveFromResponse({ body: { bActive: false } }), false);
  assert.equal(screensaverActiveFromResponse({ is_active: true }), true);
  assert.equal(screensaverActiveFromResponse({ Body: () => ({ active: () => 1 }) }), true);
  assert.equal(screensaverActiveFromResponse({ state: "active" }), null);
});
