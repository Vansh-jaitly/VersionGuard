# Hosted Integration Evidence

Additional study evidence: the teammate's CodeLlama test run is received and
validated independently, with all nine documentation-assisted repair gains
replayed in pinned Docker. `docs/TEAMMATE_INTAKE.md` records its positive
within-model finding and the mixed-runtime limitation on the combined report.

Verified 8 October 2026. Repository: https://github.com/Vansh-jaitly/VersionGuard

## Actual Actions and PR outcomes

| Evidence | Outcome | Link |
|---|---|---|
| Initial source publication | Commit `49b3265d3e9b924c61278e7ca58723975c884b5a` | [Commit](https://github.com/Vansh-jaitly/VersionGuard/commit/49b3265d3e9b924c61278e7ca58723975c884b5a) |
| Initial hosted CI | Failed: one test accidentally required downloaded benchmark data | [Run](https://github.com/Vansh-jaitly/VersionGuard/actions/runs/37764740097) |
| Corrected baseline CI | Passed: lint, 92 tests + 2 subtests, coverage, fixtures and guard demo | [Run](https://github.com/Vansh-jaitly/VersionGuard/actions/runs/37765113419) |
| Removed-API PR | Open integration demonstration | [PR #1](https://github.com/Vansh-jaitly/VersionGuard/pull/1) |
| PR before correction | Failed only at changed-file guard; VG001 at `demo/pr_example.py:5` | [Red run](https://github.com/Vansh-jaitly/VersionGuard/actions/runs/37765294720) |
| Qwen repair comment | Posted against head `f9b1848b17b8a6fb2d6ddff636dd8e822053db14` | [Comment](https://github.com/Vansh-jaitly/VersionGuard/pull/1#issuecomment-6058144727) |
| PR after reviewed correction | Passed at head `06d4606dd48cc85f5298f487dd802e49dd622a69` | [Green run](https://github.com/Vansh-jaitly/VersionGuard/actions/runs/37766024901) |
| Independent verification follow-up | Discloses failed model proposal and passing reviewed correction | [Comment](https://github.com/Vansh-jaitly/VersionGuard/pull/1#issuecomment-6058352354) |

The fresh-checkout failure was resolved by giving the import validation test a
temporary synthetic dataset. The production validator still compares real input
hashes. CI does not need to download the benchmark for that unit test.

## Model proposal versus tested correction

The model proposed `np.isscalar(array)`. Its static guard was clean, but its
runtime result was wrong: it returned a Boolean instead of a Python scalar.
The reviewed correction uses `array.item()`. Independent Docker verification
uses Python 3.12 and NumPy 1.26.4, with network disabled during execution.
The model failed the first integer conversion assertion; the correction passed
integer, float, one-element multidimensional and multiple-element rejection checks.

See `results/live-pr-repair.json`, `results/live-pr-repair.md` and
`results/live-pr-verification.json`. Reproduce the independent verification with
`python -m scripts.verify_pr_demo`. Its reviewed input is `demo/fixed.py`, the
same source text as the corrected PR file.

The repair comment is a proposal at the recorded earlier commit, not a claim
that Qwen produced the accepted correction. Main is not branch-protected, and
the demo PR remains open for review. No deployment or automatic merge is claimed.

## Real vector RAG demonstration

`results/rag-demo.json` records a real LangChain/Chroma retrieval and local Qwen
answer for scalar conversion. The answer passes NumPy 1.25.0 Docker checks.
The retrieved sources (`numpy.flexible.take`, `.nonzero`, `.astype`) are unrelated
to the required conversion. The static guard reports `not_checked` because the
host is NumPy 1.26.4. This demonstrates execution of the retrieval pipeline,
not successful grounding or a causal documentation benefit.

## Named-tool availability findings

The Qodo attempt used official `@qodo/command` 0.36.0, an authenticated account,
read-only filesystem access and an isolated directory containing only the two
approved source files and test prompt. The service responded:

> As mentioned in the email you received, Qodo Command has been discontinued.
> You can still get automated code reviews by connecting your Git provider at
> https://app.qodo.ai.

The npm package also reports "Package no longer supported." No tests were
generated; a successful process exit is not test-generation success. The prompt
and service notice are saved in `results/tool-availability/`. Current
[Qodo IDE documentation](https://docs.qodo.ai/qodo-ide) describes code review
workflows. Its existence does not establish that the former test-generation
workflow is still available. Existing 92 tests are project-authored, not Qodo output.

Sweep's [official README](https://github.com/sweepai/sweep) states that the team
is now building a JetBrains coding assistant. GitHub app API lookups for both
`sweep` and `sweep-ai` returned HTTP 404. No working legacy GitHub app or Sweep PR
was established. These observations are narrower than claiming every Sweep
product is unavailable.

The named-tool rubric items remain unmet. Obtain instructor acceptance for a
currently supported alternative, or supply working access to the requested
tools. Neither local Qwen nor this coding assistant is silently substituted for
CodiumAI/Codeium or Sweep. The rest of the prototype and hosted CI are independent
of these external service limitations.
