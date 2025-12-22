# Research Notes

## CloudAhoy
- Public login form posts to `/api/signin.cgi?form` on `https://www.cloudahoy.com/login.php`.
- No public API docs discovered from public site assets.
- Web automation mode uses the login form and relies on a configurable flights URL plus export URL template.

## FlySto
- Public SPA at `https://www.flysto.net/`.
- Public JS bundle only references `/api/koulouraki-consent` and `/api/profile`.
- No public upload endpoint discovered without an authenticated session.
- Web automation mode uses login UI and file upload form heuristics.
