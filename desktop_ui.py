import tkinter as tk
from typing import Callable

from controller import CAPTURING, ERROR, LISTENING, PROCESSING, RESULT, STARTING
from logging_setup import log_event
from models import InterpretationResult

_STATE_MESSAGES = {
    STARTING: "Starting…",
    LISTENING: "Listening. Press the button after something is unclear.",
    CAPTURING: "Saving recent speech and taking a context photo…",
    PROCESSING: "Considering possible meaning with Backboard…",
    RESULT: "Result ready.",
    ERROR: "Something went wrong.",
}

_BUSY_STATES = (CAPTURING, PROCESSING)


class DesktopUI:
    """The one Tkinter window. The controller never touches these widgets directly —
    it only calls the methods below, so the display stays swappable later.
    """

    def __init__(
        self,
        root: tk.Tk,
        on_interpret: Callable[[], None],
        on_hear_result: Callable[[], None],
        on_dismiss: Callable[[], None],
    ):
        self.root = root
        self.root.title("Iris")
        self.root.configure(bg="#1e1e1e")
        self._last_result: InterpretationResult | None = None

        header = tk.Label(
            root, text="Iris", font=("Helvetica", 22, "bold"), fg="#f5f5f5", bg="#1e1e1e",
        )
        header.pack(padx=20, pady=(20, 0), anchor="w")

        self.status_label = tk.Label(
            root, text=_STATE_MESSAGES[STARTING], font=("Helvetica", 16),
            wraplength=520, justify="left", fg="#f5f5f5", bg="#1e1e1e",
        )
        self.status_label.pack(padx=20, pady=(6, 4), anchor="w")

        status_row = tk.Frame(root, bg="#1e1e1e")
        status_row.pack(padx=20, pady=(0, 10), anchor="w")
        self.mic_status_label = tk.Label(
            status_row, text="Microphone: unknown", font=("Helvetica", 11), fg="#aaaaaa", bg="#1e1e1e",
        )
        self.mic_status_label.pack(side="left", padx=(0, 16))
        self.camera_status_label = tk.Label(
            status_row, text="Camera: unknown", font=("Helvetica", 11), fg="#aaaaaa", bg="#1e1e1e",
        )
        self.camera_status_label.pack(side="left")

        self.demo_banner = tk.Label(
            root, text="DEMO MODE", font=("Helvetica", 11, "bold"), fg="#1e1e1e", bg="#f5c542",
        )

        self.result_frame = tk.Frame(root, bg="#1e1e1e")
        self.result_frame.pack(padx=20, pady=10, fill="both", expand=True)

        self.heard_label = self._result_label(14, italic=True)
        self.meaning_label = self._result_label(15, bold=True)
        self.why_label = self._result_label(12)
        self.certainty_label = self._result_label(12)
        self.alternative_label = self._result_label(12)
        self.camera_notice_label = self._result_label(11, color="#f5c542")

        controls = tk.Frame(root, bg="#1e1e1e")
        controls.pack(padx=20, pady=20, fill="x")

        self.interpret_button = tk.Button(
            controls, text="Interpret recent sentence", font=("Helvetica", 14), command=on_interpret,
        )
        self.interpret_button.pack(side="left", padx=(0, 8))

        self.hear_button = tk.Button(
            controls, text="Hear result", font=("Helvetica", 12), command=on_hear_result, state=tk.DISABLED,
        )
        self.hear_button.pack(side="left", padx=8)

        self.try_again_button = tk.Button(
            controls, text="Try again", font=("Helvetica", 12), command=on_interpret, state=tk.DISABLED,
        )
        self.try_again_button.pack(side="left", padx=8)

        self.dismiss_button = tk.Button(
            controls, text="Dismiss", font=("Helvetica", 12), command=on_dismiss, state=tk.DISABLED,
        )
        self.dismiss_button.pack(side="left", padx=8)

        self.set_state(STARTING)

    def _result_label(self, size: int, bold: bool = False, italic: bool = False, color: str = "#f5f5f5") -> tk.Label:
        weight = "bold" if bold else "normal"
        slant = "italic" if italic else "roman"
        label = tk.Label(
            self.result_frame, text="", font=("Helvetica", size, weight, slant),
            wraplength=520, justify="left", fg=color, bg="#1e1e1e",
        )
        label.pack(anchor="w", pady=4)
        return label

    # --- state -----------------------------------------------------------

    def set_state(self, state: str) -> None:
        self.status_label.config(text=_STATE_MESSAGES.get(state, state))
        busy = state in _BUSY_STATES
        self.interpret_button.config(state=tk.DISABLED if busy else tk.NORMAL)
        self.try_again_button.config(state=tk.DISABLED if busy or self._last_result is None else tk.NORMAL)
        self.dismiss_button.config(state=tk.DISABLED if busy or self._last_result is None else tk.NORMAL)
        self.hear_button.config(
            state=tk.DISABLED if busy or not self._has_speakable_result() else tk.NORMAL
        )

    def _has_speakable_result(self) -> bool:
        return bool(self._last_result and self._last_result.success and self._last_result.spoken_summary)

    def set_mic_status(self, text: str) -> None:
        self.mic_status_label.config(text=f"Microphone: {text}")

    def set_camera_status(self, text: str) -> None:
        self.camera_status_label.config(text=f"Camera: {text}")

    def set_demo_mode(self, enabled: bool) -> None:
        if enabled:
            self.demo_banner.pack(padx=20, pady=(0, 10), anchor="w")
        else:
            self.demo_banner.pack_forget()

    # --- results -----------------------------------------------------------

    def show_result(self, result: InterpretationResult, camera_notice: str | None = None) -> None:
        self._last_result = result
        self.heard_label.config(text=f'Heard: "{result.heard}"')
        self.meaning_label.config(text=f"Possible meaning: {result.possible_meaning}")
        self.why_label.config(text=f"Why: {result.why}" if result.why else "")
        self.certainty_label.config(
            text=f"Certainty: {result.certainty} — this is one possible interpretation."
        )
        self.alternative_label.config(
            text=f"Alternative: {result.alternative}" if result.alternative else ""
        )
        self.camera_notice_label.config(text=camera_notice or "")
        self.set_state(RESULT)
        log_event("result_displayed", certainty=result.certainty)

    def show_error(self, message: str) -> None:
        self._last_result = None
        self.heard_label.config(text="")
        self.meaning_label.config(text="")
        self.why_label.config(text="")
        self.certainty_label.config(text="")
        self.alternative_label.config(text=message)
        self.camera_notice_label.config(text="")
        self.set_state(ERROR)

    def reset(self) -> None:
        self._last_result = None
        self.heard_label.config(text="")
        self.meaning_label.config(text="")
        self.why_label.config(text="")
        self.certainty_label.config(text="")
        self.alternative_label.config(text="")
        self.camera_notice_label.config(text="")
        self.set_state(LISTENING)

    def get_spoken_summary(self) -> str | None:
        if self._last_result and self._last_result.success:
            return self._last_result.spoken_summary
        return None
