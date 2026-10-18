# Konverter für Windows

Diffusion-Modelle auf einem **Windows-x64-PC lokal in Apple-Core-AI-`.caipack`-Pakete** umwandeln. Mit deutscher Desktop-Oberfläche und Kommandozeile. Das Ergebnis ist für die Apple-Zielgeräte des [AcmeUp-Converters](https://github.com/acmeup/coreai-diffusion-converter) bestimmt.

Die Windows-App führt den festgelegten Original-Converter in einer **lokalen WSL2-Umgebung** aus. Apples Compiler wird als Linux-x86-64-Wheel installiert. Ein Mac oder ein externer Konvertierungsdienst ist nicht erforderlich. Ein nativer Win32-Compiler ist in diesem Stand nicht enthalten.

## Windows starten

1. Unter [Actions → Test and Windows build](https://github.com/pawel27111/konverter/actions/workflows/build.yml) einen erfolgreichen Lauf öffnen und das Artefakt **Konverter-Windows-x64** herunterladen.
2. Die äußere Artefakt-ZIP und anschließend `Konverter-Windows-x64.zip` vollständig entpacken.
3. `Konverter.exe` öffnen und **Einrichten** anklicken. Die Einrichtung installiert WSL2/Ubuntu und Linux-Voraussetzungen, Python 3.11 und den festgelegten Compiler. Windows kann dafür eine Administratorbestätigung und einen Neustart verlangen. Nach einem Neustart erneut **Einrichten** anklicken.
4. Modellquelle und Ausgabeordner wählen, Zielgerät einstellen und **Konvertieren** anklicken. Ein fertiges Paket wird vor der Erfolgsmeldung validiert.

Alternativ führt `setup/Setup-Windows.ps1` dieselbe Einrichtung aus. Mit einer bereits vorhandenen WSL2-Verteilung deren Namen unter **Lizenz & Zugang** eintragen. Die automatische Linux-Paketinstallation unterstützt Ubuntu/Debian; als Standard wird `Ubuntu-24.04` verwendet.

**Voraussetzungen:** Windows 11 x64 oder Windows 10 mit aktuellem WSL2, aktivierte Hardwarevirtualisierung, Internet für die erste Einrichtung und Modell-Downloads. Mindestens 14 GiB freier Platz für die Engine, zusätzlich Platz für Originalmodell, Arbeitsdateien und Export. Für große Modelle sind 32 GB RAM oder mehr sinnvoll; diese Angabe ist keine Zusage, dass jedes große Modell in 32 GB passt. Windows ARM und WSL1 werden nicht unterstützt. Der erste Download umfasst mehrere GB. Die CPU genügt für den Export; eine NVIDIA-GPU wird nicht vorausgesetzt.

## Funktionen

- Quellen: Hugging-Face-IDs, lokale Diffusers-Ordner, `.safetensors`-Checkpoints und Civitai-Referenzen/URLs.
- Bis zu acht LoRAs mit individuellen Gewichten; alternative VAE; Basismodell für Einzeldateien.
- Ziel `ios` oder `macos`, Auflösung, FP16/4-Bit, Schritte, Guidance, Clip Skip und Prediction Type entsprechend den Regeln des Original-Converters.
- Lizenzdateien, Lizenznamen, private Hugging-Face-Modelle und Civitai-Token.
- Dry Run, Download-Cache, Arbeitsordner, detailliertes Protokoll und kontrollierter Abbruch der Linux-Export-Prozessgruppe.
- `validate` prüft das Paket einschließlich Struktur, Manifest und Dateihashes; `inspect` zeigt die Metadaten.
- Windows-Pfade und lokale LoRAs werden als einzelne Prozessargumente mit `wslpath` übersetzt; kein Zusammenbauen von Shell-Kommandos aus Modelleingaben.
- Tokens aus der Oberfläche werden nicht gespeichert. Sie gelangen per stdin an den Worker und als Umgebungsvariable an den Converter. Bekannte Tokenwerte werden im angezeigten Protokoll ausgeblendet. Beim Teilen eines Protokolls bleiben Modellnamen und lokale Dateipfade sichtbar.

Der festgelegte Upstream kennt folgende Familien. Unterstützung wird vom Original-Code übernommen; nicht jede Kombination wurde auf Windows mit einem vollständigen Produktionsmodell geprüft.

| Familie | Größen | Ziele / Grenzen |
| --- | --- | --- |
| Stable Diffusion 1.x | 512 | iOS, macOS |
| Stable Diffusion 2.x | 512, 768 | iOS, macOS |
| SDXL | 1024 | ausschließlich macOS-Zielpaket |
| Stable Diffusion 3.x | 512, 1024 | Architekturgrenzen des Upstreams, z. B. maximal 24 Transformer-Layer |
| FLUX.2 Klein 4B | 512, 1024 | ausschließlich die vom Upstream geprüfte 4B-Geometrie |

SDXL-Refiner, Inpainting, FLUX.1, Klein 9B, destillierte Varianten und nicht unterstützte Adapterformate bleiben entsprechend dem Vorbild ausgeschlossen. Modelllizenzen und die Zugriffsbedingungen von Hugging Face/Civitai gelten weiterhin.

## Kommandozeile

Die ZIP enthält `konverter-cli.exe`; Python muss unter Windows dafür nicht separat installiert werden. Globale Optionen stehen **vor** dem Unterbefehl:

```powershell
.\konverter-cli.exe --distro Ubuntu-24.04 setup
.\konverter-cli.exe --distro Ubuntu-24.04 doctor
.\konverter-cli.exe --distro Ubuntu-24.04 convert "C:\Modelle\modell.safetensors" --base "org/basismodell" --target ios --output-dir "C:\Exports" --license-file "C:\Modelle\LICENSE.txt"
.\konverter-cli.exe --distro Ubuntu-24.04 convert "org/modell" --target macos --lora "C:\LoRAs\stil.safetensors:0.8" --vae "org/vae" --output-dir "C:\Exports"
.\konverter-cli.exe validate "C:\Exports\Modell.ios.caipack"
.\konverter-cli.exe inspect "C:\Exports\Modell.ios.caipack"
.\konverter-cli.exe convert --help
```

Für private Quellen `HF_TOKEN` bzw. `CIVITAI_API_TOKEN` in der Windows-Sitzung setzen oder die verdeckten Felder der Oberfläche verwenden. `--civitai-token` bleibt aus Kompatibilitätsgründen verfügbar; Umgebungsvariablen vermeiden einen Token in der Windows-Kommandozeile. `--allow-missing-license` und `--allow-unverified-download` sind ausdrückliche Opt-ins.

Unter Linux x86-64 funktioniert dieselbe Kommandozeile mit `python -m konverter`; dafür werden Python 3.11+, git und glibc ≥ 2.34 vorausgesetzt. Der native Windows-Teil hat keine ML-Abhängigkeiten. Die Engine liegt im Linux-Benutzerprofil unter `~/.local/share/konverter/engine-873560b6f9c9`, Arbeitsdaten standardmäßig unter `~/.local/share/konverter/work`.

## Entwicklung und Prüfung

```powershell
python -m pip install .
python -m unittest discover -s tests -v
python -m konverter gui
# Windows-EXE bauen:
python -m pip install pyinstaller==6.22.3
python scripts/build_windows.py
```

Die Engine ist auf AcmeUp-Commit [`873560b6f9c9865d0aee0cc7ddc0b034045cd051`](https://github.com/acmeup/coreai-diffusion-converter/tree/873560b6f9c9865d0aee0cc7ddc0b034045cd051) festgelegt. Dessen `uv.lock` wird unverändert mit `--frozen` installiert. Das heruntergeladene uv-Werkzeug wird vor Ausführung anhand SHA-256 geprüft. Ein vorhandener Engine-Checkout mit anderem Commit oder Änderungen wird zurückgewiesen. `--engine-dir` erlaubt Entwicklern einen bereits installierten Checkout desselben Standes.

Die CI prüft die Oberfläche und den Windows-Build sowie einen **echten CPU-Export mit zufälligen kleinen SD1-Testgewichten**: Textencoder, UNet und VAE werden in `.aimodel` exportiert, als `.caipack` verpackt und anschließend separat validiert. Dieses synthetische Modell belegt den Exportweg, nicht Bildqualität oder Inferenz auf einem Apple-Gerät. Ein vollständiger Windows/WSL2-Export und Apple-Inferenz sind zusätzliche Abnahmeschritte; Windows-UI-/EXE-Tests und ein Linux-Compiler-Test ersetzen sie nicht. Ausführlicher Prüfstand: [docs/VERIFICATION.md](docs/VERIFICATION.md).

## Fehler finden

- **WSL startet nicht / Neustart erforderlich:** Windows neu starten, Virtualisierung prüfen, erneut **Einrichten**. Microsoft: [WSL installieren](https://learn.microsoft.com/windows/wsl/install).
- **Falsche Verteilung:** den Namen aus `wsl --list --verbose` in der Oberfläche bzw. mit `--distro` angeben. Die Verteilung muss Version 2 verwenden.
- **Compiler fehlt:** **Einrichten** ausführen; **System prüfen** installiert absichtlich nichts.
- **Export scheitert bei großen Modellen:** freien RAM und Plattenplatz in WSL prüfen; Windows/WSL-Speichergrenzen können niedriger sein als der physische RAM. Details stehen im Protokoll.
- **Zugriff verweigert:** erforderlichen Hub-/Civitai-Token hinterlegen und den Modellzugang beim jeweiligen Anbieter freischalten.
- **Abbruch während Einrichtung:** die Einrichtung darf zu Ende laufen; danach startet kein Export. Ein laufender Export wird über seine Linux-Prozessgruppe beendet.

## Lizenz

Windows-Oberfläche und Adapter: MIT. Die separat installierte AcmeUp-Engine: Apache-2.0. Apple-Compiler und weitere Abhängigkeiten unter ihren jeweiligen Lizenzen. Siehe [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
