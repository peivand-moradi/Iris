import threading
import tkinter as tk

import audio
import controller
from config import load_config
from desktop_ui import DesktopUI
from logging_setup import configure_logging, log_event


class App:
    def __init__(self) -> None:
        self.config = load_config()
        self.root = tk.Tk()
        self.ui = DesktopUI(
            self.root,
            on_interpret=self.trigger_interpretation,
            on_hear_result=self.trigger_hear_result,
            on_dismiss=self.dismiss,
        )
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

        self.ui.set_demo_mode(self.config.demo_mode)
        self._init_microphone()
        self._init_camera_status()

        self.ui.set_state(controller.LISTENING)

    def _init_microphone(self) -> None:
        if self.config.demo_mode:
            self.ui.set_mic_status("demo mode (sample audio)")
            return
        try:
            audio.start_audio_stream()
            self.ui.set_mic_status("listening")
        except Exception as exc:
            log_event("audio_saved", success=False, error=str(exc))
            self.ui.set_mic_status("unavailable — check system audio permissions")

    def _init_camera_status(self) -> None:
        if self.config.demo_mode:
            self.ui.set_camera_status("demo mode (sample image)")
        elif self.config.camera_mode == "sample":
            self.ui.set_camera_status("sample image")
        else:
            self.ui.set_camera_status("ready")

    def trigger_interpretation(self) -> None:
        threading.Thread(target=self._run_interpretation, daemon=True).start()

    def _run_interpretation(self) -> None:
        result = controller.run_interpretation(
            on_state_change=lambda state: self.root.after(0, self.ui.set_state, state)
        )
        if result.success:
            camera_notice = None
            if self.config.camera_mode != "sample" and not self.config.demo_mode and not result.visual_context_used:
                camera_notice = "Camera unavailable — interpretation used speech only."
            self.root.after(0, self.ui.show_result, result, camera_notice)
            if self.config.tts_enabled:
                threading.Thread(target=self._speak, args=(result.spoken_summary,), daemon=True).start()
        else:
            self.root.after(0, self.ui.show_error, result.error or "Something went wrong. Please try again.")

    def trigger_hear_result(self) -> None:
        text = self.ui.get_spoken_summary()
        if text:
            threading.Thread(target=self._speak, args=(text,), daemon=True).start()

    def _speak(self, text: str) -> None:
        from services.elevenlabs_client import synthesize_result

        import playback

        path = synthesize_result(text)
        played = False
        if path:
            played = playback.play_and_cleanup(path)
        log_event("tts_finished", played=played)

    def dismiss(self) -> None:
        self.ui.reset()

    def shutdown(self) -> None:
        try:
            audio.stop_audio_stream()
        except Exception:
            pass
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    configure_logging()
    App().run()


if __name__ == "__main__":
    main()
