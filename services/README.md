# Optional Services

The toolkit integrates with these external services. Each is independently optional — only configure what you use.

## Service Registry

| Service | Skills That Use It | Env Vars Required | Setup Guide |
|---------|-------------------|-------------------|-------------|
| **Reddit** | `/reddit-moderate` | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, `REDDIT_PASSWORD`, `REDDIT_SUBREDDIT` | Create "script" app at [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps/). Run `python3 scripts/reddit_mod.py setup` after configuring. |
| **WordPress** | `/wordpress-uploader`, `/wordpress-live-validation` | `WORDPRESS_SITE`, `WORDPRESS_USER`, `WORDPRESS_APP_PASSWORD` | Generate Application Password in WordPress Admin > Users > Your Profile. |
| **Gemini** | `/gemini-image-generator` | `GEMINI_API_KEY` | Get key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey). |
| **Cloudflare** | DNS management | `CLOUDFLARE_API_TOKEN` | Create token at [Cloudflare dashboard](https://dash.cloudflare.com/profile/api-tokens). |
| **YouTube** | Community posts | `YOUTUBE_OAUTH_CLIENT`, `YOUTUBE_TOKEN`, `YOUTUBE_CHANNEL_ID` | Enable YouTube Data API v3 in Google Cloud Console. |
| **Google Indexing** | Search indexing | `GOOGLE_INDEXING_CREDENTIALS` | Create service account with Indexing API access. |
| **IndexNow** | Search indexing | `INDEXNOW_KEY`, `WEBSITE_HOST` | Generate key at [indexnow.org](https://www.indexnow.org/). |

## Configuration

All credentials go in `~/.env` (never committed). See `.env.example` for the template.

## Per-Service Data Directories

Services that need local state use gitignored data directories:

| Directory | Service | Created By |
|-----------|---------|-----------|
| `reddit-data/{subreddit}/` | Reddit | `python3 scripts/reddit_mod.py setup` |

These directories contain auto-generated analysis files, audit logs, and configuration.
See `templates/reddit/README.md` for the Reddit data directory structure.
