# Legal & Compliance

> **TL;DR** - spfnotch is a **legal, unofficial, open-source remote control**
> for your own Spotify account. It uses only Spotify's **official, public Web
> API** with OAuth login. It does **not** download, record, rip, or bypass
> anything, and it does **not** unlock Premium features. Every user connects
> using **their own** Spotify Developer app credentials.

*This document is an honest good-faith assessment, not legal advice.*

---

## 1. What spfnotch does - and does not do

| ✅ Does | ❌ Does NOT |
|---|---|
| Reads "now playing" info via the official Web API | Download or cache audio |
| Sends play / pause / next / previous / seek / queue commands | Record, rip or convert streams |
| Searches the Spotify catalog | Bypass ads or unlock Premium |
| Shows album art served by Spotify | Modify / inject into the Spotify client (unlike Spicetify-style mods) |
| Fetches synced lyrics from LRCLIB at runtime | Store or redistribute lyrics |
| Stores your token **locally** on your PC | Send your data to any server owned by this project |

Because it only automates what you can already do in the Spotify app, using it
is equivalent to using any official "Spotify Connect" remote.

## 2. Spotify Developer Terms - how spfnotch complies

| Requirement (Spotify Developer Terms / Policy) | How spfnotch complies |
|---|---|
| Use only official APIs, authenticate users with OAuth | Uses `spotipy` + Authorization Code flow on `127.0.0.1`. |
| Don't embed / share a Client Secret publicly | **Bring-your-own-credentials**: no secret ships with the app; every user creates their own app. `config.json` is git-ignored. |
| Don't imply Spotify endorsement; don't use "Spotify" as the product name | Product name is **spfnotch**. "for Spotify" is used only descriptively. Disclaimer below. |
| Don't commercialize Spotify content | spfnotch is free and non-commercial. No ads, no paywall, no data sale. |
| Attribute content to Spotify | Metadata/art come from Spotify; Spotify is credited in the README and app docs. |
| Respect rate limits | Polls every ~2 s and interpolates progress locally. |
| Development Mode limits (2026) | Each Client ID is limited to **5 allow-listed users** and the app owner needs **Spotify Premium**. Since each user makes their own app, this is a non-issue for personal use. |

Spotify can change its terms at any time. Check
<https://developer.spotify.com/terms> and <https://developer.spotify.com/policy>
before redistributing a modified version.

## 3. Grey areas you should know about

1. **Synced lyrics.** Spotify's Developer Policy forbids synchronizing Spotify
   *sound recordings* with *visual media* (video, ads, slideshows). spfnotch only
   shows text lyrics from a third party (LRCLIB) next to playback state; it does
   not attach audio to any media. This is the same thing many popular open-source
   lyric widgets do, but it is the part most open to interpretation.
   Lyrics are copyrighted by their publishers - spfnotch does not store or
   redistribute them; they are fetched live for personal display only.
2. **Premium.** Playback-control endpoints (play/pause/skip/seek/queue) only work
   for **Spotify Premium** listeners. Free accounts can still see track info.
3. **Built binary & PyQt6 (GPL v3).** The source is MIT, but the pre-built
   `.exe` bundles PyQt6, so the binary is distributed under GPL v3 terms.
   See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## 4. Privacy

- Your Client ID, Client Secret and OAuth token are stored **only** in
  `config.json` and `.spotify_token_cache` next to the app on your machine.
- The app talks only to `api.spotify.com`, `accounts.spotify.com`,
  `i.scdn.co` (cover art) and `lrclib.net` (lyrics).
- No analytics, no telemetry.
- To revoke access at any time: <https://www.spotify.com/account/apps/>.

## 5. Trademark disclaimer

Spotify® is a registered trademark of Spotify AB. spfnotch is an independent,
unofficial project and is **not affiliated with, endorsed, or sponsored by
Spotify AB**. All album art, track names and artist names belong to their
respective owners.

## 6. Liability

spfnotch is provided "as is", without warranty of any kind (see [LICENSE](LICENSE)).
You are responsible for complying with Spotify's Terms of Use when you use it
with your account.
