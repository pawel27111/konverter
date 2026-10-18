"""Native desktop UI; workers communicate with Tk only through a queue."""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from . import __version__
from .backend import BackendError, Controller, process_options, redact
from .options import FLAGS, check_options, parser


class App:
    def __init__(self, root):
        self.root, self.events, self.controller = root, queue.Queue(), None
        self.busy = False
        self.values = {}
        root.title(f"Konverter {__version__} · Windows → Core AI")
        root.geometry("980x800")
        root.minsize(780, 660)
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"))
        outer = ttk.Frame(root, padding=20)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Konverter", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Diffusion-Modelle lokal in Apple .caipack umwandeln · Windows mit WSL2").pack(anchor="w", pady=(0, 14))
        tabs = ttk.Notebook(outer, height=300)
        tabs.pack(fill="x")
        pages = []
        for label in ("Modell & Export", "Erweiterte Optionen", "Lizenz & Zugang"):
            page = ttk.Frame(tabs)
            tabs.add(page, text=label)
            canvas = tk.Canvas(page, highlightthickness=0, height=300)
            scrollbar = ttk.Scrollbar(page, orient="vertical", command=canvas.yview)
            scrollbar.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)
            canvas.configure(yscrollcommand=scrollbar.set)
            form = ttk.Frame(canvas, padding=14)
            form.columnconfigure(1, weight=1)
            item = canvas.create_window((0, 0), window=form, anchor="nw")
            form.bind("<Configure>", lambda event, c=canvas: c.configure(scrollregion=c.bbox("all")))
            canvas.bind("<Configure>", lambda event, c=canvas, i=item: c.itemconfigure(i, width=event.width))
            pages.append(form)
        model, extra, access = pages
        self.field(model, 0, "source", "Modellquelle", browse="source")
        self.field(model, 1, "output_dir", "Ausgabeordner", str(Path.home() / "Documents" / "Konverter"), browse="dir")
        self.field(model, 2, "name", "Paketname (optional)")
        self.field(model, 3, "target", "Zielgerät", "ios", choices=("ios", "macos"))
        self.field(model, 4, "size", "Bildgröße", "", choices=("", "512", "768", "1024"))
        self.field(model, 5, "precision", "Präzision", "", choices=("", "fp16", "4bit"))
        ttk.Label(model, text="Quelle: Hugging-Face-ID, Civitai-URL, .safetensors oder Diffusers-Ordner.\nLeere Größe/Präzision: automatische Vorgaben des Converters.").grid(row=6, column=0, columnspan=3, sticky="w", pady=8)
        self.field(extra, 0, "base", "Basismodell", browse="source")
        self.field(extra, 1, "vae", "VAE", browse="source")
        self.field(extra, 2, "steps", "Schritte (1–100)")
        self.field(extra, 3, "guidance", "Guidance (0–30)")
        self.field(extra, 4, "clip_skip", "Clip Skip", "1", choices=("1", "2", "3", "4"))
        self.field(extra, 5, "prediction_type", "Prediction Type", "", choices=("", "epsilon", "v_prediction"))
        self.field(extra, 6, "revision", "Hugging-Face-Revision")
        self.field(extra, 7, "cache_dir", "Download-Cache", browse="dir")
        self.field(extra, 8, "work_dir", "Arbeitsordner (optional)", browse="dir")
        ttk.Label(extra, text="LoRAs (max. 8, eine Quelle pro Zeile; Gewicht optional :0.8)").grid(row=9, column=0, columnspan=3, sticky="w", pady=(8, 2))
        self.loras = tk.Text(extra, height=3, wrap="none", font=("Consolas", 10))
        self.loras.grid(row=10, column=0, columnspan=3, sticky="ew")
        self.field(access, 0, "license_file", "Lizenzdatei", browse="file")
        self.field(access, 1, "license_name", "Lizenzname")
        self.field(access, 2, "hf_token", "Hugging-Face-Token", secret=True)
        self.field(access, 3, "civitai_token", "Civitai-Token", secret=True)
        self.field(access, 4, "distro", "WSL-Verteilung (optional)", "Ubuntu-24.04" if os.name == "nt" else "")
        self.field(access, 5, "engine_dir", "Engine-Ordner (Entwicklung)", browse="dir")
        labels = {"allow_missing_license": "Export auch ohne Lizenzdatei erlauben",
                  "allow_unverified_download": "Civitai-Download ohne Hash erlauben",
                  "overwrite": "Vorhandenes Ausgabepaket überschreiben", "keep_work": "Arbeitsdateien behalten",
                  "verbose": "Ausführliches Protokoll", "dry_run": "Nur Eingaben prüfen (Dry Run)"}
        for row, flag in enumerate(FLAGS, 6):
            self.values[flag] = tk.BooleanVar(value=False)
            ttk.Checkbutton(access, text=labels[flag], variable=self.values[flag]).grid(row=row, column=0, columnspan=3, sticky="w")
        ttk.Label(access, text="Tokens gelten nur für diese Sitzung und werden nicht gespeichert.").grid(row=12, column=0, columnspan=3, sticky="w", pady=8)
        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=12)
        self.buttons = []
        for label, action in (("Konvertieren", "convert"), ("Einrichten", "setup"), ("System prüfen", "doctor"),
                              ("Paket validieren", "validate"), ("Paket ansehen", "inspect")):
            button = ttk.Button(actions, text=label, command=lambda a=action: self.start(a))
            button.pack(side="left", padx=(0, 6))
            self.buttons.append(button)
        self.cancel_button = ttk.Button(actions, text="Abbrechen", command=self.cancel, state="disabled")
        self.cancel_button.pack(side="right")
        self.status = tk.StringVar(value="Bereit. Beim ersten Export wird die lokale Engine eingerichtet.")
        ttk.Label(outer, textvariable=self.status).pack(anchor="w")
        self.progress = ttk.Progressbar(outer, mode="indeterminate")
        self.progress.pack(fill="x", pady=(5, 8))
        self.log = scrolledtext.ScrolledText(outer, height=12, state="disabled", wrap="word", font=("Consolas", 9))
        ttk.Button(outer, text="Protokoll speichern …", command=self.save_log).pack(side="bottom", anchor="e", pady=(6, 0))
        self.log.pack(fill="both", expand=True)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(100, self.poll)

    def field(self, parent, row, key, label, default="", *, choices=None, browse=None, secret=False):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
        variable = self.values[key] = tk.StringVar(value=default)
        if choices:
            entry = ttk.Combobox(parent, textvariable=variable, values=choices, state="readonly")
        else:
            entry = ttk.Entry(parent, textvariable=variable, show="•" if secret else "")
        entry.grid(row=row, column=1, sticky="ew", pady=4)
        if browse:
            box = ttk.Frame(parent)
            box.grid(row=row, column=2, padx=(6, 0))
            if browse != "dir":
                ttk.Button(box, text="Datei …", command=lambda: self.browse(key, False)).pack(side="left")
            if browse in ("dir", "source"):
                ttk.Button(box, text="Ordner …", command=lambda: self.browse(key, True)).pack(side="left")

    def browse(self, key, directory):
        value = filedialog.askdirectory() if directory else filedialog.askopenfilename()
        if value:
            self.values[key].set(value)

    def arguments(self, action, pack=None):
        p = parser()
        if action == "convert":
            args = p.parse_args(["convert", self.values["source"].get().strip(), "--target", self.values["target"].get()])
            for key, var in self.values.items():
                if hasattr(args, key) and key not in ("backend",):
                    value = var.get()
                    if isinstance(value, str):
                        value = value.strip() or ("" if key == "source" else None)
                    setattr(args, key, value)
            args.output_dir = args.output_dir or "outputs"
            for key, cast in (("size", int), ("steps", int), ("clip_skip", int), ("guidance", float)):
                if getattr(args, key) is not None:
                    setattr(args, key, cast(getattr(args, key)))
            args.lora = [s.strip() for s in self.loras.get("1.0", "end").splitlines() if s.strip()]
            check_options(args)
            return args
        return p.parse_args([action, *([pack] if pack else [])])

    def start(self, action):
        if self.busy:
            return
        pack = None
        if action in ("validate", "inspect"):
            pack = filedialog.askopenfilename(filetypes=[("Core AI Paket", "*.caipack"), ("Alle Dateien", "*.*")])
            if not pack:
                return
        try:
            args = self.arguments(action, pack)
            secrets = {key: self.values[field].get().strip() or os.environ.get(key, "")
                       for key, field in (("HF_TOKEN", "hf_token"), ("CIVITAI_API_TOKEN", "civitai_token"))}
            self.controller = Controller(distro=self.values["distro"].get().strip() or None,
                                         engine_dir=self.values["engine_dir"].get().strip() or None,
                                         emit=lambda line: self.events.put(("log", line)), secrets=secrets)
        except (ValueError, BackendError) as error:
            messagebox.showerror("Eingabe prüfen", str(error))
            return
        self.busy = True
        for button in self.buttons:
            button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.status.set("Auftrag läuft … Details im Protokoll.")
        self.progress.start(12)
        threading.Thread(target=self.worker, args=(action, args), daemon=True).start()

    def worker(self, action, args):
        code = 1
        try:
            if action == "setup":
                if os.name == "nt":
                    script = Path(__file__).with_name("Setup-Windows.ps1")
                    command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-PrerequisitesOnly"]
                    if self.controller.distro:
                        command += ["-Distro", self.controller.distro]
                    result = subprocess.run(command, capture_output=True, text=True, errors="replace", **process_options())
                    self.events.put(("log", result.stdout + result.stderr))
                    if result.returncode:
                        raise BackendError("Windows-Einrichtung unvollständig; siehe Protokoll (ggf. Neustart erforderlich).")
                    # The installer uses this distribution when none was specified.
                    self.controller.distro = self.controller.distro or "Ubuntu-24.04"
                self.controller.prepare()
                code = 0
            elif action == "doctor":
                self.controller.prepare(install=False)
                code = 0
            else:
                code = self.controller.execute(args)
        except Exception as error:
            self.events.put(("log", redact(str(error), self.controller.secrets)))
        self.events.put(("done", code))

    def cancel(self):
        if self.controller and self.busy:
            self.cancel_button.configure(state="disabled")
            def request():
                try:
                    self.controller.cancel()
                except Exception as error:
                    self.events.put(("log", str(error)))
            threading.Thread(target=request, daemon=True).start()

    def poll(self):
        for _ in range(400):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "done":
                self.busy = False
                self.progress.stop()
                self.status.set("Fertig." if value == 0 else "Abgebrochen." if value == 130 else f"Fehlgeschlagen (Exit {value}) – siehe Protokoll.")
                self.cancel_button.configure(state="disabled")
                for button in self.buttons:
                    button.configure(state="normal")
            else:
                self.log.configure(state="normal")
                self.log.insert("end", str(value) + "\n")
                if int(self.log.index("end-1c").split(".")[0]) > 20000:
                    self.log.delete("1.0", "2000.0")
                self.log.see("end")
                self.log.configure(state="disabled")
        self.root.after(100, self.poll)

    def save_log(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="konverter-protokoll.txt")
        if path:
            Path(path).write_text(self.log.get("1.0", "end"), encoding="utf-8")

    def close(self):
        if self.busy:
            messagebox.showinfo("Auftrag läuft", "Bitte zuerst abbrechen und warten, bis der laufende Auftrag beendet ist.")
            return
        self.root.destroy()


def main():
    root = tk.Tk()
    app = App(root)
    if "--smoke-test" in sys.argv:
        for geometry in ("980x800", "780x660"):
            root.geometry(geometry)
            root.update()
            assert app.log.winfo_height() >= 80, "Log area is unusable at the supported window size"
            assert app.cancel_button.winfo_ismapped(), "Action buttons are hidden"
        app.values["source"].set("org/model")
        app.values["steps"].set("25")
        app.values["guidance"].set("7.5")
        app.loras.insert("1.0", "org/lora:0.8")
        args = app.arguments("convert")
        assert args.source == "org/model" and args.steps == 25 and args.lora == ["org/lora:0.8"]
        root.destroy()
        return 0
    root.mainloop()
    return 0


if __name__ == "__main__":
    main()
