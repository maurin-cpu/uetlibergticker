# Flight Category Overhaul Plan

The user wants to refine the 5 flight categories (`DANGEROUS`, `CAUTION`, `FLYABLE`, `GOOD`, `LEGENDARY`) so that they are consistently used by both the Python codebase and the LLM via `config.py`. 

Crucially, the "fun factor" (Flyable, Good, Legendary) must be based **strictly on the height achievable above the takeoff altitude**, not absolute ASL or AGL.

Takeoff altitude for Uetliberg Balderen is 730m MSL.

## Proposed New Categories

### 1. DANGEROUS (Gefährlich)
- **Condition:** Unsafe to fly at all.
- **Criteria:** High winds (>30-40km/h depending on gusts), Föhn, severe shear, thunderstorms, or cloud base below takeoff (fog).
- **UI Element:** Red dashboard.
- **Meaning:** Stay on the ground.

### 2. CAUTION (Aufpassen)
- **Condition:** Potentially unsafe, requires high skill or extreme caution.
- **Criteria:** Gusty winds nearing limits, moderate shear, or approaching weather changes.
- **UI Element:** Yellow/Orange dashboard.
- **Meaning:** Flyable only for very experienced pilots or with extreme caution.

### 3. FLYABLE (Fliegbar - Abgleiter)
- **Condition:** Safe to fly, but no significant altitude gain possible.
- **Criteria:** Wind is weak (< 15 km/h) or thermal height is below or barely above the takeoff altitude.
- **Altitude Gain:** 0m to ~50m above takeoff.
- **UI Element:** Light Blue / Gray dashboard.
- **Meaning:** Sled run (Abgleiter). You will sink to the landing zone shortly after takeoff.

### 4. GOOD (Gut - Soaring / Lokales Kurbeln)
- **Condition:** Safe to fly with the ability to maintain altitude or climb slightly.
- **Criteria:** Good wind (15-25 km/h) to stay on the ridge, or thermals allowing climbs above the takeoff.
- **Altitude Gain:** ~50m to ~300m above takeoff. 
- **UI Element:** Green dashboard.
- **Meaning:** You can stay in the air, soar the ridge, and potentially thermal above the takeoff, but it's not enough for cross-country (XC) flights.

### 5. LEGENDARY (Legendär - Streckenflug / Top Thermik)
- **Condition:** Excellent, safe conditions with powerful thermals reaching high altitudes. 
- **Criteria:** Perfect wind direction/speed and strong thermals (`climb_rate` > 1.5 m/s).
- **Altitude Gain:** > 300m above takeoff (e.g., reaching > 1000m MSL at Uetliberg).
- **UI Element:** Purple/Gold dashboard.
- **Meaning:** Epic conditions. You can climb high above the mountain and potentially go on a cross-country flight.

## Implementation Steps (No changes until approved!)

1. **Update `config.py` (LLM Prompt):**
   - Rewrite the `LLM_SYSTEM_PROMPT` to explicitly define these 5 categories based exactly on the criteria above.
   - Introduce the "Height above Takeoff" concept into the prompt so the LLM evaluates `max_height - 730` rather than just looking at MSL.
   
2. **Update `location_evaluator.py`:**
   - Ensure the parsing logic assigns the correct safety/flyable states and colors based on the newly strictly defined categories.
   
3. **Update UI (`weather_timeline.html` / `meteo_grafik.html` / `app.js`):**
   - Verify that the dashboard color themes correctly map to these 5 states. (DANGEROUS=Red, CAUTION=Yellow, FLYABLE=Blue/Gray, GOOD=Green, LEGENDARY=Purple).

*Note: I will wait for your explicit instruction before mutating any code.*
