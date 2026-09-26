import assert from "node:assert/strict";
import test from "node:test";

import {
  classifySteamNotification,
  CommunityNotificationObserver,
  isSteamServerNotificationStore,
  screenshotWasCaptured,
} from "../../src/steam_events";

test("every valid Steam notification type maps to a light signal", () => {
  assert.equal(classifySteamNotification(5), "achievement");
  assert.equal(classifySteamNotification(14), "screenshot");
  assert.equal(classifySteamNotification(55), "record-start");
  assert.equal(classifySteamNotification(56), "record-stop");
  assert.equal(classifySteamNotification(8), "notification");
  assert.equal(classifySteamNotification(31), "notification");
  assert.equal(classifySteamNotification(27), "notification"); // Community comment
  assert.equal(classifySteamNotification(45), "notification"); // parental warning
  assert.equal(classifySteamNotification(1), "notification"); // download completion
  assert.equal(classifySteamNotification(99), "notification"); // future Steam type
  for (let type = 1; type <= 58; type++) {
    assert.notEqual(classifySteamNotification(type), null, `Steam type ${type}`);
  }
  assert.equal(classifySteamNotification(0), null);
  assert.equal(classifySteamNotification(NaN), null);
});

test("a deleted screenshot never plays the capture signal", () => {
  assert.equal(screenshotWasCaptured({ strOperation: "written" }), true);
  assert.equal(screenshotWasCaptured({ strOperation: "deleted" }), false);
  assert.equal(screenshotWasCaptured(null), false);
});

function serverStore(rollups: any[] = [], loaded = true) {
  return {
    m_bLoaded: loaded,
    m_rgNotificationRollups: rollups,
    BHasNotificationsData: () => loaded,
  };
}

function rollup(id: string | number, type: number, hidden = false) {
  return {
    type,
    item: { notification_id: id, notification_type: type, hidden },
  };
}

test("recognizes Steam's server-backed notification store", () => {
  assert.equal(isSteamServerNotificationStore(serverStore()), true);
  assert.equal(isSteamServerNotificationStore({ m_rgNotificationRollups: [] }), false);
  assert.equal(isSteamServerNotificationStore(null), false);
});

test("community observer seeds existing notifications without replaying them", () => {
  const observer = new CommunityNotificationObserver();
  const store = serverStore([rollup("existing-comment", 3), rollup("existing-post", 27)]);
  assert.deepEqual(observer.scan(store), []);
  assert.deepEqual(observer.scan(store), []);
});

test("community observer emits new subscribed discussions and group posts once", () => {
  const observer = new CommunityNotificationObserver();
  const store = serverStore([rollup("old", 3)]);
  observer.scan(store);
  store.m_rgNotificationRollups = [
    rollup("new-comment", 3),
    rollup("new-post", 27),
    rollup("wishlist", 8),
  ];
  assert.deepEqual(observer.scan(store), [
    { id: "new-comment", type: 3 },
    { id: "new-post", type: 27 },
  ]);
  assert.deepEqual(observer.scan(store), []);
});

test("community observer waits for initial load and never revives hidden items", () => {
  const observer = new CommunityNotificationObserver();
  const store = serverStore([], false);
  assert.deepEqual(observer.scan(store), []);
  store.m_bLoaded = true;
  store.BHasNotificationsData = () => true;
  store.m_rgNotificationRollups = [rollup("backlog", 3)];
  assert.deepEqual(observer.scan(store), []);
  store.m_rgNotificationRollups.push(rollup("hidden", 3, true));
  assert.deepEqual(observer.scan(store), []);
  store.m_rgNotificationRollups[1].item.hidden = false;
  assert.deepEqual(observer.scan(store), []);
});
