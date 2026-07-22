Contributing
============

Thank you for your interest in contributing. Small, focused pull requests are easiest to review.

How to contribute
-----------------

1. Fork the repository and create a branch for your change.
2. Run tests locally:

```bash
python3 -m pytest -q
```

3. Follow the code style in the repository. Keep changes small and focused.
4. Open a PR describing the change, why it's needed, and any testing you've done.

Testing and quality
-------------------

- Unit tests live under `tests/` and must pass. CI runs the `daily-run.yml` workflow.
- If your change touches prompts or the model client, explain regression tests or config used.

Communication
-------------

- Open an issue first for non-trivial features or breaking changes to get feedback.

License
-------

By contributing you agree that your contributions will be licensed under the project's MIT license.
