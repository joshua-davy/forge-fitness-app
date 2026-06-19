# Forge Mobile (Expo)

**Status: scaffolded, not built.** The web app is the canonical and shippable
frontend. This Expo project mirrors the architecture and ports the two highest-
value components (Goal Ticker, Day Progress Ring) plus a working Dashboard
screen wired to the same backend.

## What's here

- `app/_layout.tsx`, `app/index.tsx` — expo-router entry, dark theme
- `src/screens/Dashboard.tsx` — pull-to-refresh dashboard with ticker, ring,
  coach card, vitals list
- `src/components/day/DayProgressRing.tsx` — react-native-svg port
- `src/components/goals/GoalTicker.tsx` — RN port
- `src/lib/api.ts` — same contract as the web client, reads `apiUrl` from
  `app.json > expo.extra`
- `src/theme/index.ts` — the same design tokens

## What's not done

- Full goal CRUD UI (add bar, drag reorder, queue, polish, push-remaining)
- TomorrowGoalsCard
- Health rings (port HealthRings from web → react-native-svg)
- Animated reveals / Reanimated polish
- Font loading via `expo-font` (currently uses system fonts as fallback)
- App icons, splash, EAS config

## Running it

```bash
cd mobile
npm install
# Point at your backend (local LAN IP, not localhost, for device testing):
# edit app.json -> expo.extra.apiUrl
npx expo start
```

Open in Expo Go on phone or press `w` for web preview. iOS simulator needs Xcode,
Android emulator needs Android Studio.

## Why not finished

The web app at `../web/` covers every acceptance criterion in the brief and is
the shippable artifact. Native ports add weeks of work for the same logic — what
matters first is the brain (the API) and one polished surface (the web). Once
the web is in users' hands, port the rest with EAS Build.

The components here are intentionally aligned with their web siblings so a
component-by-component port stays mechanical.
