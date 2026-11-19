# Direct listing updates and screenshots

Use installed Fastlane or `scripts/asc_manage.py` only within the user's authorized listing scope. The helper supports four explicit modes and never submits/releases, selects a build, changes prices, deletes screenshots, changes privacy declarations, or sends correspondence.

## Credentials

Set process-local environment variables in the owner's local shell, using placeholders:

```sh
export ASC_KEY_TYPE=individual
export ASC_KEY_PATH='<absolute .p8 filepath outside repository>'
export ASC_KEY_ID='<key ID>'
unset ASC_ISSUER_ID
```

For team keys use `ASC_KEY_TYPE=team` and `ASC_ISSUER_ID='<issuer ID>'`; existing `key.info` discovery remains supported by the readback script. Individual mode requires an explicit filepath and key ID. Missing issuer in team mode is an error, not an implicit switch to individual. Individual tokens use `sub=user` and omit `iss`; team tokens use `iss`. A stale team issuer is ignored only when individual mode is explicit.

Authentication necessarily reads the key in the local tool process and creates a short-lived in-memory token. It does not upload the private key. Never display key contents, tokens, authorization headers or signed upload URLs. Do not copy keys into the package, generate new keys, initialize persistent credentials, or reset permissions. Authorization to use an existing key does not authorize broader account changes. Respect approval/network denials.

The helper uses `cryptography` for signing (existing readback dependency), plus installed macOS Swift/ImageIO for full PNG/JPEG decoding. `asc_image_probe.swift` is compiled once per process into a private temporary directory; the executable and module cache are temporary, and no user environment is changed. The same default Python with cryptography can perform prepare/apply/readback without Pillow. Tests generate PNG fixtures with the standard library and use system sips only for a JPEG fixture. No package installation or cross-interpreter sys.path modification is needed. Missing Swift/decoder, corrupt images or decode failures stop before writes. Fastlane 2.232.2 was independently verified to authenticate individual keys with `issuer_id:nil`, update both locale resource types, and read back 16/16 requested fields on a macOS draft. A private-key filename alone is not proof of its service/type or permissions.

## Four modes

First write a non-secret scope JSON: exact `app_id`, `bundle_id`, `platform` (e.g. `MAC_OS`), `version`, and nonempty unique `locales`. Resolve app identity by a read first; never guess IDs. API write helper accepts only one unambiguous version and app-info record in `PREPARE_FOR_SUBMISSION`.

```sh
python3 scripts/asc_manage.py read --scope scope.json --output before.json
python3 scripts/asc_manage.py prepare --manifest manifest.json --before before.json --output plan.json
# Inspect plan's exact before/after diff and asset list; apply only when authorized.
python3 scripts/asc_manage.py apply --plan plan.json --output receipt.json --authorized
python3 scripts/asc_manage.py readback --plan plan.json --output readback.json
```

`prepare` is offline and does not authenticate. `read`, `apply`, and `readback` authenticate. Mac reads include Asset Library placements by default. Use `read --metadata-only` for a metadata update without Asset Library access. `--authorized` is a mechanical guard, not a substitute for human authorization. Existing direct-update authorization is sufficient; do not ask again merely because the helper has a flag.

Manifest shape:

```json
{
  "scope": {"app_id":"<resolved ID>","bundle_id":"<verified bundle>","platform":"MAC_OS","version":"<draft version>","locales":["en-US"]},
  "locales": {"en-US":{"name":"Approved name","description":"Approved description","supportUrl":"https://example.com/support"}},
  "screenshots": []
}
```

Only provided fields change. Supported app-info fields: `name`, `subtitle`, `privacyPolicyUrl`. Version fields: `description`, `keywords`, `promotionalText`, `supportUrl`, `marketingUrl`, `whatsNew`. Omit `whatsNew` on first release unless Apple permits it. Prepare checks character/UTF-8 limits and HTTPS form; the agent must separately fetch and inspect each URL's actual content before including it. An HTTP 200 error page is insufficient. Match approved Library/source copy exactly; exclude notes/checklists from public text. A metadata change for a locale must leave both its app-info and version localizations present. If both are missing, supply fields for both. If one exists, supply the fields for the missing one.

