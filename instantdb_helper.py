#!/usr/bin/env python3
"""
InstantDB Helper - Liest und schreibt Wetterdaten ueber die InstantDB REST API.
Verwendet die Admin-API direkt ohne SDK.
"""

import json
import logging
import os
import uuid
import requests

logger = logging.getLogger(__name__)

# InstantDB Konfiguration
INSTANT_APP_ID = os.environ.get("INSTANT_APP_ID", "2387c94a-b7df-4746-942a-a2b68d5b158a")
INSTANT_ADMIN_TOKEN = os.environ.get("INSTANT_ADMIN_TOKEN", "13cee95a-4136-4ba9-b81a-53388f0bccf7")
INSTANT_API_URL = "https://api.instantdb.com"

# Feste IDs fuer die Datensaetze (werden immer ueberschrieben)
WEATHER_RECORD_ID = "00000000-0000-0000-0000-000000000001"
EVALUATION_RECORD_ID = "00000000-0000-0000-0000-000000000002"

# Namespace fuer deterministische Region-Record-IDs
REGION_NAMESPACE = uuid.UUID("10000000-0000-0000-0000-000000000000")


def _region_record_id(region_id):
    """Erzeugt eine deterministische UUID5 fuer eine Region."""
    return str(uuid.uuid5(REGION_NAMESPACE, region_id))


def _headers():
    """Erstellt die Authorization-Headers fuer die InstantDB Admin API."""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {INSTANT_ADMIN_TOKEN}",
    }


def save_weather_data(weather_data: dict) -> bool:
    """
    Speichert Wetterdaten in InstantDB (ueberschreibt bestehende Daten).
    
    Args:
        weather_data: Das komplette Wetterdaten-Dict (wie aus wetterdaten.json)
    
    Returns:
        True bei Erfolg, False bei Fehler
    """
    try:
        # Serialisiere die Daten als JSON-String, da InstantDB Limits bei verschachtelten Objekten hat
        payload = {
            "steps": [
                ["update", "weather_data", WEATHER_RECORD_ID, {
                    "data": json.dumps(weather_data, ensure_ascii=False),
                    "updated_at": __import__('datetime').datetime.utcnow().isoformat() + "Z"
                }]
            ],
            "throw-on-missing-attrs?": False
        }
        
        resp = requests.post(
            f"{INSTANT_API_URL}/admin/transact?app_id={INSTANT_APP_ID}",
            headers=_headers(),
            json=payload,
            timeout=30
        )
        
        if resp.status_code == 200:
            logger.info(f"Wetterdaten erfolgreich in InstantDB gespeichert (tx-id: {resp.json().get('tx-id')})")
            return True
        else:
            logger.error(f"InstantDB Speichern fehlgeschlagen: {resp.status_code} - {resp.text}")
            return False
            
    except Exception as e:
        logger.error(f"InstantDB Fehler beim Speichern: {e}")
        return False


def load_weather_data() -> dict | None:
    """
    Laedt Wetterdaten aus InstantDB.
    
    Returns:
        Das Wetterdaten-Dict oder None wenn keine Daten vorhanden
    """
    try:
        payload = {
            "query": {
                "weather_data": {}
            }
        }
        
        resp = requests.post(
            f"{INSTANT_API_URL}/admin/query?app_id={INSTANT_APP_ID}",
            headers=_headers(),
            json=payload,
            timeout=15
        )
        
        if resp.status_code != 200:
            logger.error(f"InstantDB Query fehlgeschlagen: {resp.status_code} - {resp.text}")
            return None
        
        result = resp.json()
        records = result.get("weather_data", [])
        
        if not records:
            logger.info("Keine Wetterdaten in InstantDB gefunden")
            return None
        
        # Nehme den ersten (einzigen) Datensatz
        record = records[0]
        data_str = record.get("data")
        
        if not data_str:
            logger.warning("InstantDB Datensatz hat keine 'data'-Feld")
            return None
        
        weather_data = json.loads(data_str)
        logger.info(f"Wetterdaten aus InstantDB geladen (updated: {record.get('updated_at', 'unbekannt')})")
        return weather_data
        
    except json.JSONDecodeError as e:
        logger.error(f"InstantDB: Fehler beim Parsen der Wetterdaten: {e}")
        return None
    except Exception as e:
        logger.error(f"InstantDB Fehler beim Laden: {e}")
        return None


def save_evaluation_data(evaluation_data: dict) -> bool:
    """
    Speichert LLM-Evaluierungsdaten in InstantDB (ueberschreibt bestehende).
    
    Args:
        evaluation_data: Das komplette Evaluierungs-Dict (wie aus evaluations.json)
    
    Returns:
        True bei Erfolg, False bei Fehler
    """
    try:
        payload = {
            "steps": [
                ["update", "evaluation_data", EVALUATION_RECORD_ID, {
                    "data": json.dumps(evaluation_data, ensure_ascii=False),
                    "updated_at": __import__('datetime').datetime.utcnow().isoformat() + "Z"
                }]
            ],
            "throw-on-missing-attrs?": False
        }
        
        resp = requests.post(
            f"{INSTANT_API_URL}/admin/transact?app_id={INSTANT_APP_ID}",
            headers=_headers(),
            json=payload,
            timeout=30
        )
        
        if resp.status_code == 200:
            logger.info(f"Evaluierungen erfolgreich in InstantDB gespeichert (tx-id: {resp.json().get('tx-id')})")
            return True
        else:
            logger.error(f"InstantDB Evaluierung-Speichern fehlgeschlagen: {resp.status_code} - {resp.text}")
            return False
            
    except Exception as e:
        logger.error(f"InstantDB Fehler beim Speichern der Evaluierungen: {e}")
        return False


