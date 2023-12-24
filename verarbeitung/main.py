from __future__ import annotations

import json
from pathlib import Path  # Zum Lesen der Dateipfade
import sys  # Zum Lesen der Kommandozeilenargumente und Beenden des Programms
import subprocess  # Zum Ausführen von tshark
from collections import defaultdict  # Zum Speichern der Pakete
from typing import DefaultDict, NamedTuple, TypeAlias, cast
from uuid import uuid4  # Zum Generieren von zufälligen UUIDs


# easy_trilateration ist eine Bibliothek, die die Trilateration
# mit dem Least Squares Algorithmus implementiert
from easy_trilateration.model import Circle
from easy_trilateration.least_squares import easy_least_squares  # type: ignore

# scapy ist eine Bibliothek, die Netzwerkpakete lesen und schreiben kann
# hier wird sie verwendet, um pcapng-Dateien zu lesen
from scapy.layers.dot11 import Dot11, Dot11ProbeReq, RadioTap
from scapy.all import rdpcap  # type: ignore

# Die RSSI-Werte in einem Meter Abstand für Bluetooth und WLAN
BLUETOOTH_RSSI_EIN_METER = -47.69767441860465
WLAN_RSSI_EIN_METER = -34.40682414698163


# mac, epoch -> sniffer_id, rssi
PaketeNachMac: TypeAlias = DefaultDict[tuple[str, int], list[tuple[str, int]]]

# x, y
Vec2: TypeAlias = tuple[float, float]


class Sniffer(NamedTuple):
    """Information über einen Sniffer"""
    id: str
    position: Vec2 = (0, 0)


