# Contribution Statement

**Team:** _SWE Final Project Team_
**Topic:** _Topic 1 — Lost & Found Matching Service_
**Repository:** _[https://github.com/ParvinSalahov/SWE-final-proj](https://github.com/ParvinSalahov/SWE-final-proj)_
**Final tag:** `v1.0-final`
**Submission date:** _2026-09-18_

---

## How to fill this in

This is the single piece of evidence we use to assess **individual contribution** within the team. Rules:

1. Every member writes their own three subsections (Owned, Co-owned, Reviewed).
2. **Be specific.** "Worked on the backend" is not acceptable; "implemented `src/services/ai_service.py` and `src/concurrency/pipeline.py`, owned PRs #4, #7, #11" is.
3. The committed-percentages must add to 100% and approximately match `git shortlog -sn` on the `main` branch.
4. All three members must sign at the bottom. Unsigned submissions are returned ungraded.

If one member contributed less than 10% without a documented reason (illness, emergency), the team loses 5 points automatically per the rubric.

---

## Member A — _Mahammad Javadzade_ (`@MahammadMaga`)

**Owned (sole author of these files / PRs):**
- `src/storage/database.py`
- `src/storage/repository.py`
- `src/concurrency/pipeline.py`
- `scripts/bench.py`
- PRs: #9, #10

**Co-owned (paired or substantially edited):**
- `src/models.py` (with Teymur Alasgarov)
- `src/services/item_service.py` (with Teymur Alasgarov)
- `tests/test_concurrency.py` (with Parvin Salahov)

**Reviewed (PRs reviewed and merged):**
- PRs: #11, #12, #13

**Approximate share of commits:** _[30]_%

---

## Member B — _Teymur Alasgarov_ (`@Ktsarvi`)

**Owned:**
- `src/api.py`
- `src/cli.py`
- `src/services/ai_service.py`
- PRs: #16, #17

**Co-owned:**
- `src/services/item_service.py` (with Mahammad Javadzade)
- `src/models.py` (with Mahammad Javadzade)
- `README.md` (with Parvin Salahov)

**Reviewed:**
- PRs: #9, #14, #15

**Approximate share of commits:** _[38]_%

---

## Member C — _Parvin Salahov_ (`@ParvinSalahov`)

**Owned:**
- `tests/test_database.py`
- `tests/test_api.py`
- `tests/test_cli.py`
- `ai/providers/openai.py`
- PRs: #11, #12, #15

**Co-owned:**
- `tests/test_concurrency.py` (with Mahammad Javadzade)
- `README.md` (with Teymur Alasgarov)
- `.env.example` (with Mahammad Javadzade)

**Reviewed:**
- PRs: #10, #16, #17

**Approximate share of commits:** _[32]_%

---

## AI tool disclosure (also in §10 of the report)

We used AI coding assistants as follows. Each item lists the module, the assistant, and what the team did with the output.

| Module / file | Assistant | What we did with it |
|---|---|---|
| `src/concurrency/pipeline.py` | GitHub Copilot | Drafted initial worker-pool structure; team revised queue lifecycle, shutdown handling, and benchmark hooks. |
| `tests/test_api.py`, `tests/test_cli.py` | GitHub Copilot | Proposed test cases and fixtures; team kept relevant assertions and rewrote failing edge cases manually. |
| `README.md` and command snippets | GitHub Copilot | Suggested wording and command examples; team validated commands and edited for project-specific behavior. |

We affirm that we **can defend every line of code** in this repository during the oral defense. "The AI wrote it" is not an answer we will use.

---

## Signatures

By signing below, we affirm that:
- The contributions described above are accurate.
- The commit percentages reflect actual work, not artificially split commits.
- Every line of code in the repository can be defended by at least one team member.
- AI assistant usage has been disclosed as described above.

| Member | Signature | Date |
|---|---|---|
| _Mahammad Javadzade_ | __________________________ | __________ |
| _Teymur Alasgarov_ | __________________________ | __________ |
| _Parvin Salahov_ | __________________________ | __________ |
