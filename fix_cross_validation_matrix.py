#!/usr/bin/env python3
"""
ET-12: Fix Cross Validation Matrix
- Use original scores instead of buckets
- Change matrix size from 6x6 to 7x6
- Update axes labels to match requirements
"""

with open('analytics_service.py', 'r') as f:
    content = f.read()

# 1. Add matrix range mapping functions after _get_distribution_bin
matrix_functions = '''
def _get_claim_range_for_matrix(score):
    """
    ET-12: Map continuous score to matrix range index for Cross Validation Matrix
    Ranges: [>4, 3-4, 2-3, 1-2, 0-1, No score] → [0, 1, 2, 3, 4, 5]
    """
    if score is None:
        return 5  # No score
    if score > 4:
        return 0  # >4
    if score >= 3:
        return 1  # 3-4
    if score >= 2:
        return 2  # 2-3
    if score >= 1:
        return 3  # 1-2
    if score >= 0:
        return 4  # 0-1
    return 5  # No score

def _get_fit_range_for_matrix(score):
    """
    ET-12: Map continuous score to matrix range index for Cross Validation Matrix
    Ranges: [5/5, 4/5, 3/5, 2/5, 1/5, 0/5, No score] → [0, 1, 2, 3, 4, 5, 6]
    """
    if score is None:
        return 6  # No score
    if score >= 5:
        return 0  # 5/5
    if score >= 4:
        return 1  # 4/5
    if score >= 3:
        return 2  # 3/5
    if score >= 2:
        return 3  # 2/5
    if score >= 1:
        return 4  # 1/5
    if score >= 0:
        return 5  # 0/5
    return 6  # No score

'''

# Insert after _get_distribution_bin function
insertion_point = 'def _is_completed(cand: Candidate) -> bool:'
content = content.replace(insertion_point, matrix_functions + insertion_point)

# 2. Update heatmap matrix size (6x6 → 7x6)
content = content.replace(
    '        # ET-12: heatmap counts (0..5 × 0..5) where 0 = No Score\n        # 6x6 matrix: rows/cols are [0,1,2,3,4,5]\n        heatmap = [[0 for _ in range(6)] for _ in range(6)]',
    '        # ET-12: heatmap counts for Cross Validation Matrix\n        # 7x6 matrix: rows=[5/5,4/5,3/5,2/5,1/5,0/5,No Score], cols=[>4,3-4,2-3,1-2,0-1,No Score]\n        heatmap = [[0 for _ in range(6)] for _ in range(7)]'
)

# 3. Update heatmap logic to use original scores
old_heatmap_logic = '''            # Keep bucket indices for heatmap (0..5, unchanged)
            claim_idx = claim_b if claim_b is not None else 0
            rel_idx = rel_b if rel_b is not None else 0

            # Update distributions (7 bins for charts)
            dist_claim[claim_dist_idx] += 1
            dist_rel[rel_dist_idx] += 1

            # ET-12: Track actual average values for statistics (NOT buckets)
            # This ensures Mean/Median/StdDev are calculated from real scores, not rounded buckets
            if claim_avg is not None:
                claim_values.append(claim_avg)
            if rel_score is not None:
                relevancy_values.append(rel_score)

            # Update heatmap (6x6 matrix with 0..5 indices)
            heatmap[rel_idx][claim_idx] += 1'''

new_heatmap_logic = '''            # Update distributions (7 bins for charts)
            dist_claim[claim_dist_idx] += 1
            dist_rel[rel_dist_idx] += 1

            # ET-12: Track actual average values for statistics (NOT buckets)
            # This ensures Mean/Median/StdDev are calculated from real scores, not rounded buckets
            if claim_avg is not None:
                claim_values.append(claim_avg)
            if rel_score is not None:
                relevancy_values.append(rel_score)

            # ET-12: Update heatmap using original scores (7x6 matrix)
            # Rows: [5/5, 4/5, 3/5, 2/5, 1/5, 0/5, No Score]
            # Cols: [>4, 3-4, 2-3, 1-2, 0-1, No Score]
            claim_matrix_idx = _get_claim_range_for_matrix(claim_avg)
            rel_matrix_idx = _get_fit_range_for_matrix(rel_score)
            heatmap[rel_matrix_idx][claim_matrix_idx] += 1'''

content = content.replace(old_heatmap_logic, new_heatmap_logic)

# 4. Update heatmap axes labels
old_axes = '''            "heatmap": {
                # 6x6 matrix: rows=relevancy [0..5], cols=claim [0..5]
                "matrix": heatmap,
                # Claim descending: 5,4,3,2,1,0 (No Score at end)
                "axes": {"relevancy": [0, 1, 2, 3, 4, 5], "claim_validity": [5, 4, 3, 2, 1, 0]},'''

new_axes = '''            "heatmap": {
                # ET-12: 7x6 matrix for Cross Validation Matrix
                # Rows: [5/5, 4/5, 3/5, 2/5, 1/5, 0/5, No Score]
                # Cols: [>4, 3-4, 2-3, 1-2, 0-1, No Score]
                "matrix": heatmap,
                "axes": {
                    "relevancy": ["5/5", "4/5", "3/5", "2/5", "1/5", "0/5", "No Score"],
                    "claim_validity": [">4", "3-4", "2-3", "1-2", "0-1", "No Score"]
                },'''

content = content.replace(old_axes, new_axes)

# 5. Update cells generation for 7x6 matrix
old_cells = '''                "cells": [
                    {
                        "relevancy": r,
                        "claim": c,
                        "candidates": cell_members.get((r, c), []),
                    }
                    for r in range(6)
                    for c in range(6)
                ],'''

new_cells = '''                "cells": [
                    {
                        "relevancy": r,
                        "claim": c,
                        "candidates": cell_members.get((r, c), []),
                    }
                    for r in range(7)  # 7 rows for Fit Score ranges
                    for c in range(6)   # 6 cols for Claim Validity ranges
                ],'''

content = content.replace(old_cells, new_cells)

# 6. Update cell_members to use matrix indices instead of bucket indices
old_cell_members = '''            # Cell members for heatmap (use 0..5 indices)
            cell_members[(rel_idx, claim_idx)].append({'''

new_cell_members = '''            # ET-12: Cell members for heatmap using matrix range indices
            cell_members[(rel_matrix_idx, claim_matrix_idx)].append({'''

content = content.replace(old_cell_members, new_cell_members)

with open('analytics_service.py', 'w') as f:
    f.write(content)

print("✅ Cross Validation Matrix updated!")
print("   - Matrix size: 6x6 → 7x6")
print("   - Uses original scores instead of buckets")
print("   - Axes labels: Fit Score ranges and Claim Validity ranges")
print("   - Rows: [5/5, 4/5, 3/5, 2/5, 1/5, 0/5, No Score]")
print("   - Cols: [>4, 3-4, 2-3, 1-2, 0-1, No Score]")
print("\nNext steps:")
print("1. Restart analytics service")
print("2. Test API response")
print("3. Verify matrix displays correctly")




