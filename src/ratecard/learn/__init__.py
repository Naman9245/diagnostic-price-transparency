"""A learned accept/abstain decision, trained on the Phase 03 labels.

Replaces the hand-set ACCEPT_THRESHOLD and MARGIN with a logistic regression
over pair features. The exact-alias layer and the veto are untouched: the model
decides only among candidates the hard rules already allow.
"""
