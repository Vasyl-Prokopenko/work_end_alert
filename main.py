import argparse
import os
import socket
import tempfile
import time
import tkinter as tk
from datetime import datetime

from aw_client import ActivityWatchClient
from screeninfo import get_monitors


def get_active_time_today():
    try:
        client_name = "work-end-alert"
        aw = ActivityWatchClient(client_name, testing=False)

        # Calculate time range for today (local time)
        now = datetime.now().astimezone()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # 1. Find the AFK bucket
        # The bucket name is usually formatted as "aw-watcher-afk_{hostname}"
        hostname = socket.gethostname()
        bucket_id = f"aw-watcher-afk_{hostname}"

        # Verify bucket exists, fallback to searching if strict match fails
        all_buckets = aw.get_buckets()
        if bucket_id not in all_buckets:
            # Try to find any bucket with 'aw-watcher-afk' in the name
            afk_buckets = [b for b in all_buckets if "aw-watcher-afk" in b]
            if not afk_buckets:
                print("Error: Could not find 'aw-watcher-afk' bucket.")
                return 0
            bucket_id = afk_buckets[0]

        # 2. Get events form today
        events = aw.get_events(bucket_id, start=today_start, end=now)

        # 3. Calculate "not-afk" duration
        active_seconds = 0
        for event in events:
            if event.data.get("status") == "not-afk":
                # Event duration is in seconds (float or int)
                active_seconds += event.duration.total_seconds()

        return active_seconds
    except Exception as e:
        print(f"Error querying ActivityWatch: {e}")
        return 0


