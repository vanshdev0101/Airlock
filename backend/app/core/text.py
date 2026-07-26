"""Small text helpers shared by the fetcher and the scanners.

`levenshtein` lives here rather than in either caller because the fetcher
imports the scanner package; a scanner importing the fetcher back would be a
cycle.
"""


def damerau_levenshtein(a: str, b: str) -> int:
    """Edit distance that counts an adjacent transposition as one edit.

    Plain Levenshtein scores `requests` → `reqeusts` as 2, because it has to
    delete and reinsert. Swapping two neighbouring characters is both the
    commonest typo and the commonest squatting technique, so it has to cost 1
    or the check misses the attack it exists for.

    This is the optimal-string-alignment variant: it does not allow a
    transposed substring to be edited again, which is fine for names.
    """
    la, lb = len(a), len(b)
    d = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        d[i][0] = i
    for j in range(lb + 1):
        d[0][j] = j

    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)

    return d[la][lb]


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        return levenshtein(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for ca in a:
        curr = [prev[0] + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (ca != cb)))
        prev = curr
    return prev[-1]
