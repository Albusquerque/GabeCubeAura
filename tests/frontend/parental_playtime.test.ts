import assert from "node:assert/strict";
import test from "node:test";

import { ParentalPlaytimeSubscription } from "../../src/parental_playtime";

test("retries when Steam Families appears after plugin startup", () => {
  let now = 1000;
  let available = false;
  let callback: ((minutes: unknown) => void) | undefined;
  const received: Array<[number, number]> = [];
  const subscription = new ParentalPlaytimeSubscription(
    () => available ? {
      owner: null,
      register: (next) => {
        callback = next;
        return { unregister: () => undefined };
      },
    } : undefined,
    (appid, minutes) => received.push([appid, minutes]),
    () => now,
  );

  assert.equal(subscription.selectApp(42), "waiting");
  available = true;
  assert.equal(subscription.ensure(), "waiting");
  now += 1000;
  assert.equal(subscription.ensure(), "registered");
  callback?.(55);
  assert.deepEqual(received, [[42, 55]]);
});

test("does not duplicate a successful registration", () => {
  let registrations = 0;
  const subscription = new ParentalPlaytimeSubscription(
    () => ({
      owner: null,
      register: () => {
        registrations += 1;
        return { unregister: () => undefined };
      },
    }),
    () => undefined,
  );

  assert.equal(subscription.selectApp(7), "registered");
  assert.equal(subscription.ensure(), "registered");
  assert.equal(subscription.selectApp(7), "registered");
  assert.equal(registrations, 1);
});

test("switching games unregisters once and ignores a stale callback", () => {
  let unregisters = 0;
  const callbacks: Array<(minutes: unknown) => void> = [];
  const received: Array<[number, number]> = [];
  const subscription = new ParentalPlaytimeSubscription(
    () => ({
      owner: null,
      register: (callback) => {
        callbacks.push(callback);
        return { unregister: () => { unregisters += 1; } };
      },
    }),
    (appid, minutes) => received.push([appid, minutes]),
  );

  subscription.selectApp(10);
  subscription.selectApp(20);
  callbacks[0](50);
  callbacks[1](40);
  assert.equal(unregisters, 1);
  assert.deepEqual(received, [[20, 40]]);
});

test("resume reset replaces an invalidated registration", () => {
  let registrations = 0;
  let unregisters = 0;
  const subscription = new ParentalPlaytimeSubscription(
    () => ({
      owner: null,
      register: () => {
        registrations += 1;
        return { unregister: () => { unregisters += 1; } };
      },
    }),
    () => undefined,
  );

  subscription.selectApp(99);
  assert.equal(subscription.reset(), "registered");
  assert.equal(registrations, 2);
  assert.equal(unregisters, 1);
});
