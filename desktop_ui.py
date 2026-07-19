import tkinter as tk
from tkinter import font as tkfont
from typing import Callable

from controller import CAPTURING, CONVERSATION, ERROR, LISTENING, PROCESSING, RESULT, STARTING
from logging_setup import log_event
from models import InterpretationResult

# Sensory-considerate default theme: low luminance, muted colour, no animation,
# no pure white/black, no colour-only meaning, and a predictable single-column flow.
COLORS = {
    "page": "#111514",
    "surface": "#181E1C",
    "surface_2": "#202724",
    "surface_3": "#28312D",
    "border": "#39443F",
    "text": "#D7DFDB",
    "muted": "#A6B0AB",
    "subtle": "#7F8B85",
    "accent": "#8DAEA3",
    "accent_surface": "#263A34",
    "accent_text": "#D7E8E2",
    "warning": "#C5B98F",
    "warning_surface": "#3A3525",
    "error": "#D1A4A4",
    "error_surface": "#3A2828",
    "disabled_bg": "#222927",
    "disabled_fg": "#69736E",
    "focus": "#B7CBC4",
}

_STATE_COPY = {
    STARTING: ("Starting", "Preparing the microphone and camera.", "STARTING"),
    LISTENING: ("Ready", "Press Interpret after a sentence feels unclear.", "READY"),
    CAPTURING: ("Capturing context", "Saving recent speech and taking one photo.", "CAPTURING"),
    PROCESSING: ("Considering possibilities", "Reviewing the words and available context.", "PROCESSING"),
    RESULT: ("Interpretation ready", "One possible reading — not a statement of intent.", "READY"),
    CONVERSATION: ("Let's talk about it", "Listening for your answer…", "TALKING"),
    ERROR: ("Unable to interpret", "Review the message below, then try again.", "ERROR"),
}

_BUSY_STATES = (CAPTURING, PROCESSING, CONVERSATION)


