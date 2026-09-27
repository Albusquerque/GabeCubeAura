import assert from "node:assert/strict";
import test from "node:test";

import { averageBand, dominantPalette, LED_COUNT, scoreBand } from "../../src/artwork";
import type { RGB } from "../../src/types";

test("artwork band always produces exactly 17 RGB pixels", () => {
  const width = 170;
  const height = 20;
  const data = new Uint8ClampedArray(width * height * 4);
  for (let offset = 0; offset < data.length; offset += 4) {
    data[offset] = (offset / 4) % width;
    data[offset + 1] = 100;
    data[offset + 2] = 200;
    data[offset + 3] = 255;
  }
  const colors = averageBand(data, width, height, 0.5);
  assert.equal(colors.length, LED_COUNT);
  for (const color of colors) {
    assert.equal(color.length, 3);
    assert.ok(color.every((channel) => Number.isInteger(channel) && channel >= 0 && channel <= 255));
  }
});

test("dominant artwork clustering returns the requested two and three colours", () => {
  const width = 90;
  const height = 30;
  const data = new Uint8ClampedArray(width * height * 4);
  const source: RGB[] = [[250, 205, 8], [5, 195, 240], [235, 30, 115]];
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const color = source[Math.min(2, Math.floor(x / 30))];
      const offset = (y * width + x) * 4;
      data.set([...color, 255], offset);
    }
  }
  const two = dominantPalette(data, width, height, 2);
  const three = dominantPalette(data, width, height, 3);
  assert.equal(two.length, 2);
  assert.equal(three.length, 3);
  assert.ok(three.some(([r, g, b]) => r > 180 && g > 140 && b < 80));
  assert.ok(three.some(([r, g, b]) => b > 150 && g > 120 && r < 80));
  assert.ok(three.some(([r, g, b]) => r > 170 && b > 70 && g < 100));
});

test("a monochrome artwork still yields exact same-hue palette sizes", () => {
  const data = new Uint8ClampedArray(24 * 12 * 4);
  for (let offset = 0; offset < data.length; offset += 4) data.set([20, 90, 180, 255], offset);
  assert.equal(dominantPalette(data, 24, 12, 2).length, 2);
  assert.equal(dominantPalette(data, 24, 12, 3).length, 3);
});

test("auto scoring prefers a varied colourful band over black or uniform white", () => {
  const black = Array.from({ length: 17 }, () => [0, 0, 0] as RGB);
  const white = Array.from({ length: 17 }, () => [255, 255, 255] as RGB);
  const varied = Array.from({ length: 17 }, (_, index) => (
    index % 3 === 0 ? [240, 30, 40] : index % 3 === 1 ? [20, 210, 80] : [30, 70, 240]
  ) as RGB);
  assert.ok(scoreBand(varied) > scoreBand(black));
  assert.ok(scoreBand(varied) > scoreBand(white));
});
