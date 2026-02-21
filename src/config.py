import os


GEOGRAPHIES = ["FR", "DE", "ES"]
FREQ_S = int(os.getenv("SCHED_FREQ_S", str(30 * 60)))
HORIZON_S = int(os.getenv("SCHED_HORIZON_S", str(48 * 60 * 60)))

MIN_DELTA_THRESHOLD = float(os.getenv("SCHED_MIN_DELTA", "0.0"))
ML_INFERENCE_URL = os.getenv("ML_INFERENCE_URL", "http://localhost:8200")
RAILS_API_URL = os.getenv("RAILS_API_URL", "http://localhost:3001")

WEIGHT_DELTA = float(os.getenv("SCHED_W_DELTA", "0.70"))
WEIGHT_COST = float(os.getenv("SCHED_W_COST", "0.30"))

EVAL_EVERY_N_EPOCHS = int(os.getenv("SCHED_EVAL_EVERY_N_EPOCHS", "10"))
MIGRATION_SCORE_THRESHOLD = float(os.getenv("SCHED_MIGRATION_THRESHOLD", "0.15"))
MIGRATION_COOLDOWN_S = int(os.getenv("SCHED_MIGRATION_COOLDOWN_S", "900"))
