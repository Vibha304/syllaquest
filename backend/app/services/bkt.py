"""Module 5 - Bayesian Knowledge Tracing (BKT).

Each (student, topic) pair holds P(L) = probability the topic is mastered.
After every response we apply the standard BKT posterior + learning transition.
"""
P_INIT = 0.30      # cold-start prior
P_LEARN = 0.10     # chance of learning from one practice opportunity
P_SLIP = 0.10      # knows it but answers wrong
GUESS = {"mcq": 0.25, "tf": 0.35, "short": 0.05}  # does not know it but answers right
DIFF_SHIFT = {"easy": 0.05, "medium": 0.0, "hard": -0.05}

WEAK_BELOW = 0.50
MASTERED_AT = 0.85
MIN_ATTEMPTS_WEAK = 2
MIN_ATTEMPTS_MASTERED = 3


def prior_for(difficulty_mix: dict | None = None) -> float:
    """Cold-start: topics whose question pool is mostly hard start a little lower."""
    if not difficulty_mix:
        return P_INIT
    total = sum(difficulty_mix.values()) or 1
    hard_share = difficulty_mix.get("hard", 0) / total
    easy_share = difficulty_mix.get("easy", 0) / total
    return round(min(0.4, max(0.2, P_INIT + 0.08 * easy_share - 0.08 * hard_share)), 3)


def update(p: float, correct: bool, qtype: str = "mcq", difficulty: str = "medium") -> float:
    guess = min(0.5, max(0.02, GUESS.get(qtype, 0.2) + DIFF_SHIFT.get(difficulty, 0)))
    slip = P_SLIP + (0.05 if difficulty == "hard" else 0)
    if correct:
        posterior = p * (1 - slip) / (p * (1 - slip) + (1 - p) * guess)
    else:
        posterior = p * slip / (p * slip + (1 - p) * (1 - guess))
    return round(min(0.995, max(0.01, posterior + (1 - posterior) * P_LEARN)), 4)


def status(p: float, attempts: int) -> str:
    if attempts == 0:
        return "new"
    if p >= MASTERED_AT and attempts >= MIN_ATTEMPTS_MASTERED:
        return "mastered"
    if p < WEAK_BELOW and attempts >= MIN_ATTEMPTS_WEAK:
        return "weak"
    return "learning"
