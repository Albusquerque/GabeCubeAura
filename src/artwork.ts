import type { ArtworkMode, RGB } from "./types";

export const LED_COUNT = 17;
export const AUTO_ROWS = [0.35, 0.45, 0.55, 0.65, 0.75, 0.82] as const;

export type DominantPalettes = { "2": RGB[]; "3": RGB[] };

const clamp = (value: number, low = 0, high = 1) => Math.max(low, Math.min(high, value));

function hsvStats([red, green, blue]: RGB) {
  const r = red / 255;
  const g = green / 255;
  const b = blue / 255;
  const high = Math.max(r, g, b);
  const low = Math.min(r, g, b);
  return { saturation: high <= 0 ? 0 : (high - low) / high, value: high };
}

export function scoreBand(colors: RGB[]): number {
  if (colors.length === 0) return Number.NEGATIVE_INFINITY;
  const hsv = colors.map(hsvStats);
  const meanS = hsv.reduce((sum, pixel) => sum + pixel.saturation, 0) / hsv.length;
  const meanV = hsv.reduce((sum, pixel) => sum + pixel.value, 0) / hsv.length;
  const contrast = Math.sqrt(
    hsv.reduce((sum, pixel) => sum + (pixel.value - meanV) ** 2, 0) / hsv.length,
  );
  const black = hsv.filter((pixel) => pixel.value < 0.10).length / hsv.length;
  const white = hsv.filter((pixel) => pixel.value > 0.92 && pixel.saturation < 0.10).length / hsv.length;
  let diversity = 0;
  for (let index = 1; index < colors.length; index += 1) {
    const left = colors[index - 1];
    const right = colors[index];
    diversity += Math.hypot(left[0] - right[0], left[1] - right[1], left[2] - right[2]) / 441.67;
  }
  diversity /= Math.max(1, colors.length - 1);
  const uniformityPenalty = diversity < 0.025 ? (0.025 - diversity) * 4 : 0;
  return meanS * 0.40 + diversity * 0.28 + contrast * 0.18 + Math.min(meanV, 0.75) * 0.14
    - black * 0.42 - white * 0.20 - uniformityPenalty;
}

export function perceptualCorrection([red, green, blue]: RGB): RGB {
  // Mild contrast/saturation lift; preserves composition without neon clipping.
  const channels = [red, green, blue];
  const average = (red + green + blue) / 3;
  return channels.map((channel) => {
    const saturated = average + (channel - average) * 1.08;
    const contrasted = 128 + (saturated - 128) * 1.04;
    return Math.round(clamp(contrasted, 0, 255));
  }) as RGB;
}

export function averageBand(
  data: Uint8ClampedArray,
  width: number,
  height: number,
  centerY: number,
): RGB[] {
  const bandHeight = Math.max(3, Math.round(height * 0.055));
  const center = Math.round(clamp(centerY) * (height - 1));
  const top = Math.max(0, Math.min(height - bandHeight, center - Math.floor(bandHeight / 2)));
  const output: RGB[] = [];
  for (let led = 0; led < LED_COUNT; led += 1) {
    const x0 = Math.floor((led * width) / LED_COUNT);
    const x1 = Math.max(x0 + 1, Math.floor(((led + 1) * width) / LED_COUNT));
    let red = 0;
    let green = 0;
    let blue = 0;
    let count = 0;
    for (let y = top; y < top + bandHeight; y += 1) {
      for (let x = x0; x < x1; x += 1) {
        const offset = (y * width + x) * 4;
        if (data[offset + 3] < 8) continue;
        red += data[offset];
        green += data[offset + 1];
        blue += data[offset + 2];
        count += 1;
      }
    }
    const raw: RGB = count ? [red / count, green / count, blue / count] : [0, 0, 0];
    output.push(perceptualCorrection(raw));
  }
  return output;
}

type LabSample = { rgb: RGB; lab: [number, number, number]; weight: number };

function srgbToLinear(value: number) {
  const channel = value / 255;
  return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
}

function rgbToOklab([red, green, blue]: RGB): [number, number, number] {
  const r = srgbToLinear(red);
  const g = srgbToLinear(green);
  const b = srgbToLinear(blue);
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}

