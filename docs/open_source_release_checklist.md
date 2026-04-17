# Open Source Release Checklist

Use this when extracting `solaris/` into its own public GitHub repository.

## Repository Prep

- [ ] Copy or split out the `solaris/` directory into a standalone repository
- [ ] Keep `README.md`, `LICENSE`, `.gitignore`, `.env.example`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and `SECURITY.md` at repo root
- [ ] Preserve the `.github/` templates if you want GitHub issues and PRs to use them
- [ ] Optional helper: `python .\tools\extract_standalone_repo.py --dest <path> --force`

## Validation

- [ ] `python -m pip install -e .[dev]`
- [ ] `pytest`
- [ ] `python .\\run_retrieval_evals.py --json`
- [ ] `python .\\run_archive_state_model_checks.py --json`
- [ ] Check that documentation links still resolve after extraction
- [ ] Optional helper: `python .\tools\validate_public_repo.py --repo <path>`

## Packaging Decisions

- [x] Confirm the final license choice: `MPL-2.0`
- [x] Publish as both `alpha` and `research preview`
- [x] Ship the standalone frontend in `v0.1` as an optional alpha surface
- [x] Keep only generic host/runtime examples in the public Solaris repo

## Public Positioning

- [x] Keep the framing honest: archive-grounded editorial memory substrate
- [x] Avoid overselling Solaris as a generic AGI memory solution
- [x] Make sure the README points clearly to the proof and eval docs

## Nice-To-Haves

- [ ] Add screenshots or a short demo clip if the standalone surface is part of the release
- [ ] Add CI once the extracted repo layout is stable; intentionally deferred for the first public alpha
- [ ] Add a changelog once external versioning begins
