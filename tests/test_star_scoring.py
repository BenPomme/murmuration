"""Test star scoring implementation per CLAUDE.md spec."""

import pytest
from sim.scoring import star_rating


def test_three_star_requires_two_surpluses_and_unused_beacon():
    """Test that 3 stars requires 2 surpluses and unused beacon."""
    res = type('R', (), dict(
        met_all_targets=True,
        days_used=7,
        arrivals=176,
        cohesion_avg=0.75,
        beacons_used=3,
        losses=10,
        protected_deaths=None,
        diversity=None
    ))
    t = type('T', (), dict(
        time_limit_days=10,
        arrivals_min=160,
        cohesion_avg_min=0.68,
        beacon_budget_max=4,
        losses_max=20,
        protected_deaths_max=None,
        diversity_min=None
    ))
    assert star_rating(res, t) == 3


def test_two_star_requires_one_surplus():
    """Test that 2 stars requires 1 surplus."""
    res = type('R', (), dict(
        met_all_targets=True,
        days_used=9,
        arrivals=168,  # 5% surplus
        cohesion_avg=0.68,
        beacons_used=4,
        losses=15,
        protected_deaths=None,
        diversity=None
    ))
    t = type('T', (), dict(
        time_limit_days=10,
        arrivals_min=160,
        cohesion_avg_min=0.68,
        beacon_budget_max=4,
        losses_max=20,
        protected_deaths_max=None,
        diversity_min=None
    ))
    assert star_rating(res, t) == 2


def test_one_star_exact_targets():
    """Test that 1 star is given for meeting exact targets."""
    res = type('R', (), dict(
        met_all_targets=True,
        days_used=10,
        arrivals=160,
        cohesion_avg=0.68,
        beacons_used=4,
        losses=20,
        protected_deaths=None,
        diversity=None
    ))
    t = type('T', (), dict(
        time_limit_days=10,
        arrivals_min=160,
        cohesion_avg_min=0.68,
        beacon_budget_max=4,
        losses_max=20,
        protected_deaths_max=None,
        diversity_min=None
    ))
    assert star_rating(res, t) == 1


def test_zero_stars_failed_targets():
    """Test that 0 stars is given for not meeting targets."""
    res = type('R', (), dict(
        met_all_targets=False,
        days_used=10,
        arrivals=150,  # Below minimum
        cohesion_avg=0.68,
        beacons_used=4,
        losses=25,
        protected_deaths=None,
        diversity=None
    ))
    t = type('T', (), dict(
        time_limit_days=10,
        arrivals_min=160,
        cohesion_avg_min=0.68,
        beacon_budget_max=4,
        losses_max=20,
        protected_deaths_max=None,
        diversity_min=None
    ))
    assert star_rating(res, t) == 0