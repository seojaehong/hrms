# Hermes HRMS Workspace Notes

Workspace
- Repo: `/home/ubuntu/workspaces/frappe-hrms`
- Branch: `develop`
- Runtime baseline: Docker Compose from `docker/docker-compose.yml`

What is already prepared
- Repo cloned on server
- Python package installed editable with `pip install --user -e .`
- Yarn installed globally
- Root/frontend/roster JS dependencies installed with `yarn install`
- Frontend production build verified with `yarn build`
- Dev helper file created for frontend build compatibility:
  - `/home/ubuntu/sites/common_site_config.json`

Useful commands
- Start/attach runtime:
  - `docker compose -f /home/ubuntu/workspaces/frappe-hrms/docker/docker-compose.yml up`
- Background runtime:
  - `docker compose -f /home/ubuntu/workspaces/frappe-hrms/docker/docker-compose.yml up -d`
- Stop runtime:
  - `docker compose -f /home/ubuntu/workspaces/frappe-hrms/docker/docker-compose.yml down`
- Build frontend bundles:
  - `cd /home/ubuntu/workspaces/frappe-hrms && yarn build`
- Frontend dev server only:
  - `cd /home/ubuntu/workspaces/frappe-hrms && yarn dev-pwa`
- Roster dev server only:
  - `cd /home/ubuntu/workspaces/frappe-hrms && yarn dev-roster`
- Repo status:
  - `cd /home/ubuntu/workspaces/frappe-hrms && git status --short`

Sass / UI entry points
- Main Desk stylesheet bundle registration:
  - `hrms/hooks.py` -> `app_include_css = "hrms.bundle.css"`
- Main Sass bundle source:
  - `hrms/public/scss/hrms.bundle.scss`
- Included Sass partials:
  - `hrms/public/scss/feedback.scss`
  - `hrms/public/scss/circular_progress.scss`
  - `hrms/public/scss/hierarchy_chart.scss`
- Vue/Tailwind frontends:
  - `frontend/`
  - `roster/`

Notes
- `import hrms` alone will fail outside a Bench/Frappe runtime because `frappe` is not installed in the system Python. Use the Docker/Bench runtime for app execution.
- For Sass/UI work, server-side source edits + `yarn build` is currently the fastest verified loop.