Apply refuses stale drafts before writes, preserves unrelated fields, and records each successful operation. The plan's `expected_fields` includes every approved value, including fields that already matched during preparation. Apply writes only `changes`, then reads back all `expected_fields` and checks that requested metadata locales have both records. Regenerate older plans that lack `expected_fields`. ASC has no atomic compare-and-swap across these requests. Coordinate concurrent editors, retain the receipt after partial failure, and prepare a new diff from current state before continuing. Review state is checked separately from metadata; saved fields do not imply review submission.

## Screenshots

Manifest screenshot entries use `locale`, `display_type`, `path`, and `approved:true`. Paths resolve relative to the manifest. For a screenshot-only English update, use `"locales":{"en-US":{}}` for the existing version localization and provide the approved image in `screenshots`. A screenshot for a new version localization requires the corresponding metadata in the same plan. `approved:true` means the agent/user already visually checked actual product content, provenance, legibility and absence of private data. No synthetic product UI or resized diagnostic capture without inspection.

The bundled uploader accepts **Mac APP_DESKTOP only** (PNG/JPEG without alpha/transparency at 1280×800, 1440×900, 2560×1600 or 2880×1800) and maps it to Asset Library `APP_SCREENSHOT` / `MAC_PROFILE`. It checks Apple’s current group limits and image specifications before writing, checks the prepared SHA-256 before transfer, and commits `uploaded:true`. It stores the hash in the image's reference name to identify an upload on readback. The receipt retains image and placement IDs without signed upload URLs.

After processing, apply creates placements on the target version localization, appends in manifest order, and verifies the existing placement IDs and relative order. The final report checks the target locale, group, image identity, and actual placement order. If image processing outlasts apply, take a fresh screenshot-inclusive snapshot and prepare again. Matching uploaded images can be reused without uploading again. If placement or ordering fails after writing, inspect the saved IDs and current localization order before proceeding. Once placements exist, `readback` can verify the prepared order without writes. Keep visual inspection as a separate check.

## Fastlane localization regression

Fastlane 2.232.2's `post_app_info_localization` supplied the `appStoreVersion` relationship with `appStoreVersions` type for an `appInfoLocalizations` POST. Apple rejected unknown relationship/missing `appInfo`. Correct relationship: `appInfo → {type:appInfos,id:<appInfo ID>}`. Version localizations use `appStoreVersion → {type:appStoreVersions,id:<version ID>}`. The helper encodes and tests both; no installed SDK patch is needed.

## Apple correspondence vs customer reviews

App Review rejection/information messages are not public customer reviews, nor are review notes the correspondence thread. No public App Review correspondence API was verified for this workflow. Use the owner's signed-in ASC browser: Apps → unresolved issues → Resolve → Reply to App Review; inspect the actual thread, draft the response and attachments, then send only when the user explicitly authorizes that message. Complete login/2FA owner-side when needed. Never treat listing-update permission as permission to reply or submit. Read/prepare capability can proceed without sending. Installed Fastlane contains resolution-center models, but this does not prove a supported public endpoint or working individual-key reply route.

Customer reviews have separate documented API resources; do not use them to answer whether Apple sent a submission message. Agreements, Trader status and App Privacy declarations also remain separate supported browser workflows.

Sources: [Individual/team API keys](https://developer.apple.com/documentation/appstoreconnectapi/creating-api-keys-for-app-store-connect-api), [version localizations](https://developer.apple.com/documentation/appstoreconnectapi/app-store-version-localizations), [app info localization creation](https://developer.apple.com/documentation/appstoreconnectapi/post-v1-appinfolocalizations), [Asset Library](https://developer.apple.com/documentation/appstoreconnectapi/app-asset-library), [asset image upload](https://developer.apple.com/documentation/appstoreconnectapi/uploading-and-managing-image-assets), [screenshot specs](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications), [reply to App Review](https://developer.apple.com/help/app-store-connect/manage-submissions-to-app-review/reply-to-app-review-messages/), [customer reviews](https://developer.apple.com/documentation/appstoreconnectapi/customer-reviews).
