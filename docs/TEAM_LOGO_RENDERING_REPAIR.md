# Universal team-logo containment repair

Implementation and isolated verification completed on 2026-10-29. Windows integration and verification of Lafayette's actual source image remain outstanding.

## Scope and working copy

Branch: `hotfix/universal-team-logo-containment`.
Base: GitHub main `1615ec6` (full SHA recorded in package BASE_COMMIT.txt).
No commit, push, merge, production deployment, or Windows-folder edit was performed.

The requested Windows development folder was not mounted in this environment. The implementation is an isolated checkout of the existing repository. Jason reported additional unpushed Windows changes; none were accessed, replaced, or discarded. The README and Project Bible contain older integration-branch statements that do not describe the newer main tree. The supplied patch is based on current main and must be checked against the actual Windows working tree.

## Root cause and rendering trace

`LogoService.process_candidate` decoded the uploaded raster and passed it through `normalize_round_logo` for both the 1024px master and 256px scorebug derivative. That routine trimmed the alpha bounding box, fit it into a 92% square, then multiplied the alpha channel by a circular mask. A rectangular mark can fit the square while extending outside the circle; its corners and outer borders are erased from the generated files. CSS containment cannot restore those pixels.

The school preview additionally applied `border-radius:50%` to the image itself, clipping boundary artwork again. The review broadcast-preview frame and Heritage's circular mark frame need inscribed fitting, rather than treating an entire square as a circle.

The branding acquisition endpoint returns PNG/JPEG/WebP bytes. Both discovery imports and manual uploads use `/api/schools/<school_id>/logo/process`, which delegates to the shared service. `primary_logo` and linked `round_master_path` supply the generated master to school review and identity consumers. The route also stores the scorebug rendition. `logo_certification`/`broadcast_identity` retain the existing authorization and generated-monogram path for broadcast identities. OBS/browser sources and the production theme runtime consume those identities; their engines already use containment in their logo image slots.

Lafayette's actual uploaded original, processed files, live database record, and source URL are absent from this checkout. Therefore this confirms an underlying clipping mechanism, not a definitive forensic assessment of that particular remote file. Source cropping, its native dimensions, SVG viewBox defects, and the presence of every gold border on that source remain unverified. No substitute logo was downloaded or reconstructed.

## Files changed

| File | Purpose |
| --- | --- |
| `logo_service.py` | Shared transparent, aspect-preserving fit with 6% nominal margins; no crop or alpha mask; EXIF orientation; truthful rendition metadata. Compatibility method and legacy record fields retained. |
| `routes/logo_routes.py` | Content/version-based filenames retain earlier originals and derivatives and avoid stale cached renditions. Existing legacy URLs remain served. |
| `static/style.css` | Removes circular image clipping from the processed review image; fits review broadcast logo within its existing circular frame. |
| `templates/index.html` | Contained transparent discovery candidates; source-original link and explicit reprocess action; accurate candidate labels. |
| `static/csrn-production-theme-runtime.css` | Fits artwork within the inscribed square of Heritage's existing round logo frame. Frame geometry and frozen engine styling remain intact. |
| `tests/test_logo_service.py` | Boundary/gold-corner, wide/tall/square, alpha/margin, original-byte/provenance, approval-reset, and review-fit regression checks. |
| `tests/test_logo_routes.py` | Versioned-path expectations and isolated first-run setup fixture for logo-route tests. No production onboarding changes. |
| `tests/test_logo_routes_blueprint.py` | Versioned paths and preservation of previous imported/legacy files. |
| `tests/test_logo_containment_browser.py` | Opt-in Chromium component and three frozen-theme geometry checks with synthetic PNG and SVG fixtures. |
| `CSRN_PROJECT_BIBLE.md` | Logo-repair continuity note only. |
| `docs/TEAM_LOGO_RENDERING_REPAIR.md` | This report. |

## Changes and compatibility

