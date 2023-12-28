# Unsichtbare Fußspuren

## Projektaufbau


### Verarbeitung

In `verarbeitung` befindet sich ein Python-Skript `main.py`, welches Daten über die Kommandozeile:

```bash
python3 main.py <sniffer_typ> <pfad_zu_den_daten>
```

sniffer_typ ist dabei entweder `wlan` oder `bluetooth`. Die Daten müssen als `.pcapng` bzw. `btsnoop` vorliegen.

Als Ausgabe wird eine `.json`-Datei erzeugt `ausgabe.json`

### Visualisierung / Web-App

In `web` befindet sich eine mit `Vite` erstellte Web-App, welche die Daten aus `ausgabe.json` visualisiert.
Hierzu mit `yarn install` die Abhängigkeiten installieren und mit `yarn dev` die Web-App starten.
