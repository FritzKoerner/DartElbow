# Darterkennung — Ellbogenwinkel-Erkennung beim Dartwurf

Hallo Lina! Dieses Projekt analysiert Seitenansicht-Videos von Dartwürfen und erkennt automatisch den **Ellbogenwinkel im Moment des Loslassens** (Release). Die Gelenke (Schulter, Ellbogen, Handgelenk) werden dabei über farbige Klebeband-Markierungen erkannt und über alle Frames hinweg verfolgt.

## Funktionsweise

Lina, die Pipeline arbeitet in mehreren Schritten — hier ein kurzer Überblick, damit du weißt, was im Hintergrund passiert:

1. **Marker-Erkennung**: Das Bild wird zunächst mit einem Gaußschen Weichzeichner vorverarbeitet, dann wird farbiges Klebeband im HSV-Farbraum über Schwellenwerte isoliert. Konturen werden erkannt und deren Mittelpunkte berechnet. Für rotes Klebeband wird ein doppelter HSV-Bereich unterstützt (da Rot im HSV-Farbraum um 0/180 herum liegt).
2. **Gelenk-Zuordnung**: Die drei erkannten Marker werden den Gelenken Schulter, Ellbogen und Handgelenk zugeordnet — anhand ihrer Position im Bild (Schulter ist oben, Handgelenk ist vorne).
3. **Tracking**: In jedem weiteren Frame werden die Marker über den Hungarian-Algorithmus den bereits bekannten Gelenken zugeordnet. Kurze Lücken (z.B. durch Verdeckung) werden automatisch interpoliert.
4. **Glättung**: Die Positionsdaten werden mit einem Savitzky-Golay-Filter geglättet, um Rauschen zu entfernen, ohne die Spitzenwerte der Geschwindigkeit zu verfälschen.
5. **Release-Erkennung**: Der Moment des Loslassens wird über das Geschwindigkeitsprofil des Handgelenks erkannt — der Pfeil wird losgelassen, wenn die Handgelenkgeschwindigkeit ihren Höhepunkt erreicht.
6. **Winkelberechnung**: Der Ellbogenwinkel wird für jeden Frame berechnet (Winkel zwischen Oberarm und Unterarm am Ellbogen). Am Release-Frame wird der Winkel ausgegeben.

## Voraussetzungen

Lina, bevor du loslegen kannst, stelle sicher, dass du Folgendes hast:

- Python 3.10+
- Kamera-Seitenansicht des Werfers
- Drei farbige Klebeband-Markierungen an **Schulter**, **Ellbogen** und **Handgelenk**
- Das Klebeband sollte eine auffällige Farbe haben (z.B. Neongrün, Rot), die sich gut vom Hintergrund abhebt

## Installation

Lina, öffne ein Terminal und führe folgende Befehle aus:

```bash
cd Darterkennung
pip install -r requirements.txt
```

Die benötigten Pakete sind:
- `opencv-python` — Bildverarbeitung und Videoein-/ausgabe
- `numpy` — Numerische Berechnungen
- `scipy` — Signalverarbeitung (Glättung, Peak-Erkennung, Hungarian-Algorithmus)
- `pyyaml` — Konfigurationsdatei lesen

## Schnellstart

Lina, folge einfach diesen vier Schritten der Reihe nach:

### 1. Video vorbereiten

Lege dein Video in einen Ordner (z.B. `videos/`) und passe den Pfad in `config.yaml` an:

```yaml
video_path: "videos/mein_wurf.mp4"
```

**Wichtig, Lina:** Das Video sollte eine konstante Framerate haben. Falls nicht, vorher mit ffmpeg konvertieren:

```bash
ffmpeg -i input.mp4 -r 30 output.mp4
```

### 2. Farbkalibrierung

Lina, bevor die Pipeline laufen kann, müssen die HSV-Farbwerte für das Klebeband eingestellt werden. Dafür gibt es ein interaktives Werkzeug:

```bash
python calibrate.py videos/mein_wurf.mp4 --frame 50
```

Es öffnet sich ein Fenster mit Schiebereglern für die HSV-Werte. Stelle die Regler so ein, dass **genau 3 Marker** im Maskenbild sichtbar sind (weiße Flecken auf schwarzem Hintergrund). Die Anzeige „Markers found: 3" sollte grün sein.