The shared derivative now preserves the complete source canvas, including transparent margins. Its longest dimension fits in 88% of the output canvas; the original bytes remain unchanged. Circular marks remain circular, rectangles retain their proportions, and artwork at the source boundary remains intact. Existing large transparent margins remain visible; the repair does not silently trim source whitespace to enlarge a mark.

Legacy names such as `round_master_path` and `normalize_round_logo` remain supported. New output filenames include a hash of the source bytes and fitting revision, preventing a newly imported candidate from overwriting an old image referenced by another consumer. The existing catalog remains a single primary-logo record; this is file preservation, not a new catalog history feature.

The original-source link uses the existing school-logo serving route. Reprocess downloads the preserved original and explicitly submits it through the existing authenticated processing endpoint. It creates a pending candidate and resets school, metadata, and linked-logo approval state. It does not auto-approve or migrate existing team data.

Approved Friday Night Stadium, 8-Bit Gameday, and Heritage Press engines and artwork have zero modifications. No scoring, roster/DragonFly integration, statistics, audio, layout-container dimensions, or team records were edited. Heritage's circular frame is unchanged; the artwork within it is smaller enough to avoid clipping square corners. Existing filters, newspaper treatment, and animations remain owned by their engines.

## Validation

- Focused logo, route, identity UI, scorebug, relevant theme and social-asset checks: **77 passed**.
- Chromium Headless Shell 134 component/theme harness: **1 passed**. Used the existing engine JavaScript and CSS, a 1920x1080 viewport, boundary square, wide/tall rectangles, circle, transparent PNG with substantial margins, and direct SVG rendering. Checked containment, a rendered gold corner, image loading, and unchanged 1920x1080 theme root dimensions across logo shapes.
- All inline Command Center JavaScript passed Node syntax checking (one script block).
- Developer validation compiled 545 tracked Python files, passed whitespace checking, and passed version/build identity checking.
- Full untouched baseline: **3069 passed, 179 failed**.
- Full patched suite: **3079 passed, 175 failed, 1 skipped** (opt-in browser test run separately).
- JUnit failure-ID comparison: **zero new failures**. The four fewer failures are logo-route tests whose isolated fixture now bypasses first-run setup. Other failures include pre-existing onboarding-gated endpoints, stale assertions, and environment-dependent media checks; they were left untouched.
- Execution host used Python 3.12. Project-supported Windows/Python 3.13.14 execution remains outstanding. No environment lock was changed.

## Screenshots and practical limits

The package contains `components-before.png`, `components-after.png`, and after screenshots of the three frozen theme engines. These are isolated component/theme harness captures with a clearly synthetic boundary fixture. They are not Lafayette screenshots, an OBS capture, or evidence of the unpushed Windows build. Before uses the original baseline processing function and circular review style; after uses the repaired processing and current application styles.

Native SVG display was exercised in the browser harness. SVG import/rasterization was already unsupported by the acquisition service and Pillow decoder; this repair does not add an SVG converter or alter import policy. Broken SVG viewBoxes cannot be repaired by CSS. Theme animation code was untouched, but a complete animation/state timing regression and an actual OBS browser-source session were not performed.

Completion against the user's Lafayette criterion requires applying the small patch to the real development worktree, opening its preserved original, reprocessing that source, reviewing the pending candidate, explicitly approving it if appropriate, and capturing the real management, candidate, broadcast, and OBS scorebug results. If the original itself lacks borders, reacquire a complete image from the authorized source; do not reconstruct missing details.

## Apply without replacing unpushed work

Use the existing Windows development folder. Preserve its current branch, Git status, and uncommitted edits. Do not replace entire files with copies from this checkout, reset the branch, or pull/merge main as a shortcut.

The package supplies a focused unified patch. Check it first:

```powershell
git status --short --branch
git apply --check "C:\path\to\CSRN-Team-Logo-Repair.patch"
```

If the check succeeds, apply the patch with `git apply` and inspect `git diff`. If it fails, integrate only the named logo-related hunks into the current files, retaining newer local work. Do not force an apply or discard changes. Run the focused tests and project validation in the supported development environment, then perform the Lafayette/OBS verification described above. No production deployment is authorized by this package.
