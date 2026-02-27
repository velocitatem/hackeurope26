try:
    from ml.models.train import Trainer, TrainerCallback
    from ml.models.registry import ModelRegistry
    from ml.models import eval as evaluate

    __all__ = ["Trainer", "TrainerCallback", "ModelRegistry", "evaluate"]
except ModuleNotFoundError:
    # torch not installed; import submodules explicitly when needed
    __all__ = []