def bluetooth_sniffer_auswerten(
    dateipfad: Path,
    pakete_nach_mac: PaketeNachMac,
    sniffer_info: Sniffer,
):
    """Werte Bluetoothaufnahmen im btsnoop-Format aus

    Args:
        dateipfad (Path): Der Pfad zur btsnoop-Datei
        pakete_nach_mac (PaketeNachMac): Die Pakete werden hier gespeichert
        sniffer_info (Sniffer): Information über den Sniffer
    """
    try:
        # tshark zum Konvertieren von btsnoop-Dateien in JSON verwenden
        # da es für Python keine funktionierende Bibliothek gibt
        output = subprocess.check_output(
            [
                "tshark",
                "-q",  # Keine Ausgabe von Fehlermeldungen
                "-r",
                str(dateipfad),
                "-T",
                "json",
            ],
            # Fehler werden ins Nirvana geschickt
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as e:
        # Falls tshark einen Fehler wirft, wird dieser ignoriert
        output = e.output

    roh_json = json.loads(output)

    anzahl_fehlerhaft = 0
    for paket in roh_json:
        # Ein Paket ist für uns fehlerhaft,
        # wenn es keine Bluetooth-Informationen enthält
        if not paket.get("_source", {}).get("layers", {}).get("bthci_evt", None):
            anzahl_fehlerhaft += 1
            continue

        mac = paket["_source"]["layers"]["bthci_evt"]["bthci_evt.bd_addr"]
        rssi = int(paket["_source"]["layers"]["bthci_evt"]["bthci_evt.rssi"])
        # Epoch in Sekunden (Sekunden seit 1.1.1970)
        epoch = int(float(paket["_source"]["layers"]["frame"]["frame.time_epoch"]))

        # Da es in BLE keine Sequenznummern gibt, wird die Zeit als
        # Sequenznummer verwendet. Theoretisch könnte es hier zu
        # Fehler kommen, wenn verschiedene Sniffer das gleiche Paket
        # zu verschiedenen Zeiten empfangen. Dies ist aber aufgrund
        # der Lichtgeschwindigkeit praktisch ausgeschlossen.
        pakete_nach_mac[(mac, epoch)].append(
            (
                sniffer_info.id,
                rssi,
            )
        )

    print(f"Sniffer {sniffer_info.id} hat {anzahl_fehlerhaft} fehlerhafte Pakete")


def wlan_sniffer_auswerten(
    dateipfad: Path,
    pakete_nach_mac: PaketeNachMac,
    sniffer_info: Sniffer,
):
    """Werte WLAN-Aufnahmen im pcapng-Format aus

    Args:
        dateipfad (Path): Der Pfad zur pcapng-Datei
        pakete_nach_mac (PaketeNachMac): Die Pakete werden hier gespeichert
        sniffer_info (Sniffer): Information über den Sniffer
    """
    # Die Funktion rdpcap von scapy kann pcapng-Dateien lesen
    pakete = rdpcap(str(dateipfad))

    for paket in pakete:  # type: ignore
        # Sicherstellen, dass das Paket ein Probe Request ist
        assert Dot11ProbeReq in paket, "Paket ist kein Probe Request"

        paket = cast(Dot11, paket)

        mac = cast(str, paket.addr2)  # type: ignore
        radiotap = cast(RadioTap, paket[RadioTap])
        rssi = cast(int, radiotap.dBm_AntSignal)  # type: ignore
        sequenznummer = cast(int, paket.SC)  # type: ignore

        pakete_nach_mac[(mac, sequenznummer)].append(
            (
                sniffer_info.id,
                rssi,
            )
        )


def rssi_zu_meter(rssi: int, ein_meter_rssi: float, n: float = 4) -> float:
    """Wandelt einen RSSI-Wert in einen Abstand um

    Args:
        rssi (int): Der RSSI-Wert
        ein_meter_rssi (float): Der RSSI-Wert in einem Meter Abstand
        n (float, optional): Der Dämpfungsfaktor, desto größer desto stärker.
            Kann auch für eine schlechte Kalibrierung kompensieren.

    Returns:
        float: Der Abstand in Metern
    """
    return 10 ** ((ein_meter_rssi - rssi) / (10 * n))


def main() -> int:
    typ = sys.argv[1]
    rssi_ein_meter = (
        BLUETOOTH_RSSI_EIN_METER if typ == "bluetooth" else WLAN_RSSI_EIN_METER
    )

    daten: list[tuple[Sniffer, Path]] = [
        (
            Sniffer(uuid4().hex, (47.66354934150967, 4.621676369539302)),
            Path(sys.argv[2]),
        ),
        (
            Sniffer(uuid4().hex, (30.66381799963902, 8.439582935680464)),
            Path(sys.argv[3]),
        ),
        (
            Sniffer(uuid4().hex, (29.940425176580693, 24.836486925002507)),
            Path(sys.argv[4]),
        ),
    ]

    sniffer_nach_id: dict[str, Sniffer] = {sniffer.id: sniffer for sniffer, _ in daten}

    pakete_nach_mac: PaketeNachMac = defaultdict(list)

    for sniffer, pfad in daten:
        if typ == "bluetooth":
            bluetooth_sniffer_auswerten(pfad, pakete_nach_mac, sniffer)
        else:
            wlan_sniffer_auswerten(pfad, pakete_nach_mac, sniffer)

    ausgabe: list[Vec2] = []

    for pakete in pakete_nach_mac.values():
        if len(pakete) < 3:
            # Paket wurde nicht von allen Sniffern empfangen
            # => kann nicht sinnvoll ausgewertet werden
            continue

        arr = [
            Circle(
                *sniffer_nach_id[sniffer_id].position,
                rssi_zu_meter(rssi, rssi_ein_meter),
            )
            for sniffer_id, rssi in pakete
        ]
        # Least Squares Algorithmus für die Trilateration verwenden
        # https://www.th-luebeck.de/fileadmin/media_cosa/Dateien/Veroeffentlichungen/Sammlung/TR-2-2015-least-sqaures-with-ToA.pdf
        result, _ = easy_least_squares(arr)  # type: ignore

        # Wenn der Algorithmus für beide Koordinaten negative Werte zurückgibt
        # ist die Position nicht sinnvoll bestimmbar
        if result.center.x < 0 and result.center.y < 0:
            continue

        ausgabe.append(
            (
                max(result.center.x, 0),
                max(result.center.y, 0),
            )
        )

    # Ausgabe als JSON-Datei speichern
    with open("ausgabe.json", "w") as f:
        json.dump(ausgabe, f)

    return 0


if __name__ == "__main__":
    sys.exit(main())