class DesktopUI:
    """A calm, responsive Tkinter interface for the Iris prototype.

    The application header, status, and actions are fixed. Only the result body
    scrolls, so the primary controls remain available at every supported size.
    """

    def __init__(
        self,
        root: tk.Tk,
        on_interpret: Callable[[], None],
        on_hear_result: Callable[[], None],
        on_dismiss: Callable[[], None],
    ):
        self.root = root
        self.root.title("Iris — Context Interpreter")
        self.root.configure(bg=COLORS["page"])
        self.root.geometry("1040x760")
        self.root.minsize(680, 560)

        self._last_result: InterpretationResult | None = None
        self._details_stacked = False
        self._font_scale = 1.0

        self._on_interpret = on_interpret
        self._on_hear_result = on_hear_result
        self._on_dismiss = on_dismiss

        # Fixed header/status/footer, flexible middle region.
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(2, weight=1)

        self._create_fonts()
        self._build_header()
        self._build_status_panel()
        self._build_scroll_region()
        self._build_footer()
        self.set_callbacks(on_interpret, on_hear_result, on_dismiss)

        self.root.bind("<Return>", lambda _e: self._invoke_if_enabled(self.interpret_button))
        self.root.bind("<Configure>", self._on_root_resize)

        self.set_state(STARTING)

    # ------------------------------------------------------------------
    # Fonts and visual primitives

    def _create_fonts(self) -> None:
        family = "Segoe UI" if "Segoe UI" in tkfont.families(self.root) else "Helvetica"
        self.fonts = {
            "brand": tkfont.Font(root=self.root, family=family, size=28, weight="bold"),
            "tagline": tkfont.Font(root=self.root, family=family, size=12),
            "status": tkfont.Font(root=self.root, family=family, size=17, weight="bold"),
            "eyebrow": tkfont.Font(root=self.root, family=family, size=11, weight="bold"),
            "meaning": tkfont.Font(root=self.root, family=family, size=19, weight="bold"),
            "body": tkfont.Font(root=self.root, family=family, size=14),
            "body_bold": tkfont.Font(root=self.root, family=family, size=14, weight="bold"),
            "small": tkfont.Font(root=self.root, family=family, size=12),
            "button": tkfont.Font(root=self.root, family=family, size=13, weight="bold"),
        }

    def _surface(self, parent: tk.Widget, *, bg: str | None = None) -> tk.Frame:
        return tk.Frame(
            parent,
            bg=bg or COLORS["surface"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            bd=0,
        )

    def _separator(self, parent: tk.Widget) -> tk.Frame:
        return tk.Frame(parent, height=1, bg=COLORS["border"])

    # ------------------------------------------------------------------
    # Fixed regions

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=COLORS["page"])
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(20, 12))
        header.grid_columnconfigure(1, weight=1)

        # Minimal geometric mark instead of a decorative image or emoji.
        mark = tk.Canvas(header, width=38, height=38, bg=COLORS["page"], highlightthickness=0)
        mark.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 12))
        mark.create_oval(4, 4, 34, 34, outline=COLORS["accent"], width=2)
        mark.create_oval(14, 14, 24, 24, fill=COLORS["accent"], outline="")

        tk.Label(
            header,
            text="Iris",
            font=self.fonts["brand"],
            fg=COLORS["text"],
            bg=COLORS["page"],
            anchor="w",
        ).grid(row=0, column=1, sticky="sw")

        tk.Label(
            header,
            text="Careful context for indirect language",
            font=self.fonts["tagline"],
            fg=COLORS["muted"],
            bg=COLORS["page"],
            anchor="w",
        ).grid(row=1, column=1, sticky="nw", pady=(1, 0))

        tools = tk.Frame(header, bg=COLORS["page"])
        tools.grid(row=0, column=2, rowspan=2, sticky="e")

        tk.Label(
            tools,
            text="Text size",
            font=self.fonts["small"],
            fg=COLORS["subtle"],
            bg=COLORS["page"],
        ).pack(side="left", padx=(0, 8))
        self.text_smaller_button = self._compact_button(tools, "A−", self._decrease_text)
        self.text_smaller_button.pack(side="left", padx=(0, 6))
        self.text_larger_button = self._compact_button(tools, "A+", self._increase_text)
        self.text_larger_button.pack(side="left")

        self.demo_banner = tk.Label(
            tools,
            text="DEMO",
            font=self.fonts["eyebrow"],
            fg=COLORS["warning"],
            bg=COLORS["warning_surface"],
            padx=10,
            pady=7,
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )

    def _build_status_panel(self) -> None:
        panel = self._surface(self.root)
        panel.grid(row=1, column=0, sticky="ew", padx=28, pady=(0, 12))
        panel.grid_columnconfigure(1, weight=1)

        self.status_badge = tk.Label(
            panel,
            text="READY",
            font=self.fonts["eyebrow"],
            fg=COLORS["accent_text"],
            bg=COLORS["accent_surface"],
            padx=10,
            pady=7,
        )
        self.status_badge.grid(row=0, column=0, rowspan=2, sticky="n", padx=(16, 14), pady=16)

        self.status_label = tk.Label(
            panel,
            text="",
            font=self.fonts["status"],
            fg=COLORS["text"],
            bg=COLORS["surface"],
            anchor="w",
        )
        self.status_label.grid(row=0, column=1, sticky="ew", pady=(14, 1))

        self.status_detail_label = tk.Label(
            panel,
            text="",
            font=self.fonts["small"],
            fg=COLORS["muted"],
            bg=COLORS["surface"],
            justify="left",
            anchor="w",
        )
        self.status_detail_label.grid(row=1, column=1, sticky="ew", pady=(1, 14))

        devices = tk.Frame(panel, bg=COLORS["surface"])
        devices.grid(row=0, column=2, rowspan=2, sticky="e", padx=16, pady=10)
        self.mic_status_label = self._device_row(devices, "Microphone", "unknown")
        self.camera_status_label = self._device_row(devices, "Camera", "unknown")

    def _build_footer(self) -> None:
        footer = tk.Frame(
            self.root,
            bg=COLORS["surface_2"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        footer.grid(row=3, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)

        inner = tk.Frame(footer, bg=COLORS["surface_2"])
        inner.grid(row=0, column=0, sticky="ew", padx=28, pady=14)
        inner.grid_columnconfigure(0, weight=3)
        inner.grid_columnconfigure(1, weight=1)
        inner.grid_columnconfigure(2, weight=1)

        self.interpret_button = self._action_button(
            inner,
            "Interpret recent sentence",
            self._placeholder_command,
            primary=True,
        )
        self.interpret_button.grid(row=0, column=0, sticky="ew")

        # This secondary action only appears after Iris has a speakable result.
        self.hear_button = self._action_button(inner, "Let's talk about it", self._placeholder_command)
        self.hear_button.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        self.hear_button.grid_remove()

        # Only shown while a conversation is actively in progress — the one
        # addition to this footer's otherwise single-action philosophy,
        # since a live back-and-forth genuinely needs a way to stop early.
        self.end_conversation_button = self._action_button(
            inner, "End conversation", self._placeholder_command
        )
        self.end_conversation_button.grid(row=0, column=2, sticky="ew", padx=(10, 0))
        self.end_conversation_button.grid_remove()

        # Kept as callback data for compatibility with the existing controller.
        # There is intentionally no persistent Clear/Try Again control in the UI.
        self.dismiss_button = None

    # ------------------------------------------------------------------
    # Scrollable centre

    def _build_scroll_region(self) -> None:
        shell = tk.Frame(self.root, bg=COLORS["page"])
        shell.grid(row=2, column=0, sticky="nsew", padx=(28, 16))
        shell.grid_rowconfigure(0, weight=1)
        shell.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            shell,
            bg=COLORS["page"],
            highlightthickness=0,
            bd=0,
            yscrollincrement=24,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.scrollbar = tk.Scrollbar(
            shell,
            orient="vertical",
            command=self.canvas.yview,
            width=12,
            relief="flat",
            bd=0,
            bg=COLORS["surface_3"],
            activebackground=COLORS["accent_surface"],
            troughcolor=COLORS["page"],
        )
        self.scrollbar.grid(row=0, column=1, sticky="ns", padx=(10, 0))
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.content = tk.Frame(self.canvas, bg=COLORS["page"])
        self._canvas_window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", self._refresh_scrollregion)
        self.canvas.bind("<Configure>", self._resize_canvas_window)

        # Scroll only while the pointer is inside the result area.
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

        self._build_empty_state()
        self._build_result_state()

    def _build_empty_state(self) -> None:
        self.empty_state = self._surface(self.content)
        self.empty_state.pack(fill="both", expand=True)

        inner = tk.Frame(self.empty_state, bg=COLORS["surface"])
        inner.pack(fill="both", expand=True, padx=26, pady=26)

        tk.Label(
            inner,
            text="READY TO INTERPRET",
            font=self.fonts["eyebrow"],
            fg=COLORS["accent"],
            bg=COLORS["surface"],
            anchor="w",
        ).pack(fill="x")

        tk.Label(
            inner,
            text="A sentence felt unclear?",
            font=self.fonts["meaning"],
            fg=COLORS["text"],
            bg=COLORS["surface"],
            anchor="w",
        ).pack(fill="x", pady=(10, 8))

        self.empty_body = tk.Label(
            inner,
            text=(
                "Press Interpret. Iris will review the recent speech and available visual context, "
                "then present one possible meaning and an alternative when useful."
            ),
            font=self.fonts["body"],
            fg=COLORS["muted"],
            bg=COLORS["surface"],
            justify="left",
            anchor="w",
            wraplength=760,
        )
        self.empty_body.pack(fill="x")

        steps = tk.Frame(inner, bg=COLORS["surface"])
        steps.pack(fill="x", pady=(24, 2))
        self._step(steps, "1", "Hear", "Iris keeps a short local audio buffer.").pack(fill="x", pady=(0, 8))
        self._step(steps, "2", "Press", "Choose Interpret after the sentence.").pack(fill="x", pady=8)
        self._step(steps, "3", "Review", "Read a careful, uncertainty-aware explanation.").pack(fill="x", pady=(8, 0))

    def _build_result_state(self) -> None:
        self.result_state = tk.Frame(self.content, bg=COLORS["page"])

        self.heard_value = self._card(self.result_state, "HEARD", quoted=True)
        self.meaning_value = self._card(self.result_state, "POSSIBLE MEANING", prominent=True)
        self.why_value = self._card(self.result_state, "WHY THIS MAY FIT")

        self.details = tk.Frame(self.result_state, bg=COLORS["page"])
        self.details.pack(fill="x")
        self.details.grid_columnconfigure(0, weight=1, uniform="detail")
        self.details.grid_columnconfigure(1, weight=1, uniform="detail")

        self.context_card, self.context_value = self._grid_card(self.details, "VISUAL CONTEXT", 0)
        self.certainty_card, self.certainty_value = self._grid_card(self.details, "CERTAINTY", 1)
        self.alternative_value = self._card(self.result_state, "ANOTHER POSSIBILITY")

        note = self._surface(self.result_state, bg=COLORS["surface_2"])
        note.pack(fill="x", pady=(0, 4))
        tk.Label(
            note,
            text="Iris offers possibilities, not facts about another person's intent.",
            font=self.fonts["small"],
            fg=COLORS["muted"],
            bg=COLORS["surface_2"],
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=16, pady=12)

    # ------------------------------------------------------------------
    # Components

    def _step(self, parent: tk.Widget, number: str, title: str, body: str) -> tk.Frame:
        row = tk.Frame(parent, bg=COLORS["surface_2"])
        badge = tk.Label(
            row,
            text=number,
            font=self.fonts["eyebrow"],
            fg=COLORS["accent_text"],
            bg=COLORS["accent_surface"],
            width=3,
            pady=6,
        )
        badge.pack(side="left", padx=(10, 12), pady=10)

        copy = tk.Frame(row, bg=COLORS["surface_2"])
        copy.pack(side="left", fill="both", expand=True, pady=9, padx=(0, 10))
        tk.Label(
            copy,
            text=title,
            font=self.fonts["body_bold"],
            fg=COLORS["text"],
            bg=COLORS["surface_2"],
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            copy,
            text=body,
            font=self.fonts["small"],
            fg=COLORS["muted"],
            bg=COLORS["surface_2"],
            anchor="w",
            justify="left",
        ).pack(fill="x", pady=(2, 0))
        return row

    def _card(self, parent: tk.Widget, heading: str, *, prominent: bool = False, quoted: bool = False) -> tk.Label:
        card = self._surface(parent)
        card.pack(fill="x", pady=(0, 10))
        return self._card_content(card, heading, prominent=prominent, quoted=quoted)

    def _grid_card(self, parent: tk.Widget, heading: str, column: int) -> tuple[tk.Frame, tk.Label]:
        card = self._surface(parent)
        card.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=(0, 5) if column == 0 else (5, 0),
            pady=(0, 10),
        )
        return card, self._card_content(card, heading)

    def _card_content(
        self,
        card: tk.Frame,
        heading: str,
        *,
        prominent: bool = False,
        quoted: bool = False,
    ) -> tk.Label:
        tk.Label(
            card,
            text=heading,
            font=self.fonts["eyebrow"],
            fg=COLORS["accent"],
            bg=COLORS["surface"],
            anchor="w",
        ).pack(fill="x", padx=18, pady=(15, 0))

        value = tk.Label(
            card,
            text="",
            font=self.fonts["meaning"] if prominent else self.fonts["body"],
            fg=COLORS["text"],
            bg=COLORS["surface"],
            justify="left",
            anchor="nw",
            wraplength=760,
        )
        value.pack(fill="both", expand=True, padx=18, pady=(8, 16))
        value._iris_quoted = quoted  # type: ignore[attr-defined]
        return value

    def _device_row(self, parent: tk.Widget, name: str, value: str) -> tk.Label:
        label = tk.Label(
            parent,
            text=f"{name}: {value}",
            font=self.fonts["small"],
            fg=COLORS["muted"],
            bg=COLORS["surface"],
            anchor="e",
        )
        label.pack(anchor="e", pady=1)
        return label

    def _compact_button(self, parent: tk.Widget, text: str, command: Callable[[], None]) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=self.fonts["small"],
            fg=COLORS["text"],
            bg=COLORS["surface_2"],
            activeforeground=COLORS["text"],
            activebackground=COLORS["surface_3"],
            disabledforeground=COLORS["disabled_fg"],
            relief="flat",
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            takefocus=True,
            highlightthickness=2,
            highlightbackground=COLORS["page"],
            highlightcolor=COLORS["focus"],
        )

    def _action_button(
        self,
        parent: tk.Widget,
        text: str,
        command: Callable[[], None],
        *,
        primary: bool = False,
    ) -> tk.Button:
        bg = COLORS["accent"] if primary else COLORS["accent_surface"]
        fg = COLORS["page"] if primary else COLORS["accent_text"]
        active_bg = COLORS["focus"] if primary else COLORS["surface_3"]
        # Secondary buttons get a visible accent border so they read as
        # clickable at a glance rather than blending into the muted
        # surface tones — disabledforeground still dims the text when busy.
        border = COLORS["accent"]
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=self.fonts["button"],
            fg=fg,
            bg=bg,
            activeforeground=fg,
            activebackground=active_bg,
            disabledforeground=COLORS["disabled_fg"],
            relief="flat",
            bd=0,
            padx=14,
            pady=11,
            cursor="hand2",
            takefocus=True,
            highlightthickness=2,
            highlightbackground=border,
            highlightcolor=COLORS["focus"],
        )

    def _placeholder_command(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Responsive behaviour and scrolling

    def _refresh_scrollregion(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._update_scrollbar_visibility()

    def _resize_canvas_window(self, event) -> None:
        self.canvas.itemconfigure(self._canvas_window, width=event.width)
        self._update_wraplengths(event.width)
        self.root.after_idle(self._update_scrollbar_visibility)

    def _update_scrollbar_visibility(self) -> None:
        bbox = self.canvas.bbox("all")
        if not bbox:
            return
        content_height = bbox[3] - bbox[1]
        if content_height <= self.canvas.winfo_height() + 2:
            self.scrollbar.grid_remove()
        else:
            self.scrollbar.grid()

    def _update_wraplengths(self, width: int) -> None:
        full = max(width - 54, 300)
        self.empty_body.configure(wraplength=full)
        for label in (self.heard_value, self.meaning_value, self.why_value, self.alternative_value):
            label.configure(wraplength=full)
        half = max((width - 84) // 2, 250)
        self.context_value.configure(wraplength=half)
        self.certainty_value.configure(wraplength=half)

    def _on_root_resize(self, event) -> None:
        if event.widget is not self.root:
            return

        should_stack = event.width < 800
        if should_stack != self._details_stacked:
            self._details_stacked = should_stack
            if should_stack:
                self.context_card.grid_configure(row=0, column=0, columnspan=2, padx=0)
                self.certainty_card.grid_configure(row=1, column=0, columnspan=2, padx=0)
            else:
                self.context_card.grid_configure(row=0, column=0, columnspan=1, padx=(0, 5))
                self.certainty_card.grid_configure(row=0, column=1, columnspan=1, padx=(5, 0))

        # Keep the single primary action dominant. When the window is narrow,
        # the optional audio/conversation actions move underneath instead of
        # squeezing text.
        if event.width < 760:
            self.interpret_button.grid_configure(row=0, column=0, columnspan=3, padx=0, pady=0)
            self.hear_button.grid_configure(row=1, column=0, columnspan=3, padx=0, pady=(8, 0))
            self.end_conversation_button.grid_configure(row=2, column=0, columnspan=3, padx=0, pady=(8, 0))
        else:
            self.interpret_button.grid_configure(row=0, column=0, columnspan=1, padx=0, pady=0)
            self.hear_button.grid_configure(row=0, column=1, columnspan=1, padx=(10, 0), pady=0)
            self.end_conversation_button.grid_configure(row=0, column=2, columnspan=1, padx=(10, 0), pady=0)

    def _bind_wheel(self, _event=None) -> None:
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", lambda _e: self.canvas.yview_scroll(-2, "units"))
        self.canvas.bind_all("<Button-5>", lambda _e: self.canvas.yview_scroll(2, "units"))

    def _unbind_wheel(self, _event=None) -> None:
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event) -> None:
        if event.delta:
            direction = -1 if event.delta > 0 else 1
            self.canvas.yview_scroll(direction * 3, "units")

    def _increase_text(self) -> None:
        self._set_font_scale(min(self._font_scale + 0.1, 1.3))

    def _decrease_text(self) -> None:
        self._set_font_scale(max(self._font_scale - 0.1, 0.9))

    def _set_font_scale(self, scale: float) -> None:
        self._font_scale = round(scale, 1)
        base_sizes = {
            "brand": 28,
            "tagline": 12,
            "status": 17,
            "eyebrow": 11,
            "meaning": 19,
            "body": 14,
            "body_bold": 14,
            "small": 12,
            "button": 13,
        }
        for name, base in base_sizes.items():
            self.fonts[name].configure(size=max(9, round(base * self._font_scale)))
        self.text_smaller_button.configure(state=tk.DISABLED if scale <= 0.9 else tk.NORMAL)
        self.text_larger_button.configure(state=tk.DISABLED if scale >= 1.3 else tk.NORMAL)
        self.root.after_idle(self._refresh_scrollregion)

    # ------------------------------------------------------------------
    # State and callbacks

    def set_callbacks(
        self,
        on_interpret: Callable[[], None],
        on_hear_result: Callable[[], None],
        on_dismiss: Callable[[], None],
    ) -> None:
        self._on_interpret = on_interpret
        self._on_hear_result = on_hear_result
        self._on_dismiss = on_dismiss
        self.interpret_button.configure(command=on_interpret)
        self.hear_button.configure(command=on_hear_result)
        self.end_conversation_button.configure(command=on_dismiss)

    def set_state(self, state: str) -> None:
        title, detail, badge = _STATE_COPY.get(state, (state, "", "STATUS"))
        self.status_label.configure(text=title)
        self.status_detail_label.configure(text=detail)

        badge_theme = {
            STARTING: (COLORS["surface_3"], COLORS["muted"]),
            LISTENING: (COLORS["accent_surface"], COLORS["accent_text"]),
            CAPTURING: (COLORS["warning_surface"], COLORS["warning"]),
            PROCESSING: (COLORS["warning_surface"], COLORS["warning"]),
            RESULT: (COLORS["accent_surface"], COLORS["accent_text"]),
            CONVERSATION: (COLORS["accent_surface"], COLORS["accent_text"]),
            ERROR: (COLORS["error_surface"], COLORS["error"]),
        }.get(state, (COLORS["surface_3"], COLORS["muted"]))
        self.status_badge.configure(text=badge, bg=badge_theme[0], fg=badge_theme[1])

        busy = state in _BUSY_STATES
        self.interpret_button.configure(state=tk.DISABLED if busy else tk.NORMAL)

        if self._has_speakable_result():
            self.hear_button.grid()
            self.hear_button.configure(state=tk.DISABLED if busy else tk.NORMAL)
        else:
            self.hear_button.grid_remove()

        # Unlike the buttons above, this one must stay enabled precisely
        # during the busy CONVERSATION state — it's the only way to interrupt it.
        if state == CONVERSATION:
            self.end_conversation_button.grid()
            self.end_conversation_button.configure(state=tk.NORMAL)
        else:
            self.end_conversation_button.grid_remove()

    def _has_speakable_result(self) -> bool:
        return bool(self._last_result and self._last_result.success and self._last_result.spoken_summary)

    def _invoke_if_enabled(self, button: tk.Button) -> None:
        if str(button.cget("state")) == tk.NORMAL:
            button.invoke()

    def set_mic_status(self, text: str) -> None:
        self.mic_status_label.configure(text=f"Microphone: {text}")

    def set_camera_status(self, text: str) -> None:
        self.camera_status_label.configure(text=f"Camera: {text}")

    def set_demo_mode(self, enabled: bool) -> None:
        if enabled:
            self.demo_banner.pack(side="left", padx=(12, 0))
        else:
            self.demo_banner.pack_forget()

    # ------------------------------------------------------------------
    # Results

    def _show_result_state(self) -> None:
        self.empty_state.pack_forget()
        self.result_state.pack(fill="both", expand=True)
        self.canvas.yview_moveto(0)

    def _show_empty_state(self) -> None:
        self.result_state.pack_forget()
        self.empty_state.pack(fill="both", expand=True)
        self.canvas.yview_moveto(0)

    def show_result(self, result: InterpretationResult, camera_notice: str | None = None) -> None:
        self._last_result = result
        self._show_result_state()

        self.heard_value.configure(text=f'“{result.heard}”')
        self.meaning_value.configure(text=result.possible_meaning)
        self.why_value.configure(text=result.why or "No additional context was available.")
        self.certainty_value.configure(
            text=f"{result.certainty.capitalize()}\nThis describes uncertainty, not a measured probability."
        )
        self.alternative_value.configure(
            text=result.alternative or "No clear alternative was needed for this result."
        )

        if camera_notice:
            context = camera_notice
        elif result.image_relevance == "relevant" or result.visual_context_used:
            context = "Relevant and used\nThe image contributed to this interpretation."
        elif result.image_relevance == "not_relevant" or result.image_captured:
            context = "Inspected, not used\nThe image did not add useful context this time."
        else:
            context = "Unavailable\nThis interpretation used speech only."
        if result.visual_description:
            context = f"{context}\n\n{result.visual_description}"
        self.context_value.configure(text=context)

        self.set_state(RESULT)
        self.root.after_idle(self._refresh_scrollregion)
        log_event("result_displayed", certainty=result.certainty)

    def show_error(self, message: str) -> None:
        self._last_result = None
        self._show_result_state()
        self.heard_value.configure(text="No result")
        self.meaning_value.configure(text=message)
        self.why_value.configure(text="Iris did not produce an interpretation.")
        self.context_value.configure(text="Not available")
        self.certainty_value.configure(text="Not available")
        self.alternative_value.configure(text="Try speaking again, then press Interpret.")
        self.set_state(ERROR)
        self.root.after_idle(self._refresh_scrollregion)

    def reset(self) -> None:
        self._last_result = None
        for label in (
            self.heard_value,
            self.meaning_value,
            self.why_value,
            self.context_value,
            self.certainty_value,
            self.alternative_value,
        ):
            label.configure(text="")
        self._show_empty_state()
        self.set_state(LISTENING)
        self.root.after_idle(self._refresh_scrollregion)

    def get_spoken_summary(self) -> str | None:
        if self._last_result and self._last_result.success:
            return self._last_result.spoken_summary
        return None

    def get_last_result(self) -> InterpretationResult | None:
        if self._last_result and self._last_result.success:
            return self._last_result
        return None

    def set_conversation_line(self, text: str) -> None:
        # Reuses the fixed status panel's detail line rather than adding a new
        # widget — set_state() only overwrites this on a state transition, and
        # the conversation loop keeps the state at CONVERSATION for its whole
        # duration, so this stays visible turn to turn.
        self.status_detail_label.configure(text=text)