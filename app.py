import logging
import threading
import time
import tkinter as tk

import audio
import controller
from config import load_config
from desktop_ui import DesktopUI
from logging_setup import configure_logging, log_event
from services.elevenlabs_client import synthesize_result

logger = logging.getLogger("iris.app")


class App:
    def __init__(self) -> None:
        self.config = load_config()
        self.root = tk.Tk()
        self.ui = DesktopUI(
            self.root,
            on_interpret=self.trigger_interpretation,
            on_hear_result=self.trigger_conversation,
            on_dismiss=self.dismiss,
        )
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

        self.ui.set_demo_mode(self.config.demo_mode)
        self._init_microphone()
        self._init_camera_status()
        self._gpio_trigger = self._init_trigger()
        self._conversation_stop_event: threading.Event | None = None

        self.ui.set_state(controller.LISTENING)

    def _init_trigger(self):
        """Task 13: start the physical GPIO button trigger if configured.

        Calls the same trigger_interpretation() the software button uses, so
        there is no separate code path for the physical button. Never lets a
        missing/misconfigured Pi break app startup — same defensive style as
        _init_microphone().
        """
        if self.config.trigger_mode != "gpio":
            return None
        try:
            from trigger import GPIOButtonTrigger

            gpio_trigger = GPIOButtonTrigger(
                pin=self.config.gpio_button_pin, on_press=self.trigger_interpretation
            )
            gpio_trigger.start()
            return gpio_trigger
        except Exception as exc:
            logger.warning("GPIO button trigger unavailable: %s", exc)
            return None

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
        if self._conversation_stop_event is not None:
            log_event("button_pressed", ignored="conversation_active")
            return
        threading.Thread(target=self._run_interpretation, daemon=True).start()

    def _run_interpretation(self) -> None:
        result = controller.run_interpretation(
            on_state_change=lambda state: self.root.after(
                0,
                self.ui.set_state,
                state,
            )
        )

        if result.success:
            camera_notice = None

            if (
                self.config.camera_mode != "sample"
                and not self.config.demo_mode
            ):
                if not result.image_captured:
                    camera_notice = (
                        "Camera unavailable — interpretation used speech only."
                    )
                elif not result.visual_context_used:
                    camera_notice = (
                        "Image captured and inspected, but it did not contribute "
                        "to this interpretation."
                    )
            self.root.after(
                0,
                self.ui.show_result,
                result,
                camera_notice,
            )

            if self.config.tts_enabled and result.spoken_summary:
                self._speak(result.spoken_summary)
                self._listen_for_conversation_trigger(result)
        else:
            self.root.after(
                0,
                self.ui.show_error,
                result.error or "Something went wrong. Please try again.",
            )

    def _listen_for_conversation_trigger(self, interpretation_result) -> None:
        """After the result is spoken aloud, listen once for the user saying
        a conversation-start phrase (e.g. "let's talk") instead of requiring
        the button. Does nothing if nothing usable was said."""
        if self._conversation_stop_event is not None:
            return
        time.sleep(self.config.conversation_answer_wait_seconds)
        turn = controller.try_start_conversation_by_voice(interpretation_result)
        if turn is None:
            return
        self._conversation_stop_event = threading.Event()
        self._conversation_loop(turn)

    def trigger_conversation(self) -> None:
        if self._conversation_stop_event is not None:
            return
        interpretation_result = self.ui.get_last_result()
        if interpretation_result is None:
            return
        self._conversation_stop_event = threading.Event()
        threading.Thread(
            target=self._run_conversation, args=(interpretation_result,), daemon=True
        ).start()

    def _run_conversation(self, interpretation_result) -> None:
        turn = controller.start_conversation(interpretation_result)
        self._conversation_loop(turn)

    def _conversation_loop(self, turn) -> None:
        stop_event = self._conversation_stop_event
        self.root.after(0, self.ui.set_state, controller.CONVERSATION)

        try:
            while True:
                if turn.message:
                    self.root.after(0, self.ui.set_conversation_line, turn.message)
                    self._speak(turn.message)

                if not turn.success or turn.conversation_over or stop_event.is_set():
                    break

                if stop_event.wait(timeout=self.config.conversation_answer_wait_seconds):
                    break  # Dismiss was pressed during the wait

                turn = controller.continue_conversation(turn.thread_id, turn.history)
        finally:
            controller.end_conversation()
            self._conversation_stop_event = None
            self.root.after(0, self.ui.reset)

    def _speak(self, text: str) -> None:
        import playback

        path = synthesize_result(text)
        played = False
        if path:
            played = playback.play_and_cleanup(path)
        log_event("tts_finished", played=played)

    def dismiss(self) -> None:
        if self._conversation_stop_event is not None:
            self._conversation_stop_event.set()
            return
        self.ui.reset()

    def shutdown(self) -> None:
        if self._conversation_stop_event is not None:
            self._conversation_stop_event.set()
        try:
            audio.stop_audio_stream()
        except Exception:
            pass
        if self._gpio_trigger is not None:
            try:
                self._gpio_trigger.stop()
            except Exception:
                pass
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    configure_logging(load_config().log_level)
    App().run()


if __name__ == "__main__":
    main()
