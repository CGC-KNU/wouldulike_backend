# wouldulike_backend

## API Endpoints

- `POST /guests/update/fcm_token/` : Update the FCM token for a guest user. The request body should be JSON with `uuid` and `fcm_token` fields.

## Admin Portal Setup

1. Configure manager accounts via the environment variable `OPERATIONS_ADMIN_ACCOUNTS`.
   - Format: `ROLE:KAKAO_ID:PASSWORD` entries separated by `;` (roles: `super`, `strategy`, `planning`).
   - Optional per-entry fourth value allows overriding the reset flag (`true`/`false`).
2. Optionally set `OPERATIONS_ADMIN_DEFAULT_PASSWORD` and `OPERATIONS_ADMIN_RESET_PASSWORDS` to control defaults.
3. Apply the configuration with `python manage.py setup_admin_portal` (run during deploy or manually).
4. Rotate passwords by updating the secrets and re-running the command with `OPERATIONS_ADMIN_RESET_PASSWORDS=1`.
