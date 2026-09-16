"""Simple desktop window: pick a .nds, get a randomized nuzlocke ROM."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from plat_rand.paths import AutoInputs, default_output_rom
from plat_rand.pipeline import RandomizeOptions, randomize_rom
from plat_rand.rom import RomError
from plat_rand.xdelta import PatchError


def run_gui(
    initial_rom: str | None = None,
    initial_output: str | None = None,
    initial_seed: int | None = None,
) -> None:
    root = tk.Tk()
    root.title("Platinum Nuzlocke Randomizer")
    root.minsize(560, 420)
    root.geometry("640x480")

    discovered = AutoInputs.discover()
    rom_var = tk.StringVar(value=initial_rom or (str(discovered.vanilla_rom) if discovered.vanilla_rom else ""))
    out_var = tk.StringVar(value=initial_output or str(default_output_rom()))
    seed_var = tk.StringVar(value="" if initial_seed is None else str(initial_seed))
    legend_var = tk.BooleanVar(value=True)
    status = tk.StringVar(
        value="Auto: Renegade Complete patch + randomize. Clean root .nds files are not overwritten."
    )

    def browse_rom() -> None:
        path = filedialog.askopenfilename(
            title="Choose Platinum / Renegade Platinum ROM",
            filetypes=[("Nintendo DS ROM", "*.nds"), ("All files", "*.*")],
        )
        if path:
            rom_var.set(path)
            if not out_var.get():
                src = Path(path)
                out_var.set(str(src.with_name(f"{src.stem}-nuzlocke.nds")))

    def browse_out() -> None:
        path = filedialog.asksaveasfilename(
            title="Save randomized ROM",
            defaultextension=".nds",
            filetypes=[("Nintendo DS ROM", "*.nds")],
        )
        if path:
            out_var.set(path)

    def go() -> None:
        rom = rom_var.get().strip()
        if not rom:
            messagebox.showerror("Missing ROM", "Choose a .nds file first.")
            return
        seed_text = seed_var.get().strip()
        seed = int(seed_text) if seed_text else None
        output = out_var.get().strip() or None
        try:
            result = randomize_rom(
                rom,
                output,
                RandomizeOptions(seed=seed, allow_legendaries=legend_var.get()),
            )
        except (RomError, FileNotFoundError, OSError, ValueError, PatchError) as exc:
            messagebox.showerror("Randomizer failed", str(exc))
            return
        log.delete("1.0", tk.END)
        log.insert(tk.END, result.public_text())
        status.set(f"Wrote {result.output_path.name}  (seed {result.seed})")
        out_var.set(str(default_output_rom()))
        seed_var.set("")
        if result.warnings:
            messagebox.showwarning("Note", "\n\n".join(result.warnings))
        else:
            messagebox.showinfo(
                "Done",
                f"Saved {result.output_path}\n\nSeed {result.seed}\n"
                f"{result.starters.describe()}",
            )

    pad = {"padx": 10, "pady": 4}
    frm = ttk.Frame(root, padding=12)
    frm.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frm, text="Input ROM").grid(row=0, column=0, sticky="w")
    ttk.Entry(frm, textvariable=rom_var).grid(row=0, column=1, sticky="ew", **pad)
    ttk.Button(frm, text="Browse…", command=browse_rom).grid(row=0, column=2, **pad)

    ttk.Label(frm, text="Output ROM").grid(row=1, column=0, sticky="w")
    ttk.Entry(frm, textvariable=out_var).grid(row=1, column=1, sticky="ew", **pad)
    ttk.Button(frm, text="Browse…", command=browse_out).grid(row=1, column=2, **pad)

    ttk.Label(frm, text="Seed (optional)").grid(row=2, column=0, sticky="w")
    ttk.Entry(frm, textvariable=seed_var, width=18).grid(row=2, column=1, sticky="w", **pad)
    ttk.Checkbutton(frm, text="Allow legendaries in wild / starters", variable=legend_var).grid(
        row=3, column=1, sticky="w", **pad
    )

    ttk.Button(frm, text="Randomize", command=go).grid(row=4, column=1, sticky="w", pady=8)
    ttk.Label(frm, textvariable=status).grid(row=5, column=0, columnspan=3, sticky="w", **pad)

    log = tk.Text(frm, height=16, wrap=tk.WORD)
    log.grid(row=6, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
    frm.columnconfigure(1, weight=1)
    frm.rowconfigure(6, weight=1)

    root.mainloop()
