# Valet Parking

A Frappe Framework application for Valet Parking Management.

## Features
- **Parking Ticket Management**: Auto-generated unique tokens, status updates, and timestamp tracking.
- Status Workflow: `Awaiting Parking` -> `Parked` -> `Retrieval Requested` -> `On The Way` -> `Delivered`.
- Automated Timestamps: Automatically records timestamps (`created_at`, `parked_at`, `retrieval_requested_at`, `on_the_way_at`, `delivered_at`) upon status transitions.

## Installation
To install on a Frappe Bench site:
```bash
bench get-app https://github.com/your-repo/valet_parking
bench --site <your-site> install-app valet_parking
bench --site <your-site> migrate
```

## Testing
Run lightweight tests locally:
```bash
python run_tests.py
```
Or on a bench site:
```bash
bench --site <your-site> run-tests --app valet_parking
```
