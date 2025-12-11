# Anleitung: Fabrics CSV in die Datenbank importieren

Diese Anleitung beschreibt, wie du die Stoffdaten aus der CSV-Datei `fabrics_export-2.csv` in die Postgres-Datenbank `henk_db` überträgst.

## Voraussetzungen
- Python-Abhängigkeiten installieren (falls noch nicht erfolgt):
  ```bash
  pip install -r requirements.txt
  ```
- Zugriff auf die Ziel-Datenbank und eine gültige Verbindungszeichenkette, z. B.:
  ```bash
  export DATABASE_URL="postgresql://user:pass@localhost:5432/henk_db"
  ```
  Alternativ kannst du `POSTGRES_CONNECTION_STRING` setzen.
- Die CSV-Datei liegt unter `storage/fabrics_export-2.csv` oder an einem eigenen Pfad (siehe Parameter unten).

## Dry-Run (ohne Datenbankzugriff)
So kannst du prüfen, ob die CSV korrekt gelesen und geparst wird, ohne etwas in der DB zu verändern:
```bash
python scripts/import_fabric_details.py --dry-run
```
- Es werden die ersten drei importierbaren Einträge als JSON ausgegeben.
- Nutze `--source`, falls die Datei nicht im Standardpfad liegt:
  ```bash
  python scripts/import_fabric_details.py --dry-run --source pfad/zur/datei.csv
  ```

## Import in die Datenbank starten
1. Stelle sicher, dass `DATABASE_URL` oder `POSTGRES_CONNECTION_STRING` gesetzt ist.
2. Führe den Import aus:
   ```bash
   python scripts/import_fabric_details.py --source storage/fabrics_export-2.csv
   ```
   - Der Standardpfad ist `storage/fabrics_export-2.csv`; passe ihn bei Bedarf mit `--source` an.
3. Während des Imports siehst du Fortschrittsmeldungen (z. B. wie viele Einträge eingefügt/aktualisiert wurden). Zeilen ohne `Stoffcode` werden übersprungen und als Fehler gezählt.

## Was das Skript macht
- Erwartet eine Semikolon-separierte CSV mit Spalten wie `Stoffcode`, `Stofflieferant`, `Lager`, `Gewicht`, `Saison`, `Status` u. a.
- Upsert-Logik: Einträge werden über `fabric_code` identifiziert. Fehlende Felder in bestehenden Zeilen werden ergänzt, vorhandene Werte nicht überschrieben.
- Weitere Angaben landen als JSON in `additional_metadata` in der Tabelle `fabrics`.

## Typische Fehlerbehebung
- **CSV nicht gefunden:** Pfad prüfen oder mit `--source` angeben.
- **DB-Verbindung schlägt fehl:** `DATABASE_URL`/`POSTGRES_CONNECTION_STRING` überprüfen (Format `postgresql://...`).
- **Falsches Trennzeichen:** Die Datei muss Semikolon (`;`) nutzen.
