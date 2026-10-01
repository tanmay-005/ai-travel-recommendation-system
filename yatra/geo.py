"""Distance maths."""
import math

import numpy as np

# HAVERSINE

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    rl1, rl2   = math.radians(lat1), np.radians(lat2)
    rlo1, rlo2 = math.radians(lon1), np.radians(lon2)
    dlat = rl2 - rl1; dlon = rlo2 - rlo1
    a = np.sin(dlat/2)**2 + math.cos(rl1)*np.cos(rl2)*np.sin(dlon/2)**2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))