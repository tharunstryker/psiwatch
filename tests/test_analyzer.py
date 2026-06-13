"""
tests/test_analyzer.py — Unit tests for psiwatch analyzer.
Run with: python tests/test_analyzer.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from psiwatch.analyzer import analyze_numeric, analyze_categorical, analyze


def test_numeric_high_drift():
    baseline = ['10', '12', '11', '10', '13']
    new = ['50', '55', '60', '52', '58']
    result = analyze_numeric(baseline, new)
    assert result['severity'] == 'HIGH', f"Expected HIGH, got {result['severity']}"
    print("PASS numeric high drift detected")


def test_numeric_no_drift():
    baseline = ['10', '10', '10', '10', '10']
    new = ['10', '10', '10', '10', '10']
    result = analyze_numeric(baseline, new)
    assert result['severity'] == 'PASS', f"Expected PASS, got {result['severity']}"
    print("PASS numeric no drift — PASS")


def test_categorical_new_category():
    baseline = ['Chennai', 'Delhi', 'Mumbai', 'Chennai', 'Delhi']
    new = ['Chennai', 'Delhi', 'Bangalore', 'Bangalore', 'Chennai']
    result = analyze_categorical(baseline, new)
    assert result['severity'] == 'HIGH', f"Expected HIGH, got {result['severity']}"
    assert 'Bangalore' in str(result['reasons'])
    print("PASS categorical new category detected")


def test_categorical_no_drift():
    baseline = ['A', 'B', 'A', 'B', 'A', 'B']
    new = ['A', 'B', 'A', 'B', 'A', 'B']
    result = analyze_categorical(baseline, new)
    assert result['severity'] == 'PASS', f"Expected PASS, got {result['severity']}"
    print("PASS categorical no drift — PASS")


def test_full_analyze():
    baseline = {
        'age': ['22', '23', '21', '24', '22'],
        'city': ['Chennai', 'Delhi', 'Mumbai', 'Chennai', 'Delhi']
    }
    new = {
        'age': ['28', '30', '29', '31', '27'],
        'city': ['Chennai', 'Delhi', 'Bangalore', 'Chennai', 'Hyderabad']
    }
    result = analyze(baseline, new)
    assert 'columns' in result
    assert 'health_score' in result
    assert result['columns']['age']['severity'] == 'HIGH'
    assert result['columns']['city']['severity'] == 'HIGH'
    assert result['health_score'] < 50
    print(f"PASS full analyze — health score: {result['health_score']}/100")


def test_health_score_clean_data():
    baseline = {'score': ['80', '80', '80', '80', '80', '80', '80', '80', '80', '80']}
    new =      {'score': ['80', '80', '80', '80', '80', '80', '80', '80', '80', '80']}
    result = analyze(baseline, new)
    assert result['health_score'] == 100, f"Expected 100, got {result['health_score']}"
    print(f"PASS health score clean data: {result['health_score']}/100")


def test_column_filter():
    baseline = {'age': ['22', '23'], 'score': ['80', '85'], 'city': ['Chennai', 'Delhi']}
    new = {'age': ['28', '30'], 'score': ['45', '40'], 'city': ['Mumbai', 'Kolkata']}
    result = analyze(baseline, new, columns=['age', 'score'])
    assert 'city' not in result['columns'], "city should be excluded"
    assert 'age' in result['columns']
    assert 'score' in result['columns']
    print("PASS column filter works")


if __name__ == '__main__':
    print("\nRunning psiwatch tests...\n")
    test_numeric_high_drift()
    test_numeric_no_drift()
    test_categorical_new_category()
    test_categorical_no_drift()
    test_full_analyze()
    test_health_score_clean_data()
    test_column_filter()
    print("\nAll tests passed.\n")
