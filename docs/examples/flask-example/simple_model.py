"""
simple_model.py - a tiny stand-in model, used ONLY if scikit-learn is not
installed (scikit-learn can be hard to install on Termux/Android).

It has the same predict_proba() interface as a scikit-learn classifier, so
the rest of the example does not change. It lives in its own file so that
joblib can load it again in app.py.
"""
import math


class SimpleModel:
    """Approves people with higher age, income and credit score."""

    def fit(self, X, y=None):
        return self

    def predict_proba(self, X):
        out = []
        for age, income_k, credit in X:
            z = 0.12 * (age - 35) + 0.06 * (income_k - 52) + 0.02 * (credit - 650)
            p = 1 / (1 + math.exp(-z))
            out.append([1 - p, p])
        return out
