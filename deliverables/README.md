# Teammate delivery

`VersionGuard-evaluation-only.zip` is the revised ready-to-share archive. It includes source,
CI workflow, tests, the fixed dataset/split/cache, Qwen results, integration
verification and teammate instructions. `HANDOFF_MANIFEST.json` inside the
archive records every delivered file's SHA-256 checksum and size.

The revised package contains 110 checksum-verified files, including the real
hosted integration evidence and named-tool service findings.

After extracting, start with `VersionGuard/docs/EVALUATION_ONLY.md`. The teammate's
remaining work is only CodeLlama 7B environment verification and evaluation.
The project owner retains integrations, testing evidence and submissions.
No additional Qwen run is needed.

Regenerate or verify the archive from the original project directory:

```powershell
python -m scripts.teammate_bundle --output deliverables/VersionGuard-evaluation-only.zip
python -m scripts.teammate_bundle --verify deliverables/VersionGuard-evaluation-only.zip
```

The user reports sending an earlier archive. The current regenerated archive
contains revised evaluation-only instructions; its regeneration does not
establish that this newer version was sent. Hosted source and demonstration
links are recorded in `docs/LIVE_EVIDENCE.md`.
