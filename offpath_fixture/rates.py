"""Fee and rate tables.

The many module-level assignments below give the fixture a realistic
executed-line footprint at import time: every assignment line executes
when the module is imported, which keeps baseline executed-line counts
meaningful so that visibility anomalies (S5) are detectable.
"""

FEE_FLAT_CENTS = 30
FEE_PCT = 3
FEE_CAP_CENTS = 1500

RATE_001 = 11
RATE_002 = 12
RATE_003 = 13
RATE_004 = 14
RATE_005 = 15
RATE_006 = 16
RATE_007 = 17
RATE_008 = 18
RATE_009 = 19
RATE_010 = 20
RATE_011 = 21
RATE_012 = 22
RATE_013 = 23
RATE_014 = 24
RATE_015 = 25
RATE_016 = 26
RATE_017 = 27
RATE_018 = 28
RATE_019 = 29
RATE_020 = 30
RATE_021 = 31
RATE_022 = 32
RATE_023 = 33
RATE_024 = 34
RATE_025 = 35
RATE_026 = 36
RATE_027 = 37
RATE_028 = 38
RATE_029 = 39
RATE_030 = 40
RATE_031 = 41
RATE_032 = 42
RATE_033 = 43
RATE_034 = 44
RATE_035 = 45
RATE_036 = 46
RATE_037 = 47
RATE_038 = 48
RATE_039 = 49
RATE_040 = 50
RATE_041 = 51
RATE_042 = 52
RATE_043 = 53
RATE_044 = 54
RATE_045 = 55
RATE_046 = 56
RATE_047 = 57
RATE_048 = 58
RATE_049 = 59
RATE_050 = 60
RATE_051 = 61
RATE_052 = 62
RATE_053 = 63
RATE_054 = 64
RATE_055 = 65
RATE_056 = 66
RATE_057 = 67
RATE_058 = 68
RATE_059 = 69
RATE_060 = 70
RATE_061 = 71
RATE_062 = 72
RATE_063 = 73
RATE_064 = 74
RATE_065 = 75
RATE_066 = 76
RATE_067 = 77
RATE_068 = 78
RATE_069 = 79
RATE_070 = 80
RATE_071 = 81
RATE_072 = 82
RATE_073 = 83
RATE_074 = 84
RATE_075 = 85
RATE_076 = 86
RATE_077 = 87
RATE_078 = 88
RATE_079 = 89
RATE_080 = 90


def refund_fee_cents(amount_cents):
    fee = FEE_FLAT_CENTS + amount_cents * FEE_PCT // 100
    return min(fee, FEE_CAP_CENTS)


def fee_note():
    return f"flat {FEE_FLAT_CENTS} + {FEE_PCT}% capped at {FEE_CAP_CENTS}"
