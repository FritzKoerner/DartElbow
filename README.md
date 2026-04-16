# Darterkennung — Ellbogenwinkel-Erkennung beim Dartwurf

Dieses Projekt analysiert Seitenansicht-Videos von Dartwürfen und erkennt automatisch den **Ellbogenwinkel im Moment des Loslassens** (Release). Die Gelenke (Schulter, Ellbogen, Handgelenk) werden dabei über farbige Klebeband-Markierungen erkannt und über alle Frames hinweg verfolgt.

## Funktionsweise

Die Pipeline arbeitet in mehreren Schritten:

1. **Marker-Erkennung**: Das Bild wird zunächst mit einem Gaußschen Weichzeichner vorverarbeitet, dann wird farbiges Klebeband im HSV-Farbraum über Schwellenwerte isoliert. Konturen werden erkannt und deren Mittelpunkte berechnet. Für rotes Klebeband wird ein doppelter HSV-Bereich unterstützt (da Rot im HSV-Farbraum um 0/180 herum liegt).
2. **Gelenk-Zuordnung**: Die drei erkannten Marker werden den Gelenken Schulter, Ellbogen und Handgelenk zugeordnet — anhand ihrer Position im Bild (Schulter ist oben, Handgelenk ist vorne).
3. **Tracking**: In jedem weiteren Frame werden die Marker über den Hungarian-Algorithmus den bereits bekannten Gelenken zugeordnet. Kurze Lücken (z.B. durch Verdeckung) werden automatisch interpoliert.
4. **Glättung**: Die Positionsdaten werden mit einem Savitzky-Golay-Filter geglättet, um Rauschen zu entfernen, ohne die Spitzenwerte der Geschwindigkeit zu verfälschen.
5. **Release-Erkennung**: Der Moment des Loslassens wird über das Geschwindigkeitsprofil des Handgelenks erkannt — der Pfeil wird losgelassen, wenn die Handgelenkgeschwindigkeit ihren Höhepunkt erreicht.
6. **Winkelberechnung**: Der Ellbogenwinkel wird für jeden Frame berechnet (Winkel zwischen Oberarm und Unterarm am Ellbogen). Am Release-Frame wird der Winkel ausgegeben.

## Voraussetzungen

- Python 3.10+
- Kamera-Seitenansicht des Werfers
- Drei farbige Klebeband-Markierungen an **Schulter**, **Ellbogen** und **Handgelenk**
- Das Klebeband sollte eine auffällige Farbe haben (z.B. Neongrün, Rot), die sich gut vom Hintergrund abhebt

## Installation

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

### 1. Video vorbereiten

Lege dein Video in einen Ordner (z.B. `videos/`) und passe den Pfad in `config.yaml` an:

```yaml
video_path: "videos/mein_wurf.mp4"
```

**Wichtig:** Das Video sollte eine konstante Framerate haben. Falls nicht, vorher mit ffmpeg konvertieren:

```bash
ffmpeg -i input.mp4 -r 30 output.mp4
```

### 2. Farbkalibrierung

Bevor die Pipeline laufen kann, müssen die HSV-Farbwerte für das Klebeband eingestellt werden. Dafür gibt es ein interaktives Werkzeug:

```bash
python calibrate.py videos/mein_wurf.mp4 --frame 50
```

Es öffnet sich ein Fenster mit Schiebereglern für die HSV-Werte. Stelle die Regler so ein, dass **genau 3 Marker** im Maskenbild sichtbar sind (weiße Flecken auf schwarzem Hintergrund). Die Anzeige „Markers found: 3" sollte grün sein.

- Drücke **`s`**, um die Werte auszugeben — kopiere sie in `config.yaml`
- Drücke **`q`**, um zu beenden

**Tipp:** Probiere verschiedene Frames aus (`--frame 0`, `--frame 100`, etc.), um sicherzustellen, dass die Werte über das ganze Video funktionieren.

### 3. Pipeline ausführen

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

### 4. Ergebnis ansehen

Das annotierte Video wird unter `output/annotated.mp4` gespeichert. Darin sind eingezeichnet:

- **Farbige Kreise** an den Gelenkpositionen (Rot = Schulter, Grün = Ellbogen, Blau = Handgelenk)
- **Weiße Linien** zwischen Schulter–Ellbogen und Ellbogen–Handgelenk (Arm-Skelett)
- **Gelber Winkelbogen** am Ellbogen mit Gradanzeige
- **Orangefarbener Rahmen** und „RELEASE"-Beschriftung im Release-Frame

## Konfiguration (`config.yaml`)

Alle Parameter lassen sich in der `config.yaml` anpassen, ohne Python-Code ändern zu müssen:

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

```
python main.py [--video PFAD] [--config PFAD] [--no-preview]
```

| Option | Beschreibung |
|---|---|
| `--video PFAD` | Videopfad (überschreibt Wert aus config.yaml) |
| `--config PFAD` | Pfad zur Konfigurationsdatei (Standard: `config.yaml`) |
| `--no-preview` | Kein Vorschaufenster anzeigen |

## Projektstruktur

```
Darterkennung/
├── config.yaml          — Alle einstellbaren Parameter
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

### „Could not detect 3 markers in any frame"
Die HSV-Farbwerte passen nicht. Starte `python calibrate.py <video>` und stelle die Werte neu ein.

### Marker werden verwechselt (Schulter/Ellbogen/Handgelenk vertauscht)
- Prüfe, ob `thrower_faces_right` korrekt gesetzt ist
- Wenn der Werfer nach links schaut, setze den Wert auf `false`

### Release wird nicht erkannt
- Senke `velocity_peak_prominence` in der config (z.B. auf `20.0`)
- Prüfe, ob das Handgelenk in den relevanten Frames erkannt wird (im annotierten Video sichtbar)

### Tracking springt / Marker gehen verloren
- Erhöhe `max_jump`, falls sich die Marker schnell bewegen
- Passe `min_marker_area` / `max_marker_area` an, falls Marker zu klein oder zu groß sind
- Nutze `roi`, um den Bildausschnitt einzuschränken und Störquellen auszuschließen

### Rotes Klebeband wird nicht erkannt
Rot liegt im HSV-Farbraum an beiden Enden der Hue-Achse (um 0 und 180). Ein einzelner HSV-Bereich reicht nicht aus. Aktiviere den zweiten Bereich in `config.yaml`:

```yaml
hsv_lower: [170, 100, 100]
hsv_upper: [180, 255, 255]
hsv_lower2: [0, 100, 100]
hsv_upper2: [10, 255, 255]
```

### Schlechte Erkennung bei wechselndem Licht
- Verwende ein Video mit manueller Belichtung (kein Auto-Exposure)
- Alternativ: HSV-Werte etwas großzügiger einstellen (größerer Bereich)
