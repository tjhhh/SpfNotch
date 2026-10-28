# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Instead, use
GitHub's [private vulnerability reporting](https://github.com/tjhhh/SpfNotch/security/advisories/new).
You'll get a response within 7 days.

## Protecting your Spotify credentials

- `config.json` holds your **Client Secret** and `.spotify_token_cache` holds your
  **OAuth refresh token**. Both are listed in `.gitignore` - never commit, share,
  or screenshot them.
- If you ever leak them: open the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
  → your app → **Settings** → **Rotate client secret**, delete
  `.spotify_token_cache`, and remove the app at <https://www.spotify.com/account/apps/>.
- The OAuth callback server listens only on `127.0.0.1:8888` and only during the
  login flow (max 60 s).