- Drücke **`s`**, um die Werte in der Konsole auszugeben — kopiere sie in `config.yaml`
- Drücke **`b`**, um die Werte direkt in `batch_config.yaml` zu speichern (der Videoname wird automatisch zugeordnet)
- Drücke **`q`**, um zu beenden

**Tipp für dich, Lina:** Probiere verschiedene Frames aus (`--frame 0`, `--frame 100`, etc.), um sicherzustellen, dass die Werte über das ganze Video funktionieren.

**Tipp für den Batch-Modus, Lina:** Wenn du mehrere Videos mit unterschiedlichen Lichtverhältnissen hast, kalibriere jedes Video einzeln und drücke jeweils **`b`** — die Werte werden automatisch in `batch_config.yaml` gesammelt.

### 3. Pipeline ausführen (Einzelvideo)

Lina, jetzt kannst du die eigentliche Analyse starten:

```bash
python main.py
```

Oder mit explizitem Videopfad:

```bash
python main.py --video videos/mein_wurf.mp4
```

Die Ausgabe sieht z.B. so aus:

```
Video: videos/mein_wurf.mp4
FPS: 30.0, Frames: 450, Duration: 15.0s
Resolution: 1920x1080

Pass 1: Detecting and tracking markers...
Markers detected in 438/450 frames (97.3%)
Smoothing position tracks...

Release detected at frame 187 (t = 6.233s)
Elbow angle at release: 142.7 degrees
Elbow angle range during video: 68.3 - 158.2 degrees

Pass 2: Writing annotated video...
Annotated video saved to: output/annotated.mp4

Done.
```

### 3b. Batch-Modus (mehrere Videos auf einmal)

Lina, wenn du mehrere Würfe auf einmal analysieren willst, nutze den Batch-Modus. Lege alle Videos in einen Ordner und starte:

```bash
python main.py --batch videos/
```

Das analysiert alle Videos im Ordner und schreibt die Ergebnisse in eine CSV-Datei. Lina, den Ausgabepfad für die CSV kannst du mit `--output-csv` festlegen:

```bash
python main.py --batch videos/ --output-csv ergebnisse.csv
```

Die CSV-Datei enthält folgende Spalten:

| Spalte | Beschreibung |
|---|---|
| `video` | Dateiname des Videos |
| `release_angle` | Ellbogenwinkel beim Release (in Grad) |
| `release_frame` | Frame-Nummer des Release |
| `release_time` | Zeitpunkt des Release (in Sekunden) |
| `angle_min` | Minimaler Ellbogenwinkel im Video |
| `angle_max` | Maximaler Ellbogenwinkel im Video |
| `detection_rate` | Anteil der Frames mit erfolgreicher Marker-Erkennung (%) |
| `fps` | Framerate des Videos |
| `total_frames` | Gesamtanzahl Frames |
| `error` | Fehlermeldung (leer wenn erfolgreich) |

Lina, am Ende bekommst du außerdem eine Zusammenfassung mit Mittelwert, Standardabweichung und Spannweite der Release-Winkel über alle Videos:

```
Summary: 12/12 videos analyzed successfully
  Release angle mean: 138.4 degrees
  Release angle std:  8.2 degrees
  Release angle range: 124.1 - 152.3 degrees
```

**Hinweis, Lina:** Im Batch-Modus werden keine annotierten Videos erzeugt und kein Vorschaufenster geöffnet, damit die Verarbeitung schnell durchläuft. Unterstützte Formate: `.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`.

#### Batch-Kalibrierung (`batch_config.yaml`)

Lina, wenn deine Videos unterschiedliche Lichtverhältnisse oder Klebebandfarben haben, kannst du in `batch_config.yaml` für jedes Video eigene HSV-Werte hinterlegen. Videos, die dort nicht aufgeführt sind, verwenden die Standardwerte aus `config.yaml`.

```yaml
# batch_config.yaml
wurf_01.mp4:
  hsv_lower: [35, 100, 100]
  hsv_upper: [85, 255, 255]

wurf_02.mp4:
  hsv_lower: [170, 100, 100]
  hsv_upper: [180, 255, 255]
  hsv_lower2: [0, 100, 100]
  hsv_upper2: [10, 255, 255]

wurf_03.mp4:
  hsv_lower: [100, 150, 100]
  hsv_upper: [130, 255, 255]
  thrower_faces_right: false
```

