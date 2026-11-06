def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


_WHEEL_EVENTS = ("<MouseWheel>", "<Button-4>", "<Button-5>")  # Button-4/5 are the wheel on X11 (Linux)


def bind_wheel(widget, scrollable):
    """Scroll `scrollable` vertically with the mouse wheel on every platform (bound app-wide)."""
    def on_wheel(e):
        up = e.num == 4 or (e.num != 5 and e.delta > 0)
        scrollable.yview_scroll(-1 if up else 1, "units")
    for ev in _WHEEL_EVENTS:
        widget.bind_all(ev, on_wheel)


def unbind_wheel(widget):
    for ev in _WHEEL_EVENTS:
        widget.unbind_all(ev)
