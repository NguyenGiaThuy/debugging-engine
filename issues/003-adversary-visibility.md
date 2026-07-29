# Adversary role not visible in chat / may be starved

## Symptoms
During investigations, the Adversary handoff does not appear in chat (same class of complaint as Verifier). Users cannot tell whether dialectic challenge is scheduled.

## Clues
- Skill says announce roles but highlights “especially Verifier / Implementer”; Adversary is easy to omit.
- After scheduler reorder, proposed experiments are approved before the competing-hypothesis Adversary branch — so Analyst submitting hyp+experiment in one batch can skip Adversary entirely.
- Competing-interpretation Adversary path is skipped when the sole interpretation is SUPPORTS.

## Success criteria
- With one hypothesis and a proposed (not yet approved) experiment, `next` returns Adversary for an alternative hypothesis/challenge.
- Approved/runnable experiments still prefer Implementer/Verifier (do not reintroduce Verifier starvation).
- Skill requires announcing **every** role handoff including Adversary, with a clear chat format.
- Regression tests cover Adversary-before-approve and Verifier-after-approve.
- Suite green; fix applied and verified.
