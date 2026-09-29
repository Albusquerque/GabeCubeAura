import assert from "node:assert/strict";
import test from "node:test";

import { GameSessionLatch } from "../../src/game_session";

test("confirmed lifetime game survives Router zero during menus and idle", () => {
  const latch = new GameSessionLatch(3);
  latch.seed({ appid: 0, title: "" });
  const started = latch.observeLifetime(42, true, "Game");
  assert.equal(started.action, "update");
  assert.equal(started.action === "update" && started.launch, true);
  for (let index = 0; index < 20; index += 1) {
    const decision = latch.observePoll({ appid: 0, title: "" });
    assert.equal(decision.action, "retain");
    assert.equal(latch.snapshot().appid, 42);
  }
  const stopped = latch.observeLifetime(42, false);
  assert.deepEqual(stopped, {
    action: "update", appid: 0, title: "", source: "Steam lifetime stop", launch: false,
  });
});

test("poll fallback uses a conservative zero grace when lifetime events are unavailable", () => {
  const latch = new GameSessionLatch(3);
  latch.seed({ appid: 7, title: "Fallback Game" });
  assert.equal(latch.observePoll({ appid: 0, title: "" }).action, "retain");
  assert.equal(latch.observePoll({ appid: 0, title: "" }).action, "retain");
  const stopped = latch.observePoll({ appid: 0, title: "" });
  assert.equal(stopped.action, "update");
  assert.equal(latch.snapshot().appid, 0);
});

test("resume suppresses a stale Router AppID until a real lifetime start", () => {
  const latch = new GameSessionLatch();
  latch.seed({ appid: 99, title: "Before suspend" });
  assert.equal(latch.suspend(99).action, "update");
  assert.equal(latch.observePoll({ appid: 99, title: "Stale" }).action, "none");
  const restarted = latch.observeLifetime(99, true, "Resumed");
  assert.equal(restarted.action, "update");
  assert.equal(latch.snapshot().appid, 99);
});

test("resume can recover from a missing lifetime callback after sustained polling", () => {
  const latch = new GameSessionLatch(3);
  latch.seed({ appid: 55, title: "Before suspend" });
  latch.suspend(55);
  assert.equal(latch.observePoll({ appid: 55, title: "Resumed" }).action, "none");
  assert.equal(latch.observePoll({ appid: 55, title: "Resumed" }).action, "none");
  const confirmed = latch.observePoll({ appid: 55, title: "Resumed" });
  assert.equal(confirmed.action, "update");
  assert.equal(latch.snapshot().appid, 55);
});
