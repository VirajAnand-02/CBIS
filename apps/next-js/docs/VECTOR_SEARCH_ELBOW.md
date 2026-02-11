# Dynamic Vector Cutoff (Elbow) Search

This document explains, in detail, how the Postgres function `cbis_vector_search_elbow(...)` works.

It implements **pgvector nearest-neighbor search** plus a **dynamic distance cutoff** based on an “elbow” (a sharp jump) in the sorted distance curve.

- Implementation SQL: [prisma/vector_search_elbow.sql](../prisma/vector_search_elbow.sql)
- Called from Next.js via Prisma: [lib/db.ts](../lib/db.ts) (function `searchByVectorElbow`) and used by [lib/search-manager.ts](../lib/search-manager.ts)

---

## Goal

Given a query embedding vector, you typically run:

- “return top N nearest vectors”

But a fixed `N` is often wrong:

- Some queries have **many good matches** (you want more results)
- Some queries have **few good matches** (you want fewer results)

The **elbow cutoff** tries to detect where results stop being “close” and start being “far”.

---

## Inputs / Outputs

### Inputs

The function signature (simplified):

- `query_vec vector(512)`
- `top_k int` (default 100): how many nearest neighbors we examine to find an elbow
- `min_results int` (default 5): never return fewer than this
- `max_results int` (default 50): never return more than this
- `sharpness real` (default 3.0): how strong the jump must be to count as an elbow
- Filters:
  - `mime_types text[]`
  - `is_document boolean`, `has_people boolean`, `is_screenshot boolean`, `is_animal boolean`
  - `min_nima_score real`, `max_nima_score real`

### Outputs

Returns a table of results with:

- blob metadata (id, filename, mime, size, createdAt, etc)
- `distance` = cosine distance (pgvector `<=>`)
- `similarity_score` = `1 - distance`
- `rank` = 1..N (nearest first)

Important: `rank` is computed **inside the filtered candidate set**.

---

## Distance Curve and the “Elbow”

### Step 1 — Build the ranked candidate list (`candidates` CTE)

The function first collects the nearest neighbors, *after applying filters*, and ranks them:

- Compute distance for each candidate:

  $$d_i = \text{distance}(v_i, q) = (v_i <=> q)$$

- Sort ascending (nearest first)
- Assign rank:

  $$\text{rank}(i) = 1,2,3,\dots$$

This ranked list is the **distance curve**: $(d_1, d_2, ..., d_n)$.

It is non-decreasing:

$$d_1 \le d_2 \le \cdots \le d_n$$

Also, we cap how many points we look at by limiting to:

- `LIMIT GREATEST(top_k, max_results, min_results)`

So the elbow detection is computed over (at most) those top candidates.

---

### Step 2 — Compute consecutive distance jumps (`diffs` CTE)

For each rank $i$, compute the step-size from the previous point:

$$\Delta_i = d_i - d_{i-1}$$

In SQL this is:

- `diff = distance - LAG(distance) OVER (ORDER BY rank)`

Notes:

- For rank 1 there is no previous point, so `diff` is `NULL`.
- A **large** $\Delta_i$ means there’s a sudden worsening between item $i-1$ and item $i$.

---

### Step 3 — Decide if a “big jump” is meaningful (`diff_stats` + `best_jump` CTE)

We compute two summary stats across the diffs:

- `max_diff` = $\max(\Delta_i)$
- `median_diff` = median of $\Delta_i$ (a robust “typical” step size)

Then we only treat the maximum jump as a real “elbow” if it is **sharp enough**:

$$\text{max\_diff} \ge \text{sharpness} \cdot \text{median\_diff}$$

- Default `sharpness = 3.0` means: the biggest jump must be at least **3×** the median step size.

Edge cases handled in SQL:

- If `median_diff` is `NULL` (e.g., too few points), any positive `max_diff` can qualify.
- If `median_diff = 0` and `max_diff > 0`, that also qualifies.

If it qualifies, `best_jump` picks:

- the row with the biggest `diff`, and if ties, the earliest rank.

This yields `jump_rank`.

---

### Step 4 — Convert the elbow into a keep-count (`limits` + `keep` CTE)

If a qualifying jump exists at `jump_rank`, the function keeps everything **before** the jump:

$$\text{elbow\_n} = \text{jump\_rank} - 1$$

Rationale:

- The jump at rank `jump_rank` means item `jump_rank` is where results become much worse.
- So we cut off at the previous item.

If **no** qualifying jump is found, the function falls back to:

$$\text{elbow\_n} = \text{max\_results}$$

Finally, clamp to the guardrails:

$$\text{keep\_n} = \min(n, \max(\text{min\_results}, \min(\text{max\_results}, \text{elbow\_n})))$$

Where $n$ is the number of candidates available.

---

### Step 5 — Return only the kept rows

The final `SELECT` returns only candidates with:

- `rank <= keep_n`

and orders by rank.

---

## What “sharpness” really does

`sharpness` controls aggressiveness:

- Higher `sharpness` ⇒ elbow requires a more dramatic jump ⇒ **more results** (less often cuts early)
- Lower `sharpness` ⇒ elbow triggers more easily ⇒ **fewer results**

A rough mental model:

- If your distance curve is smooth (no clear jump), the function will likely return `max_results`.
- If there’s a clear cluster (tight distances) and then a gap, it cuts at that gap.

---

## Pagination behavior in Next.js

The database function itself does **not** apply `OFFSET`/`LIMIT` for paging.

Instead:

1. It returns the “kept” set (up to `max_results`) after elbow cutoff.
2. The Next.js layer paginates that array using `offset` and `limit`.

This means:

- Pagination is supported.
- `total_count` represents the size of the elbow-kept set (not the total number of embeddings in the DB).

---

## Worked example (conceptual)

Assume the sorted distances are:

| rank | distance $d_i$ | diff $\Delta_i$ |
|------|----------------|-----------------|
| 1 | 0.10 | — |
| 2 | 0.11 | 0.01 |
| 3 | 0.12 | 0.01 |
| 4 | 0.13 | 0.01 |
| 5 | 0.30 | 0.17 |
| 6 | 0.31 | 0.01 |

Here:

- median(diff) ≈ 0.01
- max(diff) = 0.17

With `sharpness = 3.0`:

- `0.17 >= 3 * 0.01` ⇒ qualifies as an elbow
- biggest jump is at rank 5 ⇒ keep `5 - 1 = 4`

So it returns ranks 1–4.

---

## Limitations / design notes

- This is a **1D elbow on consecutive gaps**. It’s simple and fast in SQL, but it’s not the only elbow definition.
- If results are noisy (no clear gap), it intentionally falls back to `max_results`.
- The elbow is computed **after filters**, which is usually what you want (you don’t want a cutoff determined by items you would filter out anyway).

---

## Tuning checklist

If you see:

- Too few results: increase `max_results` and/or increase `sharpness`
- Too many weak results: decrease `max_results` and/or decrease `sharpness`
- Unstable elbow: increase `top_k` (more points makes the median diff more stable)
