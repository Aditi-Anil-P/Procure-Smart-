import os
import uuid
import logging
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from chart_utils import save_chart_metadata

from single_compare import detect_valid_data, _detect_label_column, apply_dark_theme

logging.basicConfig(level=logging.INFO)

GRAPH_FOLDER = os.path.join("static", "graphs")
os.makedirs(GRAPH_FOLDER, exist_ok=True)


def scale_fixed(data, local_min, local_max, reverse=False):
    """
    Scales data based on the provided LOCAL min/max to a 0-10 range.
    
    If data point X is outside the [local_min, local_max] range, its score 
    will be < 0 or > 10, maintaining the linearity of the scale.
    """
    if local_max - local_min == 0:
        return [0] * len(data)
    
    # Calculate scale (0.0 to 1.0, but can go outside this range)
    if reverse:
        # For lower=better: Score = 1 - Normalized
        normalized = [1 - (x - local_min) / (local_max - local_min) for x in data]
    else:
        # For higher=better: Score = Normalized
        normalized = [(x - local_min) / (local_max - local_min) for x in data]
        
    # Convert to 0-10 scale
    return [n * 10 for n in normalized]


def generate_weighted_compare_chart(file_path, params, weights, preferences, ranges,
                                    top_n=10, min_score=None, max_score=None):
    if not os.path.exists(file_path):
        raise FileNotFoundError("Uploaded file not found on server.")

    df, numeric_df = detect_valid_data(file_path)
    if df.empty or numeric_df.empty:
        raise ValueError("No valid numeric data found in file.")

    # Validate params
    for p in params:
        if p not in numeric_df.columns:
            raise ValueError(f"Parameter '{p}' not found in file.")

    # Detect label column
    label_col = _detect_label_column(df, numeric_df.columns.tolist())
    if label_col is None:
        raise ValueError("No label/identifier column found.")

    # Prepare working DataFrame
    working = df.copy().reset_index(drop=True)
    for p in params:
        working[p] = numeric_df[p]
    working = working.dropna(subset=params)

   
    # We now filter the rows based on the user-defined ranges
    for idx, p in enumerate(params):
        min_val, max_val = ranges[idx]
        if min_val is not None:
            working = working[working[p] >= min_val]
        if max_val is not None:
            working = working[working[p] <= max_val]

    if working.empty:
        raise ValueError("No companies satisfy the selected parameter constraints.")

    # Normalize weights
    total_weight = sum(weights)
    if total_weight <= 0:
        raise ValueError("Sum of weights must be greater than 0.")
    weights = [w / total_weight for w in weights]

    #  COMPUTE SCORES USING LOCAL RANGES
    scores_per_param = []
    
    for idx, p in enumerate(params):
        reverse = (preferences[idx] == "lower")
        #USE USER-DEFINED MIN/MAX FOR SCALING ---
        local_min, local_max = ranges[idx] 
        
        # default specify min/max
        if local_min is None: local_min = working[p].min()
        if local_max is None: local_max = working[p].max()
        
        # Scale to 0-10. A value equal to local_min is 0, local_max is 10.
        scaled_values = scale_fixed(working[p].tolist(), local_min, local_max, reverse=reverse)
        
        # Apply Weight
        weighted_component = [s * weights[idx] for s in scaled_values]
        scores_per_param.append(weighted_component)

    working["WeightedScore"] = np.sum(scores_per_param, axis=0)

    # --- STEP 3: FILTER BY WEIGHTED SCORE ---
    if min_score is not None:
        working = working[working["WeightedScore"] >= min_score]
    if max_score is not None:
        working = working[working["WeightedScore"] <= max_score]

    if working.empty:
        raise ValueError("No companies remain after applying weighted score constraints.")

    # Sort and truncate
    working = working.sort_values(by="WeightedScore", ascending=False).head(top_n)

    # --- STEP 4: PREPARE FINAL PLOT DATA ---
    contribs = []
    for idx, p in enumerate(params):
        reverse = (preferences[idx] == "lower")
        local_min, local_max = ranges[idx]
        
        # Fallback check again
        if local_min is None: local_min = working[p].min()
        if local_max is None: local_max = working[p].max()

        # Recalculate contributions for the final top N
        scaled = scale_fixed(working[p].tolist(), local_min, local_max, reverse=reverse)
        weighted = [s * weights[idx] for s in scaled]
        contribs.append(weighted)

    # Plot (stacked contributions)
    apply_dark_theme()
    labels = working[label_col].astype(str).tolist()

    colors = ["#FF6F61", "#FFD54F", "#4FC3F7", "#81C784", "#BA68C8"]
    
    fig_width = max(10, min(24, 0.7 * len(labels)))
    fig, ax = plt.subplots(figsize=(fig_width, 6))

    bottom = np.zeros(len(labels))
    for idx, contrib in enumerate(contribs):
        ax.bar(labels, contrib, bottom=bottom,
               color=colors[idx % len(colors)], label=params[idx])
        bottom += contrib

    ax.set_ylabel("Weighted Score (0-10 Local Scale)")
    ax.set_title("Weighted Parameter Comparison (Scale 0-10 based on Input Ranges)")
    plt.xticks(rotation=90)
    
    # Set Y limit based on the total possible score (10.0)
    plt.ylim(0, 10)

    # White legend text
    legend = ax.legend(title="Parameters", bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.setp(legend.get_texts(), color="white")
    plt.setp(legend.get_title(), color="white")

    fig.tight_layout()
    fig.subplots_adjust(bottom=0.28 if len(labels) <= 12 else 0.36, right=0.82)

    filename = f"{uuid.uuid4().hex[:10]}_weighted_compare.png"
    full_path = os.path.join(GRAPH_FOLDER, filename)
    plt.savefig(full_path, facecolor=plt.gcf().get_facecolor())
    plt.close()
    save_chart_metadata(filename, limit=3)
    logging.info("Saved weighted compare chart to %s", full_path)
    return filename