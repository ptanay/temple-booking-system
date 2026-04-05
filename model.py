import random

def predict_wait_time(visitors, day):
    base_time = 15 + (visitors * 5)

    if day == 5 or day == 6:
        base_time += 25

    variation = random.uniform(-5, 5)

    return base_time + variation
