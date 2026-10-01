import assert from "node:assert/strict";
import test from "node:test";

import { shouldNotifyUpdate } from "../../src/update_logic";
import type { UpdateStatus } from "../../src/types";


const available: UpdateStatus = {
  phase: "available",
  installed_version: "1.0.0",
  available_version: "1.1.0",
  last_checked_at: 1,
  next_check_at: 2,
  notified_version: "",
  release_notes: "notes",
  release_url: "https://github.com/Alyenax/GabeCubeAura/releases/tag/v1.1.0",
  prepared_digest: "",
  confirmation_token: "",
  rollback_version: "",
  last_result: "",
  error_category: "",
  error: "",
  auto_check: true,
  notifications: true,
  check_interval_minutes: 1440,
  channel: "stable",
  return_to_stable: false,
  test_build: false,
};

test("one update notification waits for Home and is deduplicated by version", () => {
  assert.equal(shouldNotifyUpdate(available, 0), true);
  assert.equal(shouldNotifyUpdate(available, 42), false);
  assert.equal(shouldNotifyUpdate({ ...available, notified_version: "1.1.0" }, 0), false);
  assert.equal(shouldNotifyUpdate({ ...available, notifications: false }, 0), false);
  assert.equal(shouldNotifyUpdate({ ...available, phase: "ready" }, 0), false);
});

test("a beta found after selecting the Beta channel uses the normal notification path", () => {
  const beta: UpdateStatus = {
    ...available,
    installed_version: "1.1.1",
    available_version: "1.2.0-beta.2",
    release_url: "https://github.com/Alyenax/GabeCubeAura/releases/tag/v1.2.0-beta.2",
    channel: "beta",
  };
  assert.equal(shouldNotifyUpdate(beta, 0), true);
  assert.equal(shouldNotifyUpdate({ ...beta, notified_version: "1.2.0-beta.2" }, 0), false);
});
