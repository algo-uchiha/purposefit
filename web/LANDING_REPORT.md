# Landing page implementation report

- Added a landing experience with five stacked panels: hero, problem facts, four-step process, fixture-driven recipient choices, and results with limitations.
- Added hash navigation. `#/` opens the landing page; `#/workbench?scenario=CS-S3` opens the existing workbench with that scenario selected. The workbench header returns to `#/`.
- Loaded scores, leakage, findings, released tables, and residual risks from the existing fixtures. The fixtures do not contain the brief's example 0.98 composite or a 26-column count for the unseen export, so those values are not asserted.
- Lenis and IntersectionObserver provide smooth scrolling and one-time content reveals. Reduced-motion users get regular stacked sections without Lenis or reveal motion.

## Tuning motion

Edit the CSS custom properties at the top of `src/landing/landing.scss`:

- `--landing-motion-duration` controls reveal transition duration.
- `--landing-motion-easing` controls reveal easing.
- `--landing-rise-distance` controls the reveal offset.
- `--landing-incoming-shadow` controls the incoming panel's top shadow.

Lenis duration is initialized in `src/landing/Landing.tsx` as `duration: 1.05`.