Lina, du kannst die Werte auch direkt beim Kalibrieren speichern — drücke einfach **`b`** im Kalibrierungswerkzeug:

```bash
python calibrate.py videos/wurf_01.mp4 --frame 50
# Regler einstellen, dann 'b' drücken → Werte landen in batch_config.yaml
python calibrate.py videos/wurf_02.mp4 --frame 50
# Regler einstellen, dann 'b' drücken → wird zum selben File hinzugefügt
```

Lina, neben HSV-Werten kannst du pro Video auch `min_marker_area`, `max_marker_area`, `roi` und `thrower_faces_right` überschreiben.

Wenn bei einem Video die Marker nicht erkannt werden konnten, wird es in der CSV als Fehler markiert (Spalte `error`), und die Pipeline läuft mit dem nächsten Video weiter — kein Abbruch des gesamten Batch-Laufs.

### 4. Ergebnis ansehen

Lina, das annotierte Video wird unter `output/annotated.mp4` gespeichert. Darin sind eingezeichnet:

- **Farbige Kreise** an den Gelenkpositionen (Rot = Schulter, Grün = Ellbogen, Blau = Handgelenk)
- **Weiße Linien** zwischen Schulter–Ellbogen und Ellbogen–Handgelenk (Arm-Skelett)
- **Gelber Winkelbogen** am Ellbogen mit Gradanzeige
- **Orangefarbener Rahmen** und „RELEASE"-Beschriftung im Release-Frame

## Konfiguration (`config.yaml`)

Lina, alle Parameter lassen sich in der `config.yaml` anpassen, ohne Python-Code ändern zu müssen:

| Parameter | Beschreibung | Standardwert |
|---|---|---|
| `video_path` | Pfad zum Eingabevideo | `"videos/throw01.mp4"` |
| `hsv_lower` | Untere HSV-Grenze für Markerfarbe [H, S, V] | `[35, 100, 100]` |
| `hsv_upper` | Obere HSV-Grenze für Markerfarbe [H, S, V] | `[85, 255, 255]` |
| `hsv_lower2` | Zweiter HSV-Bereich, untere Grenze (für rotes Klebeband) | `null` |
| `hsv_upper2` | Zweiter HSV-Bereich, obere Grenze (für rotes Klebeband) | `null` |
| `min_marker_area` | Minimale Konturfläche in Pixeln (filtert Rauschen) | `50` |
| `max_marker_area` | Maximale Konturfläche in Pixeln (filtert Fehlerkennungen) | `5000` |
| `max_jump` | Maximale Pixeldistanz, die ein Marker pro Frame springen darf | `100` |
| `thrower_faces_right` | `true` wenn der Werfer nach rechts schaut, `false` wenn nach links | `true` |
| `smoothing_window` | Fenstergröße für den Savitzky-Golay-Filter (muss ungerade sein) | `7` |
| `smoothing_polyorder` | Polynomgrad für den Filter | `2` |
| `velocity_peak_prominence` | Mindest-Prominenz für die Geschwindigkeitsspitze | `50.0` |
| `frames_after_peak` | Offset vom Geschwindigkeits-Peak zum Release | `3` |
| `velocity_component` | Geschwindigkeitskomponente: `"speed"`, `"x"` oder `"y"` | `"speed"` |
| `roi` | Region of Interest `[x, y, breite, höhe]` oder `null` für ganzes Bild | `null` |
| `output_video` | Ausgabepfad für annotiertes Video | `"output/annotated.mp4"` |
| `show_preview` | Vorschaufenster während der Verarbeitung anzeigen | `true` |

## Kommandozeilen-Optionen

Lina, hier die verfügbaren Optionen beim Aufruf:

```
python main.py [--video PFAD] [--batch ORDNER] [--batch-config PFAD] [--output-csv PFAD] [--config PFAD] [--no-preview]
```