def load_evaluation_data() -> dict | None:
    """
    Laedt LLM-Evaluierungsdaten aus InstantDB.
    
    Returns:
        Das Evaluierungs-Dict oder None wenn keine Daten vorhanden
    """
    try:
        payload = {
            "query": {
                "evaluation_data": {}
            }
        }
        
        resp = requests.post(
            f"{INSTANT_API_URL}/admin/query?app_id={INSTANT_APP_ID}",
            headers=_headers(),
            json=payload,
            timeout=15
        )
        
        if resp.status_code != 200:
            logger.error(f"InstantDB Evaluierung-Query fehlgeschlagen: {resp.status_code} - {resp.text}")
            return None
        
        result = resp.json()
        records = result.get("evaluation_data", [])
        
        if not records:
            logger.info("Keine Evaluierungen in InstantDB gefunden")
            return None
        
        record = records[0]
        data_str = record.get("data")
        
        if not data_str:
            return None
        
        eval_data = json.loads(data_str)
        logger.info(f"Evaluierungen aus InstantDB geladen (updated: {record.get('updated_at', 'unbekannt')})")
        return eval_data
        
    except json.JSONDecodeError as e:
        logger.error(f"InstantDB: Fehler beim Parsen der Evaluierungen: {e}")
        return None
    except Exception as e:
        logger.error(f"InstantDB Fehler beim Laden der Evaluierungen: {e}")
        return None


def save_all_regions_weather(regions_dict: dict, batch_size: int = 5) -> bool:
    """
    Speichert rohe Wetterdaten fuer alle Regionen in InstantDB.
    Sendet in Batches um Payload-Groessenlimits zu umgehen.

    Args:
        regions_dict: {"region_id": {"hourly_data": {...}, "pressure_level_data": {...}}, ...}
        batch_size: Anzahl Regionen pro Transaktion (Default: 5)

    Returns:
        True bei Erfolg aller Batches, False bei Fehler
    """
    try:
        updated_at = __import__('datetime').datetime.utcnow().isoformat() + "Z"
        items = list(regions_dict.items())
        total_ok = 0
        total_fail = 0

        for batch_start in range(0, len(items), batch_size):
            batch = items[batch_start:batch_start + batch_size]
            steps = []
            for region_id, data in batch:
                record_id = _region_record_id(region_id)
                steps.append([
                    "update", "regions_weather", record_id, {
                        "data": json.dumps(data, ensure_ascii=False),
                        "region_id": region_id,
                        "updated_at": updated_at
                    }
                ])

            payload = {
                "steps": steps,
                "throw-on-missing-attrs?": False
            }

            resp = requests.post(
                f"{INSTANT_API_URL}/admin/transact?app_id={INSTANT_APP_ID}",
                headers=_headers(),
                json=payload,
                timeout=60
            )

            if resp.status_code == 200:
                total_ok += len(batch)
            else:
                total_fail += len(batch)
                logger.error(f"InstantDB Batch {batch_start//batch_size+1} fehlgeschlagen: "
                             f"{resp.status_code} - {resp.text[:500]}")

        if total_fail == 0:
            logger.info(f"Regionen-Wetterdaten gespeichert ({total_ok} Regionen in "
                         f"{(len(items) + batch_size - 1) // batch_size} Batches)")
            return True
        else:
            logger.warning(f"Regionen-Wetterdaten teilweise gespeichert: "
                           f"{total_ok} OK, {total_fail} fehlgeschlagen")
            return total_ok > 0

    except Exception as e:
        logger.error(f"InstantDB Fehler beim Speichern der Regionen-Wetterdaten: {e}")
        return False


def load_region_weather(region_id: str) -> dict | None:
    """
    Laedt rohe Wetterdaten einer einzelnen Region aus InstantDB.

    Args:
        region_id: z.B. "mittelland_ost"

    Returns:
        Dict mit "hourly_data" + "pressure_level_data" oder None
    """
    try:
        record_id = _region_record_id(region_id)
        payload = {
            "query": {
                "regions_weather": {}
            }
        }

        resp = requests.post(
            f"{INSTANT_API_URL}/admin/query?app_id={INSTANT_APP_ID}",
            headers=_headers(),
            json=payload,
            timeout=15
        )

        if resp.status_code != 200:
            logger.error(f"InstantDB Region-Query fehlgeschlagen: {resp.status_code} - {resp.text}")
            return None

        result = resp.json()
        records = result.get("regions_weather", [])

        for record in records:
            if record.get("id") == record_id:
                data_str = record.get("data")
                if not data_str:
                    return None
                return json.loads(data_str)

        logger.info(f"Keine Wetterdaten fuer Region '{region_id}' gefunden")
        return None

    except json.JSONDecodeError as e:
        logger.error(f"InstantDB: Fehler beim Parsen der Region-Daten: {e}")
        return None
    except Exception as e:
        logger.error(f"InstantDB Fehler beim Laden der Region '{region_id}': {e}")
        return None
