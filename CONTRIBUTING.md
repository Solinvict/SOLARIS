# Contributing To Solaris

Thanks for taking Solaris seriously enough to improve it.

This project is still in `alpha`, so the most helpful contributions are the ones that improve clarity, correctness, provenance, or eval coverage without weakening the core design principles.

## Guiding Principles

- keep the archive as source truth
- treat editorial memory as distinct from storage
- prefer inspectable behavior over clever opacity
- do not store projected patterns as durable truth
- favor relative documentation links over local absolute paths

## Local Setup

From `solaris/`:

```powershell
python -m pip install -e .[dev]
```

Optional frontend setup:

```powershell
cd .\frontend
npm install
```

## Run The Main Checks

Core tests:

```powershell
pytest
```

Retrieval eval harness:

```powershell
python .\run_retrieval_evals.py --json
```

Archive-state proof checks:

```powershell
python .\run_archive_state_model_checks.py --json
```

If you change retrieval, query semantics, or editorial behavior, please run the eval harnesses in addition to the unit tests.

## What Kinds Of Contributions Help Most

- bug fixes in derivation, review, retrieval, or explainability
- eval corpus expansions
- documentation improvements
- graph and pattern realism improvements
- integration examples that keep Solaris extractable

## Documentation Expectations

- use relative links that work on GitHub
- avoid local machine paths in committed docs
- distinguish clearly between what Solaris proves, what it implements, and what is still aspirational

## Pull Request Notes

Helpful PRs usually include:

- a short explanation of the problem
- the concrete behavioral change
- any relevant tests or eval updates
- notes about tradeoffs or remaining caveats

If your change affects retrieval behavior, divergence semantics, or pattern ranking, mention it explicitly so reviewers know to evaluate it with the right lens.

## License Of Contributions

Solaris is licensed under `MPL-2.0`.

By contributing to Solaris, you agree that your contributions to the project are provided under that same license.

## Community Expectations

Please also read:

- [Code Of Conduct](./CODE_OF_CONDUCT.md)
- [Security Policy](./SECURITY.md)
