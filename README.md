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

## Generating Test Referral Codes

Use the management command below to create a throwaway user (or reuse an existing one) and immediately obtain a referral/invite code:

```bash
python manage.py create_test_invite_code \
  --kakao-id 910000001 \
  --type-code ISTJ
```

- Omit `--kakao-id` to auto-create a new user with a random Kakao ID.
- Add `--no-create` if you only want to read the code for an existing user without creating a new record.
- The command prints the user ID, Kakao ID, and the invite code so you can plug it straight into referral API tests.
