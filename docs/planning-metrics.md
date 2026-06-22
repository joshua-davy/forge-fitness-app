# Forge Planning Metrics

Forge planning tools are decision aids. They use the user's stored profile and
Garmin history, display coverage/confidence, and do not diagnose, prescribe,
or promise an outcome.

## Fuel plan

1. **BMR** uses the Mifflin-St Jeor equation when date of birth, sex, height,
   and weight are available. If data is incomplete, Forge falls back to a
   weight-only estimate and marks confidence low.
2. **Daily energy estimate** is `BMR x 1.25 + Garmin active calories + goal
   adjustment`. Goal adjustments are deliberately modest: -300 kcal for loss
   goals, +150 to +250 kcal for gain goals, and 0 for maintenance.
3. **Protein** is calculated from body mass and goal. Maintenance is 1.4-1.8
   g/kg/day; fat-loss and muscle-gain ranges are higher. Strength work and
   endurance work longer than 60 minutes can increase the upper end, capped at
   2.4 g/kg/day.

## Personal sleep timing

Forge selects the upper quartile of recorded sleep scores within the selected
history window, then uses the median bedtime and wake time from those nights.
Target bedtime is calculated backwards from preferred wake time and desired
sleep duration. Wind-down begins one hour before target bedtime.

The sleep explorer filters historical nights by bedtime and prior activity
type. It reports average Sleep Score and the matched-night count. It does not
claim the activity caused the outcome.

## Race outlook

Running uses comparable Garmin activities from the prior 90 days and a
distance-normalisation curve with exponent 1.06. Cycling uses 1.04. The
forecast is the median of the best three comparable equivalent performances,
with a wider range when few sessions are available. Heart rate and VO2 Max are
shown as context; a future manual RPE entry is needed before they adjust the
prediction directly.

Route elevation, surface, weather, pacing, power, injury status, and race-day
conditions are not fully captured. Forecasts are planning ranges, not promises.
Forge presents a conservative no-training planning range only after comparable
session history exists. It is not a prediction of an individual outcome.
