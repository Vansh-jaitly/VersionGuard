# Teammate delivery

`VersionGuard-teammate.zip` is the ready-to-share archive. It includes source,
CI workflow, tests, the fixed dataset/split/cache, Qwen results, integration
verification and teammate instructions. `HANDOFF_MANIFEST.json` inside the
archive records every delivered file's SHA-256 checksum and size.

After extracting, start with `VersionGuard/docs/HANDOFF.md`. The teammate's
remaining work is the CodeLlama 7B evaluation, hosted GitHub demonstrations,
Qodo/Sweep evidence and presentation. No additional Qwen run is needed.

Regenerate or verify the archive from the original project directory:

```powershell
python -m scripts.teammate_bundle
python -m scripts.teammate_bundle --verify deliverables/VersionGuard-teammate.zip
```

The archive has been verified locally and has not been sent or published.
