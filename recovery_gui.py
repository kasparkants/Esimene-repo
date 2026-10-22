"""Windows-friendly desktop front end for recovery.py (standard-library only)."""
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class RecoveryApp:
    def __init__(self, root):
        self.root, self.process = root, None
        self.events = queue.Queue()
        root.title("Drive Recovery — read-only scanner")
        root.geometry("880x590")
        self.source = tk.StringVar()
        self.destination = tk.StringVar()
        frame = ttk.Frame(root, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Drive Recovery", font=("Segoe UI", 20)).pack(anchor="w")
        ttk.Label(frame, text="Scan a disk image first. Recover copies to a different healthy drive.").pack(anchor="w", pady=(0, 12))
        for label, variable, callback in [
            ("Source image or device path", self.source, self.choose_source),
            ("Recovery folder (must not exist yet)", self.destination, self.choose_destination),
        ]:
            ttk.Label(frame, text=label).pack(anchor="w")
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=(2, 10))
            ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
            ttk.Button(row, text="Browse…", command=callback).pack(side="right", padx=(8, 0))
        ttk.Label(frame, text="Formats: JPEG, PNG, PDF, ZIP / Office containers. Contiguous files only.").pack(anchor="w")
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=12)
        self.scan = ttk.Button(row, text="Scan only", command=lambda: self.start(False))
        self.scan.pack(side="left")
        self.recover = ttk.Button(row, text="Scan and recover copies", command=lambda: self.start(True))
        self.recover.pack(side="left", padx=8)
        self.cancel = ttk.Button(row, text="Stop", command=self.stop, state="disabled")
        self.cancel.pack(side="left")
        self.status = tk.StringVar(value="Ready. Nothing is written to the source.")
        ttk.Label(frame, textvariable=self.status).pack(anchor="w")
        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.pack(fill="x", pady=6)
        output_frame = ttk.Frame(frame)
        output_frame.pack(fill="both", expand=True)
        self.output = tk.Text(output_frame, wrap="word", state="disabled", font=("Consolas", 10))
        scroll = ttk.Scrollbar(output_frame, command=self.output.yview)
        self.output.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.output.pack(fill="both", expand=True)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(100, self.poll)

    def choose_source(self):
        path = filedialog.askopenfilename(title="Select a disk image", filetypes=[("Disk images", "*.img *.dd *.raw *.bin"), ("All files", "*.*")])
        if path:
            self.source.set(path)

    def choose_destination(self):
        parent = filedialog.askdirectory(title="Choose a folder on a DIFFERENT healthy drive")
        if parent:
            self.destination.set(str(Path(parent) / "RecoveredFiles"))

    def append(self, text):
        self.output.configure(state="normal")
        self.output.insert("end", text + "\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def start(self, recover):
        source = self.source.get().strip()
        destination = self.destination.get().strip()
        if not source or (recover and not destination):
            messagebox.showerror("Missing path", "Choose a source and, for recovery, a new destination folder.")
            return
        command = [sys.executable, str(Path(__file__).with_name("recovery.py")), source]
        if recover:
            command += ["--recover", destination]
        try:
            self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                            text=True, encoding="utf-8", errors="replace",
                                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as error:
            messagebox.showerror("Cannot start", str(error))
            return
        self.scan.configure(state="disabled")
        self.recover.configure(state="disabled")
        self.cancel.configure(state="normal")
        self.status.set("Scanning… large drives can take hours. Stop is available.")
        self.progress.start()
        self.append("Started: " + source)
        threading.Thread(target=self.read_output, args=(self.process,), daemon=True).start()

    def read_output(self, process):
        for line in process.stdout:
            self.events.put(("line", line.rstrip()))
        process.stdout.close()
        self.events.put(("done", process.wait()))

    def poll(self):
        for _ in range(100):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "done":
                self.progress.stop()
                self.scan.configure(state="normal")
                self.recover.configure(state="normal")
                self.cancel.configure(state="disabled")
                self.status.set("Finished. Review candidates below." if value == 0 else f"Stopped or failed (exit {value}). See details below.")
                self.process = None
            else:
                try:
                    item = json.loads(value)
                    if item.get("summary"):
                        self.append(f"Found {item['candidates']} candidates. Limit reached: {item['candidate_limit_reached']}.")
                        self.append(item["note"])
                    else:
                        self.append(f"{item['format'].upper()} at byte {item['offset']}: {item['status']}, size {item['bytes']}" + (f" → {item['saved_to']}" if 'saved_to' in item else ""))
                except (ValueError, KeyError, TypeError):
                    self.append(value)
        self.root.after(100, self.poll)

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()

    def close(self):
        self.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    RecoveryApp(root)
    root.mainloop()
