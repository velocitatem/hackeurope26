from lib import get_logger
import random
import numpy as np

GEOGRAPHIES = ["FR", "DE", "ES"]
PROVIDERS = ["AWS", "Azure", "GCP"]
FREQ = 60 * 30 # 30 minutes
HORIZON = 60 * 60 * 24 # 24 hours


def get_detlta(GEO : str):
    # TODO: we create a model for each geography that predicts the delta
    # the delta is the production - demand of energy in that geography which we use as a heuristic to decide where to run the workloads
    # once we have the models they will be deployed on a server and we can infer on them.
    offsets = [0.5, 0, -0.5]
    offset = offsets[GEOGRAPHIES.index(GEO)]
    return np.sin(random.random() * 2 * np.pi + offset) + random.random() * 0.1

class Node:
    def __init__(self, parent : Node|None):
        self.deltas = {K: get_detlta(K) for K in GEOGRAPHIES}
        self.parent = parent




def main():
    logger = get_logger("scheduler", level="DEBUG")

    root = Node(None)
    for t in range(0, HORIZON, FREQ):
        logger.info(f"Time: {t}")
        node = Node(root)
        logger.debug(f"Deltas: {node.deltas}")
        root = node

    # best path of geographies with highest delta at each step
    path = []
    node = root
    while node is not None:
        best_geo = max(node.deltas, key=node.deltas.get)
        path.append(best_geo)
        node = node.parent
    logger.info(f"Best path: {path}")



if __name__ == "__main__":
    main()