| Option | Beschreibung |
|---|---|
| `--video PFAD` | Videopfad (überschreibt Wert aus config.yaml) |
| `--batch ORDNER` | Batch-Modus: alle Videos im Ordner analysieren, Ergebnisse als CSV |
| `--batch-config PFAD` | Per-Video HSV-Kalibrierung (Standard: `batch_config.yaml`) |
| `--output-csv PFAD` | CSV-Ausgabepfad im Batch-Modus (Standard: `results.csv`) |
| `--config PFAD` | Pfad zur Konfigurationsdatei (Standard: `config.yaml`) |
| `--no-preview` | Kein Vorschaufenster anzeigen |

## Projektstruktur

Lina, hier ist ein Überblick über alle Dateien im Projekt und was sie machen:

```
Darterkennung/
├── config.yaml          — Alle einstellbaren Parameter
├── batch_config.yaml    — Per-Video HSV-Kalibrierung für Batch-Modus
├── requirements.txt     — Python-Abhängigkeiten
├── main.py              — Hauptprogramm und Pipeline-Steuerung
├── calibrate.py         — Interaktives HSV-Kalibrierungswerkzeug
├── detection.py         — Marker-Erkennung (HSV-Schwellenwert + Konturen)
├── tracking.py          — Gelenk-Zuordnung und Frame-zu-Frame-Tracking
├── angle.py             — Ellbogenwinkel-Berechnung
├── release.py           — Release-Erkennung über Geschwindigkeitsanalyse
└── visualization.py     — Annotiertes Video mit Overlay-Zeichnungen
```

## Fehlerbehebung

Lina, falls etwas nicht funktioniert, findest du hier die häufigsten Probleme und Lösungen:

### „Could not detect 3 markers in any frame"
Lina, die HSV-Farbwerte passen nicht. Starte `python calibrate.py <video>` und stelle die Werte neu ein.

### Marker werden verwechselt (Schulter/Ellbogen/Handgelenk vertauscht)
- Lina, prüfe ob `thrower_faces_right` korrekt gesetzt ist
- Wenn der Werfer nach links schaut, setze den Wert auf `false`

### Release wird nicht erkannt
- Lina, senke `velocity_peak_prominence` in der config (z.B. auf `20.0`)
- Prüfe, ob das Handgelenk in den relevanten Frames erkannt wird (im annotierten Video sichtbar)

### Tracking springt / Marker gehen verloren
- Lina, erhöhe `max_jump`, falls sich die Marker schnell bewegen
- Passe `min_marker_area` / `max_marker_area` an, falls Marker zu klein oder zu groß sind
- Nutze `roi`, um den Bildausschnitt einzuschränken und Störquellen auszuschließen

### Rotes Klebeband wird nicht erkannt
Lina, Rot liegt im HSV-Farbraum an beiden Enden der Hue-Achse (um 0 und 180). Ein einzelner HSV-Bereich reicht nicht aus. Aktiviere den zweiten Bereich in `config.yaml`:

```yaml
hsv_lower: [170, 100, 100]
hsv_upper: [180, 255, 255]
hsv_lower2: [0, 100, 100]
hsv_upper2: [10, 255, 255]
```

### Schlechte Erkennung bei wechselndem Licht
- Lina, verwende ein Video mit manueller Belichtung (kein Auto-Exposure)
- Alternativ: HSV-Werte etwas großzügiger einstellen (größerer Bereich)

## Zitierung

Lina, wenn du dieses Projekt in einer wissenschaftlichen Arbeit, einem Bericht oder einer Präsentation verwendest, zitiere es bitte wie folgt:

**APA:**

> Körner, F. (2026). *DartElbow: Automatische Ellbogenwinkel-Erkennung beim Dartwurf* [Software]. GitHub. https://github.com/FritzKoerner/DartElbow

**BibTeX:**

```bibtex
@software{koerner2026dartelbow,
  author       = {Körner, Fritz},
  title        = {DartElbow: Automatische Ellbogenwinkel-Erkennung beim Dartwurf},
  year         = {2026},
  url          = {https://github.com/FritzKoerner/DartElbow},
}
```

**IEEE:**

> F. Körner, "DartElbow: Automatische Ellbogenwinkel-Erkennung beim Dartwurf," 2026. [Online]. Available: https://github.com/FritzKoerner/DartElbow

---

Lina, bei Fragen oder Problemen melde dich einfach!
