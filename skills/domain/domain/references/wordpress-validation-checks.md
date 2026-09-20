# WordPress validation decisions

| Check | Blocker condition | Warning condition |
|---|---|---|
| Title | expected title differs materially from rendered H1/title | no expected title was supplied (report informationally) |
| H2 structure | — | missing or obviously malformed section structure |
| Images | any content image has failed HTTP or zero rendered width | — |
| Console | — | first-party uncaught error or CSP violation |
| Social metadata | — | missing/empty OG fields, wrong canonical URL, logo used instead of featured image |
| Meta description | — | missing/empty or conspicuously outside 50–160 characters |
| Draft text | visible placeholder/draft fragment | — |
| Responsive | content unavailable | horizontal overflow or hidden/clipped content |

For social metadata, inspect `og:title`, `og:description`, `og:image`, `og:url`, and `twitter:card`. An SEO plugin may intentionally make OG title/description differ from the visible page, so record values rather than declaring any difference a failure. Verify `og:image` resolves and `og:url` is the canonical post, not the homepage.

Each result includes the observed DOM value, request/status, console entry, or screenshot path. Do not convert missing evidence into PASS.