def format_duration(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{int(h)}h {int(m)}m"


def get_snooze_file_path():
    return os.path.join(tempfile.gettempdir(), "work_end_alert_snooze.txt")


def get_remaining_snooze_time():
    snooze_file = get_snooze_file_path()
    if not os.path.exists(snooze_file):
        return 0

    try:
        with open(snooze_file, "r") as f:
            timestamp = float(f.read().strip())

        remaining = timestamp - time.time()
        return max(0, remaining)
    except (ValueError, OSError):
        return 0


def set_snooze(minutes):
    snooze_file = get_snooze_file_path()
    snooze_until = time.time() + (minutes * 60)
    try:
        with open(snooze_file, "w") as f:
            f.write(str(snooze_until))
    except OSError as e:
        print(f"Error setting snooze: {e}")


def setup_window_content(window, title, message, close_cmd, snooze_cmd, snooze_options):
    # Remove window decorations (title bar)
    window.overrideredirect(True)
    window.attributes("-topmost", True)

    # Modern Dark Theme Colors
    COLOR_BG = "#1a1a1a"      # Dark Gray/Black
    COLOR_ACCENT = "#ff1744"  # Vivid Red
    COLOR_TEXT = "#ffffff"
    COLOR_SUBTEXT = "#aaaaaa"
    COLOR_BTN_BG = "#2d2d2d"

    window.configure(bg=COLOR_BG)

    # Main Container with bright border
    frame = tk.Frame(
        window,
        bg=COLOR_BG,
        padx=60,
        pady=50,
        highlightbackground=COLOR_ACCENT,
        highlightthickness=4,
    )
    frame.pack(fill="both", expand=True)

    # Icon/Header (Text-based emoji)
    lbl_icon = tk.Label(
        frame,
        text="🛑",
        font=("Segoe UI Emoji", 64),
        bg=COLOR_BG,
        fg=COLOR_ACCENT,
    )
    lbl_icon.pack(pady=(0, 20))

    # Title
    lbl_title = tk.Label(
        frame,
        text=title.upper(),
        font=("Segoe UI", 36, "bold"),
        fg=COLOR_TEXT,
        bg=COLOR_BG,
    )
    lbl_title.pack(pady=(0, 10))

    # Message
    lbl_msg = tk.Label(
        frame,
        text=message,
        font=("Segoe UI", 16),
        fg=COLOR_SUBTEXT,
        bg=COLOR_BG
    )
    lbl_msg.pack(pady=(0, 40))

    # Primary Action Button (STOP)
    def on_enter_stop(e):
        btn_stop.config(bg="#d50000")  # Darker red on hover

    def on_leave_stop(e):
        btn_stop.config(bg=COLOR_ACCENT)

    btn_stop = tk.Button(
        frame,
        text="I AM STOPPING NOW",
        command=close_cmd,
        font=("Segoe UI", 14, "bold"),
        bg=COLOR_ACCENT,
        fg="white",
        relief="flat",
        cursor="hand2",
        padx=40,
        pady=15,
        activebackground="#b71c1c",
        activeforeground="white",
    )
    btn_stop.bind("<Enter>", on_enter_stop)
    btn_stop.bind("<Leave>", on_leave_stop)
    btn_stop.pack(pady=(0, 40))

    # Snooze Label
    tk.Label(
        frame,
        text="SNOOZE (Extend Session)",
        bg=COLOR_BG,
        fg="#666666",
        font=("Segoe UI", 9, "bold"),
    ).pack(pady=(0, 10))

    # Snooze Buttons Container
    btn_container = tk.Frame(frame, bg=COLOR_BG)
    btn_container.pack()

    for mins in snooze_options:
        def create_snooze_btn(m=mins):
            btn = tk.Button(
                btn_container,
                text=f"+{m}m",
                command=lambda: snooze_cmd(m),
                font=("Segoe UI", 11),
                bg=COLOR_BTN_BG,
                fg=COLOR_TEXT,
                relief="flat",
                cursor="hand2",
                width=8,
                pady=5,
                activebackground="#3e3e3e",
                activeforeground=COLOR_TEXT,
            )
            # Hover effects
            btn.bind("<Enter>", lambda e: btn.config(bg="#3e3e3e"))
            btn.bind("<Leave>", lambda e: btn.config(bg=COLOR_BTN_BG))
            btn.pack(side="left", padx=8)

        create_snooze_btn()


def show_centered_alert(title, message, snooze_options):
    """Displays a centered, always-on-top alert window on all detected screens."""

    # Common command to close all windows
    # We will initialize root later
    root_ref = {}  # Use dict to hold root reference for callbacks

    def close_all():
        if "root" in root_ref:
            root_ref["root"].destroy()

    def snooze_all(minutes):
        set_snooze(minutes)
        close_all()

    try:
        monitors = get_monitors()
    except Exception:
        monitors = []

    # If no monitors detected (or error), create one dummy object for primary
    # But for geometry we need to be careful. If get_monitors fails, we can't use x/y.
    # So we'll have a fallback path.

    root = tk.Tk()
    root.title(title)
    root_ref["root"] = root  # Store for callbacks

    if not monitors:
        # Fallback to single window centering logic
        setup_window_content(root, title, message, close_all, snooze_all, snooze_options)

        root.update_idletasks()
        width = root.winfo_reqwidth()
        height = root.winfo_reqheight()
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        root.geometry(f"{width}x{height}+{x}+{y}")

    else:
        # Setup first monitor on root
        m0 = monitors[0]
        setup_window_content(root, title, message, close_all, snooze_all, snooze_options)

        # Function to position window centered on monitor
        def center_on_monitor(window, monitor):
            window.update_idletasks()
            w = window.winfo_reqwidth()
            h = window.winfo_reqheight()
            x = monitor.x + (monitor.width - w) // 2
            y = monitor.y + (monitor.height - h) // 2
            window.geometry(f"{w}x{h}+{x}+{y}")

        center_on_monitor(root, m0)

        # Setup other monitors
        for m in monitors[1:]:
            win = tk.Toplevel(root)
            win.title(title)
            setup_window_content(win, title, message, close_all, snooze_all, snooze_options)
            center_on_monitor(win, m)

    root.mainloop()


def main():
    parser = argparse.ArgumentParser(
        description="Check active work time from ActivityWatch."
    )
    parser.add_argument(
        "--target",
        type=int,
        default=480,
        help="Target work time in minutes (default: 480 = 8h)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore snooze timer and force check",
    )
    parser.add_argument(
        "--snooze-options",
        type=str,
        default="15,30,60",
        help="Comma-separated list of snooze minutes (default: 15,30,60)",
    )
    args = parser.parse_args()

    try:
        snooze_opts = [int(x.strip()) for x in args.snooze_options.split(",")]
    except ValueError:
        print("Invalid format for --snooze-options. Using default.")
        snooze_opts = [15, 30, 60]

    try:
        active_seconds = get_active_time_today()
        formatted_time = format_duration(active_seconds)

        print(f"Active work time today: {formatted_time} ({active_seconds} seconds)")

        remaining_snooze = get_remaining_snooze_time()
        if not args.force and remaining_snooze > 0:
            m, s = divmod(int(remaining_snooze), 60)
            print(f"Alert is currently snoozed. Remaining time: {m}m {s}s")
            return

        if active_seconds >= args.target * 60:
            try:
                show_centered_alert(
                    "Work Day Complete",
                    f"You have worked {formatted_time} today.\nTime to rest!",
                    snooze_opts,
                )
            except Exception as e:
                print(f"Notification error: {e}")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
