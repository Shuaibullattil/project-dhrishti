import numpy as np
import pandas as pd
from math import ceil
from scipy.spatial.distance import euclidean

def calculate_abnormal_stats(movement_data, vid_fps, data_record_frame, frame_size, track_max_age=3):
    """
    Computes abnormal activity statistics from movement data in memory.
    Replicates logic from abnormal_data_process.py without writing to disk.
    """
    if not movement_data or vid_fps <= 0:
        return None, None
        
    time_steps = data_record_frame / vid_fps
    stationary_time = ceil(track_max_age / time_steps)
    stationary_distance = frame_size * 0.01
    
    tracks = []
    for row in movement_data:
        # row format: [track_id, entry, exit, x1, y1, x2, y2, ...]
        if len(row[3:]) > stationary_time * 2:
            temp = []
            data_pts = row[3:]
            for i in range(0, len(data_pts), 2):
                temp.append([int(data_pts[i]), int(data_pts[i+1])])
            tracks.append(temp)
            
    if not tracks:
        return None, None
        
    useful_tracks = []
    for movement in tracks:
        check_index = stationary_time
        start_point = 0
        track = movement[:check_index]
        while check_index < len(movement):
            for i in movement[check_index:]:
                if euclidean(movement[start_point], i) > stationary_distance:
                    track.append(i)
                    start_point += 1
                    check_index += 1
                else:
                    start_point += 1
                    check_index += 1
                    break
            useful_tracks.append(track)
            track = movement[start_point:check_index]
            
    energies = []
    for movement in useful_tracks:
        for i in range(len(movement) - 1):
            speed = round(euclidean(movement[i], movement[i+1]) / time_steps , 2)
            energy = int(0.5 * speed ** 2)
            energies.append(energy)
            
    if not energies:
        return None, None
        
    energies_ser = pd.Series(energies)
    df = pd.DataFrame({'Energy': energies_ser})
    
    original_stats = {
        "kurtosis": float(df.kurtosis().iloc[0]),
        "skew": float(df.skew().iloc[0]),
        "mean": float(df.Energy.mean()),
        "std": float(df.Energy.std()),
        "min": float(df.Energy.min()),
        "max": float(df.Energy.max()),
        "q1": float(df.Energy.quantile(0.25)),
        "q2": float(df.Energy.quantile(0.50)),
        "q3": float(df.Energy.quantile(0.75)),
        "acceptable_energy": int(df.Energy.mean() ** 1.05) if not df.empty else 0
    }
    
    # Cleaning outliers (replicates while-loop logic)
    cleaned_df = df.copy()
    iter_count = 0
    while cleaned_df.skew().iloc[0] > 7.5 and iter_count < 10:
        energies_ser = cleaned_df.Energy
        cleaned_df = cleaned_df[abs(energies_ser - np.mean(energies_ser)) < 3 * np.std(energies_ser)]
        iter_count += 1
        if cleaned_df.empty: break
        
    cleaned_stats = {
        "kurtosis": float(cleaned_df.kurtosis().iloc[0]) if not cleaned_df.empty else 0,
        "skew": float(cleaned_df.skew().iloc[0]) if not cleaned_df.empty else 0,
        "mean": float(cleaned_df.Energy.mean()) if not cleaned_df.empty else 0,
        "std": float(cleaned_df.Energy.std()) if not cleaned_df.empty else 0,
        "min": float(cleaned_df.Energy.min()) if not cleaned_df.empty else 0,
        "max": float(cleaned_df.Energy.max()) if not cleaned_df.empty else 0,
        "q1": float(cleaned_df.Energy.quantile(0.25)) if not cleaned_df.empty else 0,
        "q2": float(cleaned_df.Energy.quantile(0.50)) if not cleaned_df.empty else 0,
        "q3": float(cleaned_df.Energy.quantile(0.75)) if not cleaned_df.empty else 0,
        "acceptable_energy": int(cleaned_df.Energy.mean() ** 1.05) if not cleaned_df.empty else 0,
        "outliers_removed": int(len(df) - len(cleaned_df))
    }
    
    return original_stats, cleaned_stats
