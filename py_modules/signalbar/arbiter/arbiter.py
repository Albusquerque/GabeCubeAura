"""Policy-only selection of the active provider."""

from __future__ import annotations

from signalbar.models import ProviderOutput, normalize_frame
from signalbar.providers.events import RED


class Arbiter:
    @staticmethod
    def _with_recording_marker(base, enabled, isolation):
        if not enabled or base.frame is None:
            return base
        pixels = list(base.frame)
        if isolation:
            pixels[7] = (0, 0, 0)
            pixels[9] = (0, 0, 0)
        pixels[8] = RED
        return ProviderOutput(base.provider + "+recording", normalize_frame(pixels), base.reason)

    def choose(self, *, mode, guard_allows, game, performance, artwork, idle,
               signal=None, event=None, signal_critical=False, recording_marker=False,
               recording_marker_isolation=False, performance_always=False,
               controller_event=None, controller_base=None, weather_base=None,
               customization_base=None, launch_artwork=None):
        if mode == "disabled":
            return ProviderOutput("none", None, "GabeCubeAura disabled")
        # Short, opted-in effects can briefly use an otherwise native-owned bar.
        # The runtime still yields if it detects a new external write mid-effect.
        if controller_event is not None and controller_event.frame is not None and not signal_critical and controller_event.provider == "controller:low":
            return controller_event
        if event is not None and event.frame is not None and not signal_critical:
            return event
        if controller_event is not None and controller_event.frame is not None and not signal_critical:
            return controller_event
        if not guard_allows:
            return ProviderOutput("valve", None, "Valve/system owns the bar")

        if signal_critical and signal is not None and signal.frame is not None:
            return signal

        if launch_artwork is not None and launch_artwork.frame is not None:
            return launch_artwork

        if signal is not None and signal.frame is not None:
            return signal

        if weather_base is not None and weather_base.provider == "weather:preview" and weather_base.frame is not None:
            return self._with_recording_marker(weather_base, recording_marker, recording_marker_isolation)
        if customization_base is not None and customization_base.provider == "customization:preview" and customization_base.frame is not None:
            return self._with_recording_marker(customization_base, recording_marker, recording_marker_isolation)

        if controller_base is not None and controller_base.frame is not None:
            return self._with_recording_marker(controller_base, recording_marker, recording_marker_isolation)
        if weather_base is not None and weather_base.frame is not None:
            return self._with_recording_marker(weather_base, recording_marker, recording_marker_isolation)

        if mode == "events":
            return ProviderOutput("none", None, "No permanent GabeCubeAura display selected here")

        if mode == "performance":
            base = performance if (game.running or performance_always) and performance.frame else ProviderOutput("none", None, "performance unavailable")
        elif mode == "artwork":
            base = artwork if game.running and artwork.frame else ProviderOutput("none", None, "artwork unavailable")
        elif mode == "customization":
            base = customization_base if customization_base is not None and customization_base.frame \
                else ProviderOutput("none", None, "Customization+ unavailable")
        elif game.running and performance.frame:
            base = performance
        elif game.running and artwork.frame:
            base = artwork
        else:
            base = idle

        return self._with_recording_marker(
            base, recording_marker and base.provider.startswith(("performance", "artwork", "customization")),
            recording_marker_isolation,
        )
