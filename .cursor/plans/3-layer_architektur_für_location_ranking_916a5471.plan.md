---
name: 3-Layer Architektur für Location Ranking
overview: ""
todos:
  - id: add_safety_limits
    content: Safety Limits und LLM Prompts zu config.py hinzufügen (SAFETY_LIMITS, LLM_SYSTEM_PROMPT, LLM_INITIAL_PROMPT, LLM_EVALUATION_INSTRUCTIONS, LLM_EVALUATION_INSTRUCTIONS_FIRST_TIME)
    status: completed
  - id: extend_fetch_weather
    content: fetch_weather.py erweitern um neue Wetterdaten abzurufen (CAPE, wind_gusts_10m, rain) falls noch nicht vorhanden
    status: completed
  - id: create_safety_filter
    content: Safety Filter Service erstellen (apply_safety_filter Funktion - cloud_cover NICHT im Filter, nur im LLM Ranking)
    status: completed
    dependencies:
      - add_safety_limits
      - extend_fetch_weather
  - id: refactor_weather_enrichment
    content: Weather Enrichment Service refactoren (enrich_location_with_weather Funktion)
    status: completed
  - id: refactor_llm_ranking
    content: LLM Ranking Service refactoren (Interaktive Rückfragen-Schleife implementieren, Prompts aus config.py)
    status: completed
    dependencies:
      - refactor_weather_enrichment
  - id: restructure_main
    content: main() Funktion nach 3-Layer-Modell umstrukturieren
    status: completed
    dependencies:
      - create_safety_filter
      - refactor_weather_enrichment
      - refactor_llm_ranking
---

