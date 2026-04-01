# Y.H. Kao Portfolio Website

A static portfolio website for Y.H. Kao (高育萱), showcasing consultancy services.

## Services Featured
- Thesis Guidance (論文指導)
- Government Subsidy Consulting (政府補助案輔導)
- Web Development (網站架設)

## Tech Stack
- Pure HTML5 and CSS3 (no build system or package manager)
- Static site served via Python's built-in HTTP server in development

## Project Structure
- `index.html` — Main landing page
- `thesis.html`, `thesis-faq.html`, `thesis-form.html`, etc. — Thesis guidance pages
- `government.html` — Government subsidy consulting page
- `website.html` — Web development services page
- `style.css` — Primary stylesheet
- `*-style.css` — Page-specific stylesheets
- `main-website/` — Alternative entry point

## Running Locally
The workflow runs: `python3 -m http.server 5000 --bind 0.0.0.0`

## Deployment
Configured as a static site deployment with `publicDir: "."`.
