import psiwatch
from psiwatch import DriftDetected
import random

random.seed(42)

def gen_baseline(n=1000):
    cities = ['Chennai', 'Delhi', 'Mumbai', 'Hyderabad', 'Bangalore']
    grades = ['A', 'B', 'C']
    loan_types = ['Home', 'Car', 'Personal']
    statuses = ['Active', 'Closed', 'Pending']
    return {
        'age':          [random.randint(22, 35) for _ in range(n)],
        'salary':       [round(random.gauss(55000, 8000), 2) for _ in range(n)],
        'credit_score': [round(random.gauss(720, 40), 2) for _ in range(n)],
        'loan_amount':  [round(random.gauss(300000, 50000), 2) for _ in range(n)],
        'city':         [random.choice(cities) for _ in range(n)],
        'grade':        [random.choice(grades) for _ in range(n)],
        'loan_type':    [random.choice(loan_types) for _ in range(n)],
        'status':       [random.choice(statuses) for _ in range(n)],
        'experience':   [random.randint(0, 10) for _ in range(n)],
        'debt_ratio':   [round(random.uniform(0.1, 0.6), 4) for _ in range(n)],
    }

def gen_drifted(n=1000):
    cities = ['Pune', 'Noida', 'Gurugram', 'Kochi', 'Jaipur']
    grades = ['C', 'D', 'F']
    loan_types = ['Home', 'Car', 'BNPL', 'Crypto']
    statuses = ['Active', 'Defaulted', 'Frozen']
    return {
        'age':          [random.randint(18, 25) for _ in range(n)],
        'salary':       [round(random.gauss(32000, 12000), 2) for _ in range(n)],
        'credit_score': [round(random.gauss(580, 70), 2) for _ in range(n)],
        'loan_amount':  [round(random.gauss(700000, 100000), 2) for _ in range(n)],
        'city':         [random.choice(cities) for _ in range(n)],
        'grade':        [random.choice(grades) for _ in range(n)],
        'loan_type':    [random.choice(loan_types) for _ in range(n)],
        'status':       [random.choice(statuses) for _ in range(n)],
        'experience':   [random.randint(0, 3) for _ in range(n)],
        'debt_ratio':   [round(random.uniform(0.5, 0.95), 4) for _ in range(n)],
    }

baseline = gen_baseline()
new_data = gen_drifted()

print("\n=== TEST 1 — Terminal report ===")
psiwatch.compare(baseline, new_data)

print("\n=== TEST 2 — HTML report ===")
psiwatch.compare(baseline, new_data, output="drift_report.html")

print("\n=== TEST 3 — JSON report ===")
psiwatch.compare(baseline, new_data, output="drift_report.json")

print("\n=== TEST 4 — Specific columns ===")
psiwatch.compare(baseline, new_data, columns=["credit_score", "salary", "city"])

print("\n=== TEST 5 — Custom PSI threshold ===")
psiwatch.compare(baseline, new_data, psi_threshold=0.1)

print("\n=== TEST 6 — analyze() raw ===")
result = psiwatch.analyze(baseline, new_data)
print(f"Health score: {result['health_score']}/100")
for col, data in result['columns'].items():
    print(f"  {col:15} {data['severity']:8} PSI={data['metrics'].get('psi', 'N/A')}")

print("\n=== TEST 7 — compare_columns ===")
old_scores = [random.randint(700, 800) for _ in range(500)]
new_scores = [random.randint(500, 650) for _ in range(500)]
psiwatch.compare_columns(old_scores, new_scores, name="credit_score")

print("\n=== TEST 8 — fail_on_drift triggered ===")
try:
    psiwatch.compare(baseline, new_data, fail_on_drift=True)
except DriftDetected as e:
    print(f"PASS — DriftDetected: {e}")

print("\n=== TEST 9 — fail_on_drift clean data ===")
try:
    psiwatch.compare(baseline, baseline, fail_on_drift=True)
    print("PASS — No exception on identical data")
except DriftDetected as e:
    print(f"FAIL — {e}")

print("\n=== TEST 10 — Missing column warning ===")
b2 = {**baseline, 'old_feature': [1]*1000}
psiwatch.compare(b2, new_data)

print("\nAll tests done.")
