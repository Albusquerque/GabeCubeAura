export const CONTROLLER_VARIANTS = {
  connect: [
    { data: "welcome", label: "Magnetic welcome", detail: "Two currents meet, make a white glint, then show the battery if Steam reports it." },
    { data: "orbit", label: "Arc return", detail: "A point traverses the bar and returns before the available battery level appears." },
    { data: "handshake", label: "Twin bloom", detail: "Two points open from the centre, then show the available battery level." },
  ],
  persistent: [
    { data: "clean", label: "Quiet fill", detail: "A steady, easy-to-read battery gauge." },
    { data: "tip", label: "Bright tip", detail: "A white endpoint marks the remaining charge." },
    { data: "horizon", label: "Soft horizon", detail: "A dimmer living-room gauge." },
  ],
  low: [
    { data: "beacon", label: "Last ember", detail: "The bar contracts to the charge left, then two warning beats." },
    { data: "drain", label: "Signal flare", detail: "A warning runs to the far edge and back." },
    { data: "heartbeat", label: "Afterglow", detail: "Brief warning pulses settle into a dim red remainder." },
  ],
  charging: [
    { data: "current", label: "Photon current", detail: "A white particle crosses the charged area, then rests at its tip." },
    { data: "breath", label: "Tidal fill", detail: "A broad wave moves through the charged area." },
    { data: "spark", label: "Spark lattice", detail: "Small highlights move through the reported charge level." },
  ],
  duo: [
    { data: "twin", label: "Twin reveal", detail: "Every active seat grows into view; white tips appear after the intro." },
    { data: "focus", label: "Two signatures", detail: "A white point introduces each active seat in turn; fixed white tips appear after the intro." },
    { data: "double-welcome", label: "Mirror greeting", detail: "White points greet every active seat and withdraw; fixed white tips finish." },
  ],
} as const;
