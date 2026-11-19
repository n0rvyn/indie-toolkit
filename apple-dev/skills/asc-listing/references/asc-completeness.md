# ASC completeness: scoped success versus submission readiness

A listing update is complete only for its explicit fields. Full preparation must still expose all rows below. Do not fill unknown decisions or invent exemptions. Read current data first, preserve owner edits, and report whole-app readiness separately from scope_complete. A queued submission is not release approval and is not independent proof of every declaration's correctness.

| Item | Required/optional and verification |
| --- | --- |
| App Privacy collection answers | Required for app submission. Read the actual browser answers; privacyPolicyUrl and a source privacy audit do not prove these answers were entered. No documented public nutrition-label questionnaire API is established for this workflow. |
| App Privacy publication | Separate mandatory status: saved answers are not published answers. Inspect the browser Published state or preview; do not click Publish without specific authority. Login blocked means unverified, not API-key permission denied. |
| Primary category | Required. GET appInfos/{id}/primaryCategory. For macOS compare with actual shipped LSApplicationCategoryType; source project settings alone are not final binary verification. |
| Secondary category | Optional. GET appInfos/{id}/secondaryCategory; an empty secondary category is not a submission blocker. Games/Stickers subcategories are conditional. |
| Content Rights | Read apps/{id}.attributes.contentRightsDeclaration. Declaration needs owner-authorized factual/legal determination. Do not infer it from an offline app, or equate third-party code licensing with every possible content scenario. |
| Copyright | Required at appStoreVersions/{id}.attributes.copyright. Needs year and actual exclusive rights holder, not a guessed account/reviewer name. Apple adds the copyright symbol. |
| Price | Required price schedule, including deliberately free. GET apps/{id}/appPriceSchedule, then follow returned manualPrices/automaticPrices links, include appPricePoint and territory, follow pagination. Base territory alone proves no price. |
| Availability | Read apps/{id}/appAvailabilityV2, follow territoryAvailabilities links and pagination. Record selected territories and China status separately; enabled does not mean already sellable or legally eligible. Preserve owner region selections. |
| Age rating / Kids | Required age-rating questionnaire/rating, optional Kids selection with its own consequences. Read ageRatingDeclaration and appInfo rating; do not guess answers. |
| Build association | Read the selected version's build relationship, processingState, build number, preReleaseVersion marketing version, platform and encryption status. A local archive or uploaded build list does not prove association. |
| Submission / release | Read reviewSubmissions state/submittedDate and selected version state/releaseType. Never submit, withdraw, select a build or change releaseType under ordinary metadata authority. |
| Remaining submission fields | Verify localized required text/URLs, valid current screenshots by supported device, review contact/demo info, export compliance, applicable agreements/trader/tax/compliance states and any App Review validation messages. |

## Capability evidence

Individual keys inherit the user's role/app access; there is no blanket metadata/pricing exclusion. Record actual endpoint/status/error for a denied operation. HTTP200 with null is an empty resource, not denied permission; HTTP404 can mean wrong endpoint or missing resource. The scoped helper intentionally excludes category/legal/price/build/submission writes; that is a safety boundary, not an Apple API limitation. Do not probe undocumented private APIs or guess nutrition-label paths to turn404 into a capability claim. Browser-only checks must retain an explicit blocker when no signed-in session is available.

## China mainland

Content Rights and China compliance are separate. Selecting DOES_NOT_USE_THIRD_PARTY_CONTENT does not establish an ICP exemption. Apple's app-information reference says some apps need ICP and identifies additional game/publishing/religion/news permits; it does not resolve every offline macOS utility's applicability. Record applicable documentation/review evidence; do not remove China or make a legal declaration as a workaround.

Sources: [individual keys](https://developer.apple.com/documentation/AppStoreConnectAPI/creating-api-keys-for-app-store-connect-api), [App Privacy and Publish](https://developer.apple.com/help/app-store-connect/manage-app-information/manage-app-privacy/), [app information](https://developer.apple.com/help/app-store-connect/reference/app-information/app-information/), [version/copyright](https://developer.apple.com/help/app-store-connect/reference/app-information/platform-version-information/), [required properties](https://developer.apple.com/help/app-store-connect/reference/app-information/required-localizable-and-editable-properties/).