function labDistance(left: [number, number, number], right: [number, number, number]) {
  return (left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2 + (left[2] - right[2]) ** 2;
}

function shade([red, green, blue]: RGB, factor: number): RGB {
  return perceptualCorrection([
    clamp(red * factor, 0, 255),
    clamp(green * factor, 0, 255),
    clamp(blue * factor, 0, 255),
  ]);
}

function collectSamples(data: Uint8ClampedArray, width: number, height: number): LabSample[] {
  const step = Math.max(1, Math.floor(Math.sqrt((width * height) / 5000)));
  const all: LabSample[] = [];
  const useful: LabSample[] = [];
  for (let y = Math.floor(step / 2); y < height; y += step) {
    for (let x = Math.floor(step / 2); x < width; x += step) {
      const offset = (y * width + x) * 4;
      if (data[offset + 3] < 64) continue;
      const rgb: RGB = [data[offset], data[offset + 1], data[offset + 2]];
      const { saturation, value } = hsvStats(rgb);
      const luminance = 0.2126 * srgbToLinear(rgb[0])
        + 0.7152 * srgbToLinear(rgb[1]) + 0.0722 * srgbToLinear(rgb[2]);
      const weight = (0.35 + saturation * 0.65) * (0.55 + Math.min(1, value * 1.35) * 0.45);
      const sample = { rgb, lab: rgbToOklab(rgb), weight };
      all.push(sample);
      if (luminance >= 0.018 && !(value > 0.96 && saturation < 0.07)) useful.push(sample);
    }
  }
  return useful.length >= 12 ? useful : all;
}

export function dominantPalette(
  data: Uint8ClampedArray,
  width: number,
  height: number,
  count: 2 | 3,
): RGB[] {
  const samples = collectSamples(data, width, height);
  if (samples.length === 0) return count === 2 ? [[72, 72, 72], [150, 150, 150]]
    : [[60, 60, 60], [118, 118, 118], [190, 190, 190]];

  const first = samples.reduce((best, sample) => {
    const chroma = Math.hypot(sample.lab[1], sample.lab[2]);
    const bestChroma = Math.hypot(best.lab[1], best.lab[2]);
    return sample.weight * (0.6 + chroma * 4) > best.weight * (0.6 + bestChroma * 4) ? sample : best;
  });
  const centroids: [number, number, number][] = [[...first.lab]];
  while (centroids.length < count) {
    const next = samples.reduce((best, sample) => {
      const distance = Math.min(...centroids.map((centroid) => labDistance(sample.lab, centroid)));
      const bestDistance = Math.min(...centroids.map((centroid) => labDistance(best.lab, centroid)));
      return distance * sample.weight > bestDistance * best.weight ? sample : best;
    });
    centroids.push([...next.lab]);
  }

  let groups: LabSample[][] = [];
  for (let iteration = 0; iteration < 10; iteration += 1) {
    groups = Array.from({ length: count }, () => [] as LabSample[]);
    for (const sample of samples) {
      let selected = 0;
      for (let index = 1; index < centroids.length; index += 1) {
        if (labDistance(sample.lab, centroids[index]) < labDistance(sample.lab, centroids[selected])) selected = index;
      }
      groups[selected].push(sample);
    }
    groups.forEach((group, index) => {
      if (group.length === 0) return;
      const total = group.reduce((sum, sample) => sum + sample.weight, 0);
      centroids[index] = [0, 1, 2].map((channel) => (
        group.reduce((sum, sample) => sum + sample.lab[channel] * sample.weight, 0) / total
      )) as [number, number, number];
    });
  }

  const clustered = groups.map((group, index) => {
    const total = group.reduce((sum, sample) => sum + sample.weight, 0);
    const raw: RGB = total > 0 ? [0, 1, 2].map((channel) => (
      group.reduce((sum, sample) => sum + sample.rgb[channel] * sample.weight, 0) / total
    )) as RGB : samples[index % samples.length].rgb;
    return { color: perceptualCorrection(raw), weight: total };
  }).sort((left, right) => right.weight - left.weight);

  const output: RGB[] = [];
  for (const cluster of clustered) {
    if (output.every((color) => labDistance(rgbToOklab(color), rgbToOklab(cluster.color)) > 0.0016)) {
      output.push(cluster.color);
    }
  }
  const base = output[0] ?? perceptualCorrection(samples[0].rgb);
  const factors = count === 2 ? [0.68, 1.22] : [0.62, 1.0, 1.28];
  for (const factor of factors) {
    if (output.length >= count) break;
    const candidate = shade(base, factor);
    if (output.every((color) => color.some((channel, index) => Math.abs(channel - candidate[index]) >= 10))) {
      output.push(candidate);
    }
  }
  while (output.length < count) output.push([...base] as RGB);
  return output.slice(0, count);
}

function loadImage(dataUri: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Steam Library Hero could not be decoded"));
    image.src = dataUri;
  });
}

export async function sampleArtwork(dataUri: string, mode: ArtworkMode, manualY: number) {
  const image = await loadImage(dataUri);
  const sourceWidth = Math.max(1, image.naturalWidth || image.width);
  const sourceHeight = Math.max(1, image.naturalHeight || image.height);
  const width = Math.min(680, sourceWidth);
  const height = Math.max(32, Math.round((sourceHeight / sourceWidth) * width));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) throw new Error("Canvas 2D is unavailable");
  context.drawImage(image, 0, 0, width, height);
  const pixels = context.getImageData(0, 0, width, height).data;
  const rows = mode === "center" ? [0.5]
    : mode === "lower" ? [0.76]
      : mode === "manual" ? [clamp(manualY, 0.15, 0.90)]
        : [...AUTO_ROWS];
  const candidates = rows.map((y) => {
    const colors = averageBand(pixels, width, height, y);
    return { y, colors, score: scoreBand(colors) };
  });
  const best = candidates.reduce((current, candidate) => candidate.score > current.score ? candidate : current);
  const dominantPalettes: DominantPalettes = {
    "2": dominantPalette(pixels, width, height, 2),
    "3": dominantPalette(pixels, width, height, 3),
  };
  return { ...best, dominantPalettes };
}
